# Alzatec · Agente de agenda de camiones

Un agente lee una copia de los correos de `asistentetecnico@alzatec.com` y separa cotizaciones, solicitudes de despacho y solicitudes de recepción. Con los despachos y recepciones llena el **Excel de agenda** de Patricio Farías, y marca una alerta cuando el día pedido está copado. No interfiere con el trabajo de la casilla ni con MADA.

## Documentos

1. [Diagnóstico](docs/01-diagnostico.md): cómo se organiza el área de proyectos, el flujo de la cotización al camión y los tipos de solicitud.
2. [Propuesta](docs/02-propuesta.md): cómo funciona el agente, la agenda de Pato, el stack, las fases y los riesgos.
3. [Reunión con Andrea y Pato](docs/03-reunion.md): definir los tipos de correo con Andrea y revisar el Excel con Pato.
4. [Requerimientos](docs/04-requerimientos.md): el borrador que se envía a gerencia después de la reunión.
5. [Implementación](docs/05-implementacion.md): cómo conectar el correo, el Excel en OneDrive y el agente en n8n.
6. [Clasificación de correos](docs/06-clasificacion.md): qué preguntarle a Andrea para definir cotización, despacho y recepción. Incluye el alcance de la versión 1.
7. [Agente v1](docs/07-agente-v1.md): cómo funciona paso a paso, el JSON que devuelve la IA, las reglas, los errores y el mantenimiento.
8. [Notas de la reunión](docs/08-notas-reunion.md): lo confirmado en la reunión y el nuevo alcance en dos etapas.

Ejemplo: [`ejemplos/agenda-camiones-ejemplo.xlsx`](ejemplos/agenda-camiones-ejemplo.xlsx) muestra cómo queda la agenda llenada por el agente (datos ficticios).

## Estado

**Alcance actualizado en la reunión:** la etapa 1 es solo un **clasificador**. Los correos de Andrea y de Javier pasan por `agente@` y se reenvían a `despachosconfirmados@`, `retirosconfirmados@` o `pendientesandrea@`. El Excel queda para la etapa 2. Ver [notas](docs/08-notas-reunion.md).

**Fase 0 · Levantamiento.** Confirmado: 25–30 cotizaciones diarias, unos 10 camiones al día, y MADA como sistema de gestión, que el proyecto no toca. Todas las solicitudes pasan por `asistentetecnico@` y la agenda es un Excel. Falta la reunión con Andrea y Patricio Farías.
