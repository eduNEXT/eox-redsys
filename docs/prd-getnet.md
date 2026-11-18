# PRD for MetaRed course payments with Getnet

Status: scope confirmed on November 17, 2026.

## Objective

Enable MetaRed to collect payments for course purchases in Open edX through Getnet, using the Redsys Virtual POS hosted payment page. The integration must initiate payment, receive and validate its outcome, record the transaction, and grant course access without depending on the buyer returning to the platform.

The processor will be developed in `eox-redsys` as an independent extension of `openedx-zeitlabs-payments`. Getnet will appear as a payment option at checkout. MetaRed will use a single merchant account and terminal, with prices and charges in EUR.

## First release scope

- Course purchases using debit, credit, international, and AMEX cards, through the payment methods enabled by Getnet for the merchant.
- Signed requests, redirection to the Virtual POS, verified notifications, and return pages showing the outcome or pending confirmation.
- Cardholder authentication handled by the Virtual POS through its EMV3DS flow.
- A new order number for each payment attempt initiated from Open edX.
- Storage of processor responses in a Django model and its MySQL table.
- Preservation of historical purchase data and attribution by course and Open edX organization (`org`).
- Resolution of unconfirmed payments and recovery of failed enrollments through Django Admin, with permissions and an audit trail.
- Required changes to the e-commerce plugin to preserve special characters, process payments independently of the browser, and retain the invoice when enrollment fails.
- Validation in the Redsys test environment and preparation of deployment configuration.

This release excludes certificate purchases as a standalone product, other products, subscriptions, recurring payments, installment payments, refunds from Open edX, DCC, and report generation. The data needed for a future report using a PDF template will be retained, including payment, course, university, and user information.

The release adds Getnet; it does not establish a global policy for removing other processors that an installation may have configured.

## Buyers and payment attribution

A user who has already purchased the course will not be allowed to purchase it again. A free enrollment will allow the user to purchase paid access. An approved payment with enrollment still pending will continue to block a new purchase.

Payment attribution will use the course's `org`, which generally represents a university. The buyer's institution will not determine this attribution. All organizations will share the credentials of MetaRed's single merchant account; this attribution does not imply distributing funds among merchant accounts.

## Purchase flow

1. The plugin validates that the user can purchase the course and that no payment in progress or previous purchase blocks it.
2. The platform obtains the EUR price from its purchase data. The browser does not determine the amount or currency accepted for the charge.
3. The attempt and its unique order number are recorded before sending the buyer to the Virtual POS. The request contains the amount, currency, and required references and URLs, and is signed with the merchant key.
4. The buyer enters card details and completes authentication on the Virtual POS hosted page.
5. The Virtual POS sends its notification to the server. The integration checks the signature, merchant, terminal, order, amount, and currency before applying an outcome to a purchase.
6. A valid approval records the payment, generates the invoice, and grants access through the plugin. If enrollment fails, the payment and invoice are retained and access fulfillment remains pending.
7. The browser return page displays the recorded status. If no valid outcome is available yet, it shows pending confirmation and blocks another attempt for the same product.

Confirmation must work even if the buyer closes the browser. Duplicate notifications, page reloads, and concurrent notification and browser return processing must not duplicate payments, invoices, or enrollments.

## Outcomes and retries

The following are functional states. Their mapping to the plugin's existing states will be defined during technical design, without assuming their names match.

| Situation | Outcome for the buyer and purchase | Payment retry |
| --- | --- | --- |
| Attempt submitted without a definitive outcome | Confirmation pending, no access | Blocked |
| Payment approved and access granted | Success and access to the invoice and course | Blocked |
| Payment approved and enrollment failed | Payment and invoice retained, message to contact support | Blocked; retry access fulfillment |
| Definitive decline | Decline message, no access | Allowed with a new order number |
| Confirmed definitive cancellation | Purchase canceled, no access | Allowed with a new order number |
| Invalid notification or mismatched data | No purchase state transition; evidence recorded | Not unblocked by that notification |

Closing the page, navigating back, or reaching a timeout does not prove that a payment was canceled or declined. The attempt remains pending until a definitive outcome arrives or support records a verified resolution.

Internal Virtual POS retries using the same order number will be disabled. After a definitive decline or cancellation, the buyer may initiate another attempt from Open edX with a new order number. Resolving one attempt must not modify a different purchase.

