# 03 · Reunión de levantamiento (Andrea y Pato)

## Objetivo

Salir de la reunión con dos cosas:

1. **De Andrea:** una definición clara de qué es una cotización, una solicitud de despacho y una solicitud de recepción, con ejemplos reales.
2. **De Pato:** cómo es el Excel de agenda, dónde vive y cuándo un día está copado.

Con eso se completan los requerimientos ([04-requerimientos.md](04-requerimientos.md)).

## Al empezar (2 min)

- [ ] Pedir permiso para **grabar o transcribir** la reunión.
- [ ] Explicar la idea en una frase:

  > "Un agente lee una copia de los correos de asistentetecnico@, separa cotizaciones, despachos y recepciones, y llena el Excel de Pato como 'por confirmar'. Si el día está copado, avisa. Andrea no cambia nada y MADA no se toca."

## 1. Con Andrea: definir los tipos

> La guía completa, con los casos difíciles y una ficha para llenar por categoría, está en [06-clasificacion.md](06-clasificacion.md).

Esto va primero, porque todo lo demás depende de esta definición.

- Para ella, ¿qué es una **cotización**, un **despacho** y una **recepción**?
- Al leer un correo, ¿cómo sabe de qué tipo es? ¿Por el asunto, por quién lo manda, por las palabras ("retiro", "devolución", "paso a buscar"), por los adjuntos?
- **Vocabulario (confirmado):**
  - **Despacho:** el cliente viene a **retirar** equipos de Alzatec. "Retiro" siempre significa esto.
  - **Recepción:** el cliente **devuelve** equipos a Alzatec.
- ¿Hay casos especiales?
  - casos puntuales con el camión de Alzatec (llevar faltantes a una obra, ir a retirar material galvanizado: ¿a la obra del cliente o a la galvanizadora?),
  - cambios de fecha y cancelaciones,
  - correos que mezclan cosas ("acepto la cotización y la busco mañana").
- De cada solicitud, ¿qué datos le pasa a Pato?
- ¿Las solicitudes que llegan por otro medio siempre terminan en su correo? ¿Cómo: un vendedor la copia o le reenvía?
- Cuando el día está lleno, ¿qué hace ella? ¿Quién le avisa al cliente?

**Ejercicio (15–20 min, si se puede):** revisar con Andrea los correos de un día y que diga qué es cada uno. Es la forma más rápida de tener ejemplos bien clasificados.

**Pedirle:** 5 a 10 correos reales de cada tipo, reenviados o exportados.

## 2. Con Pato: el Excel

- Que lo muestre en pantalla.
- **¿Dónde vive?** ¿En su PC, en una carpeta compartida o en OneDrive? Si está en OneDrive, **¿es una cuenta personal (hotmail/outlook) o de empresa (Microsoft 365)?** ¿Quién más lo abre?
- **¿Cómo está armado?** ¿Una hoja por día, semana o mes? ¿Una fila por camión? ¿Los horarios van en columnas?
- ¿Qué columnas llena y cuáles son obligatorias?
- **¿Cuándo un día está copado?** ¿Hay un máximo de camiones por día, por bloque horario, o uno distinto para despachos y recepciones?
- **¿Qué pasa cuando está copado?** ¿Se ofrece otro día, se rechaza o se hace igual? ¿Dónde debería quedar la solicitud que no cupo?
- ¿Le sirve que el agente agregue una columna **Estado** (POR CONFIRMAR, CONFIRMADO, SIN CUPO, URGENTE, REVISAR) con colores?
- La regla de los 2 días: ¿qué se hace con lo que piden para el mismo día?
- ¿El camión de Alzatec va en el mismo Excel?
- Las alertas, ¿por correo o por WhatsApp? ¿Para él, para Andrea o para ambos?
- (Solo para entender) ¿Qué se registra en MADA en cada despacho o recepción?

## Pedir al cerrar

- [ ] **Una copia del Excel**, idealmente de 1 a 2 semanas pasadas.
- [ ] **Los correos de `asistentetecnico@` de esas mismas semanas.** Con el Excel y los correos de las mismas fechas se puede medir al agente contra lo que pasó de verdad.
- [ ] Quién administra el cPanel de HostingPlus.
- [ ] Contraparte para dudas: Andrea para los tipos y Pato para la agenda.

## Para gerencia

- Autorizar que se cree la casilla `agente@alzatec.com` y el reenvío con copia desde `asistentetecnico@`.
- Si no tienen Microsoft 365 de empresa, aprobar 1 licencia Business Basic para alojar el Excel. El correo no se mueve.
- Aprobar la cuenta de API del modelo de IA y dónde corre n8n, ambas a nombre de Alzatec.

## Después de la reunión

1. Actualizar [01-diagnostico.md](01-diagnostico.md) y quitar los **(confirmar)** que se resolvieron.
2. Completar los **[validar]** de [04-requerimientos.md](04-requerimientos.md) y enviarlo a gerencia.
