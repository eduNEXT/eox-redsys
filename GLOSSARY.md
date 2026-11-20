# Redsys payments

Vocabulary for course purchases and payments through the Redsys Virtual POS.

## Language

**Redsys Virtual POS**:
Payment gateway used by an online merchant to request payments and receive their outcomes.

**Hosted payment page**:
Redsys Virtual POS page to which the buyer is directed to make a payment.
_Avoid_: Platform card entry form.

**Course purchase**:
Acquisition of access to a paid course by a buyer.

**Payment attempt**:
Each request to the Virtual POS to pay for a purchase, identified by a unique order number. Starting a new payment request after a non-authorized outcome constitutes a separate attempt.
_Avoid_: Purchase as a synonym for payment attempt.

**Payment notification**:
Communication from the Virtual POS to the platform containing a transaction outcome, whose authenticity is verified through its signature.
_Avoid_: Browser return as a synonym for payment notification.

**Non-authorized payment outcome**:
Verified payment result indicating that the payment was not authorized. Declines and cancellations reported by the payment gateway share this functional outcome; an unknown result is not a non-authorized outcome.

**Payment pending confirmation**:
Payment attempt whose definitive outcome is not yet known. Abandoning the payment page or not receiving a notification does not establish a non-authorized outcome.
_Avoid_: Non-authorized payment as a synonym for an unconfirmed payment.

**Access fulfillment**:
Granting the buyer access to the purchased course. It may remain pending even when payment has already been approved.
_Avoid_: Payment approval as a synonym for access fulfillment.

**Processor response**:
Received message containing data attributed to the Virtual POS about a payment operation. Receipt does not imply that the message is authentic or that its outcome has been applied to the purchase.
_Avoid_: Confirmed payment as a synonym for a received response.
