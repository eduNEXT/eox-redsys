eox-redsys
###########

Payment processor for `openedx-zeitlabs-payments`_ (contract ``v1``).

.. _openedx-zeitlabs-payments: https://github.com/zeit-labs/openedx-zeitlabs-payments

Installation
************

Requires ``openedx-zeitlabs-payments`` >= 1.0.0 (processor contract ``v1``) installed in the LMS. Install the package
next to it::

    pip install eox-redsys

The package registers itself through two entry points, without changes in zeitlabs:

- ``zeitlabs_payments.v1``: ``redsys = eox_redsys.processor:RedsysProcessor``.
- ``lms.djangoapp``: installs the Django app, so the LMS finds its templates.

The processor is hidden in the checkout while ``REDSYS_SETTINGS`` is not configured.

Configuration
*************

``REDSYS_SETTINGS`` is read from the site configuration first and from the Django settings otherwise::

    REDSYS_SETTINGS = {}

URLs
****

zeitlabs mounts the views of the processor by its slug:

- ``payment/v1/processor/redsys/return/``
- ``payment/v1/processor/redsys/status/``

Pending
*******

- ``RedsysProcessor.get_transaction_parameters`` and ``RedsysProcessor.reconcile_payment``.
- ``RedsysStatusView``: ``get_order_cart_reference``, ``get_order_status``, ``get_payment_status``,
  ``verify_success_response`` and ``get_transaction_details``.
- ``GATEWAY_ORDER_ID_PARAM`` and the template ``eox_redsys/payment.html``.
