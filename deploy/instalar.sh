#!/usr/bin/env bash
# Instala el clasificador en Google Cloud: prueba las claves, sube el código, hace la primera corrida
# y lo deja revisando agente@ cada 3 minutos.
# Reenvía directo a las casillas reales: despachosconfirmados@, devolucionesconfirmadas@ y pendientesdespachoyrecepcion@.
# Correr en Cloud Shell:  bash alzatec/deploy/instalar.sh
# Se puede volver a correr cuantas veces haga falta: lo que ya está hecho se salta.
# Las claves se escriben aquí mismo, se prueban y quedan en Secret Manager; no se muestran ni se guardan en el historial.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f Dockerfile ] && [ -d clasificador ] || { echo "No encuentro el código del clasificador."; exit 1; }

REGION=${REGION:-southamerica-west1}
MODELO=${MODELO:-openai:gpt-6.1-sol}

echo "== 1/6 Proyecto de Google Cloud"
if [ -z "${PROYECTO:-}" ]; then
  ACTUAL=$(gcloud config get-value project 2>/dev/null || true)
  R=n
  [ -z "$ACTUAL" ] || read -r -p "   Usar el proyecto $ACTUAL? (S/n): " R
  if [ -n "$ACTUAL" ] && [[ ! "$R" =~ ^[nN] ]]; then
    PROYECTO=$ACTUAL
  else
    gcloud projects list --format 'table(projectId,name)'
    read -r -p "   ID del proyecto (columna PROJECT_ID): " PROYECTO
  fi
fi
gcloud projects describe "$PROYECTO" >/dev/null 2>&1 || {
  echo "   No encuentro el proyecto '$PROYECTO'. Hay que usar el ID (columna PROJECT_ID), no el nombre."; exit 1; }
gcloud config set project "$PROYECTO" >/dev/null 2>&1
echo "   Proyecto: $PROYECTO"

echo "== 2/6 Activando servicios (la primera vez tarda 1 o 2 minutos)"
if ! gcloud services enable run.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com \
    cloudbuild.googleapis.com artifactregistry.googleapis.com logging.googleapis.com monitoring.googleapis.com; then
  echo "   No se pudieron activar. Lo más común: el proyecto no tiene la facturación activada."
  echo "   Actívala aquí y vuelve a correr el mismo comando:"
  echo "   https://console.cloud.google.com/billing/linkedaccount?project=$PROYECTO"
  exit 1
fi
echo "   Preparando Compute Engine (puede tardar un par de minutos sin mostrar nada)..."
# Crea la cuenta con la que Cloud Build arma la imagen en los proyectos nuevos
gcloud services enable compute.googleapis.com >/dev/null 2>&1 || true

echo "== 3/6 Claves (se prueban antes de guardarlas)"
probar() {  # tipo, clave → 0 bien, 1 mala, 2 no se pudo probar, 3 falta algo en la cuenta
  CLAVE="$2" python3 deploy/verificar.py "$1" "${MODELO#*:}"
}
guardar() {  # secreto, valor
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    printf '%s' "$2" | gcloud secrets versions add "$1" --data-file=- >/dev/null
  else
    printf '%s' "$2" | gcloud secrets create "$1" --data-file=- >/dev/null
  fi
}
clave() {  # secreto, tipo, texto
  local X="" r
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    X=$(gcloud secrets versions access latest --secret "$1" 2>/dev/null || true)
    if [ -n "$X" ]; then
      echo "   $3: ya estaba guardada, probándola..."
      r=0; probar "$2" "$X" || r=$?
      case $r in 0|2) return 0 ;; 3) exit 1 ;; esac
      echo "   Hay que escribirla de nuevo."
    fi
  fi
  for _ in 1 2 3; do
    read -r -s -p "   $3 (al pegarla no se ve nada; después Enter): " X; echo
    X="${X#"${X%%[![:space:]]*}"}"; X="${X%"${X##*[![:space:]]}"}"   # sin espacios al inicio ni al final
    [ -n "$X" ] || continue
    r=0; probar "$2" "$X" || r=$?
    if [ "$r" != 1 ]; then
      guardar "$1" "$X"
      echo "   Guardada en Secret Manager."
      [ "$r" != 3 ] || exit 1   # la clave quedó guardada; falta arreglar la cuenta y volver a correr
      return 0
    fi
  done
  echo "   Tres intentos sin éxito. Revisa la clave y vuelve a correr el mismo comando."
  exit 1
}
clave agente-pw agente "Contraseña de agente@alzatec.com"
clave openai-api-key openai "API key de OpenAI"

