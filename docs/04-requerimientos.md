# Requerimientos · Automatización de cotizaciones, despachos y devoluciones

**Para:** Gerencia Alzatec S.A.
**Estado:** borrador previo a la sesión de levantamiento. Los puntos marcados **[validar]** se completan con lo que se vea en la sesión.

## 1. Contexto y objetivo

El cargo que ocupaba Andrea concentraba la gestión del correo comercial: unas **25–30 cotizaciones enviadas al día**, sus respuestas, el agendamiento de despachos y devoluciones, y las modificaciones que piden los comerciales. Hoy no hay un ERP que registre ese flujo, por lo que depende de una persona.

El objetivo es que **la mayor parte de ese trabajo se haga de forma automática**, y que lo que requiera criterio llegue ordenado y resumido a la persona correcta, sin que se pierda ningún correo.

## 2. Alcance

**Incluye**
- Lectura, clasificación y derivación automática de los correos de la casilla comercial.
- Registro y seguimiento de cotizaciones.
- Agenda de despachos y devoluciones, con autoagendamiento para clientes.
- Panel web para el equipo.

**No incluye**
- Contabilidad, facturación del arriendo ni remuneraciones.
- Negociación de precios ni cálculo técnico de andamios. El sistema resume y deriva, pero no decide.
- Cambiar el proveedor de correo de la empresa.

## 3. Usuarios

| Usuario | Qué hace en el sistema |
|---|---|
| Gerencia | Ve tableros y aprueba reglas. |
| Comerciales | Reciben avisos de sus clientes, validan modificaciones y aprueban borradores. |
| Coordinación de despachos **[validar quién]** | Confirma fechas y ve el calendario. |
| Devoluciones | Recibe las solicitudes ya derivadas y agenda los retiros. |
| Asistente técnico **[validar rol]** | Recibe las consultas técnicas. |
| Cliente (externo) | Agenda su despacho o retiro desde un link. |

## 4. Requerimientos funcionales

Prioridad: **I** = imprescindible, **M** = importante, **D** = deseable.

### A. Recepción y clasificación de correos

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-01 | Leer una casilla única **[validar cuál]** en tiempo casi real. | I |
| RF-02 | Clasificar cada correo en: respuesta a cotización, solicitud de despacho, solicitud de devolución, confirmación o modificación de un comercial, u otro. | I |
| RF-03 | Extraer los datos clave: N° de cotización, cliente, RUT, obra, dirección, contacto en obra, fecha pedida, equipos, cantidades y OC. | I |
| RF-04 | Asociar cada correo a la cotización, obra y cliente que correspondan. | I |
| RF-05 | Enviar los casos dudosos a una cola de revisión. Ningún correo queda sin destino. | I |
| RF-06 | Enviar un resumen diario de lo pendiente al responsable. | M |

### B. Cotizaciones

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-07 | Registrar cada cotización enviada: número, cliente, obra, comercial, monto, fecha y PDF. | I |
| RF-08 | Mantener el estado de cada cotización: enviada, respondida, aceptada, rechazada, modificada o vencida. | I |
| RF-09 | Avisar al comercial cuando su cliente responde, con un resumen. | I |
| RF-10 | Guardar cada modificación como una nueva versión de la cotización. | M |
| RF-11 | Hacer seguimiento automático a las cotizaciones sin respuesta después de **[validar]** días. | M |
| RF-12 | Mostrar un tablero de cotizaciones enviadas, aceptadas y perdidas por comercial y por semana. | M |

### C. Despachos

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-13 | Llevar un calendario de despachos por sucursal con capacidad diaria **[validar capacidad]**. | I |
| RF-14 | Crear la solicitud de despacho con los datos obligatorios **[validar cuáles]**. | I |
| RF-15 | Enviar la confirmación al cliente y un recordatorio el día anterior, y avisar a bodega. | M |
| RF-16 | Ofrecer al cliente un link de autoagendamiento con las reglas de Alzatec (cotización aceptada, OC, etc.). | M |
| RF-17 | Emitir la guía de despacho electrónica al confirmar el despacho **[validar cómo se emite hoy]**. | D |

