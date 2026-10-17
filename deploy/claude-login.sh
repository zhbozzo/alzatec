#!/usr/bin/env bash
# Para Claude: conecta gcloud en la sesión con la clave del entorno (variable GCP_SA_KEY, la crea acceso-claude.sh).
# Uso:  bash deploy/claude-login.sh
set -euo pipefail
unset CLOUDSDK_AUTH_ACCESS_TOKEN
[ -n "${GCP_SA_KEY:-}" ] || {
  echo "Falta la variable de entorno GCP_SA_KEY: el usuario debe correr deploy/acceso-claude.sh en Cloud Shell"
  echo "y agregarla en la configuración del entorno de Claude Code (nunca por el chat)."
  exit 1
}
DIR=$(mktemp -d)
trap 'rm -rf "$DIR"' EXIT
if [ "${GCP_SA_KEY:0:1}" = "{" ]; then
  printf '%s' "$GCP_SA_KEY" > "$DIR/clave.json"
else
  printf '%s' "$GCP_SA_KEY" | base64 -d > "$DIR/clave.json"
fi
gcloud auth activate-service-account --key-file "$DIR/clave.json" --quiet
gcloud config set project "$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["project_id"])' "$DIR/clave.json")" --quiet
gcloud config list --format 'value(core.account,core.project)'
echo "Ojo: en Claude Code hay que correr gcloud con  unset CLOUDSDK_AUTH_ACCESS_TOKEN  antes (el entorno pone un token de relleno)."
