# Cobros de MetaRed

Vocabulario de los cobros de la plataforma MetaRed mediante Getnet y el TPV Virtual de Redsys.

## Language

**MetaRed**:
Organización que requiere que los cobros de su plataforma se procesen mediante Getnet, incluyendo compras de cursos, certificados y otros modelos de pago.

**Getnet**:
Proveedor de procesamiento de pagos de Banco Santander requerido por MetaRed para sus cobros en línea.

**TPV Virtual de Redsys**:
Servicio mediante el cual Getnet procesa los pagos en línea de esta integración.
_Avoid_: Getnet como sinónimo del TPV Virtual de Redsys.

**Página de pago alojada**:
Página del TPV Virtual de Redsys a la que se dirige al comprador para realizar el pago.
_Avoid_: Formulario de tarjeta de la plataforma.

**Compra de curso**:
Adquisición del acceso a un curso de pago por un usuario de MetaRed.

**Universidad**:
Institución responsable de ofrecer el curso a la que se atribuye su cobro en los reportes. No identifica necesariamente la institución a la que pertenece el comprador.

**Organización del curso (`org`)**:
Organización a la que pertenece un curso en Open edX. En MetaRed generalmente representa una universidad y sirve como base para atribuir el cobro del curso.
_Avoid_: Institución del comprador como sinónimo de organización del curso.

**Intento de pago**:
Cada ocasión en que se solicita al TPV Virtual el pago de una compra, identificada por un número de pedido único. Reintentar una compra rechazada o cancelada constituye un intento distinto.
_Avoid_: Compra como sinónimo de intento de pago.

**Notificación de pago**:
Comunicación del TPV Virtual a la plataforma con el resultado de una transacción, cuya autenticidad se verifica mediante su firma.
_Avoid_: Retorno del comprador como sinónimo de notificación de pago.

**Pago pendiente de confirmación**:
Intento de pago cuyo resultado definitivo todavía no se conoce. Abandonar la página de pago o no recibir una notificación no equivale a un rechazo ni a una cancelación confirmada.
_Avoid_: Pago rechazado o cancelado como sinónimo de pago sin confirmación.

**Entrega del acceso**:
Otorgamiento al comprador del acceso al curso adquirido. Puede quedar pendiente aunque el pago ya esté aprobado.
_Avoid_: Aprobación del pago como sinónimo de entrega del acceso.

**Respuesta del procesador**:
Mensaje recibido con datos atribuidos al TPV Virtual sobre una operación de pago. Su recepción no implica que sea auténtico ni que su resultado haya sido aplicado a la compra.
_Avoid_: Pago confirmado como sinónimo de respuesta recibida.
