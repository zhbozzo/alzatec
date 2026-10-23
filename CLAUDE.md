# Alzatec: automatización de correos

Proyecto de Lorenzo para la empresa de su papá (Alzatec, gerente general). Hablar en español, simple y directo.
Contexto completo en `README.md` y `docs/` (diagnóstico, propuesta, requerimientos, análisis de correos).

## Qué está en producción (desde el 17-oct-2026)

Clasificador de correos (etapa 1), código en `clasificador/`:
- Las copias de lo que reciben y envían Andrea (asistentetecnico@, departamentotecnico@) y Javier (devoluciones@) llegan a `agente@alzatec.com`.
- Cada 3 minutos se clasifican con GPT-6.1 Sol y se reenvían: despacho acordado → despachosconfirmados@, recepción acordada → devolucionesconfirmadas@ (hasta el 19-oct, retirosconfirmados@), pendiente → pendientesdespachoyrecepcion@. Lo que no aplica no se reenvía y sale en un resumen diario (17:45, L-V).
- El estado vive en la propia casilla como marcas IMAP (sin base de datos). En cPanel las carpetas van dentro de INBOX (`INBOX.Alertas`).
- **Memoria entre correos** (`clasificador/memoria.py`): cada reenvío deja una entrada en `INBOX.Registro`; el modelo recibe lo ya reenviado en el mismo hilo o cotización, y un correo que solo repite un acuerdo ya reenviado no se reenvía. Precargada con los reenvíos del 15 y 16-oct.
- Si algo falla, avisa por correo a lbpiphone4@gmail.com con qué pasó y qué hacer (desde el 23-oct, solo ese correo; también recibe el resumen diario y la alerta de respaldo de Google Cloud).

## Operar en Google Cloud

- Proyecto `alzatec`, región `southamerica-west1`. Jobs de Cloud Run: `clasificador` (args `procesar`) y `clasificador-resumen` (args `resumen`). Cloud Scheduler: `clasificador-cada-3-min` y `clasificador-resumen-diario`. Secretos: `agente-pw`, `openai-api-key`.
- Conectarse: `bash deploy/claude-login.sh` (cuenta `claude-operador`, Editor solo en el proyecto). La clave va como **secreto de red** del entorno, tipo "GCP access token (with Service Account Key)": el entorno cambia el token de relleno `CLOUDSDK_AUTH_ACCESS_TOKEN` por uno real y la clave nunca entra a la sesión. Si falta, el usuario corre `deploy/acceso-claude.sh` en Cloud Shell y la agrega ahí (Entorno → engranaje → Secretos de red); la toma una sesión nueva.
- Con la clave en la variable `GCP_SA_KEY` (forma antigua) hay que quitar el token de relleno: los scripts de `deploy/` y `revision.py` lo hacen solos; en comandos `gcloud` sueltos, anteponer `unset CLOUDSDK_AUTH_ACCESS_TOKEN;` solo en ese caso.
- Ver qué hizo: `bash deploy/ver.sh` (`HORAS=72` para más atrás).
- Ver la casilla agente@ (desde aquí no se llega a IMAP): `gcloud run jobs execute clasificador --region southamerica-west1 --args estado --wait` y leer el evento `estado` en los registros (totales y últimos correos, no toca nada).
- Revisar por qué un correo quedó como quedó: `--args "explicar,TEXTO DEL ASUNTO"` (solo ASCII); registra el evento `explicacion` con el motivo del modelo y el texto, sin reenviar ni marcar. Cada correo clasificado también registra `motivo` y `resumen`.
- Cloud Scheduler quedó en `southamerica-east1` (no existe en Santiago): `gcloud scheduler jobs pause|resume clasificador-cada-3-min --location southamerica-east1`.
- Cambiar código: editar, `python3 -m pytest -q`, commit y push a esta rama, y `bash deploy/actualizar.sh` (sube la versión nueva a los dos jobs sin tocar claves ni programación).
- **"Revisa hoy"**: seguir `docs/10-revision-diaria.md` (exportar el día, revisar con Opus, verificar, `corregir` cada correo, guardar casos y correr la regresión con `herramientas/revision.py`, arreglar la causa si se repite, informar). Historial en `docs/11-revisiones.md`. El usuario eligió revisión a pedido, no programada.
- Instalación desde cero: `deploy/instalar.sh` (interactivo, lo corre el usuario en Cloud Shell). Detalle en `deploy/README.md`.

## Reglas

- Nunca pedir ni mostrar claves, contraseñas o API keys en el chat (tampoco imprimir `GCP_SA_KEY` ni los secretos). Se ingresan en Cloud Shell o en la configuración del entorno.
- Los correos reales no van al repositorio (`datos/` está en `.gitignore`).
- El agente no modifica las casillas de Andrea ni de Javier, no responde a clientes y no toca MADA.
- No cambiar de modelo ni agregar un segundo modelo sin que el usuario lo pida (eligió GPT-6.1 Sol, un solo modelo). Presupuesto: ~US$50/mes, tope de US$65 en OpenAI.
- Usar pocos subagentes: al usuario le preocupa que la sesión se corte por consumo.

## Pendientes

- **Copias de enviados (resuelto 22-oct):** el 21-oct Víctor rehízo la regla de Outlook en el PC de Andrea (antes estaba en otro PC). El 22-oct a las 12:30 ya habían llegado 11 enviados de Andrea y los de departamentotecnico@ (los usa Marcelo Henríquez); cobertura Andrea 1/1, Javier 3/3. Las reglas son de Outlook: solo copian con Outlook abierto, y el hosting no puede copiar lo enviado. Lo que llega solo a departamentotecnico@ puede depender de la regla de Outlook (se copia al abrir Outlook): el usuario acepta que se atrase porque no se pierde, y los clientes suelen responder también a asistentetecnico@, que se copia en el servidor. Los reenvíos propios siguen volviendo a agente@ (13 el 22-oct; inofensivo).
- **Respaldo de Víctor (23-oct):** llegaron `datos/pst/andrea_enviados/` (asistentetecnico@: 1.902 recibidos del 11-ago al 21-oct; departamentotecnico@: 540 recibidos de septiembre), sin los enviados. No se vuelve a pedir: los enviados de Andrea llegan en vivo desde el 22-oct. Sirve para ampliar la validación si hace falta.
- **Más adelante:** cuando Javier use celular, lo que envíe desde ahí no se copia (la regla es de Outlook); opción: que el agente lea en solo lectura su carpeta de enviados. devolucionesconfirmadas@ sigue reenviando a agente@ (inofensivo).
- Revisar los primeros días: `[REVISAR]`, resumen diario de descartados, gasto.
- Primera revisión (17-oct, 159 correos): 96,2% de coincidencia con la revisión de Opus (1 grave); tras corregir la rúbrica, 98,7% y 0 graves. Detalle en `docs/09-analisis-correos.md` §8.
- Validación histórica (18-oct, 200 correos): sin memoria 197/200; con memoria y la regla de la plantilla, 199/200 en dos corridas (casos límite: A086, y a veces J047 y A092). Criterios (28) enviados a Andrea y Javier el 19-oct: Andrea y Javier respondieron "de acuerdo" con todos (§13). Se reevalúa con `python3 herramientas/revision.py evaluar`. Simulación con los correos reales: job `clasificador-prueba`. Detalle en `docs/09-analisis-correos.md` §9 y §10.
