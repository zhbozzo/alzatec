# Agenda de camiones (etapa 2)

En marcha desde el 4-nov-2026. Es una planilla de Google Sheets paralela al Excel de Pato. Solo tiene lo **confirmado**, y la llena sola el clasificador con cada despacho o devolución acordada que reenvía.

Planilla: `https://docs.google.com/spreadsheets/d/1E_-OoaJFamsrI8Nlhr-J7qNSXuWpoAYkNYJQiwugXMA` (de Lorenzo). Está compartida como Editor con la cuenta del clasificador, `clasificador@alzatec.iam.gserviceaccount.com`. Su ID va en la variable `AGENDA_ID` de los dos jobs; sin ella el clasificador no toca la agenda. Código en `clasificador/agenda.py`.

## Hojas de la planilla

- **Semana**:
  - lunes a domingo en columnas, con lo de cada día ordenado por hora en una línea ("08:00  Devolución · EBCO · obra · camión", y el estado entre corchetes si no es Agendado);
  - colores por estado y por tipo, y el día de hoy en azul;
  - la semana se elige en la celda **B1** (Esta semana, Semana siguiente, Semana anterior, En 2 semanas, Hace 2 semanas). En "Esta semana" avanza sola y el domingo ya muestra la siguiente.
  - Es solo para mirar.
- **Hoy**: lo de hoy, ordenado por hora.
- **Agenda**: una fila por movimiento. Columnas: Fecha, Hora, Tipo (Despacho/Devolución), Cliente, Obra, Cotización, Camión, **Estado**, **Nota de bodega**, Resumen, Correo, Historial, y las internas Hilo, UID y Aviso.

## Qué hace Pato

Pato marca **Estado** en la lista de la hoja Agenda y, si quiere, escribe una **Nota de bodega**:

| Estado | Qué significa | Qué hace el agente |
|---|---|---|
| Agendado | Lo puso el agente | — |
| Llegó | El camión vino | Nada |
| **No llegó** | El camión no vino | En los siguientes 3 minutos manda `[PENDIENTE DESPACHO] [REAGENDAMIENTO] …` (o `DEVOLUCIÓN`) a pendientes, con copia a Andrea (despachos) o a Javier (devoluciones) y el correo original adjunto. Lo avisa una sola vez y anota la hora en Aviso |
| Reagendado | Se cambió de fecha (lo marca el agente) | — |
| Anulado | Ya no va | — |
| Revisar | Hay que mirarlo: piden un cambio o una anulación en el hilo, o no se entendió la fecha | — |

## Lógica

- **Una fila por fecha.** Si un correo agenda varias devoluciones (por ejemplo, todos los miércoles), queda una fila por cada fecha.
- **Recordatorios.** Un correo del mismo hilo con la misma fecha (por ejemplo, "le recuerdo su devolución de mañana") no se repite. Si cambió la hora, la actualiza; si la fila estaba en Revisar o Reagendado, la vuelve a Agendado.
- **Otra fecha en el mismo hilo:**
  - si el resumen del modelo dice que se cambió la fecha ("reagenda", "reprogramación", "en reemplazo", "queda sin efecto") y hay una sola fecha futura que pudo ser la cambiada, esa fila queda Reagendado;
  - si hay varias fechas posibles, no adivina: lo anota en el Historial;
  - si no dice que se cambió (por ejemplo, "segunda devolución"), es otro movimiento y las dos filas quedan agendadas.
- **Pendiente de cambio o anulación** en el mismo hilo: lo agendado a futuro queda en Revisar.
- **Ya llegó, anulada o no llegó:**
  - si la misma fecha vuelve a llegar en un correo y esa fila ya está en Llegó, no se agrega otra; solo se anota en el Historial;
  - si estaba Anulado, vuelve a Agendado;
  - si estaba "No llegó", se agrega la fila nueva (es la nueva hora).
- **Una corrección** con `corregir` que saca un acordado, o lo cambia de despacho a devolución o al revés, deja la fila anterior como Anulado y agrega la correcta.
- **La "AGENDA dd-mm-aaaa" diaria de Javier** no se carga: repite lo que ya está en cada hilo.
- **Cliente y obra:** los da el modelo. Si no vienen, el cliente sale del dominio del correo del cliente (ebco.cl → EBCO) y la obra de "Obra X" en el asunto o el resumen.
- **Aviso de "No llegó":**
  - antes de mandar el correo se anota "enviando…" en la columna Aviso;
  - si no se puede anotar, no se manda, así nunca sale dos veces;
  - si el correo falla, se borra y se reintenta en la próxima corrida.
- **Escrituras seguras:** antes de escribir, el clasificador vuelve a leer la hoja.
  - Si alguien la ordenó, ubica la fila por UID, fecha, tipo e hilo.
  - Arma el Historial con lo último que tiene la hoja.
  - No pisa un estado que alguien cambió entremedio.
- **No mover ni renombrar columnas de la hoja Agenda.** Si cambian, el clasificador no escribe nada y avisa ("no tiene las columnas esperadas"). Se pueden agregar columnas al final, después de Aviso.
- **Si la planilla falla**, el correo se reenvía igual y llega un aviso a lbpiphone4@gmail.com, como máximo uno cada 3 horas. Si Google dice que hay demasiadas lecturas (unas 60 por minuto, pasa en cargas grandes), espera y reintenta.
- **Seguridad:** todo se escribe tal cual, así que nada de un correo se interpreta como fórmula. La app guarda notas e historial siempre como texto.

## Comandos (job `clasificador`, `--args`)

- `agenda_ver`: solo lectura. Registra el evento `agenda_ver` con las filas por estado y por fecha, cómo se ven y las vistas.
- `agenda_preparar`: arma las hojas, los títulos, la lista de estados, los colores y las vistas (Semana, Hoy). Se puede correr más de una vez: no toca las filas ni la semana elegida en Semana!B1. Borra la hoja vieja "Próximos 7 días".
- `agenda_cargar,UID,UID,…`: carga acordados ya reenviados usando la memoria, sin volver a llamar al modelo.
  - Con `agenda_cargar,desde_cero,UID,…` primero vacía la planilla, pero solo si bodega todavía no marcó nada.

## Carga inicial (4-nov)

Se cargaron los 60 acordados con fecha desde el 4-nov:
- 59 filas;
- 11 correos que repetían una fecha ya cargada (recordatorios o un cambio de hora), sin filas nuevas;
- 1 AGENDA diaria omitida;
- 1 fecha que quedó Reagendado (Javier cambió del lunes 9 al martes 10).
