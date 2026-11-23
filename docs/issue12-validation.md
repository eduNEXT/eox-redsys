# Issue 12 validation

Implementation starts at integration commit `79f8e545ae40fc9543ab927cf50d3ccc22fdb49e`.
Public boundaries: shared processor payment initiation, anonymous Redsys HTTP
notification, buyer return/status, persisted shared payment/invoice and Open edX
fulfillment results, and the documented Redsys signing protocol interface.

The shared plugin is installed from exact upstream commit
`f1669db7020951f810b9d9a3b3b996cfaf12fd36`, version 1.2.0. An older local checkout
was inspected but is not part of the runtime/test path.

## Recorded red → green cycles

1. Checkout tracer: `1 failed`, `get_transaction_parameters` raised
   `NotImplementedError`; implemented original amount/currency, signed hosted
   form and shared order recording; `1 passed`.
2. Anonymous approval/replay tracer: `1 failed, 1 passed`, notification route
   returned 501; implemented validation and shared payment delegation. A real
   duplicate AuditLog contract error exposed missing context; supplied its
   required transaction/status context; `2 passed`.
3. Signed original-amount/currency mismatch tracer: `2 failed, 7 passed`,
   uncaught `GatewayError` produced 500; mapped rejection to sanitized 400;
   `9 passed`.
4. Buyer-owned pending return/status tracer: `1 failed, 9 passed`, empty view
   returned 405; implemented authenticated persisted-state reads; `10 passed`.
5. Added official literal signing vector and negative configuration/currency/
   invalid-signature cases; existing implementation passed, `19 passed`.
   These cases were not artificially made red.
6. Success return and shared fulfillment failure: success first failed because
   the initial test URL setup omitted the shared invoice route. Replaced the
   test URL setup with the real shared plugin URL module; `21 passed`.
7. Callback site fallback and unrecorded approval: failures were missing
   `request.site` and an incorrect 200 acknowledgment after shared flow refused
   an already closed cart. Added host-based site fallback and 503 for unsettled
   approvals; `23 passed`.
8. Random order collision: real shared database raised `IntegrityError` on the
   second colliding order; added bounded handoff retry around shared recording;
   `24 passed`.

The notification tests never mock `process_payment_and_update_records`, invoice
creation, shared models, or shared fulfillment. Enrollment uses the real shared
course handler against the Open edX boundary model double. Invalid-signature
coverage compares row counts for every installed model and uses a CSRF-enforcing
anonymous HTTP client.

## Reproduction and results

Documented install command verified successfully:

```sh
uv --cache-dir /tmp/eox-redsys-uv-cache pip install \
  --python /tmp/eox-redsys-venv/bin/python -r requirements/test.txt
/tmp/eox-redsys-venv/bin/pytest -q
```

The first command rebuilt the pinned plugin from GitHub and replaced the earlier
editable research checkout. Python 3.11.18, Django 5.2.19, pytest 9.2.0 and
pytest-django 4.14.0 were used. Final result is recorded below after the last run.

The official signing specification and literal expected vector are linked in the
test and README. Current official protocol is `HMAC_SHA512_V2`, superseding the
PRD's older V1 manual reference. DCC behavior is bank-managed. No live bank
sandbox execution or concurrent production-database test was performed; SQLite
only establishes repeat-delivery behavior, while production serialization uses
`select_for_update` with database uniqueness.

Final run after adding DCC present/absent cases: **25 passed in 0.98s**.
`uv pip check` reported all 38 installed packages compatible; `git diff --check`
passed. Both DCC cases use a CSRF-enforcing anonymous HTTP client. The first
absent-DCC fixture used nulls, which upstream sanitization renders as strings;
the fixture was corrected to omit optional bank fields, matching a DCC-disabled
notification.
