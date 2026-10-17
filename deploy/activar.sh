#!/usr/bin/env bash
# Deja el clasificador corriendo solo: cada 3 minutos, resumen diario y alertas de Google Cloud.
# Correr en Cloud Shell después de instalar.sh:  bash deploy/activar.sh
set -euo pipefail

PROYECTO=$(gcloud config get-value project 2>/dev/null)
REGION=${REGION:-southamerica-west1}
SA=clasificador@$PROYECTO.iam.gserviceaccount.com
URI=https://run.googleapis.com/v2/projects/$PROYECTO/locations/$REGION/jobs

echo "Proyecto: $PROYECTO"
echo "¿A dónde reenviar los correos clasificados?"
echo "  1) A las casillas reales de Alzatec (despachosconfirmados@, retirosconfirmados@, pendientesdespachoyrecepcion@)"
echo "  2) Seguir en modo sombra, todo a la casilla de prueba"
read -r -p "Opción [1]: " OPCION
if [ "${OPCION:-1}" = "1" ]; then
  for J in clasificador clasificador-resumen; do
    gcloud run jobs update "$J" --region "$REGION" --update-env-vars "MODO=vivo,PREFIJO=[PRUEBA]" >/dev/null
  done
  echo "   Modo vivo, con [PRUEBA] en el asunto mientras se valida."
fi

programar() {  # nombre, horario, job
  if gcloud scheduler jobs describe "$1" --location "$REGION" >/dev/null 2>&1; then
    echo "   $1 ya existe"
    return
  fi
  for LOC in "$REGION" southamerica-east1; do   # si Scheduler no está en Santiago, usa São Paulo
    if gcloud scheduler jobs create http "$1" --location "$LOC" --schedule "$2" --time-zone America/Santiago \
      --uri "$URI/$3:run" --http-method POST --oauth-service-account-email "$SA" >/dev/null 2>&1; then
      echo "   $1 creado ($LOC)"
      return
    fi
  done
  echo "   No se pudo crear $1; ver deploy/README.md paso 7"; return 1
}
echo "== Programando"
programar clasificador-cada-3-min "*/3 * * * *" clasificador
programar clasificador-resumen-diario "45 17 * * 1-5" clasificador-resumen

echo "== Alerta de respaldo de Google Cloud (si falla la propia casilla agente@)"
gcloud logging metrics describe clasificador-errores >/dev/null 2>&1 || \
  gcloud logging metrics create clasificador-errores \
    --description "Corridas del clasificador que terminaron con error" \
    --log-filter 'resource.type="cloud_run_job" AND resource.labels.job_name=~"^clasificador" AND severity>=ERROR'
CANALES=()
for C in lbozzo@fen.uchile.cl lbpiphone4@gmail.com; do
  N=$(gcloud beta monitoring channels list --filter "labels.email_address=\"$C\"" --format 'value(name)' | head -1)
  if [ -z "$N" ]; then
    N=$(gcloud beta monitoring channels create --display-name "Alertas $C" --type email \
      --channel-labels "email_address=$C" --format 'value(name)')
  fi
  CANALES+=("$N")
done
if [ -z "$(gcloud alpha monitoring policies list --filter 'displayName="Clasificador de correos: corrida con error"' --format 'value(name)')" ]; then
  gcloud alpha monitoring policies create --policy-from-file deploy/alerta-errores.json \
    --notification-channels "$(IFS=,; echo "${CANALES[*]}")" >/dev/null
fi
echo "   Alerta lista"

echo
echo "Listo: el clasificador revisa agente@ cada 3 minutos."
echo "Registros: Cloud Run → Jobs → clasificador → Registros."
