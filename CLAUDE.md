# Alzatec: automatización de correos

Proyecto de Lorenzo para la empresa de su papá (Alzatec, gerente general). Hablar en español, simple y directo.
Contexto completo en `README.md` y `docs/` (diagnóstico, propuesta, requerimientos, análisis de correos).

## Qué está en producción (desde el 17-oct-2026)

Clasificador de correos (etapa 1), código en `clasificador/`:
- Las copias de lo que reciben y envían Andrea (asistentetecnico@, departamentotecnico@) y Javier (devoluciones@) llegan a `agente@alzatec.com`.
- Cada 3 minutos se clasifican con GPT-6.1 Sol y se reenvían: despacho acordado → despachosconfirmados@, recepción acordada → retirosconfirmados@, pendiente → pendientesdespachoyrecepcion@. Lo que no aplica no se reenvía y sale en un resumen diario (17:45, L-V).
- El estado vive en la propia casilla como marcas IMAP (sin base de datos). En cPanel las carpetas van dentro de INBOX (`INBOX.Alertas`).
- Si algo falla, avisa por correo a lbozzo@fen.uchile.cl y lbpiphone4@gmail.com con qué pasó y qué hacer.

## Operar en Google Cloud

- Proyecto `alzatec`, región `southamerica-west1`. Jobs de Cloud Run: `clasificador` (args `procesar`) y `clasificador-resumen` (args `resumen`). Cloud Scheduler: `clasificador-cada-3-min` y `clasificador-resumen-diario`. Secretos: `agente-pw`, `openai-api-key`.
- Conectarse: `bash deploy/claude-login.sh` (usa la variable de entorno `GCP_SA_KEY`; cuenta `claude-operador`, Editor solo en el proyecto). Si falta, el usuario corre `deploy/acceso-claude.sh` en Cloud Shell y la agrega en la configuración del entorno.
- Ver qué hizo: `bash deploy/ver.sh` (`HORAS=72` para más atrás).
- Cambiar código: editar, `python3 -m pytest -q`, commit y push a esta rama, y `bash deploy/actualizar.sh` (sube la versión nueva a los dos jobs sin tocar claves ni programación).
- Instalación desde cero: `deploy/instalar.sh` (interactivo, lo corre el usuario en Cloud Shell). Detalle en `deploy/README.md`.

## Reglas

- Nunca pedir ni mostrar claves, contraseñas o API keys en el chat (tampoco imprimir `GCP_SA_KEY` ni los secretos). Se ingresan en Cloud Shell o en la configuración del entorno.
- Los correos reales no van al repositorio (`datos/` está en `.gitignore`).
- El agente no modifica las casillas de Andrea ni de Javier, no responde a clientes y no toca MADA.
- No cambiar de modelo ni agregar un segundo modelo sin que el usuario lo pida (eligió GPT-6.1 Sol, un solo modelo). Presupuesto: ~US$50/mes, tope de US$65 en OpenAI.
- Usar pocos subagentes: al usuario le preocupa que la sesión se corte por consumo.

## Pendientes

- Cambiar la contraseña de agente@ (circuló por WhatsApp) y actualizar el secreto `agente-pw`.
- Confirmar que el correo de alertas es lbozzo@fen.uchile.cl.
- Respaldo de enviados de Andrea (Víctor, sin apuro) y copia de salida en el servidor cuando Javier use celular.
- Validación de Andrea/Javier (Excel de validación y preguntas en `docs/09-analisis-correos.md`).
- Revisar los primeros días: `[REVISAR]`, resumen diario de descartados, gasto.
