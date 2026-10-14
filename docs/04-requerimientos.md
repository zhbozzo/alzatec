# Requerimientos · Agente de agenda de camiones

**Para:** Gerencia Alzatec S.A.
**Estado:** borrador previo a la reunión con Patricio Farías. Los puntos marcados **[validar]** se completan con lo que salga de esa reunión.

## 1. Contexto y objetivo

La casilla `asistentetecnico@` envía unas **25–30 cotizaciones diarias**. Los clientes responden en esos mismos hilos para coordinar **retiros y devoluciones de equipos**, y a la bodega entran unos **10 camiones al día**. Hoy esas solicitudes se detectan a mano entre todos los correos y se traspasan a la agenda de camiones que lleva Patricio Farías.

**Objetivo:** que un agente detecte automáticamente esas solicitudes y alimente la agenda de camiones, **sin interferir con el trabajo de la casilla `asistentetecnico@` ni con MADA**.

## 2. Alcance

**Incluye**
- Lectura de una copia de los correos que llegan a `asistentetecnico@`.
- Clasificación de las solicitudes y extracción de sus datos.
- Agenda digital de camiones para Patricio Farías, con confirmación de cada solicitud.
- Avisos de las solicitudes urgentes y un resumen diario.

**No incluye**
- Enviar o responder correos desde `asistentetecnico@`.
- Registrar o modificar datos en MADA.
- El trabajo de cotizaciones y de proyectistas.
- Cambiar el proveedor de correo.

## 3. Usuarios

| Usuario | Uso |
|---|---|
| Patricio Farías | Usuario principal. Confirma, corrige o descarta las propuestas, y administra la agenda. |
| Andrea (`asistentetecnico@`) | No cambia su forma de trabajar. Puede consultar la agenda **[validar]**. |
| Bodega / portería | Ve la agenda del día **[validar]**. |
| Gerencia | Ve los indicadores. |

## 4. Requerimientos funcionales

Prioridad: **I** = imprescindible, **M** = importante, **D** = deseable.

### A. Lectura sin interferir

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-01 | Recibir una copia de cada correo que llega a `asistentetecnico@`, mediante un reenvío con copia a una casilla del agente. | I |
| RF-02 | No modificar nada en la casilla `asistentetecnico@`: no marcar como leído, no mover, no borrar y no responder. | I |
| RF-03 | Agrupar los correos por hilo, para que las respuestas actualicen la misma solicitud. | I |

### B. Clasificación y extracción

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-04 | Clasificar cada correo en uno de estos tipos **[validar la lista]**: retiro en bodega; devolución en bodega; camión de Alzatec (despacho a obra, retiro en obra o retiro de galvanizado); reprogramación o cancelación; cotización sin camión; otro. | I |
| RF-05 | Extraer los datos de la solicitud: fecha, hora o bloque, cliente, obra, N° de cotización, contacto, patente y chofer, y equipos mencionados. | I |
| RF-06 | Convertir las fechas relativas ("hoy", "mañana", "el jueves") en una fecha real, en horario de Chile y considerando días hábiles y feriados. | I |
| RF-07 | Cuando haya dudas, marcar la solicitud como "revisar". Ningún correo con posible solicitud se descarta sin que una persona lo vea. | I |

### C. Agenda

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-08 | Crear cada solicitud como evento "por confirmar", con el texto original y un enlace al correo. | I |
| RF-09 | Que una reprogramación o cancelación actualice el evento que ya existe. | I |
| RF-10 | Marcar como **urgente** toda solicitud con menos de 2 días de anticipación **[validar la regla]**. | I |
| RF-11 | Que Patricio Farías pueda confirmar, corregir o descartar cada propuesta con 1 clic. | I |
| RF-12 | Vista del día y de la semana, con bloques horarios y capacidad por bloque **[validar bloques y capacidad]**. | I |
| RF-13 | Carga manual de las solicitudes que llegan por teléfono o WhatsApp. | M |
| RF-14 | Hoja del día imprimible. | M |
| RF-15 | Agenda o filtro separado para el camión de Alzatec **[validar]**. | M |
| RF-16 | Registrar si el cliente llegó o no llegó. | D |

### D. Avisos

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-17 | Aviso inmediato a Patricio Farías cuando llegue una solicitud para el mismo día. | I |
| RF-18 | Resumen diario con lo de mañana y pasado, a la hora que se defina **[validar hora]**. | M |
| RF-19 | Confirmación y recordatorio al cliente desde una casilla de agenda (no desde `asistentetecnico@`), con aprobación previa de Patricio Farías. | D |

### E. Medición

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-20 | Registrar cada propuesta del agente y qué se hizo con ella (confirmada, corregida o descartada), para medir la precisión. | I |
| RF-21 | Tablero con camiones por día, urgentes y clientes que no llegaron. | D |

### F. Extensiones

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-22 | Leer la cotización en MADA para mostrar qué equipos hay que preparar, solo si INQSOL lo permite. | D |
| RF-23 | Leer otras casillas, como `pfarias@` o las de los comerciales. | D |

## 5. Requerimientos no funcionales

- **No interferencia:** el trabajo en `asistentetecnico@` y en MADA sigue exactamente igual.
- **Rapidez:** la solicitud aparece en la agenda menos de 5 minutos después de que llega el correo.
- **Sin pérdida:** si el agente falla, los correos se acumulan en su casilla y se procesan cuando vuelve.
- **Trazabilidad:** queda registro de quién confirmó o modificó cada evento.
- **Seguridad:** acceso con usuario personal, contraseñas cifradas y respaldo diario.
- **Uso:** funciona en el celular, en español y en horario de Chile.

## 6. Lo que se necesita de Alzatec

| Qué | Para qué | Cuándo |
|---|---|---|
| Patricio Farías como contraparte, con 1 hora a la semana | Validar tipos, reglas y avances | Desde el inicio |
| Acceso al cPanel de HostingPlus, o alguien que lo tenga | Crear `agente@` y el reenvío con copia | Fase 1 |
| La agenda real de 1–2 semanas, más los correos de `asistentetecnico@` de esas mismas semanas | Medir al agente contra la realidad antes de que opere | Fase 0 |
| Las reglas de la agenda: bloques, capacidad, anticipación y horarios | Configurar la agenda | Fase 0 |

## 7. Fases y criterios de aceptación

| Fase | Entregable | Se da por cumplida cuando… |
|---|---|---|
| 0 · Levantamiento | Requerimientos validados y set de prueba | Gerencia y Patricio Farías aprueban este documento. |
| 1 · Modo sombra | El agente propone solicitudes, sin reemplazar la agenda actual | Sobre semanas reales, detecta **≥ 95%** de las solicitudes de la agenda de Patricio y acierta tipo y fecha en **≥ 90%** **[validar metas]**. |
| 2 · Agenda digital | Agenda con confirmación, hoja imprimible y avisos | Dos semanas de operación sin solicitudes perdidas. |
| 3 · Camión Alzatec y clientes | Agenda del camión propio, reprogramaciones y confirmación al cliente | Se definen al cerrar la fase 2. |
| 4 · Extensiones | Lectura de MADA, otras casillas, WhatsApp | Se definen con gerencia. |

## 8. Supuestos y pendientes

- El volumen de 25–30 cotizaciones diarias y de unos 10 camiones al día está confirmado por gerencia.
- MADA se usa para cotizaciones, pedidos, devoluciones e inventario, y el proyecto no lo modifica.
- La mayoría de los camiones son de los clientes, que retiran o devuelven en la bodega de Alzatec **[validar]**.
- El formato actual de la agenda de Patricio Farías **[por ver en la reunión]**.
