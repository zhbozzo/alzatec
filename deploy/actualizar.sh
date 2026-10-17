#!/usr/bin/env bash
# Sube una versión nueva del código a los dos jobs, sin tocar claves, variables ni programación. No pregunta nada.
# Uso, desde la carpeta del repositorio:  bash deploy/actualizar.sh
set -euo pipefail
cd "$(dirname "$0")/.."
REGION=${REGION:-southamerica-west1}
gcloud run jobs deploy clasificador --source . --region "$REGION" --quiet
IMAGEN=$(gcloud run jobs describe clasificador --region "$REGION" \
  --format 'value(spec.template.spec.template.spec.containers[0].image)')
gcloud run jobs update clasificador-resumen --image "$IMAGEN" --region "$REGION" --quiet
echo "Versión nueva arriba: $IMAGEN"
