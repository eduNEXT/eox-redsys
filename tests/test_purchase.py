"""Approved hosted-payment scenarios arranged through public boundaries."""
import base64
import json
import re

import pytest
from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from django.apps import apps
from django.contrib.sites.models import Site
from django.test import Client, RequestFactory
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from zeitlabs_payments.exceptions import GatewayError
from zeitlabs_payments.models import AuditLog, Cart, CartItem, CatalogueItem, Invoice, Transaction

from eox_redsys.processor import RedsysProcessor, sign_parameters


@pytest.fixture
def purchase(db, django_user_model):
    """Create a server-priced course purchase and its authenticated request."""
    site = Site.objects.get(pk=1)
    site.domain = 'testserver'
    site.save()
    user = django_user_model.objects.create_user('buyer', first_name='José', last_name='Muñoz')
    item = CatalogueItem.objects.create(sku='paid-course', type='paid_course', title='Español', item_ref_id='course-v1:org+course+run', price='45.25', currency='EUR')
    cart = Cart.objects.create(user=user, status=Cart.Status.PROCESSING, gateway='redsys', payment_origin='https://testserver')
    CartItem.objects.create(cart=cart, catalogue_item=item, original_price='45.25', final_price='45.25')
    request = RequestFactory().get('/', secure=True)
    request.site = site
    request.user = user
    return cart, request


def test_checkout_records_original_amount_and_unique_order_before_redirect(purchase):
    """Checkout signs the original purchase and records its order before sending it."""
    # Arrange
    cart, request = purchase
    processor = RedsysProcessor()

    # Act
    response = processor.payment_view(cart, request)

    # Assert
    cart.refresh_from_db()
    assert cart.gateway_order_id and len(cart.gateway_order_id) == 12
    assert cart.gateway_order_id.isascii() and cart.gateway_order_id.isdecimal()
    assert response.status_code == 200
    encoded = re.search(rb'name="Ds_MerchantParameters" value="([^"]+)"', response.content).group(1)
    data = json.loads(base64.urlsafe_b64decode(encoded + b'=' * (-len(encoded) % 4)))
    assert data['DS_MERCHANT_AMOUNT'] == '4525'
    assert data['DS_MERCHANT_CURRENCY'] == '978'
    assert data['DS_MERCHANT_ORDER'] == cart.gateway_order_id
    assert data['DS_MERCHANT_MERCHANTURL'] == 'https://testserver/redsys/notification/'
    assert data['DS_MERCHANT_URLOK'].endswith('?order=' + cart.gateway_order_id)
    assert b'Ds_MerchantParameters' in response.content


def notification(cart, **overrides):
    """Build a signed gateway notification with optional result-field overrides."""
    data = {'Ds_Order': cart.gateway_order_id, 'Ds_MerchantCode': '999008881', 'Ds_Terminal': '001', 'Ds_Amount': '4525', 'Ds_Currency': '978', 'Ds_TransactionType': '0', 'Ds_Response': '0000', 'Ds_AuthorisationCode': 'ABC123', 'Ds_Amount_DCC': '9999', 'Ds_Currency_DCC': '840'}
    data.update(overrides)
    data = {key: value for key, value in data.items() if value is not None}
    encoded = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')
    return {'Ds_SignatureVersion': 'HMAC_SHA512_V2', 'Ds_MerchantParameters': encoded, 'Ds_Signature': sign_parameters(encoded, data['Ds_Order'], 'sq7HjrUOBfKmC576')}


@pytest.mark.parametrize('dcc', [False, True])
def test_approved_notification_without_browser_fulfills_purchase_once(purchase, client, dcc):
    """Anonymous approval and its replay fulfill the purchase only once."""
    # Arrange
    cart, request = purchase
    course = CourseOverview.objects.create(id='course-v1:org+course+run', org='org', display_name='Español')
    CourseMode.objects.create(course=course, sku='paid-course', mode_slug='verified', currency='EUR')
    RedsysProcessor().payment_view(cart, request)
    payload = notification(cart) if dcc else notification(cart, Ds_Amount_DCC=None, Ds_Currency_DCC=None)
    client = Client(enforce_csrf_checks=True)

    # Act
    response = client.post('/redsys/notification/', payload, secure=True)
    cart.refresh_from_db()
    initial_status = cart.status
    initial_counts = (Transaction.objects.count(), Invoice.objects.count(), CourseEnrollment.objects.count())
    replay = client.post('/redsys/notification/', payload, secure=True)

    # Assert
    assert response.status_code == replay.status_code == 200
    assert initial_status == Cart.Status.PAID
    assert initial_counts == (1, 1, 1)
    cart.refresh_from_db()
    assert cart.status == Cart.Status.PAID
    invoice = Invoice.objects.get(cart=cart)
    assert invoice.learner_info == {'name': 'José Muñoz'}
    assert invoice.related_transaction.response.get('Ds_Amount_DCC') == ('9999' if dcc else None)
    assert invoice.related_transaction.amount == 45.25
    assert invoice.related_transaction.currency == 'EUR'
    assert CourseEnrollment.objects.get(user=cart.user, course=course).mode == 'verified'
    assert Transaction.objects.count() == Invoice.objects.count() == CourseEnrollment.objects.count() == 1


