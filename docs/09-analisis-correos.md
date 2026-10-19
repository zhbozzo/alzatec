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

### 2.3 Andrea también envía confirmaciones ⚠️

En su bandeja hay 19 correos de clientes que responden citando la plantilla *"el equipo se encuentra disponible para retirar el día…"* **escrita por Andrea** (16 hilos). Como con Javier, lo que ella envía no pasa por el reenvío.
**Acción:** ✓ Víctor configuró la regla CC también en el Outlook de Andrea. Se pidió el respaldo de sus Elementos enviados para medir el volumen.

### 2.4 Un despacho genera varios correos

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
   - *Decisión provisoria (17-oct, tras revisar los primeros 159 correos reales):* queda **pendiente** hasta el *"agendo su hora"* de Javier, que es el que va a retiros confirmados. Así no se duplica el reenvío y nada se pierde. Confirmar con Javier.
4. ¿Un despacho sin OC está acordado? Por ejemplo, "se libera el camión con el compromiso de enviar la OC", o clientes que trabajan con estado de pago mensual.
5. Las **anulaciones**, ¿van a pendientes o a otra casilla?
6. Los movimientos **en curso** (el camión ya llegó o va en camino) y la agenda consolidada del día, ¿se reenvían?
7. Un despacho **parcial** (una parte sin stock), ¿es acordado o pendiente?
8. Una aceptación de cotización sin pedir despacho, ¿va a pendientes?

**Hallazgo técnico.** En varias recepciones de Javier la fecha y la hora **no están en el texto**: vienen en una imagen o en una tabla pegada. El clasificador tiene que mirar también el hilo citado. Si eso no basta, se evalúa leer las imágenes en la etapa de prueba.

## 6. Comparación de modelos (preliminar)

Haiku y Sonnet clasificaron por separado los mismos 200 correos, sin ver las etiquetas y con acceso a las imágenes y PDF de cada correo. El resultado se comparó con las etiquetas verificadas de la sección 5.

**Es preliminar por tres razones:**
- las etiquetas aún no las valida Andrea;
- se hizo una sola pasada por modelo;
- la prueba se corrió con subagentes de Claude Code, no con la llamada a la API que se usará en producción.

**Tipos de error**
- **Graves:** un despacho o devolución que terminaría en "no aplica" (se pierde), o algo no acordado que terminaría en una casilla de confirmados.
- **Leves:** algo acordado que termina en pendientes, o ruido en pendientes.

| | Haiku | Sonnet |
|---|---|---|
| Coincide con la etiqueta | 177/200 (88,5%) | **190/200 (95%)** |
| Errores graves | 4 (3 se perderían, 1 falso confirmado) | **1** |
| Errores leves | 19 | 9 |
| Errores en casos sin duda de criterio | 6 | **1** |

**Detalle**
- **Sonnet:**
  - Los 9 errores leves son todos casos con duda de criterio. Por ejemplo, un cliente que elige un cupo de la lista de Javier: Sonnet lo deja en pendientes. Se resuelven con las respuestas de Andrea a las 8 preguntas.
  - Su único error grave es discutible: un cliente "reaccionó" (👍) a la hora que Javier ya había agendado, y Sonnet lo reenvió como recepción acordada. Como la recepción ya estaba acordada, el efecto sería un reenvío duplicado, no un error de agenda.
- **Haiku:** perdería 3 correos con movimiento:
  - una recotización con el cliente esperando retirar;
  - un saldo de despacho pendiente;
  - un camión que ya estaba en la planta.
- **Imágenes:** los dos modelos leyeron bien el pantallazo de agenda que pega Javier y sacaron de ahí la fecha y la hora. La diferencia entre ellos está en **interpretar el hilo**, no en leer imágenes.

**Conclusión preliminar:** Sonnet es el modelo que cumple la meta de cero errores graves. Haiku no la cumple sin reglas adicionales. Con unos 3.000 correos al mes, la diferencia es de unos US$50 contra unos US$3 al mes (tabla de costos en [05](05-implementacion.md)).

## 7. Próximos pasos

1. **Informática:**
   - ~~reenvío `asistentetecnico@ → agente@`~~ ✓;
   - ~~reglas CC en el Outlook de Andrea y de Javier~~ ✓;
   - respaldo de los Elementos enviados de Andrea (pendiente).
2. **Andrea y Javier:** revisar el archivo de validación y responder las 8 preguntas.
3. **Ajustar la rúbrica** con sus respuestas. Los 200 correos corregidos pasan a ser el **set de prueba**.
4. **Prompt y prueba offline:** medir aciertos contra ese set (meta ≥ 95% en despachos y recepciones) antes de conectar.


## 8. Primera revisión en producción (17-oct-2026)