If the Virtual POS is unavailable and it can be established that no payment was initiated, a retry will be allowed without enrollment or an approved charge being recorded. If the outcome is uncertain, the payment will be treated as pending.

## Processor response storage

A Django model and its MySQL table will be created to retain every response received from the processor. This includes approvals, declines, duplicate notifications, and messages with invalid signatures. Browser returns containing processor parameters will be distinguished from server notifications.

Each received message must be able to retain the following, when available:

- Receipt date and time, and message source: notification or browser return.
- Relationship to the payment attempt and purchase, and the order number reported by the Virtual POS.
- Merchant, terminal, and transaction references, result code, authorization code, and reported card type.
- Reported amount and currency.
- Signature validation result and purchase data verification result.
- Received content with secrets and sensitive card data removed.
- Processing outcome: applied, duplicate, rejected, or pending review.

An invalid or unknown message may have no linked purchase. Its fields will not be considered authentic and will not be used to modify a purchase. Duplicate receipts will retain their evidence without duplicating business effects.

Verification will use the original data before sanitization for storage. The merchant secret key and sensitive card data will not be stored in responses or logs. Technical design will specify model names, fields, indexes, and storage limits.

## Historical data for future reports

The purchase record will preserve a snapshot of the price and charged amount, EUR currency, course identity and name, responsible organization, and buyer identification needed for reporting. Subsequent changes to the course price, name, or attribution will not alter the historical record.

Virtual POS responses will supplement this history with data for each attempt, whether approved or declined. Purchases will be linked to their payments, invoices, and fulfillment outcomes to support a future PDF report by payment, course, university, and user.

Data provenance will remain distinct: purchase data comes from the platform, while outcome data comes from verified Virtual POS responses. A response can be recorded even when it contains no authorization code or card type.

## Django Admin operations

### Unconfirmed payments

Support will be able to locate an attempt by order, purchase, and user, review received responses, and verify the outcome in the Virtual POS portal. Support will be able to record a resolution with the operator, date, verification reference, and reason.

A verified approval will follow the payment recording, invoicing, and fulfillment flow. A definitive decline or cancellation will allow a new attempt. The intervention will be recorded as a support action, distinguished from an authentic Virtual POS notification. Elapsed time alone will not enable another purchase.

### Approved payments with failed enrollment

Support will be able to retry access fulfillment from Django Admin using the already approved payment. The action will retain the invoice and will not initiate a charge or generate another invoice. If access has already been granted, repeating the action will not duplicate enrollment. Failures and actions taken will be recorded.

Actions will be restricted through Django Admin permissions. The buyer will see a message explaining the fulfillment problem and directing them to contact support.

## Component responsibilities

| Component | Responsibility |
| --- | --- |
| `eox-redsys` | Processor registration, Getnet configuration, signed request, redirect page, response receipt and validation, attempt identification, and Virtual POS response storage |
| `openedx-zeitlabs-payments` | Checkout, purchase, transactions, invoice, access fulfillment, and operational tools; shared changes required to meet this PRD |
| Open edX | User, course, organization, and enrollment |
| Virtual POS configuration | Credentials and terminal, enabled notifications, contracted payment methods, internal retries disabled, and DCC disabled |

The reviewed plugin exposes browser return and status query views that depend on the authenticated user, but does not provide a complete processor notification interface. The implementation must add server notification handling and reuse the shared processing flow with concurrency control.

In the reviewed version, the invoice and enrollment are created within the same atomic transaction. Retaining the invoice when enrollment fails will require changes to that flow, in addition to preserving accented characters and ñ in data sent to the processor. These changes are in scope and must be checked against the specific plugin version to be deployed.

## Acceptance criteria

