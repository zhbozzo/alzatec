# Requerimientos · Agente de agenda de camiones

**Para:** Gerencia Alzatec S.A.
**Estado:** borrador previo a la reunión con Andrea y Patricio Farías. Los puntos marcados **[validar]** se completan con lo que salga de esa reunión.

## 1. Contexto y objetivo

La casilla `asistentetecnico@` envía unas **25–30 cotizaciones diarias**. Por esa misma casilla llegan todas las **solicitudes de despacho y de recepción** de equipos: las mandan los clientes, muchas veces en el mismo hilo de la cotización, o los vendedores, con copia a la casilla. A la bodega entran unos **10 camiones al día**, y esa agenda la lleva Patricio Farías en un Excel.

**Objetivo:** que un agente separe automáticamente las cotizaciones de las solicitudes de despacho y recepción, **llene el Excel de agenda** y **marque una alerta cuando el día pedido esté copado**. Todo esto sin interferir con el trabajo de `asistentetecnico@` ni con MADA.

## 2. Alcance

**Incluye**
- Lectura de una copia de los correos que llegan a `asistentetecnico@`, incluidas las copias (CC).
- Clasificación de cada correo en cotización, despacho, recepción u otro, y extracción de sus datos.
- Escritura de las solicitudes en el Excel de agenda, revisando el cupo.
- Alertas de día copado, de solicitudes urgentes y de casos a revisar.

**No incluye**
- Enviar o responder correos desde `asistentetecnico@`.
- Registrar o modificar datos en MADA.
- El trabajo de cotizaciones y de proyectistas.

## 3. Usuarios

| Usuario | Uso |
|---|---|
| Patricio Farías | Usa el Excel igual que hoy y confirma las filas que escribe el agente. Recibe las alertas. |
| Andrea (`asistentetecnico@`) | Define los tipos de correo. No cambia su forma de trabajar. Recibe las alertas de día copado **[validar]**. |
| Gerencia | Autoriza los accesos y ve los resultados. |

## 4. Requerimientos funcionales

Prioridad: **I** = imprescindible, **M** = importante, **D** = deseable.

### A. Lectura sin interferir

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-01 | Recibir una copia de cada correo que llega a `asistentetecnico@`, incluidas las copias (CC), mediante un reenvío a una casilla del agente. | I |
| RF-02 | No modificar nada en la casilla `asistentetecnico@`: no marcar como leído, no mover, no borrar y no responder. | I |
| RF-03 | Agrupar los correos por hilo y evitar duplicados cuando el mismo pedido llega en varios correos. | I |

### B. Clasificación y extracción

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-04 | Clasificar cada correo como **cotización**, **solicitud de despacho**, **solicitud de recepción** u **otro**, según los criterios que defina Andrea **[validar criterios]**. | I |
| RF-05 | Reconocer los cambios de fecha y las cancelaciones de solicitudes que ya están en el Excel. | M |
| RF-06 | Reconocer los viajes del camión de Alzatec (faltantes a obra, material galvanizado) **[validar si van en el mismo Excel]**. | M |
| RF-07 | Extraer los datos que piden las columnas del Excel **[validar columnas]**: fecha, hora, cliente, obra, N° de cotización, contacto, transporte y equipos. | I |
| RF-08 | Convertir las fechas relativas ("hoy", "mañana", "el jueves") en una fecha real, en horario de Chile y con días hábiles y feriados. | I |

### C. Escritura en el Excel

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-09 | Escribir cada despacho o recepción como una fila nueva en el Excel de agenda, con el formato actual. | I |
| RF-10 | Agregar una columna **Estado**: POR CONFIRMAR, CONFIRMADO, SIN CUPO, URGENTE, REVISAR o CANCELADO. El agente nunca escribe CONFIRMADO; eso lo hace Patricio Farías. | I |
| RF-11 | Antes de escribir, **revisar el cupo del día** contando los **camiones** de ese día (todas las filas, incluidas las escritas a mano) contra la capacidad definida. **No considera inventario**, que sigue en MADA **[validar regla de cupo]**. | I |
| RF-12 | Agregar una columna **Origen** con el asunto, la fecha y el remitente del correo. | M |
| RF-13 | Revisar los encabezados del Excel antes de escribir. Si cambió el formato, no escribir y avisar. | I |
| RF-14 | Actualizar la fila existente cuando llega un cambio de fecha o una cancelación. | M |

