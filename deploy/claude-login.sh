#!/usr/bin/env bash
# Para Claude: conecta gcloud en la sesión. Dos formas (las prepara acceso-claude.sh):
#  - secreto de red del entorno, tipo "GCP access token (with Service Account Key)": el entorno cambia
#    el token de relleno CLOUDSDK_AUTH_ACCESS_TOKEN por uno real; la clave nunca entra a la sesión.
#  - variable de entorno GCP_SA_KEY con la clave (JSON o base64): se activa la cuenta y se quita el token de relleno.
# Uso:  bash deploy/claude-login.sh
set -euo pipefail
PROYECTO=alzatec
if [ -n "${GCP_SA_KEY:-}" ]; then
  unset CLOUDSDK_AUTH_ACCESS_TOKEN
  DIR=$(mktemp -d)
  trap 'rm -rf "$DIR"' EXIT
  if [ "${GCP_SA_KEY:0:1}" = "{" ]; then
    printf '%s' "$GCP_SA_KEY" > "$DIR/clave.json"
  else
    printf '%s' "$GCP_SA_KEY" | base64 -d > "$DIR/clave.json"
  fi
  gcloud auth activate-service-account --key-file "$DIR/clave.json" --quiet
  PROYECTO=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["project_id"])' "$DIR/clave.json")
fi
gcloud config set project "$PROYECTO" --quiet 2>/dev/null
if gcloud run jobs list --region southamerica-west1 --format 'value(name)' >/dev/null 2>&1; then
  echo "Conectado a Google Cloud, proyecto $PROYECTO."
else
  echo "No hay acceso a Google Cloud desde esta sesión."
  echo "El usuario corre deploy/acceso-claude.sh en Cloud Shell y agrega la clave en la configuración del entorno"
  echo "de Claude Code: Secretos de red → Agregar secreto → tipo \"GCP access token (with Service Account Key)\"."
  echo "Nunca por el chat. La toma una sesión nueva."
  exit 1
fi
