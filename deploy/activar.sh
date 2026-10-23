#!/usr/bin/env bash
# Deja el clasificador corriendo solo: cada 3 minutos, resumen diario y alertas de Google Cloud.
# instalar.sh lo llama al final; también se puede correr aparte:  bash deploy/activar.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PROYECTO=$(gcloud config get-value project 2>/dev/null)
REGION=${REGION:-southamerica-west1}
SA=clasificador@$PROYECTO.iam.gserviceaccount.com
URI=https://run.googleapis.com/v2/projects/$PROYECTO/locations/$REGION/jobs

echo "== Programando (proyecto $PROYECTO)"
programar() {  # nombre, horario, job
  local LOC
  for LOC in "$REGION" southamerica-east1; do   # si Scheduler no está en Santiago, usa São Paulo
    if gcloud scheduler jobs describe "$1" --location "$LOC" >/dev/null 2>&1; then
      echo "   $1 ya estaba programado ($LOC)"
      return 0
    fi
  done
  for LOC in "$REGION" southamerica-east1; do
    if gcloud scheduler jobs create http "$1" --location "$LOC" --schedule "$2" --time-zone America/Santiago \
      --uri "$URI/$3:run" --http-method POST --oauth-service-account-email "$SA" >/dev/null 2>&1; then
      echo "   $1 programado ($LOC)"
      return 0
    fi
  done
  echo "   No se pudo programar $1; ver deploy/README.md paso 7"
  return 1
}
programar clasificador-cada-3-min "*/3 * * * *" clasificador
programar clasificador-resumen-diario "45 17 * * 1-5" clasificador-resumen

echo "== Alerta de respaldo de Google Cloud (por si falla la propia casilla agente@)"
alerta() {
  gcloud logging metrics describe clasificador-errores >/dev/null 2>&1 || \
    gcloud logging metrics create clasificador-errores \
      --description "Corridas del clasificador que terminaron con error" \
      --log-filter 'resource.type="cloud_run_job" AND resource.labels.job_name=~"^clasificador" AND severity>=ERROR' \
      >/dev/null
  local C N CANALES=()
  for C in lbpiphone4@gmail.com; do
    N=$(gcloud beta monitoring channels list --filter "labels.email_address=\"$C\"" --format 'value(name)' | head -1)
    if [ -z "$N" ]; then
      N=$(gcloud beta monitoring channels create --display-name "Alertas $C" --type email \
        --channel-labels "email_address=$C" --format 'value(name)')
    fi
    CANALES+=("$N")
  done
  if [ -z "$(gcloud alpha monitoring policies list \
      --filter 'displayName="Clasificador de correos: corrida con error"' --format 'value(name)')" ]; then
    for _ in 1 2 3 4 5 6; do   # la métrica recién creada tarda un poco en estar disponible para alertas
      gcloud alpha monitoring policies create --policy-from-file deploy/alerta-errores.json \
        --notification-channels "$(IFS=,; echo "${CANALES[*]}")" >/dev/null 2>&1 && return 0
      sleep 20
    done
    return 1
  fi
}
if alerta; then
  echo "   Alerta lista"
else
  echo "   No se pudo crear la alerta de respaldo (no es grave: las alertas por correo desde agente@ funcionan igual)."
  echo "   Se puede reintentar después con: bash deploy/activar.sh"
fi

echo
echo "Listo: el clasificador revisa agente@ cada 3 minutos."
echo "Registros: console.cloud.google.com → Cloud Run → Jobs → clasificador → Registros."
