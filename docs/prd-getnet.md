# PRD de pagos de cursos con Getnet para MetaRed

Estado: alcance confirmado el 17 de noviembre de 2026.

## Objetivo

Permitir que MetaRed cobre la compra de cursos en Open edX mediante Getnet, utilizando la página de pago alojada del TPV Virtual de Redsys. La integración debe iniciar el pago, recibir y validar su resultado, registrar la operación y entregar el acceso al curso sin depender de que el comprador regrese a la plataforma.

El procesador se desarrollará en `eox-redsys` como una extensión independiente de `openedx-zeitlabs-payments`. Getnet aparecerá como opción en el checkout. Se utilizará un único comercio y terminal para MetaRed, con precios y cobros en EUR.

## Alcance de la primera versión

- Compra de cursos con tarjeta de débito, crédito, internacional y AMEX, mediante los medios habilitados por Getnet para el comercio.
- Peticiones firmadas, redirección al TPV, notificaciones verificadas y páginas de retorno con resultado o confirmación pendiente.
- Autenticación del titular gestionada en el TPV mediante su flujo EMV3DS.
- Un número de pedido nuevo por intento iniciado desde Open edX.
- Registro de respuestas del procesador en un modelo de Django y su tabla en MySQL.
- Conservación del histórico de la compra y atribución por curso y organización de Open edX (`org`).
- Resolución de pagos sin confirmación y recuperación de inscripciones fallidas desde Django Admin, con permisos y trazabilidad.
- Ajustes necesarios en el plugin de e-commerce para conservar caracteres especiales, procesar pagos sin navegador y conservar la factura ante un fallo de inscripción.
- Validación en el entorno de pruebas de Redsys y preparación de la configuración de despliegue.

Quedan fuera de esta versión las compras de certificados como producto independiente, otros productos, suscripciones, pagos recurrentes, pagos fraccionados, devoluciones desde Open edX, DCC y la generación de reportes. Se conservarán los datos necesarios para incorporar después un reporte con template PDF que incluya pago, curso, universidad y usuario.

La entrega incorpora Getnet; no establece una política global de eliminación de otros procesadores que una instalación pudiera tener configurados.

## Compradores y atribución de los cobros

Un usuario que ya compró el curso no podrá comprarlo nuevamente. Una inscripción gratuita permitirá adquirir el acceso de pago. Un pago aprobado cuya inscripción esté pendiente seguirá bloqueando una nueva compra.

La atribución del cobro utilizará la `org` del curso, que generalmente representa una universidad. No se utilizará la institución del comprador para determinar esta atribución. Todas las organizaciones compartirán las credenciales del único comercio de MetaRed; esta atribución no implica distribución del dinero entre comercios.

## Flujo de compra

1. El plugin valida que el usuario pueda comprar el curso y que no exista un pago en curso o una compra previa que lo bloquee.
2. La plataforma obtiene el precio en EUR desde sus datos de compra. El navegador no determina el monto ni la moneda aceptados para el cobro.
3. Se registra el intento y su número de pedido único antes de enviar al comprador al TPV. La petición contiene el importe, la moneda y las referencias y URLs requeridas, y se firma con la clave del comercio.
4. El comprador introduce los datos de tarjeta y completa la autenticación en la página alojada del TPV.
5. El TPV envía su notificación al servidor. La integración comprueba firma, comercio, terminal, pedido, importe y moneda antes de aplicar un resultado a una compra.
6. Una aprobación válida registra el pago, genera la factura y entrega el acceso mediante el plugin. Si falla la inscripción, se conservan el pago y la factura y queda pendiente la entrega del acceso.
7. El retorno del navegador muestra el estado registrado. Si todavía no hay un resultado válido, muestra confirmación pendiente y bloquea otro intento para el mismo producto.

La confirmación debe funcionar aunque el comprador cierre el navegador. Las notificaciones duplicadas, las recargas y la concurrencia entre notificación y retorno no deben repetir pagos, facturas ni inscripciones.

## Resultados y reintentos

Los siguientes son estados funcionales. Su correspondencia con los estados existentes del plugin se definirá durante el diseño técnico, sin asumir que sus nombres coinciden.

