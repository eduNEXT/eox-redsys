"""Anonymous authenticated gateway delivery and buyer-owned recorded status."""
import base64
import binascii
import hmac
import json
import logging
import re
from urllib.parse import urlsplit

from django.contrib.auth.views import redirect_to_login
from django.contrib.sites.models import Site
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from zeitlabs_payments.exceptions import GatewayError
from zeitlabs_payments.models import AuditLog, Cart

from eox_redsys.processor import RedsysProcessor, SIGNATURE_VERSION, sign_parameters

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class RedsysNotificationView(View):
    """Authenticate before entering the shared recording and fulfillment flow."""

    def post(self, request):
        """Verify a notification and settle an approved purchase exactly once."""
        processor = RedsysProcessor()
        try:
            if not getattr(request, 'site', None):
                request.site = Site.objects.get(domain=request.get_host())
            config, _ = processor.configuration()
            encoded = request.POST['Ds_MerchantParameters']
            if len(encoded) > 16384 or request.POST['Ds_SignatureVersion'] != SIGNATURE_VERSION:
                raise ValueError('unsupported envelope')
            data = json.loads(base64.b64decode(encoded + '=' * (-len(encoded) % 4), altchars=b'-_', validate=True))
            order = data['Ds_Order']
            if not isinstance(order, str) or not re.fullmatch(r'[0-9]{4}[a-zA-Z0-9]{0,8}', order):
                raise ValueError('invalid order')
            expected = sign_parameters(encoded, order, config['secret_key'])
            if not hmac.compare_digest(expected, request.POST['Ds_Signature'].rstrip('=')):
                raise ValueError('invalid signature')
            with transaction.atomic():
                cart = Cart.objects.select_for_update().get(gateway='redsys', gateway_order_id=order)
                if (str(data['Ds_MerchantCode']) != str(config['merchant_code'])
                        or not re.fullmatch(r'[0-9]{1,3}', str(data['Ds_Terminal']))
                        or int(data['Ds_Terminal']) != int(config['terminal'])
                        or data['Ds_TransactionType'] != '0'
                        or urlsplit(cart.payment_origin).netloc != request.site.domain):
                    raise ValueError('purchase data mismatch')
                processor.reconcile_payment(data, cart)
                if not re.fullmatch(r'[0-9]{4}', str(data['Ds_Response'])):
                    raise ValueError('invalid response code')
                if not 0 <= int(data['Ds_Response']) <= 99:
                    return HttpResponse(status=200)
                if cart.status == Cart.Status.PAID:
                    AuditLog.log(action=AuditLog.AuditActions.DUPLICATE_TRANSACTION, cart=cart, processor=processor, context={'transaction_id': 'redsys:' + order, 'cart_status': cart.status})
                    return HttpResponse(status=200)
                # Store only the explicitly supported response fields; never card data or signatures.
                safe = {key: data[key] for key in ('Ds_Order', 'Ds_MerchantCode', 'Ds_Terminal', 'Ds_Amount', 'Ds_Currency', 'Ds_TransactionType', 'Ds_Response', 'Ds_AuthorisationCode', 'Ds_Amount_DCC', 'Ds_Currency_DCC') if key in data}
                processor.process_payment_and_update_records(
                    cart=cart, data=safe, request=request, transaction_id='redsys:' + order,
                    transaction_status=processor.TRANSACTION_STATUS_SUCCESS, method='redsys',
                    amount=str(cart.total), currency=data['Ds_Currency'], reason='Redsys authorization ' + data['Ds_Response'],
                )
                cart.refresh_from_db()
                if cart.status != Cart.Status.PAID:
                    logger.warning('Redsys approval could not be settled; shared records require review')
                    return HttpResponse(status=503)
            return HttpResponse(status=200)
        except (KeyError, ValueError, TypeError, UnicodeError, binascii.Error, Cart.DoesNotExist, Site.DoesNotExist, GatewayError):
            logger.warning('Redsys notification rejected: invalid envelope or purchase data')
            return HttpResponse(status=400)


class RedsysStatusView(View):
    """Read persisted results for the authenticated buyer; never settle on browser input."""

    def get(self, request, **kwargs):
        """Return the authenticated buyer's saved payment and fulfillment status."""
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'login_required'}, status=401)
        order = request.GET.get('order')
        if not order:
            return JsonResponse({'status': 'not_found'}, status=404)
        cart = Cart.objects.filter(user=request.user, gateway='redsys', gateway_order_id=order).first()
        if not cart or cart.payment_origin != f'{request.scheme}://{request.get_host()}':
            return JsonResponse({'status': 'not_found'}, status=404)
        invoice = cart.invoices.first()
        if invoice and cart.status == Cart.Status.PAID:
            return JsonResponse({'status': 'paid', 'invoice_url': reverse('zeitlabs_payments:invoice', args=[invoice.invoice_number])})
        if cart.status == Cart.Status.PAID:
            return JsonResponse({'status': 'not_fulfilled', 'message': 'Payment received. Please contact support for course access.'}, status=409)
        return JsonResponse({'status': 'pending'}, status=202)


class RedsysReturnView(RedsysStatusView):
    """Show the recorded outcome and poll while the server notification is pending."""

    def get(self, request, **kwargs):
        """Render the saved outcome or a waiting page for the purchase owner."""
        response = super().get(request, **kwargs)
        if response.status_code == 401:
            return redirect_to_login(request.get_full_path())
        if response.status_code == 404:
            return response
        data = json.loads(response.content)
        return render(request, 'eox_redsys/return.html', {
            **data,
            'status_url': reverse('zeitlabs_payments:processor-status', args=['redsys']) + '?order=' + request.GET['order'],
        })