### D. Devoluciones

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-18 | Derivar automáticamente las solicitudes de devolución a `devoluciones@`, con los datos ya extraídos. | I |
| RF-19 | Registrar cada retiro: fecha, obra, equipos y estado. | M |
| RF-20 | Llevar el saldo de equipos por obra (despachado menos devuelto). | D |

### E. Respuestas y envíos

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-21 | Preparar borradores de respuesta que se aprueban con 1 clic. | I |
| RF-22 | Permitir activar el envío automático por categoría, una vez que esa categoría demuestre buena precisión. | M |

### F. Panel

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-23 | Login individual con permisos por rol. | I |
| RF-24 | Vistas de bandeja clasificada, cola de revisión, cotizaciones, calendario y ficha por obra. | I |
| RF-25 | Funcionar bien desde el celular. | M |

## 5. Requerimientos no funcionales

- **Correo actual:** el sistema usa las casillas de HostingPlus (IMAP y SMTP), sin cambiar de proveedor. Los envíos salen por el mismo servidor para no caer en spam.
- **Rapidez:** cada correo queda clasificado en menos de 5 minutos desde que llega.
- **Sin pérdida:** si el sistema falla, los correos siguen en la casilla y se procesan cuando vuelve.
- **Trazabilidad:** queda registro de quién aprobó o envió cada respuesta.
- **Seguridad:** las contraseñas se guardan cifradas, el acceso es por usuario y hay respaldo diario.
- **Idioma y zona horaria:** español, horario de Chile.

## 6. Lo que se necesita de Alzatec

| Qué | Para qué | Cuándo |
|---|---|---|
| Una **contraparte** con 1–2 horas a la semana | Resolver dudas y validar avances | Desde el inicio |
| **Export de 2–3 meses** de la casilla de Andrea, o acceso de solo lectura | Medir el volumen real y probar la clasificación con correos reales | Fase 0 |
| La casilla que se usará como entrada única, con acceso IMAP y SMTP | Conectar el sistema | Fase 1 |
| Plantilla de cotización, lista de precios y catálogo de equipos | Leer y generar cotizaciones | Fase 1 |
| Reglas del negocio: capacidad de despacho, días de seguimiento, requisitos para despachar | Configurar agenda y seguimientos | Fase 2 |
| Comunicar la casilla única a clientes y comerciales | Que todo entre por un solo lugar | Fase 2 |

## 7. Fases y criterios de aceptación

| Fase | Entregable | Se da por cumplida cuando… |
|---|---|---|
| 0 · Levantamiento | Requerimientos validados y volumen medido con el historial real | Gerencia aprueba este documento. |
| 1 · Modo sombra | Clasificación y extracción funcionando **sin enviar nada**, con un panel para revisar | La clasificación acierta en **≥ 90%** de una muestra de 200 correos reales **[validar meta]**. |
| 2 · Derivación y seguimiento | Derivación a devoluciones, avisos a comerciales, borradores y seguimiento de cotizaciones | Dos semanas de operación sin correos perdidos. |
| 3 · Agenda | Calendario de despachos y retiros, con link para clientes | Los despachos de una semana completa se agendan por el sistema. |
| 4 · Extensiones | Guía de despacho, saldo de equipos por obra, WhatsApp | Se definen al cerrar la fase 3. |

## 8. Supuestos y pendientes

- **No hay ERP** (respuesta de gerencia: "Mada", leído como "Nada"). **[validar cómo se emiten hoy guías y facturas]**
- El volumen de 25–30 cotizaciones diarias está confirmado. El volumen total de correos se mide con el historial.
- Se asume que el negocio es principalmente de **arriendo**. **[validar el mix arriendo/venta]**
- Los roles de cmontes, pfarias y pbriceno están **[por definir en la sesión]**.