| Situación | Resultado para el comprador y la compra | Reintento de pago |
| --- | --- | --- |
| Intento enviado sin resultado definitivo | Confirmación pendiente, sin acceso | Bloqueado |
| Pago aprobado y acceso entregado | Éxito y acceso a la factura y al curso | Bloqueado |
| Pago aprobado e inscripción fallida | Pago y factura conservados, aviso de contactar a soporte | Bloqueado; se reintenta la entrega |
| Rechazo definitivo | Mensaje de rechazo, sin acceso | Permitido con un pedido nuevo |
| Cancelación definitiva confirmada | Compra cancelada, sin acceso | Permitido con un pedido nuevo |
| Notificación inválida o datos incompatibles | Sin transición de la compra; evidencia registrada | No se desbloquea por esa notificación |

Cerrar la página, volver atrás o agotar un plazo no demuestra que el pago esté cancelado o rechazado. El intento permanece pendiente hasta recibir un resultado definitivo o una resolución verificada por soporte.

Los reintentos internos del TPV con el mismo pedido estarán deshabilitados. Después de un rechazo o una cancelación definitivos, el comprador podrá iniciar otro intento desde Open edX con un pedido nuevo. La resolución de un intento no debe modificar una compra distinta.

Si el TPV no está disponible y se demuestra que no se inició un pago, se permitirá reintentar sin inscripción ni registro de un cobro aprobado. Si existe incertidumbre sobre el resultado, se aplicará el tratamiento de pago pendiente.

## Registro de respuestas del procesador

Se creará un modelo de Django con su tabla en MySQL para conservar cada respuesta recibida del procesador. Incluirá aprobaciones, rechazos, notificaciones repetidas y mensajes con firma inválida. Los retornos que incluyan parámetros del procesador se distinguirán de las notificaciones al servidor.

Cada recepción deberá poder conservar, cuando estén disponibles:

- Fecha y hora de recepción y origen del mensaje: notificación o retorno.
- Relación con el intento de pago y la compra, y número de pedido informado por el TPV.
- Referencias de comercio, terminal y transacción, código de resultado, código de autorización y tipo de tarjeta informado.
- Importe y moneda informados.
- Resultado de validación de firma y de comprobación de los datos de la compra.
- Contenido recibido depurado de secretos y datos sensibles de tarjeta.
- Resultado de procesamiento: aplicado, repetido, rechazado o pendiente de revisión.

Un mensaje inválido o desconocido podrá no tener una compra vinculada. Sus campos no se considerarán auténticos y no se utilizarán para modificar una compra. Las recepciones duplicadas conservarán su evidencia sin duplicar los efectos de negocio.

La verificación utilizará los datos originales antes de depurarlos para almacenamiento. La clave secreta del comercio y los datos sensibles de tarjeta no se guardarán en las respuestas ni en los logs. El diseño técnico concretará nombres de modelos, campos, índices y límites de almacenamiento.

## Histórico para reportes futuros

El registro de la compra conservará una instantánea del precio e importe cobrado, moneda EUR, identidad del curso y su nombre, organización responsable e identificación del comprador necesaria para el reporte. Cambios posteriores de precio, nombre o atribución del curso no alterarán el histórico.

Las respuestas del TPV complementarán este histórico con los datos de cada intento, tanto aprobado como rechazado. Las compras se relacionarán con sus pagos, facturas y resultados de entrega para permitir un futuro reporte PDF por pago, curso, universidad y usuario.

La procedencia de cada dato permanecerá diferenciada: los datos de compra provienen de la plataforma y los datos del resultado provienen de respuestas verificadas del TPV. La ausencia de un código de autorización o tipo de tarjeta en una respuesta no impedirá registrarla.

## Operación desde Django Admin

### Pagos sin confirmación

Soporte podrá localizar el intento por su pedido, compra y usuario, revisar las respuestas recibidas y verificar el resultado en el portal del TPV. Podrá registrar una resolución con el operador, fecha, referencia de verificación y motivo.

