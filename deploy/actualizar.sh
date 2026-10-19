#!/usr/bin/env bash
# Sube una versión nueva del código a los dos jobs, sin tocar claves, variables ni programación. No pregunta nada.
# Uso, desde la carpeta del repositorio:  bash deploy/actualizar.sh
set -euo pipefail
# En Claude Code: con la clave en la variable GCP_SA_KEY se usa la cuenta activada y hay que quitar el token de relleno;
# con la clave como secreto de red, ese token es el que el entorno cambia por uno real y se deja.
if [ -n "${GCP_SA_KEY:-}" ]; then unset CLOUDSDK_AUTH_ACCESS_TOKEN; fi
cd "$(dirname "$0")/.."
REGION=${REGION:-southamerica-west1}
gcloud run jobs deploy clasificador --source . --region "$REGION" --quiet
IMAGEN=$(gcloud run jobs describe clasificador --region "$REGION" \
  --format 'value(spec.template.spec.template.spec.containers[0].image)')
gcloud run jobs update clasificador-resumen --image "$IMAGEN" --region "$REGION" --quiet
echo "Versión nueva arriba: $IMAGEN"