@pytest.mark.parametrize('changed', [{'Ds_Amount': '1'}, {'Ds_Currency': '840'}, {'Ds_MerchantCode': '999999999'}, {'Ds_Terminal': '2'}, {'Ds_Order': '999999999999'}, {'Ds_TransactionType': '1'}, {'Ds_Response': 'nonsense'}])
def test_signed_mismatched_notification_cannot_mutate_purchase(purchase, client, changed, caplog):
    """A valid signature cannot authorize mismatched or uninterpretable data."""
    # Arrange
    cart, request = purchase
    RedsysProcessor().payment_view(cart, request)
    counts = (AuditLog.objects.count(), Transaction.objects.count(), Invoice.objects.count())
    payload = notification(cart, **changed)

    # Act
    response = client.post('/redsys/notification/', payload, secure=True)

    # Assert
    assert response.status_code == 400
    cart.refresh_from_db()
    assert cart.status == Cart.Status.PROCESSING
    assert (AuditLog.objects.count(), Transaction.objects.count(), Invoice.objects.count()) == counts
    assert 'Redsys notification rejected' in caplog.text


def test_browser_can_only_read_its_own_recorded_purchase(purchase, client, django_user_model):
    """Only the authenticated owner can read a purchase's pending status."""
    # Arrange
    cart, request = purchase
    RedsysProcessor().payment_view(cart, request)
    path = '/payment/v1/processor/redsys/status/?order=' + cart.gateway_order_id
    anonymous_client = Client()
    other_client = Client()
    other_client.force_login(django_user_model.objects.create_user('other'))
    client.force_login(cart.user)

    # Act
    anonymous_response = anonymous_client.get(path, secure=True)
    other_response = other_client.get(path, secure=True)
    response = client.get(path, secure=True)
    page = client.get('/payment/v1/processor/redsys/return/?order=' + cart.gateway_order_id, secure=True)

    # Assert
    assert anonymous_response.status_code == 401
    assert other_response.status_code == 404
    assert response.status_code == 202
    assert response.json() == {'status': 'pending'}
    assert page.status_code == 200
    cart.refresh_from_db()
    assert cart.status == Cart.Status.PROCESSING


def test_signing_matches_redsys_official_sha512_v2_vector():
    """The public signing interface reproduces the official Redsys V2 vector."""
    # Arrange
    # https://pagosonline.redsys.es/desarrolladores-inicio/documentacion-operativa/firmar-una-operacion/
    encoded = 'eyJEU19NRVJDSEFOVF9BTU9VTlQiOiI5OTkiLCJEU19NRVJDSEFOVF9PUkRFUiI6IjEyMzQ1Njc4OTAiLCJEU19NRVJDSEFOVF9NRVJDSEFOVENPREUiOiI5OTkwMDg4ODEiLCJEU19NRVJDSEFOVF9DVVJSRU5DWSI6Ijk3OCIsIkRTX01FUkNIQU5UX1RSQU5TQUNUSU9OVFlQRSI6IjAiLCJEU19NRVJDSEFOVF9URVJNSU5BTCI6IjEiLCJEU19NRVJDSEFOVF9NRVJDSEFOVFVSTCI6Imh0dHA6XC9cL3d3dy5wcnVlYmEuY29tXC91cmxOb3RpZmljYWNpb24ucGhwIiwiRFNfTUVSQ0hBTlRfVVJMT0siOiJodHRwOlwvXC93d3cucHJ1ZWJhLmNvbVwvdXJsT0sucGhwIiwiRFNfTUVSQ0hBTlRfVVJMS08iOiJodHRwOlwvXC93d3cucHJ1ZWJhLmNvbVwvdXJsS08ucGhwIn0'
    order = '1234567890'
    secret = 'sq7HjrUOBfKmC576ILgskD5srU870gJ7'
    expected_signature = 'Vjo02eSWq249IeZZp3R-ArFnGLhKY0OuzDDlx1BuVtZDC2yhczA7_11uZhsYzLZBCMFAz8u8uzGDX3AErHKmmw'

    # Act
    signature = sign_parameters(encoded, order, secret)

    # Assert
    assert signature == expected_signature