### D. Alertas

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-15 | **Día copado:** marcar la fila como SIN CUPO, indicar el próximo día con cupo y avisar a Patricio Farías y a Andrea **[validar destinatarios y qué hacer con la solicitud]**. | I |
| RF-16 | **Urgente:** marcar y avisar cuando la solicitud tiene menos de 2 días de anticipación **[validar regla]**. | I |
| RF-17 | **Revisar:** marcar y avisar cuando el agente no está seguro del tipo o de la fecha. | I |
| RF-18 | Enviar un resumen diario de lo agendado para mañana y pasado **[validar hora]**. | D |

### E. Medición

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-19 | Registrar cada correo procesado, cómo se clasificó y qué escribió el agente, para medir la precisión. | I |

## 5. Requerimientos no funcionales

- **No interferencia:** el trabajo en `asistentetecnico@` y en MADA sigue exactamente igual.
- **El Excel se sigue usando igual:** mismo formato, se puede escribir a mano y se puede imprimir.
- **Escritura segura:** el agente puede escribir aunque el Excel esté abierto. Para eso tiene que vivir en **OneDrive para empresas o SharePoint** (Microsoft 365), como Tabla de Excel. Un OneDrive personal no sirve **[validar dónde vive hoy]**.
- **Rapidez:** la fila aparece menos de 5 minutos después de que llega el correo.
- **Sin pérdida:** si el agente falla, los correos se acumulan en su casilla y se procesan cuando vuelve.
- **Seguridad:** las credenciales se guardan cifradas, el agente tiene el mínimo acceso necesario y queda registro de lo que escribió.

## 6. Lo que se necesita de Alzatec

| Qué | Para qué | Cuándo |
|---|---|---|
| Andrea: criterios para cada tipo, más 5–10 correos reales de cada uno | Enseñarle al agente a clasificar | Fase 0 |
| Patricio Farías: una copia del Excel y la regla de cupo | Saber qué columnas llenar y cuándo un día está copado | Fase 0 |
| Los correos de 1–2 semanas pasadas, más el Excel de esas mismas semanas | Medir al agente contra lo que pasó de verdad | Fase 0 |
| Acceso al cPanel de HostingPlus, o alguien que lo tenga | Crear `agente@` y el reenvío con copia | Fase 1 |
| Cuenta Microsoft 365 de empresa, o 1 licencia Business Basic, para alojar el Excel | Que el agente pueda escribir en el Excel | Fase 1 |
| Cuenta de API del modelo de IA elegido, y n8n (VPS o n8n Cloud), a nombre de Alzatec | Que el agente funcione | Fase 1 |

## 7. Fases y criterios de aceptación

| Fase | Entregable | Se da por cumplida cuando… |
|---|---|---|
| 0 · Levantamiento | Tipos, columnas y regla de cupo definidos, y un set de prueba | Gerencia, Andrea y Patricio Farías aprueban este documento. |
| 1 · Versión 1 en modo sombra | Solo clasificar y anotar en una copia del Excel, marcando SIN CUPO, URGENTE o REVISAR | Sobre semanas reales, detecta **≥ 95%** de las solicitudes del Excel real, acierta tipo y fecha en **≥ 90%**, y las alertas de día copado son correctas **[validar metas]**. |
| 2 · Versión 1 en vivo | Lo mismo sobre el Excel real (la alerta es el color en el Excel) | Dos semanas de operación sin solicitudes perdidas. |
| 3 · Versión 2 | Alertas por correo, cambios de fecha y cancelaciones automáticas, camión de Alzatec | Se definen al cerrar la fase 2. |
| 4 · Extensiones | Lectura de MADA, WhatsApp, indicadores | Se definen con gerencia. |

## 8. Supuestos y pendientes

- Todas las solicitudes se canalizan por `asistentetecnico@`, incluidas las que reenvían o copian los vendedores ✓.
- La agenda de camiones es un Excel que lleva Patricio Farías ✓. Falta ver dónde vive y cómo está armado **[por ver en la reunión]**.
- El volumen de 25–30 cotizaciones diarias y de unos 10 camiones al día está confirmado ✓.
- MADA se usa para cotizaciones, pedidos, devoluciones e inventario, y el proyecto no lo modifica ✓.
