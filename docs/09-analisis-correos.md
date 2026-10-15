# 09 · Análisis de la base de correos

> Basado en los `.pst` entregados por Informática. Este documento solo contiene **datos agregados y patrones**: los correos reales están en `datos/`, que no se sube al repositorio.

## 1. Qué se recibió

| Casilla | Carpetas | Período | Correos | Promedio por día hábil |
|---|---|---|---|---|
| Andrea | Bandeja de entrada | 11-ago al 14-oct-2026 | 1.664 | ~36 |
| Javier (`devoluciones@`) | Bandeja de entrada | septiembre 2026 | 605 | ~29 |
| Javier (`devoluciones@`) | Elementos enviados | septiembre 2026 | 626 | ~30 |

- En el buzón de Andrea aparecen **341 números de cotización distintos** en los asuntos, y 53 menciones con sufijo `-0X` (versiones con observaciones).
- El **47%** de los correos de Andrea son internos (`@alzatec.com`): ejecutivas comerciales, departamento técnico, cobranza y bodega.

## 2. Hallazgos críticos para la integración

### 2.1 La dirección real de Andrea es `asistentetecnico@` ⚠️

| Destinatario del correo | Correos |
|---|---|
| Solo `asistentetecnico@` | **777 (47%)** |
| `asistentetecnico@` y `departamentotecnico@` | 871 (52%) |
| Otros | 16 |

El reenvío configurado hoy (`departamentotecnico@ → agente@`) **no captura casi la mitad** de los correos de Andrea.
**Acción:** ✓ Víctor agregó el reenvío `asistentetecnico@ → agente@`. El de `departamentotecnico@` **se mantiene**, por decisión del proyecto, por si acaso. Los correos que llegan a ambas direcciones se deduplican por `Message-ID`.

### 2.2 Las recepciones acordadas las escribe Javier, en correos que él envía ⚠️

- En septiembre, Javier **envió ~221 confirmaciones** de devolución ("agendo su hora de devolución…" y "confirmar devolución para el día de mañana…"). Son unas **10 por día hábil**.
- El reenvío solo copia lo que **entra**. Esas confirmaciones **no llegan a `agente@`**, salvo cuando el cliente responde citándolas.

**Acción, eligiendo una opción:**
- **(Recomendada)** Una regla en el Outlook de Javier: *"a los mensajes que envío, agregar CC a agente@alzatec.com"*.
- Leer por IMAP la carpeta de enviados de `devoluciones@`. Solo funciona si su Outlook guarda los enviados en el servidor (IMAP); a confirmar con Informática.

### 2.3 Un despacho genera varios correos

Una solicitud pasa por varios correos:
1. el cliente acepta;
2. pide fecha;
3. Alzatec propone una fecha;
4. el cliente confirma.

Por eso el mismo despacho puede aparecer primero en **pendientes** y luego en **acordados**. El reenvío debe llevar en el asunto el **N° de cotización y la obra**, para poder relacionarlos.

## 3. Distribución estimada por categoría

Muestra aleatoria clasificada a mano: 60 correos de Andrea y 40 de la bandeja de Javier. Son **aproximaciones**, con un margen de ±10 puntos.

| Categoría | Andrea | Javier (entrada) |
|---|---|---|
| Despacho acordado | ~10% (~3–4 por día) | — |
| Despacho pendiente | ~20% (~7 por día) | — |
| Recepción acordada | ~2% | ~10% (~3 por día), más ~10 por día en sus enviados |
| Recepción pendiente | — | ~50% (~14 por día) |
| No aplica | ~67% (~24 por día) | ~40% (~12 por día) |

## 4. Señales de cada categoría (patrones reales)

### Despacho acordado

Hay **fecha (y normalmente hora)** asignada o confirmada para que el cliente retire, o para despachar.

| Quién lo escribe | Señal |
|---|---|
| Ejecutivas comerciales | Plantilla: *"informo que Cotización Alzatec N°…, el equipo se encuentra disponible para retirar el día DD-MM a las HH:MM. Camión X tn… Es necesario confirmar su hora…"* (42 casos) |
| Ejecutivas comerciales | *"se agenda retiro para el día…"*, *"Favor enviar camión ¾ mañana viernes a las 11:00 para cargar cotización…"*, *"Miércoles 8:30 am, camión de 5.000"* |
| Cliente | *"confirmo fecha de retiro para mañana jueves…"* + datos del chofer y patente; *"Aprobado retiro"* en respuesta a una coordinación |

**[validar con Andrea]** La plantilla de las ejecutivas pide al cliente "confirmar su hora". ¿Ya cuenta como **acordado**, o sigue **pendiente** hasta que el cliente responda?

### Despacho pendiente

Hay solicitud o aceptación, pero **falta algo**:

| Qué falta | Señal |
|---|---|
| Fecha u hora | *"Se acepta presupuesto, favor indicar fecha para coordinar retiro"*, *"¿A qué hora enviamos el camión mañana?"*, *"Aprobado cotización, enviaremos camión a retiro"* |
| Confirmación de Alzatec | El cliente propone: *"¿es factible ir hoy a las 14:00 a retirar?"*, *"me ayuda con el retiro hoy a la tarde"* |
| Orden de compra | *"Enviaremos a generar la OC para coordinar el retiro"*, *"favor adjuntar la OC respectiva"* |
| Condición comercial / cobranza | *"no se le puede despachar hasta que regularicen la deuda"*, *"¿aún estamos bloqueados en Alzatec?"*, facturas rechazadas (21 casos) |
| Cotización final | Cotización `-01` en revisión |
| Stock | *"Estamos sin stock de… a penas reciba…"* |