@pytest.mark.parametrize('configuration', [{}, {'merchant_code': 'bad'}, {'terminal': '0'}, {'environment': 'live'}, {'currency': 'ZZZ'}, {'secret_key': ''}])
def test_missing_or_invalid_configuration_hides_and_prevents_checkout(purchase, settings, configuration):
    """Invalid settings hide Redsys and prevent allocating a payment order."""
    # Arrange
    cart, request = purchase
    settings.REDSYS_SETTINGS = {} if not configuration else {**settings.REDSYS_SETTINGS, **configuration}
    processor = RedsysProcessor()

    # Act
    hidden = processor.is_hidden_for(request)
    with pytest.raises(GatewayError):
        processor.payment_view(cart, request)

    # Assert
    assert hidden
    cart.refresh_from_db()
    assert cart.gateway_order_id is None


def test_incompatible_purchase_currency_cannot_redirect(purchase, settings):
    """A currency mismatch prevents a signed redirect or a recorded order."""
    # Arrange
    cart, request = purchase
    settings.REDSYS_SETTINGS = {**settings.REDSYS_SETTINGS, 'currency': 'USD'}

    # Act
    with pytest.raises(GatewayError):
        RedsysProcessor().payment_view(cart, request)

    # Assert
    cart.refresh_from_db()
    assert cart.gateway_order_id is None


def test_invalid_signature_is_sanitized_and_creates_no_database_rows(purchase, caplog):
    """Rejected signatures leave only a sanitized warning and no database writes."""
    # Arrange
    cart, request = purchase
    RedsysProcessor().payment_view(cart, request)
    payload = notification(cart)
    payload['Ds_Signature'] = 'sensitive-card-secret-signature'
    before = {model: model.objects.count() for model in apps.get_models()}
    client = Client(enforce_csrf_checks=True)

    # Act
    response = client.post('/redsys/notification/', payload, secure=True)

    # Assert
    assert response.status_code == 400
    assert {model: model.objects.count() for model in apps.get_models()} == before
    assert 'Redsys notification rejected' in caplog.text
    assert payload['Ds_Signature'] not in caplog.text
    assert payload['Ds_MerchantParameters'] not in caplog.text


def test_failed_fulfillment_keeps_shared_paid_record_and_directs_buyer_to_support(purchase, client):
    """An enrollment failure preserves payment and exposes the support outcome."""
    # Arrange
    cart, request = purchase
    RedsysProcessor().payment_view(cart, request)
    payload = notification(cart)
    gateway_client = Client()
    client.force_login(cart.user)
    path = '/payment/v1/processor/redsys/status/?order=' + cart.gateway_order_id

    # Act
    response = gateway_client.post('/redsys/notification/', payload, secure=True)
    result = client.get(path, secure=True)

    # Assert
    assert response.status_code == 200
    cart.refresh_from_db()
    assert cart.status == Cart.Status.PAID
    assert Transaction.objects.get(cart=cart).status == 'success'
    assert not Invoice.objects.filter(cart=cart).exists()
    assert result.status_code == 409
    assert 'support' in result.json()['message']


def test_success_browser_return_reads_invoice_without_creating_another_payment(purchase, client):
    """Reading success repeatedly exposes the invoice without another payment."""
    # Arrange
    cart, request = purchase
    course = CourseOverview.objects.create(id='course-v1:org+course+run', org='org')
    CourseMode.objects.create(course=course, sku='paid-course', mode_slug='verified', currency='EUR')
    RedsysProcessor().payment_view(cart, request)
    client.post('/redsys/notification/', notification(cart), secure=True)
    client.force_login(cart.user)
    status_path = '/payment/v1/processor/redsys/status/?order=' + cart.gateway_order_id
    return_path = '/payment/v1/processor/redsys/return/?order=' + cart.gateway_order_id

    # Act
    results = [
        (client.get(status_path, secure=True), client.get(return_path, secure=True))
        for _ in range(2)
    ]

    # Assert
    invoice_number = Invoice.objects.get(cart=cart).invoice_number
    for result, page in results:
        assert result.json()['status'] == 'paid'
        assert result.json()['invoice_url'].endswith(invoice_number + '/')
        assert b'Payment confirmed' in page.content
    assert Transaction.objects.count() == Invoice.objects.count() == 1