- GPT-6.1 Sol clasificó los 159 correos reales del jueves 15 y el viernes 16 (sin contar los rebotes). Cuatro revisores Opus los revisaron uno por uno con la misma rúbrica: hubo **6 desacuerdos**, **1 grave** y 5 leves. Costo: US$0,75 por 234 correos, unos US$0,003 por correo.
- **Grave (corregido):** un aviso interno de *"saldo pendiente"* (OT de MADA con equipos que faltan por entregar) quedó como no aplica. La rúbrica ahora lo trata explícitamente como despacho pendiente (falta stock).
- **Porcentaje:** antes de corregir, GPT coincidió con la revisión en 153 de 159 correos (**96,2%**; graves: 1 de 159). Después de corregir la rúbrica coincide en 157 de 159 (**98,7%**, sin graves). Los 2 que quedan son discutibles y van a pendientes, el lado seguro. Ojo: se midió sobre los mismos correos que sirvieron para corregir, los revisores no vieron las imágenes y la referencia es Opus, no Andrea ni Javier.
- **Leves:** el cliente elige una hora de la lista de Javier (ahora queda pendiente, ver la pregunta 3), y una reacción "me gusta" de Outlook que duplicaba un reenvío (ahora es una regla fija). Otros dos casos se dejaron como estaban porque son discutibles.
- **Falla de entrega (corregida):** el filtro de cPanel rechazaba los reenvíos porque el original iba adjunto como `correo-original.eml`. Ahora va sin nombre de archivo, y si un reenvío rebota, el clasificador avisa por correo.

## 9. GPT-6.1 Sol en los 200 correos de validación (18-oct-2026)

GPT-6.1 Sol no se había medido con la muestra histórica. Se corrió dentro de Google Cloud (el job `clasificador-eval`, que tiene la API key y los 200 correos), con el mismo código de producción:

| Corrida | Rúbrica | Coincide | Graves | Comentario |
|---|---|---|---|---|
| 1 | la del 17-oct | 184/200 (92%) | 4 | 8 de los 16 desacuerdos son el criterio nuevo (hora elegida de la lista de Javier = pendiente); las etiquetas antiguas decían acordado |
| 2 | + parcial, OC, "favor agendar" | 194/200 (97%) | 2 | la regla de la OC se pasó: dos acuerdos con "procederemos con la OC" quedaron pendientes |
| 3 | OC afinada | 195/200 (97,5%) | 3 | un caso límite (A056) cambió por la variabilidad del modelo |
| 4 y 5 | + "sin cotización enviada no hay acuerdo" | **197/200 (98,5%)** las dos | 2 | las dos corridas fallan en los mismos 3 casos: estable |

Ajustes a los datos: en 35 correos de muestra la dirección de Javier venía sin "@" (un problema del archivo de muestra, no de producción), y las 8 etiquetas del criterio 3 se pasaron a pendiente según la decisión del 17-oct. Los originales quedaron respaldados en `datos/validacion/*_antes_17oct.*`.

Los 3 desacuerdos que quedan son preguntas de criterio para Andrea y Javier, y ninguno pierde un movimiento real: (1) el día de la devolución el cliente avisa "el camión está en su planta" (el acuerdo ya se había reenviado); (2) Javier pregunta "¿van a venir hoy?" sobre una hora ya agendada; (3) "devuelva cuando quiera" y el cliente responde "OK". Comparación: Sonnet 5.5 sacó 190/200 y Haiku 5.5 177/200 con la rúbrica anterior. Costo: US$0,75 por los 200 correos.

## 10. Memoria entre correos (18-oct-2026)

El clasificador ahora recuerda qué reenvió antes en el mismo hilo o cotización. Cada reenvío deja una entrada en la carpeta `INBOX.Registro` de agente@, y cuando llega un correo se le pasan al modelo las decisiones anteriores de su hilo. El hilo se reconoce por el número de cotización, por el asunto junto con el dominio del cliente (así un asunto genérico como "Hora devolución" no mezcla clientes distintos) y por las referencias del correo. Si un correo solo repite un acuerdo que ya se reenvió (gracias, recibido, un recordatorio), no se vuelve a reenviar. Esto solo pasa si el historial tiene de verdad ese acuerdo. Costo: casi igual, unos US$0,001 más por correo con historial.

Pruebas antes de subirlo:

