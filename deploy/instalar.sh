#!/usr/bin/env bash
# Instala el clasificador en Google Cloud y hace la primera corrida.
# Reenvía directo a las casillas reales: despachosconfirmados@, retirosconfirmados@ y pendientesdespachoyrecepcion@.
# Correr en Cloud Shell, desde la carpeta del repositorio:  bash deploy/instalar.sh
# Las claves se escriben aquí mismo y quedan en Secret Manager; no se muestran ni se guardan en el historial.
set -euo pipefail
[ -f Dockerfile ] && [ -d clasificador ] || { echo "Correr desde la carpeta del repositorio (donde está el Dockerfile)."; exit 1; }

read -r -p "ID del proyecto de Google Cloud: " PROYECTO
REGION=${REGION:-southamerica-west1}
DESDE=$(LC_ALL=C date +%d-%b-%Y)   # solo correos llegados desde hoy

gcloud config set project "$PROYECTO" >/dev/null

echo "== 1/5 Activando servicios de Google Cloud"
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com logging.googleapis.com monitoring.googleapis.com

echo "== 2/5 Guardando las claves en Secret Manager"
crear_secreto() {
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    echo "   $1 ya existe (para cambiarla: gcloud secrets versions add $1 --data-file=-)"
  else
    read -r -s -p "   $2: " X; echo
    printf '%s' "$X" | gcloud secrets create "$1" --data-file=- >/dev/null
    unset X
  fi
}
crear_secreto agente-pw "Contraseña de agente@alzatec.com"
crear_secreto openai-api-key "API key de OpenAI"

echo "== 3/5 Cuenta de servicio con permisos mínimos"
SA=clasificador@$PROYECTO.iam.gserviceaccount.com
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create clasificador --display-name "Clasificador de correos"
for S in agente-pw openai-api-key; do
  gcloud secrets add-iam-policy-binding "$S" --member "serviceAccount:$SA" \
    --role roles/secretmanager.secretAccessor >/dev/null
done
gcloud projects add-iam-policy-binding "$PROYECTO" --member "serviceAccount:$SA" \
  --role roles/run.invoker --condition None >/dev/null

echo "== 4/5 Subiendo el clasificador (tarda unos minutos)"
COMUN=(--region "$REGION" --service-account "$SA" --cpu 1 --memory 512Mi --max-retries 0
  --set-secrets AGENTE_PW=agente-pw:latest,OPENAI_API_KEY=openai-api-key:latest
  --set-env-vars "MODO=vivo,MODELO=openai:gpt-6.1-sol,ESFUERZO=medium,DESDE=$DESDE")
gcloud run jobs deploy clasificador --source . "${COMUN[@]}" --task-timeout 10m --args procesar
IMAGEN=$(gcloud run jobs describe clasificador --region "$REGION" \
  --format 'value(spec.template.spec.template.spec.containers[0].image)')
gcloud run jobs deploy clasificador-resumen --image "$IMAGEN" "${COMUN[@]}" --task-timeout 5m --args resumen

echo "== 5/5 Primera corrida (correos llegados a agente@ desde hoy)"
gcloud run jobs execute clasificador --region "$REGION" --wait || true
sleep 20
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="clasificador"' \
  --limit 30 --freshness 30m \
  --format 'value(jsonPayload.evento,jsonPayload.categoria,jsonPayload.asunto,jsonPayload.costo_usd,jsonPayload.error,textPayload)'

echo
echo "Listo. Arriba aparece cada correo procesado con su categoría; los despachos, recepciones y pendientes"
echo "ya se reenviaron a sus casillas. Si se ve bien, el siguiente paso es: bash deploy/activar.sh"
