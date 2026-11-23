eox-redsys
###########

Redsys hosted authorization processor for ``openedx-zeitlabs-payments``.

Installation
************

Python 3.11+ and an Open edX LMS with the shared payments plugin are required::

    pip install .

The runtime dependency pins the reviewed shared plugin to
``f1669db7020951f810b9d9a3b3b996cfaf12fd36`` (version 1.2.0), using its
``zeitlabs_payments.v1`` contract. Older 1.0-era snapshots do not provide the
same order correlation or reconciliation contract and are not compatible.
The package declares Django 4.2–5.2 compatibility; the standalone suite below
is verified on Python 3.11 and Django 5.2.19.

The ``lms.djangoapp`` entry point installs the application, templates and
notification URL. The ``zeitlabs_payments.v1`` entry point registers Redsys
in the shared checkout. For a plain Django deployment, install both apps
and mount ``eox_redsys.urls`` under ``redsys/`` with namespace ``eox_redsys``,
and mount ``zeitlabs_payments.urls`` under its usual namespace. Run the
shared plugin migrations; this processor adds no tables.

Configuration
*************

Set ``REDSYS_SETTINGS`` in protected LMS or site configuration. The shared
plugin's site-aware settings layer gives site configuration precedence::

    REDSYS_SETTINGS = {
        'merchant_code': '999008881',
        'terminal': '1',
        'environment': 'test',       # exactly 'test' or 'production'
        'currency': 'EUR',           # merchant/terminal's contracted ISO currency
        'secret_key': '<merchant secret>',
    }

Configure the shared plugin's ``valid_currency`` to the same currency and
its invoice/organization settings normally. Merchant code has nine digits;
terminal has one to three digits and must be positive. Incomplete or invalid
configuration hides Redsys and stops direct initiation. The cart's server-side
currency must equal the configured currency; amounts use its ISO minor-unit
precision, with no implicit conversion or rounding.

Set the Django Site domain and public HTTPS origin correctly, including proxy
HTTPS settings. Callbacks must reach the same configured site where checkout
started. A callback resolves the site from the host if middleware did not
supply it. Configure the merchant to send online server notifications to the
URL generated in ``DS_MERCHANT_MERCHANTURL``. Default routes are:

- ``/redsys/notification/``: anonymous, CSRF-exempt, signed server POST.
- ``/payment/v1/processor/redsys/return/``: buyer-authenticated recorded result.
- ``/payment/v1/processor/redsys/status/``: buyer-owned recorded result.

Test payments post to ``https://sis-t.redsys.es:25443/sis/realizarPago``;
production uses ``https://sis.redsys.es/sis/realizarPago``. Enable or disable
DCC at the bank terminal; Redsys owns currency choice and conversion. This
processor always sends and reconciles original purchase amount/currency,
regardless of extra DCC values.

Protocol and processing
***********************

This implementation uses current Redsys ``HMAC_SHA512_V2``: AES-128-CBC with
PKCS7 padding diversifies the secret by order, its Base64 text keys HMAC-SHA512,
and the exact received encoded parameters are verified with constant-time
comparison. ``sign_parameters(encoded, order, secret)`` is the public protocol
signing interface. The official known vector is an independent test fixture.
The older PRD manual's ``HMAC_SHA512_V1`` reference is superseded by the
`current Redsys signing specification`_.

.. _current Redsys signing specification: https://pagosonline.redsys.es/desarrolladores-inicio/documentacion-operativa/firmar-una-operacion/

The shared cart records a twelve-digit unique order before the redirect form
is returned. Database uniqueness guards collisions, which are retried at
handoff. Each cart is handed off once. Server notifications verify signature,
merchant, terminal, operation type, order, original amount and currency before
calling the shared ``process_payment_and_update_records`` method. Type-0
response codes 0000–0099 are approved. The Redsys order is the payment
correlation key; the shared transaction reference is ``redsys:<order>``.

Shared payment recording, invoice issuance, enrollment and failure auditing
remain in the shared plugin. Supported response fields are retained in
``Transaction.response``; envelope signatures, secrets and card details are
never retained. Invalid notifications generate one fixed sanitized warning
and no database writes. A cart row lock serializes callbacks; a repeated
approval uses the existing duplicate audit action and cannot fulfill twice.
Use a database with row locking in production; SQLite tests exercise basic
repeated delivery, not database concurrency guarantees.

A successful server delivery receives HTTP 200, including an already recorded
approval or a paid purchase whose fulfillment failed. Unrecorded/unsettled
approvals receive HTTP 503 for retry/operational inspection. Invalid messages
receive HTTP 400. Browser return and polling only read saved state. An invoice
links the buyer to the shared invoice/course pages; paid purchases whose
fulfillment failed direct the buyer to support.

This issue-12 slice implements approvals and basic replay safety. Authentic
non-authorized notifications are acknowledged without changing purchase
state. Non-authorized recording, internal retry precedence, timeout retries,
lifecycle extensions and enhanced operational tooling belong to later tickets.
No live Redsys/bank sandbox payment has been performed by the automated suite.

Standalone integration tests
****************************

From the repository root::

    python3.11 -m venv .venv
    .venv/bin/python -m pip install -r requirements/test.txt
    .venv/bin/python -m pytest -q

The install fetches the exact runtime plugin revision; it does not require an
external checkout or absolute local paths. Tests use real shared migrations
and persisted carts, transactions, invoices and audit records. Only Open edX
boundary APIs/models are replaced with attributed upstream test doubles.
Coverage includes approval without browser return, DCC originals, duplicate
receipts, authenticated read-only return/status, fulfillment failure,
configuration/currency rejection, signed mismatches, invalid signatures with
zero added rows, order collision and the official SHA512 V2 vector.

Red/green implementation evidence is in ``docs/issue12-validation.md``.