Una aprobación verificada seguirá el flujo de registro de pago, factura y entrega. Un rechazo o cancelación definitivos permitirán un nuevo intento. La intervención quedará registrada como acción de soporte, diferenciada de una notificación auténtica del TPV. El paso del tiempo por sí solo no habilitará otra compra.

### Pagos aprobados con inscripción fallida

Soporte podrá reintentar la entrega del acceso desde Django Admin usando el pago ya aprobado. La acción conservará la factura y no iniciará un cobro ni generará otra factura. Si el acceso ya fue entregado, repetir la acción no duplicará la inscripción. Los fallos y las acciones realizadas quedarán registrados.

Las acciones estarán restringidas mediante permisos de Django Admin. El comprador verá un mensaje que confirme el problema de entrega e indique contactar a soporte.

## Responsabilidades de los componentes

| Componente | Responsabilidad |
| --- | --- |
| `eox-redsys` | Registro del procesador, configuración de Getnet, petición firmada, página de redirección, recepción y validación de respuestas, identificación de intentos y registro de respuestas del TPV |
| `openedx-zeitlabs-payments` | Checkout, compra, transacciones, factura, entrega del acceso y herramientas de operación; ajustes compartidos necesarios para cumplir este PRD |
| Open edX | Usuario, curso, organización e inscripción |
| Configuración del TPV | Credenciales y terminal, notificaciones habilitadas, medios contratados, reintentos internos deshabilitados y DCC deshabilitado |

El plugin revisado expone vistas de retorno y consulta de estado dependientes del usuario autenticado, pero no una interfaz completa de notificación del procesador. La implementación deberá incorporar la entrada de notificaciones al servidor y reutilizar el flujo compartido de procesamiento, con control de concurrencia.

En la versión revisada, la factura y la inscripción se crean dentro de una misma transacción atómica. Para conservar la factura cuando falle la inscripción será necesario ajustar ese flujo, además de conservar las tildes y la ñ en los datos enviados al procesador. Estos cambios forman parte del alcance y deben verificarse contra la versión concreta del plugin que se desplegará.

## Criterios de aceptación

| Caso | Resultado esperado |
| --- | --- |
| Pago aprobado | El usuario vuelve a una página de éxito, accede a la factura y recibe el acceso al curso |
| Rechazo inmediato | Se informa el rechazo, no se entrega acceso y se permite un intento nuevo con otro pedido |
| Cancelación definitiva | No se entrega acceso y se permite un intento nuevo únicamente tras conocer la cancelación definitiva |
| Abandono o cierre del navegador | No se interpreta como cancelación; si el resultado es desconocido, el intento permanece pendiente |
| Confirmación pendiente | Se informa al comprador y se bloquea otra compra del mismo producto |
| Aprobación tardía | Se completa la compra y se entrega el acceso sin intervención del comprador |
| Rechazo tardío | Se registra el rechazo y se muestra el resultado, sin entregar acceso |
| Cierre después de pagar | La notificación válida completa la compra sin retorno del navegador |
| Notificaciones duplicadas | Se conserva evidencia de las recepciones y solo se aplica una vez el efecto de negocio |
| Recarga o concurrencia | La recarga del retorno y las notificaciones concurrentes no duplican pago, factura ni inscripción |
| Firma inválida | Se conserva el mensaje depurado y el fallo de validación sin modificar ninguna compra |
| Pedido desconocido o datos incompatibles | Se registra el problema sin aprobar ni entregar una compra por esos datos |
| Integridad del importe | El monto y la moneda coinciden con la compra del servidor; manipular el navegador no permite alterarlos |
| TPV no disponible | No se entrega acceso ni se declara un pago aprobado; se permite reintentar si no hay un pago en curso y se mantiene pendiente si el resultado es incierto |
| Curso comprado previamente | Se bloquea otra compra; una inscripción gratuita no bloquea adquirir el acceso de pago |
| Pago aprobado e inscripción fallida | Se conservan pago y factura, se registra el fallo y se indica contactar a soporte |
| Recuperación de acceso | Un operador autorizado reintenta la entrega desde Django Admin sin otro cobro ni factura |
| Resolución manual de un pendiente | Soporte registra el resultado verificado en el TPV y su evidencia, operador, fecha y motivo |
| Medios de pago | Se valida el flujo con débito, crédito, tarjeta internacional y AMEX mediante los casos disponibles para el comercio de pruebas |
| Caracteres especiales | Los nombres de curso y usuario conservan tildes y ñ en los datos enviados y mostrados |
| Histórico | Cambiar después el precio, nombre u organización del curso no altera los datos de la compra registrada |
| Moneda | Los cobros se realizan en EUR y el terminal no ofrece DCC en esta versión |
| Configuración de reintentos | El TPV no ofrece reintentos internos; un nuevo intento en Open edX recibe otro pedido |

