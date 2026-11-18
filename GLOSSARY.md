# MetaRed payments

Vocabulary for payments on the MetaRed platform through Getnet and the Redsys Virtual POS.

## Language

**MetaRed**:
Organization requiring its platform payments to be processed through Getnet, including course purchases, certificates, and other payment models.

**Getnet**:
Banco Santander's payment processing provider, required by MetaRed for its online payments.

**Redsys Virtual POS**:
Service through which Getnet processes online payments for this integration.
_Avoid_: Getnet as a synonym for the Redsys Virtual POS.

**Hosted payment page**:
Redsys Virtual POS page to which the buyer is directed to make a payment.
_Avoid_: Platform card entry form.

**Course purchase**:
Acquisition of access to a paid course by a MetaRed user.

**University**:
Institution responsible for offering the course, to which its payment is attributed in reports. It does not necessarily identify the institution to which the buyer belongs.

**Course organization (`org`)**:
Organization to which a course belongs in Open edX. In MetaRed, it generally represents a university and provides the basis for attributing the course payment.
_Avoid_: Buyer's institution as a synonym for course organization.

**Payment attempt**:
Each request to the Virtual POS to pay for a purchase, identified by a unique order number. Retrying a declined or canceled purchase constitutes a separate attempt.
_Avoid_: Purchase as a synonym for payment attempt.

**Payment notification**:
Communication from the Virtual POS to the platform containing a transaction outcome, whose authenticity is verified through its signature.
_Avoid_: Browser return as a synonym for payment notification.

**Payment pending confirmation**:
Payment attempt whose definitive outcome is not yet known. Abandoning the payment page or not receiving a notification does not constitute a decline or a confirmed cancellation.
_Avoid_: Declined or canceled payment as a synonym for an unconfirmed payment.

**Access fulfillment**:
Granting the buyer access to the purchased course. It may remain pending even when payment has already been approved.
_Avoid_: Payment approval as a synonym for access fulfillment.

**Processor response**:
Received message containing data attributed to the Virtual POS about a payment operation. Receipt does not imply that the message is authentic or that its outcome has been applied to the purchase.
_Avoid_: Confirmed payment as a synonym for a received response.