- **200 históricos con memoria** (cada hilo en orden cronológico): 199/200 y 198/200 en dos corridas, contra 197/200 sin memoria. Los casos que fallan cambian de una corrida a otra (J047, A086, A092): es el ruido del modelo en casos límite, no un error sistemático.
- **164 correos reales del 15 y 16-oct, simulados con memoria** sin reenviar: 158/162 iguales a la decisión ya revisada. 1 duplicado evitado (un "Gracias" a un despacho ya reenviado), 1 caso discutible que quedó en acordado (la ejecutiva confirma la fecha y la aprobación que pide es para facturar) y 2 que suman ruido en pendientes (el lado seguro). Ningún movimiento perdido.
- **Regresión de casos reales**: detectó que un correo ya precargado se encontraba a sí mismo en la memoria. Se corrigió: cada correo solo ve decisiones anteriores a él. Después: 13/13.

Reglas agregadas en la misma jornada: "cuando quiera" solo es pendiente si el día quedó abierto. La memoria se precargó con los 74 reenvíos ya revisados del 15 y 16-oct.

## 11. Casos dudosos para Andrea y Javier (18-oct-2026)

Archivo: `datos/validacion/preguntas-andrea-javier.xlsx`. No está en el repositorio porque contiene correos reales.

- **Preguntas:** 16 reglas de criterio. Cada una dice cómo clasifica hoy el clasificador y por qué. Andrea y Javier marcan si están de acuerdo y, si no, cómo debería ser. Incluye las 8 preguntas originales y las reglas que se agregaron el 17 y 18 de octubre: saldo pendiente, OC reenviada, "cuando quiera", "favor agendar" interno, cotización sin enviar, memoria y material ajeno.
- **Casos:** 57 ejemplos, cada uno con cómo lo clasificamos y la duda. Son los 47 casos con "duda de criterio" de la muestra histórica más 10 correos reales del 15 y 16 de octubre.
- **Resumen:** el % de acierto por pregunta se calcula solo a medida que se llena.

Con sus respuestas se ajusta la rúbrica, se corrigen las etiquetas de la muestra y se vuelve a correr `herramientas/revision.py evaluar` para tener el % definitivo.

## 12. Criterio de la plantilla y decisiones sin preguntar (18-oct-2026)

De las 22 preguntas armadas para Andrea y Javier, ninguna resultó necesaria: se resolvieron con los datos o con la regla de no perder nada (ante la duda, a pendientes).

- **Plantilla de ejecutivas:** la misma plantilla dice *"Es necesario confirmar su hora por este medio para poder agendarle y mandar a preparar el equipo"*. Por eso queda **pendiente (falta confirmación)**, y la respuesta del cliente que acepta (aunque sea "gracias", "ok" o mandando chofer y patente) pasa a **despacho acordado**. Con la memoria, el modelo sabe qué fecha está confirmando el cliente. Se cambiaron 9 etiquetas de la muestra (los 8 correos que son la plantilla y A025, "¿me confirmas?").
- **OC:** cada correo dice si la OC bloquea o no, y el clasificador sigue lo que dice ese correo.
- **Resultado con memoria y la regla nueva:** 199/200 en las dos corridas, sin errores graves. El que queda (A086, la plantilla con la fecha mal escrita) se va a pendientes por precaución.
- **Pendiente técnico:** un correo con dos movimientos va a una sola casilla (2 de 200). Si aparece en la operación, se reenvía a las dos.

## 13. Criterios confirmados con Andrea y Javier (19-oct-2026)

Se les envió por correo, con copia a gerencia, el Excel `datos/validacion/criterios-clasificador.xlsx`: los 28 criterios que sigue hoy el clasificador, cada uno con quién lo revisa (Andrea, Javier o ambos) y "Sí" ya marcado. Si no están de acuerdo, lo cambian a "No" o "Duda" y comentan.

- **Andrea:** respondió "de acuerdo" el 19-oct. No cambia nada en el clasificador.
- **Javier:** respondió "de acuerdo" el 19-oct. Con eso los 28 criterios quedan confirmados por los dos.
- **Quién lee cada casilla de destino:** lo define Alzatec internamente; no es parte del proyecto.
- **Criterios que faltaban en la rúbrica (19-oct):** tres criterios aprobados no estaban escritos en las instrucciones del modelo. Por eso un retiro de material ajeno con día dado por Javier se fue a despachos. Se agregaron material ajeno (siempre pendiente), venta de equipos (igual que despacho) y contrato de arriendo u otros documentos antes de despachar (pendiente). La primera versión decía que pedir documentos sin condicionar el despacho era no aplica, y eso hizo perder A018 (envío del contrato firmado). Se corrigió, y la evaluación quedó en 200/200 con 14/14 en la regresión.
- **Nombre de la casilla de devoluciones:** Paola Briceño (Producción e Inventario) hizo notar que "retiro" en Alzatec es despacho y propuso devolucionesconfirmadas@ o recepcionesconfirmadas@. Víctor creó devolucionesconfirmadas@ el 19-oct y desde ese día las recepciones acordadas se reenvían ahí. Lo reenviado antes quedó en retirosconfirmados@.