def test_notification_resolves_site_without_buyer_or_site_middleware(purchase, settings, client):
    """A gateway callback resolves its site without a buyer session or site middleware."""
    # Arrange
    cart, request = purchase
    RedsysProcessor().payment_view(cart, request)
    settings.MIDDLEWARE = [value for value in settings.MIDDLEWARE if 'CurrentSiteMiddleware' not in value]
    payload = notification(cart)

    # Act
    response = client.post('/redsys/notification/', payload, secure=True)

    # Assert
    assert response.status_code == 200
    cart.refresh_from_db()
    assert cart.status == Cart.Status.PAID


def test_notification_does_not_acknowledge_an_unrecorded_approval(purchase, client):
    """An approval that cannot settle receives a retryable server response."""
    # Arrange
    cart, request = purchase
    RedsysProcessor().payment_view(cart, request)
    cart.status = Cart.Status.CLOSED
    cart.save(allow_status_change=True)
    payload = notification(cart)

    # Act
    response = client.post('/redsys/notification/', payload, secure=True)

    # Assert
    assert response.status_code == 503
    assert not Transaction.objects.filter(cart=cart).exists()


def test_checkout_chooses_an_unused_order_when_random_reference_collides(purchase, monkeypatch):
    """A random-reference collision is retried before returning the hosted form."""
    # Arrange
    cart, request = purchase
    numbers = iter([123456789012, 123456789012, 123456789013])
    monkeypatch.setattr('eox_redsys.processor.secrets.randbelow', lambda maximum: next(numbers))
    RedsysProcessor().payment_view(cart, request)
    other = Cart.objects.create(user=cart.user, status=Cart.Status.PROCESSING, gateway='redsys', payment_origin='https://testserver')
    CartItem.objects.create(cart=other, catalogue_item=cart.items.get().catalogue_item, original_price='45.25', final_price='45.25')

    # Act
    response = RedsysProcessor().payment_view(other, request)

    # Assert
    assert response.status_code == 200
    other.refresh_from_db()
    assert other.gateway_order_id == '123456789013'


@pytest.fixture
def iqd_purchase(purchase, settings):
    """Configure a 45 IQD purchase with its three ISO minor-unit digits."""
    cart, request = purchase
    settings.ZEITLABS_PAYMENTS_SETTINGS = {**settings.ZEITLABS_PAYMENTS_SETTINGS, 'valid_currency': 'IQD'}
    settings.REDSYS_SETTINGS = {**settings.REDSYS_SETTINGS, 'currency': 'IQD'}
    item = cart.items.get()
    item.catalogue_item.currency = 'IQD'
    item.catalogue_item.price = '45'
    item.catalogue_item.save()
    item.original_price = item.final_price = '45'
    item.save()
    return cart, request


def test_iqd_checkout_uses_three_iso_minor_unit_digits(iqd_purchase):
    """A 45 IQD purchase requests exactly 45000 minor units from Redsys."""
    # Arrange
    cart, request = iqd_purchase

    # Act
    response = RedsysProcessor().payment_view(cart, request)

    # Assert
    encoded = re.search(rb'name="Ds_MerchantParameters" value="([^"]+)"', response.content).group(1)
    data = json.loads(base64.urlsafe_b64decode(encoded + b'=' * (-len(encoded) % 4)))
    assert data['DS_MERCHANT_AMOUNT'] == '45000'
    assert data['DS_MERCHANT_CURRENCY'] == '368'


def test_signed_iqd_underpayment_cannot_settle_the_full_purchase(iqd_purchase, client):
    """A signed approval for 45 minor units cannot fulfill a 45 IQD purchase."""
    # Arrange
    cart, request = iqd_purchase
    RedsysProcessor().payment_view(cart, request)
    payload = notification(cart, Ds_Amount='45', Ds_Currency='368')
    counts = (Transaction.objects.count(), Invoice.objects.count(), CourseEnrollment.objects.count())

    # Act
    response = client.post('/redsys/notification/', payload, secure=True)

    # Assert
    assert response.status_code == 400
    cart.refresh_from_db()
    assert cart.status == Cart.Status.PROCESSING
    assert (Transaction.objects.count(), Invoice.objects.count(), CourseEnrollment.objects.count()) == counts
