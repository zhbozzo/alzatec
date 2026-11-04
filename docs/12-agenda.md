# Agenda de camiones (etapa 2)

En marcha desde el 4-nov-2026. Es una planilla de Google Sheets paralela al Excel de Pato. Solo tiene lo **confirmado**, y la llena sola el clasificador con cada despacho o devolución acordada que reenvía.

Planilla: `https://docs.google.com/spreadsheets/d/1E_-OoaJFamsrI8Nlhr-J7qNSXuWpoAYkNYJQiwugXMA` (de Lorenzo). Está compartida como Editor con la cuenta del clasificador, `clasificador@alzatec.iam.gserviceaccount.com`. Su ID va en la variable `AGENDA_ID` de los dos jobs; sin ella el clasificador no toca la agenda. Código en `clasificador/agenda.py`.

Hay dos formas de verla:
- **la app de calendario** (recomendada, se instala una vez; ver abajo);
- **la planilla misma**.

## App de calendario

Es una página tipo Google Calendar hecha con Google Apps Script (código en `agenda-web/`). Lee y escribe la misma hoja Agenda, así que todo lo de abajo (reagendamiento, historial) funciona igual.

- **Vista semanal:** lunes a sábado en columnas (domingo solo si hay algo) y las horas en filas.
  - Cada camión es una tarjeta: hora, tipo (azul = despacho, verde = devolución), cliente, obra, camión y estado.
  - Arriba de cada día salen los movimientos y las toneladas aproximadas.
  - Se navega con **‹ ›** (semana anterior / siguiente) y **Hoy**; en el teclado, ← → y T.
  - Abre sola en la semana actual (el domingo ya muestra la siguiente), se actualiza cada minuto y, si la dejas abierta, pasa sola a la semana nueva.
- **Marcar:**
  - **✓** en la tarjeta = Llegó; tocarlo de nuevo lo desmarca.
  - **✗** = No llegó: pide confirmar y avisa a pendientes.
  - Tocar la tarjeta abre el detalle: los mismos botones, más Anulado, Revisar y Desmarcar, la **Nota de bodega**, lo acordado y el historial.
  - Después de marcar aparece **Deshacer** por unos segundos.
  - Marcar "Llegó" algo de un día futuro pide confirmar.
- **Avisos:**
  - lo de días pasados (o de hoy, pasada una hora) que sigue sin marcar sale como **¿Llegó?** y se cuenta arriba;
  - lo que no tiene fecha clara sale abajo, en amarillo.
- **Tabla:** la misma semana (o todas las fechas) en filas, con búsqueda, orden por columna y el estado en una lista.
- **Celular:** una tira con los días de la semana y la lista del día elegido, con botones grandes.
- **Imprimir:** imprime la semana.
- **Quién marcó:** cada cambio queda en la columna Historial con la hora y el usuario (por ejemplo, "04-11 15:20 pfarias: Agendado → Llegó").

### Instalarla (una vez, en el PC, ~10 minutos)

1. Abrir la planilla → menú **Extensiones → Apps Script**.
2. En el archivo `Código.gs`, borrar lo que trae y pegar todo `agenda-web/Codigo.gs`.
3. Junto a "Archivos", **+ → HTML**, nombre `Index` (sin ".html"). Borrar lo que trae y pegar todo `agenda-web/Index.html`.
4. Guardar (Ctrl+S). Arriba, ponerle de nombre al proyecto "Agenda de camiones".
5. **Implementar → Nueva implementación** → en el engranaje, **Aplicación web**:
   - Ejecutar como: **Usuario que accede a la aplicación web**.
   - Quién tiene acceso: **Cualquier usuario con cuenta de Google**.
   - **Implementar**.
6. **Autorizar acceso** → elegir la cuenta.
   - Sale "Google no verificó esta app" porque es una app propia, no publicada. Se sigue con **Configuración avanzada → Ir a Agenda de camiones (no seguro) → Permitir**.
   - El permiso dice "todas tus hojas de cálculo", pero el código solo abre esta planilla (su ID está fijo en `Codigo.gs`).
7. Copiar la **URL de la aplicación web** (termina en `/exec`) y mandarla a Pato y al papá. En el celular se puede agregar a la pantalla de inicio.

**Acceso:**
- La app usa la cuenta de Google de quien la abre, así que solo funciona para quien tiene la planilla compartida.
- Con **Editor** se puede marcar; con **Lector** solo se mira (si intenta marcar, la app le dice que pida permiso de Editor).
- La primera vez cada uno ve la misma pantalla de autorización del paso 6.

**Actualizarla** (si cambia el código):
1. Pegar los archivos nuevos y guardar.
2. **Implementar → Gestionar implementaciones** → lápiz → Versión: **Nueva versión** → **Implementar**.

La URL no cambia.

**Probarla sin Google:** `node agenda-web/prueba/probar.js CARPETA` corre la app con una planilla simulada y datos inventados (56 comprobaciones) y deja capturas en CARPETA.

## Hojas de la planilla

- **Semana**:
  - lunes a domingo en columnas, con lo de cada día ordenado por hora en una línea ("08:00  Devolución · EBCO · obra · camión", y el estado entre corchetes si no es Agendado);
  - colores por estado y por tipo, y el día de hoy en azul;
  - la semana se elige en la celda **B1** (Esta semana, Semana siguiente, Semana anterior, En 2 semanas, Hace 2 semanas). En "Esta semana" avanza sola y el domingo ya muestra la siguiente.
  - Es solo para mirar.
- **Hoy**: lo de hoy, ordenado por hora.
- **Agenda**: una fila por movimiento. Columnas: Fecha, Hora, Tipo (Despacho/Devolución), Cliente, Obra, Cotización, Camión, **Estado**, **Nota de bodega**, Resumen, Correo, Historial, y las internas Hilo, UID y Aviso.

## Qué hace Pato

Pato marca **Estado** en la app (o en la lista de la hoja Agenda) y, si quiere, escribe una **Nota de bodega**:

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
- **Una corrección** con `corregir` que saca un acordado deja su fila como Anulado. Si lo vuelve acordado, lo agrega.
- **La "AGENDA dd-mm-aaaa" diaria de Javier** no se carga: repite lo que ya está en cada hilo.
- **Cliente y obra:** los da el modelo. Si no vienen, el cliente sale del dominio del correo del cliente (ebco.cl → EBCO) y la obra de "Obra X" en el asunto o el resumen.
- **Si la planilla falla**, el correo se reenvía igual y llega un aviso a lbpiphone4@gmail.com, como máximo uno cada 3 horas.
- **Seguridad:** todo se escribe tal cual, así que nada de un correo se interpreta como fórmula.

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