## Validación y despliegue

Se probarán firma y verificación, correlación de pedidos, importes y moneda, conservación de Unicode, persistencia de respuestas y transiciones de negocio. Las pruebas de integración cubrirán notificaciones sin sesión de usuario, duplicados y concurrencia, bloqueos de recompra, resolución por soporte y recuperación del acceso.

Antes de producción se validará el flujo completo en el entorno de pruebas del TPV, incluyendo resultados de aprobación y rechazo, retorno, llegada de notificaciones y medios de pago requeridos. Se confirmará con Getnet que las capacidades contratadas y la configuración del comercio cubren esos medios.

La configuración de despliegue incluirá credenciales protegidas, selección de entorno, URLs accesibles por el TPV, habilitación de notificaciones y desactivación de DCC y reintentos internos. Se verificará la versión compatible de `openedx-zeitlabs-payments` y sus cambios necesarios.

## Estimación preliminar

| Tarea original | Horas base |
| --- | ---: |
| Desarrollo del procesador y ajuste de caracteres especiales | 9 |
| Pruebas del procesador y entorno Redsys | 3 |
| Configuración y despliegue | 2 |
| Total original | 14 |

Las 14 horas son una referencia preliminar, revisable con el diseño técnico. La estimación final deberá incluir la tabla de respuestas y su auditoría, el histórico, la resolución desde Django Admin, el procesamiento independiente del navegador, el control de concurrencia y los ajustes del plugin para conservar factura y recuperar la inscripción.

## Referencias técnicas

- Vocabulario del dominio: [GLOSSARY.md](../GLOSSARY.md).
- Manual proporcionado por Getnet: `TPV-Virtual Manual Integración - Redirección V4.0.pdf`, versión 4.0, fecha 20/03/2025, referencia RS.TE.CEL.MAN.0039. Secciones relevantes: envío y firma, páginas 9–13; notificación, página 14; retorno, página 15; parámetros y reintentos, páginas 32–34; alternativa SHA-256, páginas 43–44.
- El manual recomienda `HMAC_SHA512_V1` y describe UTF-8. El detalle de parámetros y códigos se completará con el documento complementario `TPV-Virtual Parámetros Entrada-Salida.xlsx`, referenciado por el manual, antes de implementar sus validaciones.
- Plugin revisado en el commit [`f1669db7020951f810b9d9a3b3b996cfaf12fd36`](https://github.com/zeit-labs/openedx-zeitlabs-payments/tree/f1669db7020951f810b9d9a3b3b996cfaf12fd36): [contrato del procesador](https://github.com/zeit-labs/openedx-zeitlabs-payments/blob/f1669db7020951f810b9d9a3b3b996cfaf12fd36/docs/how-tos/build-a-payment-processor.rst), [procesamiento y factura](https://github.com/zeit-labs/openedx-zeitlabs-payments/blob/f1669db7020951f810b9d9a3b3b996cfaf12fd36/zeitlabs_payments/providers/base.py#L579-L759), [vistas de estado](https://github.com/zeit-labs/openedx-zeitlabs-payments/blob/f1669db7020951f810b9d9a3b3b996cfaf12fd36/zeitlabs_payments/providers/mixins.py#L127), [normalización de textos](https://github.com/zeit-labs/openedx-zeitlabs-payments/blob/f1669db7020951f810b9d9a3b3b996cfaf12fd36/zeitlabs_payments/helpers.py#L107-L216).