### Recepción acordada

| Quién lo escribe | Señal |
|---|---|
| Javier (enviado) | *"según lo conversado, agendo su hora de devolución: para el viernes 09-10, 10:00 hrs…"*; *"confirmar devolución para el día de mañana. Recordar traer guía física…"*; *"se asigna sobre cupo para el…"* |
| Cliente | *"Sí, confirmado"*, *"se confirma la devolución de mañana, camión 2 tn"*, *"Le confirmo devolución para mañana martes"* |

### Recepción pendiente

- *"Solicito hora para la devolución…"*, *"Favor agendarnos para el día 29-09"*, *"favor enviar disponibilidad de horas"*.
- Cambios y anulaciones: *"favor cambiar hora… para el viernes"*, *"favor anular hora de devolución"*.

### No aplica (no se reenvía)

- Solicitudes y envío de cotizaciones, consultas técnicas, modulaciones, planos y visitas.
- Cobranza: estados de pago (EEPP), facturas, HES.
- Movimientos **ya realizados**: `RECEPCION #### - GUIA #### - …`, notas de salida, fotos de despacho.
- Ruido:
  - rebotes "Mail delivery failed" (~41);
  - "Recepción Marca Asistencia" (~38 en `devoluciones@`);
  - phishing o spam;
  - reportes automáticos (`MovimientosPorBodegaAgrupado….xlsx`);
  - auto-respuestas.

## 5. Archivo de validación

Archivo: `datos/validacion/validacion-clasificador.xlsx`. No está en el repositorio porque contiene correos reales.

**Contenido**
- **200 correos reales:** 100 de Andrea; de Javier, 65 recibidos y 35 enviados.
- La muestra se cargó a propósito hacia despachos y recepciones, para revisar bien los casos que importan. Por eso **no** refleja la proporción real; esa está en la sección 3.
- Cada correo trae la categoría propuesta, qué falta, la fecha del movimiento, el N° de cotización y el motivo. Además tiene columnas para que Andrea y Javier marquen si está bien y cuál es la categoría correcta.
- La hoja *Resumen* calcula sola el % de acierto por categoría a medida que se llena.

**Cómo se etiquetó**
1. Dos clasificadores independientes etiquetaron cada correo con la misma rúbrica. Coincidieron en 199 de 200; el caso restante lo decidió un juez.
2. Verificación adversarial:
   - un revisor escéptico por lote;
   - un crítico que comparó los 200 entre sí para detectar casos parecidos con etiquetas distintas;
   - dos jueces con distinta mirada (rúbrica literal y operativa) para cada objeción.
3. Se aplicaron solo los cambios en que los dos jueces coincidieron: **5 de categoría** y **4 de "qué falta"**.

**Etiquetas propuestas**

| Categoría | Andrea | Javier |
|---|---|---|
| Despacho acordado | 27 | 1 |
| Recepción acordada | 1 | 35 |
| Pendiente | 43 | 38 |
| No aplica | 29 | 26 |

**47 correos tienen una "duda de criterio".** Son casos que la rúbrica no resuelve sola y quedaron agrupados en 8 preguntas, que están en el mismo archivo:

1. Cuando Alzatec asigna día y hora (la plantilla de ejecutivas, *"Es necesario confirmar su hora"*), ¿ya es **acordado** o queda **pendiente** hasta que el cliente confirme? Es la duda más frecuente.
2. Si el cliente responde solo "gracias" u "ok" a esa hora, ¿cuenta como confirmación?
3. Si el cliente elige un cupo de la lista de horas de Javier, ¿ya está acordada, o falta el *"agendo su hora"*?
4. ¿Un despacho sin OC está acordado? Por ejemplo, "se libera el camión con el compromiso de enviar la OC", o clientes que trabajan con estado de pago mensual.
5. Las **anulaciones**, ¿van a pendientes o a otra casilla?
6. Los movimientos **en curso** (el camión ya llegó o va en camino) y la agenda consolidada del día, ¿se reenvían?
7. Un despacho **parcial** (una parte sin stock), ¿es acordado o pendiente?
8. Una aceptación de cotización sin pedir despacho, ¿va a pendientes?

**Hallazgo técnico.** En varias recepciones de Javier la fecha y la hora **no están en el texto**: vienen en una imagen o en una tabla pegada. El clasificador tiene que mirar también el hilo citado. Si eso no basta, se evalúa leer las imágenes en la etapa de prueba.

## 6. Próximos pasos

1. **Informática:**
   - ~~reenvío `asistentetecnico@ → agente@`~~ ✓;
   - regla CC en el Outlook de Javier (Víctor).
2. **Andrea y Javier:** revisar el archivo de validación y responder las 8 preguntas.
3. **Ajustar la rúbrica** con sus respuestas. Los 200 correos corregidos pasan a ser el **set de prueba**.
4. **Prompt y prueba offline:** medir aciertos contra ese set (meta ≥ 95% en despachos y recepciones) antes de conectar.
