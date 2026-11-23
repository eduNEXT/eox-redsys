"""Redsys hosted authorization using the shared payments processor contract."""
import base64
import hashlib
import hmac
import json
import re
import secrets
from decimal import Decimal

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from django.db import IntegrityError, transaction
from django.urls import reverse
from zeitlabs_payments.constants import ISO_4217_NUMERIC_TO_ALPHA
from zeitlabs_payments.exceptions import GatewayError
from zeitlabs_payments.helpers import get_currency
from zeitlabs_payments.providers.base import BaseProcessor
from zeitlabs_payments.validators import get_currency_exponent

SIGNATURE_VERSION = 'HMAC_SHA512_V2'
GATEWAYS = {'test': 'https://sis-t.redsys.es:25443/sis/realizarPago', 'production': 'https://sis.redsys.es/sis/realizarPago'}


def sign_parameters(encoded, order, secret):
    """Sign the exact encoded bytes using Redsys' AES diversified SHA512 key."""
    key = secret[:16].ljust(16, '0').encode('ascii')
    diversified = AES.new(key, AES.MODE_CBC, iv=bytes(16)).encrypt(pad(order.encode('ascii'), 16))
    digest = hmac.new(base64.b64encode(diversified), encoded.encode('ascii'), hashlib.sha512).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')


class RedsysProcessor(BaseProcessor):
    """Prepare hosted payments and reconcile their original purchase values."""

    SLUG = 'redsys'
    NAME = 'Redsys'
    CHECKOUT_TEXT = 'Pay with Redsys'
    TEMPLATE_NAME = 'eox_redsys/payment.html'
    SETTINGS_ROOT_KEY = 'REDSYS_SETTINGS'
    RETURN_VIEW = 'eox_redsys.views.RedsysReturnView'
    STATUS_VIEW = 'eox_redsys.views.RedsysStatusView'
    GATEWAY_ORDER_ID_PARAM = 'order'

    def configuration(self):
        """Return validated site settings and the numeric ISO currency code.

        Raises:
            GatewayError: If required merchant settings are missing or invalid.
        """
        config = self.get_settings()
        numeric = {alpha: number for number, alpha in ISO_4217_NUMERIC_TO_ALPHA.items()}
        if (not isinstance(config, dict)
                or not re.fullmatch(r'[0-9]{9}', str(config.get('merchant_code', '')))
                or not re.fullmatch(r'[0-9]{1,3}', str(config.get('terminal', '')))
                or int(config['terminal']) == 0
                or config.get('environment') not in GATEWAYS
                or config.get('currency') not in numeric
                or not isinstance(config.get('secret_key'), str)
                or not config['secret_key'] or not config['secret_key'].isascii()):
            raise GatewayError('Redsys configuration is incomplete or invalid')
        return config, numeric[config['currency']]

    def is_hidden_for(self, request):
        """Hide checkout when the site's Redsys configuration is unusable."""
        try:
            self.configuration()
        except GatewayError:
            return True
        return False

    def purchase_amount(self, cart):
        """Return the purchase amount in minor units and its numeric currency.

        Raises:
            GatewayError: If the currency differs from the configuration or
                the amount cannot be represented by Redsys without rounding.
        """
        config, numeric = self.configuration()
        if get_currency(cart) != config['currency']:
            raise GatewayError('Purchase currency does not match Redsys currency')
        amount = cart.total * (Decimal(10) ** get_currency_exponent(config['currency']))
        if amount != amount.to_integral_value() or not 0 < amount < 10 ** 12:
            raise GatewayError('Purchase amount cannot be represented by Redsys')
        return str(int(amount)), numeric

    def payment_view(self, cart, request=None, use_client_side_checkout=False, **kwargs):
        """Let the shared flow record the order, retrying a random-reference collision."""
        for _ in range(5):
            try:
                with transaction.atomic():
                    return super().payment_view(cart, request, use_client_side_checkout, **kwargs)
            except IntegrityError:
                continue
        raise GatewayError('Unable to allocate a unique Redsys order')

    def get_transaction_parameters(self, cart, request=None, use_client_side_checkout=False, **kwargs):
        """Build a signed hosted-payment form from server-side purchase data."""
        config, _ = self.configuration()
        amount, currency = self.purchase_amount(cart)
        order = f'{secrets.randbelow(10 ** 12):012d}'
        return_url = request.build_absolute_uri(self.get_return_url()) + '?order=' + order
        if len(return_url) > 250:
            raise GatewayError('Redsys return URLs must not exceed 250 characters')
        parameters = {
            'DS_MERCHANT_AMOUNT': amount, 'DS_MERCHANT_CURRENCY': currency,
            'DS_MERCHANT_ORDER': order, 'DS_MERCHANT_MERCHANTCODE': config['merchant_code'],
            'DS_MERCHANT_TERMINAL': str(config['terminal']), 'DS_MERCHANT_TRANSACTIONTYPE': '0',
            'DS_MERCHANT_MERCHANTURL': request.build_absolute_uri(reverse('eox_redsys:notification')),
            'DS_MERCHANT_URLOK': return_url, 'DS_MERCHANT_URLKO': return_url,
        }
        encoded = base64.urlsafe_b64encode(json.dumps(parameters, separators=(',', ':'), ensure_ascii=False).encode()).decode().rstrip('=')
        return {'gateway_url': GATEWAYS[config['environment']], 'order': order,
                'signature_version': SIGNATURE_VERSION, 'merchant_parameters': encoded,
                'signature': sign_parameters(encoded, order, config['secret_key'])}

    def get_gateway_order_id(self, transaction_parameters):
        """Return the order reference the shared flow records before redirection."""
        return transaction_parameters['order']

    def reconcile_payment(self, response, cart):
        """Check that the response pays the original purchase amount and currency.

        Raises:
            GatewayError: If either value differs from the server-side purchase.
        """
        amount, currency = self.purchase_amount(cart)
        if response.get('Ds_Amount') != amount or response.get('Ds_Currency') != currency:
            raise GatewayError('Redsys original purchase amount or currency mismatch')
