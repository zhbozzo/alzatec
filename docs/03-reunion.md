# 03 · Sesión online de levantamiento

Gerencia definió el formato: **el equipo muestra todo online** y después de la sesión se envían los requerimientos ([04-requerimientos.md](04-requerimientos.md)).

El objetivo es salir de la sesión con lo necesario para completar ese documento, sin tener que volver a preguntar.

## Antes de la sesión: preguntas para gerencia

Preguntas cortas que gerencia puede responder por WhatsApp. Sirven para llegar a la sesión sabiendo qué mirar.

1. ¿Las cotizaciones se hacen en MADA o en Excel o Word?
2. ¿Andrea las mandaba desde MADA o descargaba el PDF y lo enviaba desde su correo?
3. Cuando un cliente acepta, ¿alguien lo marca en MADA?
4. ¿Los despachos y devoluciones se registran en MADA? ¿La guía de despacho sale de ahí?
5. ¿Quién es el contacto en INQSOL? ¿Puedes preguntarles si MADA se puede conectar con otro sistema (API o exportar/importar)?
6. ¿Quién está haciendo hoy lo de Andrea y qué es lo que más se está cayendo?
7. ¿Qué hacen cmontes, pfarias y pbriceno?
8. ¿Quién va a ser mi contraparte para dudas?

## La pregunta central de la sesión

> **¿Qué parte del trabajo de Andrea pasaba por MADA y qué parte quedaba solo en el correo, Excel o papel?**

Lo que queda fuera de MADA es exactamente lo que hay que automatizar. Para responderla, en cada flujo preguntar:

- ¿Esto se registra en MADA? ¿Quién lo registra y en qué momento?
- Si no se registra en MADA, ¿dónde queda?

| Si las cotizaciones… | Entonces el sistema… |
|---|---|
| **Se hacen en MADA** | Enlaza cada correo con el número de cotización de MADA. No guarda cotizaciones propias. |
| **Se hacen en Excel o Word** | Tiene que registrarlas él. También se puede proponer empezar a usar el módulo de cotizaciones de MADA, que puede que ya estén pagando. |

## Antes de empezar

- [ ] Pedir permiso para **grabar o transcribir** la sesión (Meet, Zoom y Teams tienen transcripción). Con la transcripción se completan los requerimientos sin perder detalle.
- [ ] Tener abierta esta lista y la tabla de la ronda por persona (más abajo).
- [ ] Explicar en 1 minuto el objetivo: automatizar lo repetitivo, **no** cambiar cómo trabaja cada uno.

## Qué pedir que muestren (en este orden)

Lo ideal es que en cada punto compartan pantalla con un **caso real**.

1. **La casilla de Andrea.** Carpetas, filtros y reglas que tenía, y cómo se ve un día normal. ¿Con qué programa la leía (Outlook, webmail, celular)?
2. **Una cotización de punta a punta.** Solicitud del cliente → quién la arma y con qué (Excel, Word, lista de precios) → envío → respuesta del cliente.
3. **Una modificación de un comercial.** Qué llega, qué cambia y cómo queda la nueva versión.
4. **Un despacho.** Dónde se anota, quién decide la fecha, qué datos se piden al cliente y si **la guía de despacho sale de MADA**.
5. **Una devolución.** Qué se reenvía a `devoluciones@`, cómo se coordina el retiro y cómo se cuenta lo que vuelve.
6. **La agenda o planilla de despachos**, si existe. ¿Es la de horarios de 8:00 a 13:00 que estaba al reverso de la nota?
7. **MADA por dentro.**
   - Qué módulos usan y cómo se crea una cotización.
   - Si MADA manda el correo, o se descarga el PDF y se envía desde la casilla.
   - Qué cambia en MADA cuando el cliente acepta.
   - Dónde quedan los despachos y las devoluciones.
   - Qué reportes se pueden exportar a Excel.
   - **Qué cosas no están en MADA y se llevan aparte.**

## Preguntas que sí o sí deben quedar respondidas

1. ¿Quién arma la cotización: comercial, Andrea o asistente técnico? ¿Con qué herramienta? ¿Hay lista de precios?
2. ¿Por dónde llegan las solicitudes de cotización: correo, web, teléfono o WhatsApp?
3. ¿Qué tipos de respuesta llegan y qué se hacía con cada uno?
4. ¿Qué se necesita para pasar de "aceptada" a "despacho" (OC, pago, crédito aprobado)?
5. ¿Cuál es la capacidad de despacho por día y por sucursal (Lampa / Concón)?
6. ¿La guía de despacho y la factura salen de MADA o de otro sistema conectado a MADA?
7. ¿Alzatec retira con su camión o el cliente devuelve en bodega? ¿Cómo se registra lo devuelto?
8. ¿Quién está haciendo hoy el trabajo de Andrea y qué se está cayendo?
9. ¿Qué había en la línea vacía de la nota? ¿Qué más hacía Andrea (llamadas, WhatsApp, cobranza)?
10. ¿Quién será la **contraparte** del proyecto para dudas y validaciones?
11. ¿Quién administra la cuenta de MADA y quién es el contacto en INQSOL? ¿El contrato incluye API o integraciones?

## Preguntas de detalle (si hay tiempo)

**Cotizaciones**
- ¿Qué datos lleva la cotización? (equipos, m², plazo de arriendo, flete, montaje, condiciones de pago)
- ¿Tienen número correlativo? ¿Cómo se versionan los cambios?
- ¿Se hace seguimiento si el cliente no contesta? ¿A los cuántos días?
- ¿Quién aprueba un cambio de precio o un descuento?

**Despachos**
- ¿Qué datos hacen falta: dirección, contacto en obra, horario de recepción, accesos?
- ¿Se reprograman seguido? ¿Por qué?

**Devoluciones**
- ¿Qué significa exactamente "derivados"?
- ¿Cómo afecta lo devuelto a la facturación del arriendo (faltantes, daños)?

**Sistemas**
- ¿Quién administra el hosting (HostingPlus) y las casillas de correo?
- ¿Usan WhatsApp con clientes o choferes? ¿Personal o WhatsApp Business?
- ¿Algún cliente (constructora) usa **ADAM**, el otro producto de INQSOL, para pedir equipos?

## Ronda por persona

| Casilla | Rol | Qué le llegaba de Andrea | Qué le mandaba a Andrea | Qué le duele hoy |
|---|---|---|---|---|
| abozzo | Gerencia | | | |
| cmontes | | | | |
| pfarias | | | | |
| pbriceno | | | | |
| asistentetecnico | | | | |
| devoluciones | | | | |

## Qué pedir al cerrar la sesión

- [ ] **Export de 2–3 meses** de la casilla de Andrea (desde el webmail de cPanel o Outlook) o un **acceso IMAP de solo lectura**.
- [ ] 5 correos reales de cada tipo (si no hay export).
- [ ] Una cotización de ejemplo (PDF o Excel), la plantilla y la lista de precios.
- [ ] La planilla o agenda de despachos.
- [ ] Nombre de la contraparte.
- [ ] Contacto en INQSOL y autorización para pedirles las opciones de integración con MADA.
- [ ] Un usuario de MADA de solo lectura para el proyecto.

## Después de la sesión

1. Completar [01-diagnostico.md](01-diagnostico.md) y quitar los **(confirmar)** que se resolvieron.
2. Completar los **[validar]** de [04-requerimientos.md](04-requerimientos.md) y enviarlo a gerencia.
