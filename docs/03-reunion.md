# 03 · Reunión de levantamiento (Andrea y Pato)

**Objetivo:** salir con dos cosas.
1. **De Andrea:** cómo reconocer cotizaciones, despachos y recepciones, con ejemplos reales.
2. **De Pato:** cómo es el Excel de agenda y cuándo un día está copado.

Con eso se completan los requerimientos ([04-requerimientos.md](04-requerimientos.md)). El detalle de la clasificación está en [06-clasificacion.md](06-clasificacion.md).

## Al empezar (2 min)

- [ ] Pedir permiso para **grabar o transcribir**.
- [ ] Explicar la idea:

  > "Un agente lee una copia de los correos de asistentetecnico@, separa cotizaciones, despachos y recepciones, y anota los despachos y recepciones en el Excel de Pato como 'por confirmar'. Si el día ya está lleno de camiones, lo marca. Andrea sigue trabajando igual y MADA no se toca."

- [ ] Si sirve, mostrar el ejemplo [`ejemplos/agenda-camiones-ejemplo.xlsx`](../ejemplos/agenda-camiones-ejemplo.xlsx).

## 1. Con Andrea: clasificación de correos

1. Aparte de cotizaciones, despachos y recepciones, ¿llega otro tipo de correo que importe? ¿Qué llega que no importa (proveedores, facturas, avisos de MADA)?
2. Cuando abres un correo, ¿cómo sabes qué es? ¿Por el asunto, por quién lo manda, por las palabras, por los adjuntos?
3. ¿Qué palabras usan los clientes para pedir un **despacho** ("retiro", "paso a buscar"…) y para una **recepción** ("devolución", "término de obra"…)?
4. ¿El **N° de cotización** viene siempre en el correo? ¿En qué formato? ¿Es el de MADA?
5. Si el cliente **acepta la cotización pero no da fecha**, ¿qué haces?
6. Si da una **fecha vaga** ("la próxima semana", "lo antes posible"), ¿qué haces?
7. ¿La **hora** la propone el cliente o la asigna Pato?
8. De cada solicitud, ¿qué **datos le pasas a Pato**? ¿Cuáles son obligatorios? Si falta alguno, ¿qué haces?
9. ¿A veces la fecha o el detalle viene **solo en un adjunto** (una orden de compra o un PDF)?
10. Cuando un **vendedor te copia**, ¿cómo es ese correo? ¿Pasa que el mismo pedido llega dos veces, del vendedor y del cliente?
11. ¿Con qué frecuencia **cambian la fecha o cancelan**? ¿Cómo lo escriben?
12. En un día normal, ¿**cuántos correos de cada tipo** llegan?

**Si hay tiempo (15–20 min):** abrir con ella los correos de un día y que diga qué es cada uno y por qué.

## 2. Con Pato: el Excel y el cupo

1. Que muestre el Excel. **¿Dónde está guardado?** Si es OneDrive, ¿es una cuenta **personal o de empresa** (Microsoft 365)?
2. ¿Cómo está armado? ¿**Una fila por camión**, o una grilla con los horarios en columnas?
3. ¿Qué columnas llena? ¿Cuáles son obligatorias?
4. **Cupo:** ¿cuántos camiones caben al día? ¿El límite es por día o por bloque horario? ¿Despachos y recepciones comparten el mismo cupo?
5. Cuando un día **está copado**, ¿qué hace? ¿Dónde debería quedar esa solicitud?
6. **Regla de los 2 días:** ¿son días hábiles? ¿Se atiende los sábados? ¿Cuál es el horario? ¿Qué pasa con lo que piden para el mismo día?
7. ¿Le sirve una columna **Estado** con colores (POR CONFIRMAR, CONFIRMADO, SIN CUPO, URGENTE, REVISAR, CANCELADO)?
8. **Camión de Alzatec (casos puntuales):**
   - ¿Qué casos hay, aparte de faltantes y material galvanizado?
   - El material galvanizado, ¿se retira de la obra del cliente o de la galvanizadora?
   - ¿Esos pedidos llegan al correo de Andrea?
   - ¿Van en el mismo Excel?
9. ¿Quién más usa el Excel (bodega, portería)?

## 3. Accesos (con gerencia)

- [ ] ¿Quién administra el hosting (cPanel de HostingPlus)? Autorizar que se cree `agente@alzatec.com` y el reenviador.
- [ ] ¿Tienen **Microsoft 365 de empresa**? Si no, aprobar 1 licencia Business Basic para el Excel.
- [ ] Aprobar que la cuenta de API de IA y n8n queden **a nombre de Alzatec**.
- [ ] Comentar que el contenido de los correos pasa por el proveedor de IA.

## 4. Pedir al cerrar

- [ ] **5 a 10 correos reales de cada tipo**, incluidos los casos difíciles.
- [ ] **Los correos de 1–2 semanas** de `asistentetecnico@` y **el Excel de Pato de esas mismas semanas**. Sirven para medir al agente antes de usarlo.
- [ ] **Contrapartes:** Andrea para la clasificación y Pato para la agenda.

## Después de la reunión

1. Actualizar [01-diagnostico.md](01-diagnostico.md) y quitar los **(confirmar)** que se resolvieron.
2. Completar los **[validar]** de [04-requerimientos.md](04-requerimientos.md) y enviarlo a gerencia.