| Scenario | Expected outcome |
| --- | --- |
| Approved payment | The user returns to a success page, can access the invoice, and receives course access |
| Immediate decline | The decline is reported, no access is granted, and a new attempt with a different order number is allowed |
| Definitive cancellation | No access is granted, and a new attempt is allowed only after the definitive cancellation is known |
| Abandonment or browser closure | This is not treated as cancellation; if the outcome is unknown, the attempt remains pending |
| Pending confirmation | The buyer is informed and another purchase of the same product is blocked |
| Late approval | The purchase is completed and access is granted without buyer intervention |
| Late decline | The decline is recorded and the outcome is displayed, without granting access |
| Browser closure after payment | A valid notification completes the purchase without a browser return |
| Duplicate notifications | Evidence of each receipt is retained and the business effect is applied only once |
| Reload or concurrency | Return page reloads and concurrent notifications do not duplicate payment, invoice, or enrollment |
| Invalid signature | The sanitized message and validation failure are retained without modifying any purchase |
| Unknown order or mismatched data | The problem is recorded without approving or fulfilling a purchase based on that data |
| Amount integrity | The amount and currency match the server-side purchase; browser manipulation cannot change them |
| Virtual POS unavailable | No access is granted or payment declared approved; a retry is allowed if no payment is in progress, and the attempt remains pending if its outcome is uncertain |
| Previously purchased course | Another purchase is blocked; a free enrollment does not prevent purchasing paid access |
| Approved payment with failed enrollment | Payment and invoice are retained, the failure is recorded, and the user is directed to contact support |
| Access recovery | An authorized operator retries fulfillment from Django Admin without another charge or invoice |
| Manual resolution of a pending payment | Support records the outcome verified in the Virtual POS, with evidence, operator, date, and reason |
| Payment methods | The flow is validated with debit, credit, international, and AMEX cards using the cases available for the test merchant |
| Special characters | Course and user names preserve accented characters and ñ in transmitted and displayed data |
| Historical data | Later changes to the course price, name, or organization do not alter the recorded purchase data |
| Currency | Charges are made in EUR and the terminal does not offer DCC in this release |
| Retry configuration | The Virtual POS does not offer internal retries; a new attempt in Open edX receives a different order number |

## Validation and deployment

Testing will cover signing and verification, order correlation, amounts and currency, Unicode preservation, response persistence, and business state transitions. Integration tests will cover notifications without a user session, duplicates and concurrency, repeat purchase blocking, support resolution, and access recovery.

Before production, the full flow will be validated in the Virtual POS test environment, including approval and decline outcomes, browser return, notification delivery, and required payment methods. Getnet must confirm that the merchant's contracted capabilities and configuration support those methods.

Deployment configuration will include protected credentials, environment selection, URLs reachable by the Virtual POS, notification enablement, and disabling DCC and internal retries. The compatible version of `openedx-zeitlabs-payments` and its required changes will be verified.

## Preliminary estimate

| Original task | Base hours |
| --- | ---: |
| Processor development and special character changes | 9 |
| Processor testing and Redsys environment validation | 3 |
| Configuration and deployment | 2 |
| Original total | 14 |

The 14 hours are a preliminary reference, subject to revision during technical design. The final estimate must include the response table and its audit trail, historical data, Django Admin resolution, browser-independent processing, concurrency control, and plugin changes to retain invoices and recover enrollment.

## Technical references

- Domain vocabulary: [GLOSSARY.md](../GLOSSARY.md).
- Manual provided by Getnet: `TPV-Virtual Manual Integración - Redirección V4.0.pdf`, version 4.0, dated March 20, 2025, reference RS.TE.CEL.MAN.0039. Relevant sections: submission and signing, pages 9–13; notification, page 14; browser return, page 15; parameters and retries, pages 32–34; SHA-256 alternative, pages 43–44.
- The manual recommends `HMAC_SHA512_V1` and describes UTF-8. Parameter and code details will be completed using the supplementary document `TPV-Virtual Parámetros Entrada-Salida.xlsx`, referenced by the manual, before implementing their validation.
- Plugin reviewed at commit [`f1669db7020951f810b9d9a3b3b996cfaf12fd36`](https://github.com/zeit-labs/openedx-zeitlabs-payments/tree/f1669db7020951f810b9d9a3b3b996cfaf12fd36): [processor contract](https://github.com/zeit-labs/openedx-zeitlabs-payments/blob/f1669db7020951f810b9d9a3b3b996cfaf12fd36/docs/how-tos/build-a-payment-processor.rst), [payment processing and invoicing](https://github.com/zeit-labs/openedx-zeitlabs-payments/blob/f1669db7020951f810b9d9a3b3b996cfaf12fd36/zeitlabs_payments/providers/base.py#L579-L759), [status views](https://github.com/zeit-labs/openedx-zeitlabs-payments/blob/f1669db7020951f810b9d9a3b3b996cfaf12fd36/zeitlabs_payments/providers/mixins.py#L127), [text normalization](https://github.com/zeit-labs/openedx-zeitlabs-payments/blob/f1669db7020951f810b9d9a3b3b996cfaf12fd36/zeitlabs_payments/helpers.py#L107-L216).
