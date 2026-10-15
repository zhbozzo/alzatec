# Requerimientos · Clasificador de correos (etapa 1)

**Para:** Gerencia Alzatec S.A.
**Estado:** borrador después de la reunión de levantamiento. Lo marcado **[validar]** se completa con el análisis de la base de correos de los últimos meses.

## 1. Contexto y objetivo

A los correos de Andrea y de Javier llegan diariamente unas **25–35 cotizaciones**, mezcladas con solicitudes de despacho y de recepción de equipos. Hoy hay que leerlos todos para saber cuáles son despachos o recepciones ya acordados y cuáles tienen algo pendiente.

**Objetivo de la etapa 1:** un **clasificador automático** que separe esos correos y los envíe a tres casillas:

| Categoría | Casilla de destino |
|---|---|
| **Despacho acordado** | `despachosconfirmados@alzatec.com` |
| **Recepción acordada** | `retirosconfirmados@alzatec.com` **[validar nombre]** |
| **Pendiente**: despacho o recepción al que le falta algo | `pendientesdespachoyrecepcion@alzatec.com` |

Las cotizaciones y el resto de los correos **no se mueven**: siguen donde están.

## 2. Alcance

**Incluye**
- Recibir una copia de los correos que llegan a Andrea y a Javier en `agente@alzatec.com`, que funciona como **embudo**.
- Clasificar cada correo en una de las tres categorías, o en "no aplica".
- Reenviar cada despacho, recepción o pendiente a su casilla, con un resumen.

**No incluye (etapa 1)**
- Agenda, Excel o revisión de cupo de camiones. Eso queda para una etapa posterior.
- Responder correos a clientes.
- Modificar las casillas de Andrea o de Javier.
- Tocar MADA.

## 3. Definición de las categorías **[validar con la base de correos]**

| Categoría | Definición preliminar |
|---|---|
| **Despacho acordado** | Salen equipos de Alzatec y están acordadas las condiciones: cotización final aceptada, condición comercial, fecha y stock. El ~90% se hace con camión del cliente y el ~10% con camión de Alzatec. |
| **Recepción acordada** | Vuelven equipos a Alzatec, con la fecha acordada. |
| **Pendiente** | Hay una solicitud de despacho o recepción, pero **falta algo**: fecha, stock, condición comercial, o la **cotización final**. Por ejemplo, una cotización con observaciones que lleva sufijo `-01`, porque no se despacha hasta la versión final. |
| **No aplica** | Cotizaciones sin pedido de despacho ni recepción, consultas, proveedores, avisos automáticos. No se reenvían. |

**Reglas conocidas**
- Se puede agendar aunque la cotización no esté aprobada, pero **no se despacha** hasta tener la cotización final.
- Una cotización con observaciones conserva su número con un guion: `N°28484` pasa a `N°28484-01`.
- Asunto típico: `Re: Cotización Alzatec N°<número> - <CLIENTE> - <OBRA>`.

## 4. Requerimientos funcionales

Prioridad: **I** = imprescindible, **M** = importante, **D** = deseable.

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-01 | Recibir en `agente@` una copia de cada correo que llega a Andrea (`asistentetecnico@` y `departamentotecnico@`) y a Javier (`devoluciones@`), mediante reenvíos con copia en el hosting. | I |
| RF-01b | Recibir también una copia de los correos que **envía** Javier, porque ahí están la mayoría de las recepciones acordadas (regla CC en Outlook o lectura de enviados por IMAP). Ver [09-analisis-correos.md](09-analisis-correos.md). | I |
| RF-02 | No modificar nada en las casillas de origen. | I |
| RF-03 | Procesar cada correo **una sola vez**, aunque llegue a Andrea y a Javier a la vez (por `Message-ID`). | I |
| RF-04 | Clasificar cada correo como despacho acordado, recepción acordada, pendiente o no aplica. | I |
| RF-05 | Reenviar a la casilla de destino el **correo original completo** (con sus adjuntos), con un **resumen** al inicio: categoría, N° de cotización (con sufijo si lo tiene), cliente, obra, fecha si existe y, en los pendientes, **qué falta**. | I |
| RF-06 | Poner un prefijo en el asunto del reenvío, por ejemplo `[DESPACHO ACORDADO] Re: Cotización Alzatec N°…`, para filtrar fácil en Outlook. | M |
| RF-07 | Si el clasificador no está seguro y el correo podría ser un despacho o una recepción, mandarlo a **pendientes** con la nota "revisar". **Nunca** descartarlo en silencio. | I |
| RF-08 | Registrar cada correo procesado, con su categoría y lo que se hizo, para medir la precisión. | I |
| RF-09 | Avisar al mantenedor si algo falla. El correo no se pierde y se puede reprocesar. | I |

## 5. Requerimientos no funcionales

- **No interferencia:** Andrea y Javier siguen trabajando igual.
- **Rapidez:** el reenvío sale menos de 5 minutos después de que llega el correo.
- **Sin pérdida:** si el agente falla, los correos esperan en `agente@`.
- **Privacidad:** el contenido de los correos de clientes pasa por el proveedor de IA (con aprobación de gerencia). La base de correos de análisis **no se guarda en el repositorio**.
- **Seguridad:** credenciales cifradas y acceso mínimo.

## 6. Lo que se necesita de Alzatec

| Qué | Quién | Para qué |
|---|---|---|
| **Base de correos de los últimos meses** de Andrea y de Javier | Alzatec | Definir las categorías con datos reales y medir el clasificador antes de usarlo |
| Crear `agente@`, `despachosconfirmados@`, `retirosconfirmados@` y `pendientesdespachoyrecepcion@` | Víctor (hosting) | Embudo y destinos |
| Reenvíos con copia: `departamentotecnico@` → `agente@` y `devoluciones@` → `agente@` | Víctor (hosting) | Que el agente reciba los correos |
| Datos de conexión de `agente@` (IMAP y SMTP) | Víctor (hosting) | Leer y reenviar |
| Validar una muestra clasificada (50–100 correos) | Andrea | Confirmar que el criterio es el correcto |
| Cuenta de IA y n8n a nombre de Alzatec | Gerencia | Que el agente funcione |

## 7. Fases y criterios de aceptación

| Fase | Entregable | Se da por cumplida cuando… |
|---|---|---|
| 0 · Análisis | Análisis de la base de correos: volumen por tipo, patrones y definiciones finales | Andrea valida las definiciones y una muestra clasificada. |
| 1 · Prueba offline | Clasificador probado con correos reales, sin conectar nada | Acierta en **≥ 95%** de los despachos y recepciones **[validar meta]** y no deja ninguno sin clasificar. |
| 2 · Modo sombra | Clasificador conectado; reenvía a una casilla de prueba durante 1–2 semanas | Andrea revisa y confirma que coincide con su criterio. |
| 3 · En vivo | Reenvía a las tres casillas reales | Dos semanas sin correos perdidos. |
| Etapa 2 (futuro) | Agenda y Excel de Pato, cupo de camiones | Se define al cerrar la etapa 1. |

## 8. Supuestos y pendientes

- Las casillas de entrada son `departamentotecnico@alzatec.com` y `devoluciones@alzatec.com`, según Informática (Víctor Sánchez). **[confirmar cuál usa Andrea y cuál Javier]**
- El nombre final de la casilla de recepciones (`retirosconfirmados@`), y si conviene usar la `devoluciones@` que ya existe **[validar]**.
- Quién lee cada casilla de destino **[validar]**.
- La frase incompleta de la reunión: "cuando un vendedor coordina un despacho en la misma llamada debe…" **[completar]**.
