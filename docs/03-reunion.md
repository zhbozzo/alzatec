# 03 · Reunión con Patricio "Pato" Farías

## Objetivo

Entender **la agenda de camiones de Pato** y cómo le llegan hoy las solicitudes, para definir exactamente qué tiene que detectar el agente. Con lo que salga de aquí se completan los requerimientos ([04-requerimientos.md](04-requerimientos.md)) y se envían a gerencia.

## Al empezar (2 min)

- [ ] Pedir permiso para **grabar o transcribir** la reunión.
- [ ] Explicar la idea en una frase:

  > "Un agente lee una copia de los correos de asistentetecnico@ y te propone las entradas de tu agenda. Tú confirmas. Andrea no cambia nada y MADA no se toca."

## Pedirle que muestre

1. **Su agenda actual**, con una semana completa. ¿Es la planilla de horarios de 8:00 a 13:00?
2. **3 a 5 correos reales** que terminaron en la agenda. Idealmente uno de cada tipo:
   - un retiro,
   - una devolución,
   - un pedido para el mismo día,
   - una reprogramación,
   - un viaje del camión de Alzatec.
3. **Cómo se entera hoy** de cada solicitud, paso a paso.

## Preguntas

### La agenda
- ¿Dónde la lleva? ¿Quién más la ve (bodega, portería)?
- ¿Qué horario tiene y en qué bloques la divide? ¿Cuántos camiones se pueden atender al mismo tiempo?
- ¿Los retiros y las devoluciones usan el mismo espacio y el mismo equipo de bodega?
- ¿Qué anota de cada camión (cliente, obra, patente, chofer, N° de cotización, equipos)?
- ¿Cuántos camiones hay en un día normal y en uno peak?

### Las solicitudes
- ¿Cómo le llegan? ¿Andrea se las reenvía, le avisa, él mira el correo, llegan por teléfono o WhatsApp, o directo a `pfarias@`?
- Más o menos, ¿qué porcentaje llega por `asistentetecnico@`?
- ¿Cómo se ven esos correos? ¿Son respuestas al hilo de la cotización o correos nuevos? ¿Traen el número de cotización?
- ¿Hay casos que confunden, por ejemplo un correo que menciona un retiro pero no es un pedido?

### Las reglas
- La regla de los 2 días, ¿para qué sirve exactamente? ¿Para preparar el pedido en bodega?
- ¿Qué pasa cuando un cliente pide para el mismo día? ¿Quién decide si se acepta?
- ¿Hay días u horarios en que no se atiende? ¿Sábados?
- ¿Qué pasa si el cliente no llega?

### El camión de Alzatec
- ¿Cuántos camiones propios tienen?
- ¿Qué viajes hacen: faltantes a obra, retiro de galvanizado, otros?
- ¿Quién pide esos viajes y por dónde? ¿Van en la misma agenda o en otra?

### Confirmación al cliente
- Hoy, ¿se le confirma la hora al cliente? ¿Quién lo hace y cómo?
- Más adelante, ¿le serviría que el sistema mande la confirmación y un recordatorio el día anterior?

### MADA (solo para entender, no se toca)
- En cada retiro o devolución, ¿qué se registra en MADA y quién lo hace? ¿La guía sale de ahí?

### Cómo lo quiere usar
- ¿Lo quiere ver en el computador, en el celular o impreso?
- ¿Prefiere aviso inmediato, un resumen, o ambos? ¿A qué hora le sirve el resumen?
- Para él, ¿qué sería un éxito?

## Pedir al cerrar

- [ ] **La agenda real de 1 a 2 semanas pasadas** (fotos o Excel), más **los correos de `asistentetecnico@` de esas mismas semanas**. Con eso se puede medir al agente contra lo que pasó de verdad antes de que opere.
- [ ] Quién administra el hosting (cPanel de HostingPlus), para crear `agente@` y el reenvío con copia.
- [ ] Confirmar que Pato es la contraparte para dudas.

## Para gerencia

- Autorizar que se cree la casilla `agente@alzatec.com` y el reenvío con copia desde `asistentetecnico@`.
- Confirmar quién tiene acceso al cPanel de HostingPlus.

## Después de la reunión

1. Actualizar [01-diagnostico.md](01-diagnostico.md) y quitar los **(confirmar)** que se resolvieron.
2. Completar los **[validar]** de [04-requerimientos.md](04-requerimientos.md) y enviarlo a gerencia.