echo "== 4/6 Cuenta de servicio con permisos mínimos"
reintentar() {  # los permisos de una cuenta recién creada tardan unos segundos en estar disponibles
  for _ in 1 2 3 4 5 6; do "$@" >/dev/null 2>&1 && return 0; sleep 10; done
  "$@" >/dev/null
}
SA=clasificador@$PROYECTO.iam.gserviceaccount.com
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create clasificador --display-name "Clasificador de correos" >/dev/null
for S in agente-pw openai-api-key; do
  reintentar gcloud secrets add-iam-policy-binding "$S" --member "serviceAccount:$SA" \
    --role roles/secretmanager.secretAccessor
done
reintentar gcloud projects add-iam-policy-binding "$PROYECTO" --member "serviceAccount:$SA" \
  --role roles/run.invoker --condition None
# Cloud Build arma la imagen con la cuenta de Compute Engine. En proyectos dentro de una organización
# esa cuenta nace sin permisos, así que se le dan los justos para armar la imagen.
NUM=$(gcloud projects describe "$PROYECTO" --format 'value(projectNumber)')
CB=$NUM-compute@developer.gserviceaccount.com
for _ in $(seq 18); do gcloud iam service-accounts describe "$CB" >/dev/null 2>&1 && break; sleep 10; done
for ROL in roles/run.builder roles/logging.logWriter roles/artifactregistry.writer roles/storage.objectViewer; do
  reintentar gcloud projects add-iam-policy-binding "$PROYECTO" --member "serviceAccount:$CB" \
    --role "$ROL" --condition None 2>/dev/null || echo "   (no se pudo dar $ROL a la cuenta de Cloud Build; si falla el paso 5, avisar)"
done

echo "== 5/6 Subiendo el clasificador (tarda 3 a 5 minutos)"
# Fecha desde la que se clasifica: si ya estaba instalado se mantiene; si no, desde hoy
if [ -z "${DESDE:-}" ]; then
  DESDE=$(gcloud run jobs describe clasificador --region "$REGION" --format json 2>/dev/null | python3 -c '
import json, sys
try:
    env = json.load(sys.stdin)["spec"]["template"]["spec"]["template"]["spec"]["containers"][0].get("env", [])
    print(next((e.get("value", "") for e in env if e.get("name") == "DESDE"), ""))
except Exception:
    pass' || true)
  DESDE=${DESDE:-$(TZ=America/Santiago LC_ALL=C date +%d-%b-%Y)}
fi
echo "   Clasifica los correos llegados a agente@ desde el $DESDE"
gcloud artifacts repositories describe cloud-run-source-deploy --location "$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create cloud-run-source-deploy --repository-format docker \
    --location "$REGION" --description "Imágenes del clasificador" >/dev/null
COMUN=(--region "$REGION" --service-account "$SA" --cpu 1 --memory 512Mi --max-retries 0
  --set-secrets AGENTE_PW=agente-pw:latest,OPENAI_API_KEY=openai-api-key:latest
  --set-env-vars "MODO=vivo,MODELO=$MODELO,ESFUERZO=medium,DESDE=$DESDE" --quiet)
gcloud run jobs deploy clasificador --source . "${COMUN[@]}" --task-timeout 10m --args procesar
IMAGEN=$(gcloud run jobs describe clasificador --region "$REGION" \
  --format 'value(spec.template.spec.template.spec.containers[0].image)')
gcloud run jobs deploy clasificador-resumen --image "$IMAGEN" "${COMUN[@]}" --task-timeout 5m --args resumen

echo "== 6/6 Primera corrida"
INICIO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if gcloud run jobs execute clasificador --region "$REGION" --wait; then BIEN=1; else BIEN=0; fi
FILTRO="resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"clasificador\" AND timestamp>=\"$INICIO\""
for _ in $(seq 12); do   # los registros tardan unos segundos en aparecer
  [ -z "$(gcloud logging read "$FILTRO AND (jsonPayload.evento=\"corrida\" OR jsonPayload.evento=\"error\")" --limit 1 \
    --format 'value(timestamp)' 2>/dev/null)" ] || break
  sleep 5
done
echo "   Lo que hizo (evento, categoría, asunto, costo en US\$, error):"
gcloud logging read "$FILTRO" --order asc --limit 80 \
  --format 'value(jsonPayload.evento,jsonPayload.categoria,jsonPayload.asunto,jsonPayload.costo_usd,jsonPayload.error,textPayload)'
echo

if [ "$BIEN" != 1 ]; then
  echo "La primera corrida terminó con error: arriba sale el motivo (y debería llegar un correo de alerta)."
  echo "Cuando esté arreglado, vuelve a correr el mismo comando."
  exit 1
fi
echo "La primera corrida salió bien. Los despachos, recepciones y pendientes de arriba ya se reenviaron."
R=""
read -r -p "¿Dejarlo funcionando solo, revisando agente@ cada 3 minutos? (S/n): " R
if [[ "$R" =~ ^[nN] ]]; then
  echo "Quedó instalado pero sin programar. Para programarlo después: bash deploy/activar.sh"
else
  REGION=$REGION bash deploy/activar.sh
fi
