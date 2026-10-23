# Puesta en marcha en Google Cloud

El clasificador corre como un **Cloud Run Job** que un **Cloud Scheduler** lanza cada 3 minutos. Un segundo job manda el resumen diario de lo descartado. Las contraseñas y API keys van en **Secret Manager**, nunca en el repositorio.

Todo se hace desde [Cloud Shell](https://shell.cloud.google.com), la terminal en el navegador de Google Cloud. No hay que instalar nada.

## Forma rápida (recomendada)

1. Abrir [Cloud Shell](https://shell.cloud.google.com) con la cuenta dueña del proyecto (si pide "Autorizar", aceptar).
2. Pegar este comando y apretar Enter:

   ```bash
   git clone -b claude/automatizacion-empresa-papa-1a1tca https://github.com/zhbozzo/alzatec.git 2>/dev/null || git -C alzatec pull; bash alzatec/deploy/instalar.sh
   ```

3. Responder lo que pregunta:
   - el proyecto (Enter si es el que muestra);
   - la contraseña de `agente@` y la API key de OpenAI (al pegarlas no se ve nada; después Enter). Cada una se prueba antes de guardarla en Secret Manager: si está mala, lo dice y la pide de nuevo;
   - al final, si dejarlo funcionando solo (Enter = sí).

Sube el clasificador (3 a 5 minutos), hace una primera corrida que ya reenvía a las casillas reales, muestra qué hizo con cada correo y lo programa cada 3 minutos, con el resumen diario y la alerta de respaldo.

Si algo falla, el script dice qué arreglar (facturación, saldo de OpenAI, contraseña). Una vez arreglado, se vuelve a pegar el mismo comando: lo que ya está hecho se salta, y las claves guardadas se prueban de nuevo sin volver a pedirlas.

Los pasos de abajo son lo mismo, a mano.

## 0. Antes de empezar

- Un proyecto de Google Cloud con facturación activa.
- La contraseña de `agente@alzatec.com`.
- La API key de OpenAI.

## 1. Variables

```bash
PROYECTO=el-id-de-tu-proyecto
REGION=southamerica-west1          # Santiago
gcloud config set project $PROYECTO
```

## 2. Activar los servicios

```bash
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 3. Guardar las claves

`read -s` las pide sin mostrarlas ni dejarlas en el historial.

```bash
read -s -p "Contraseña de agente@: " X && printf '%s' "$X" | gcloud secrets create agente-pw --data-file=- && unset X
read -s -p "API key de OpenAI: " X && printf '%s' "$X" | gcloud secrets create openai-api-key --data-file=- && unset X
```

## 4. Cuenta de servicio

```bash
gcloud iam service-accounts create clasificador --display-name "Clasificador de correos"
SA=clasificador@$PROYECTO.iam.gserviceaccount.com
for S in agente-pw openai-api-key; do
  gcloud secrets add-iam-policy-binding $S --member serviceAccount:$SA --role roles/secretmanager.secretAccessor
done
gcloud projects add-iam-policy-binding $PROYECTO --member serviceAccount:$SA --role roles/run.invoker
```

## 5. Subir el clasificador

Desde la carpeta del repositorio (`git clone` en Cloud Shell). `DESDE` evita procesar de golpe los correos que se acumularon en `agente@` antes de la puesta en marcha: poner la fecha de inicio.

```bash
COMUN="--region $REGION --service-account $SA --cpu 1 --memory 512Mi --max-retries 0 \
  --set-secrets AGENTE_PW=agente-pw:latest,OPENAI_API_KEY=openai-api-key:latest \
  --set-env-vars MODO=vivo,MODELO=openai:gpt-6.1-sol,ESFUERZO=medium,DESDE=19-Oct-2026"

gcloud run jobs deploy clasificador --source . $COMUN --task-timeout 10m --args procesar
IMAGEN=$(gcloud run jobs describe clasificador --region $REGION --format 'value(spec.template.spec.template.spec.containers[0].image)')
gcloud run jobs deploy clasificador-resumen --image $IMAGEN $COMUN --task-timeout 5m --args resumen
```

## 6. Primera corrida a mano

```bash
gcloud run jobs execute clasificador --region $REGION --wait
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="clasificador"' --limit 30 --format 'value(textPayload)'
```

Cada correo deja una línea con su categoría, el costo y si quedó para revisar. Los reenvíos llegan a las casillas reales.

## 7. Programar

```bash
URI=https://run.googleapis.com/v2/projects/$PROYECTO/locations/$REGION/jobs
gcloud scheduler jobs create http clasificador-cada-3-min --location $REGION \
  --schedule "*/3 * * * *" --time-zone America/Santiago \
  --uri $URI/clasificador:run --http-method POST --oauth-service-account-email $SA
gcloud scheduler jobs create http clasificador-resumen-diario --location $REGION \
  --schedule "45 17 * * 1-5" --time-zone America/Santiago \
  --uri $URI/clasificador-resumen:run --http-method POST --oauth-service-account-email $SA
```

Si Cloud Scheduler no está disponible en `southamerica-west1`, usar `--location southamerica-east1` solo en estos dos comandos.

## 7b. Alerta de respaldo de Google Cloud

Las alertas normales (sin saldo en OpenAI, API key inválida, caída del proveedor) las manda el propio clasificador desde `agente@` a `lbpiphone4@gmail.com`. Pero si lo que falla es la casilla `agente@` (por ejemplo, alguien cambió su contraseña), no puede mandar correos. Para ese caso, Google Cloud avisa por su cuenta:

```bash
gcloud logging metrics create clasificador-errores \
  --description "Corridas del clasificador que terminaron con error" \
  --log-filter 'resource.type="cloud_run_job" AND resource.labels.job_name=~"^clasificador" AND severity>=ERROR'
for C in lbpiphone4@gmail.com; do
  gcloud beta monitoring channels create --display-name "Alertas $C" --type email --channel-labels email_address=$C
done
CANALES=$(gcloud beta monitoring channels list --filter 'type="email"' --format 'value(name)' | paste -sd, -)
gcloud alpha monitoring policies create --policy-from-file deploy/alerta-errores.json --notification-channels $CANALES
```

Google avisa una vez cuando empieza el problema y otra cuando se resuelve.

## 8. Modo sombra (opcional)

Si alguna vez se quiere probar un cambio sin tocar las casillas reales, todo se puede mandar a una casilla de prueba (`MODO=sombra,CASILLA_PRUEBA=correo@...`). Para volver:

```bash
for J in clasificador clasificador-resumen; do
  gcloud run jobs update $J --region $REGION --update-env-vars MODO=vivo
done
```

El resumen diario de lo descartado llega por defecto a los mismos correos de las alertas. Para que le llegue a Andrea: `--update-env-vars "RESUMEN_A=asistentetecnico@alzatec.com"` en el job `clasificador-resumen`.

## Costos

- **Google Cloud:** casi nada (unos US$0–5 al mes) con una corrida cada 3 minutos.
- **Modelo:** unos US$40–60 al mes con ~2.000 correos. La cuenta de OpenAI tiene un tope de gasto mensual de US$65.

## Si algo falla

- El correo **no se pierde**: queda en `agente@` sin la marca `Clasificado` y se reintenta en la próxima corrida (o a los 30 minutos si una corrida se cayó a la mitad).
- Si el modelo falla con un correo, ese correo va a pendientes con `[REVISAR]`.
- Si falla el servicio (sin saldo, API key inválida, caída de OpenAI, contraseña de `agente@`), la corrida se detiene sin tocar los correos y llega una alerta a `lbpiphone4@gmail.com` que dice **qué pasó y qué hacer**. El mismo aviso no se repite antes de 3 horas, y cuando se resuelve llega un correo de confirmación. Para cambiar los destinatarios: variable `ALERTAS_A`.

## Segunda opinión (opcional, apagada)

El código permite que un segundo modelo revise los correos que el principal marca como "acordado". Está apagada. Solo se activaría si la evaluación o el uso real muestran errores graves que un segundo modelo atraparía:

```bash
gcloud run jobs update clasificador --region $REGION --update-env-vars VERIFICADOR=anthropic:claude-sonnet-5-5
```

(Requiere además guardar la API key de Anthropic como secreto y pasarla como `ANTHROPIC_API_KEY`.)

## Acceso de Claude

Para que Claude (Claude Code en la nube) pueda operar el clasificador sin pasar por Cloud Shell:

1. En Cloud Shell: `git -C alzatec pull -q; bash alzatec/deploy/acceso-claude.sh`. Crea la cuenta `claude-operador` con permiso de Editor solo en este proyecto y una clave. Si la organización bloquea las claves, pregunta antes de permitirlas solo en este proyecto.
2. Copiar la clave que muestra y agregarla en la configuración del entorno de Claude Code (nunca en el chat): Entorno → engranaje → **Secretos de red** → Agregar secreto → tipo **"GCP access token (with Service Account Key)"**. La clave queda en el entorno y no entra a la sesión.
3. Abrir una sesión nueva de Claude Code en el mismo entorno. Claude se conecta con `bash deploy/claude-login.sh`.

Para quitar el acceso: `gcloud iam service-accounts delete claude-operador@alzatec.iam.gserviceaccount.com`.
