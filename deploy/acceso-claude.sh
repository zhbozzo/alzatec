#!/usr/bin/env bash
# Le da acceso a Claude (Claude Code en la nube) para operar el clasificador en Google Cloud:
# ver registros, corregir, subir versiones nuevas y reprogramar sin pasar por ti.
# Crea la cuenta claude-operador con permiso de Editor SOLO en este proyecto: no ve otros proyectos,
# no toca la organización ni la facturación y no puede cambiar permisos.
# Correr en Cloud Shell:  bash alzatec/deploy/acceso-claude.sh
# Para quitarle el acceso en cualquier momento:
#   gcloud iam service-accounts delete claude-operador@alzatec.iam.gserviceaccount.com
set -euo pipefail
PROYECTO=${PROYECTO:-$(gcloud config get-value project 2>/dev/null || true)}
[ -n "$PROYECTO" ] || { echo "Primero: gcloud config set project alzatec"; exit 1; }
SA=claude-operador@$PROYECTO.iam.gserviceaccount.com
ARCHIVO=$HOME/clave-claude.txt
DIR=$(mktemp -d)
trap 'rm -rf "$DIR"' EXIT

cat <<EOF
Esto le da a Claude permiso de Editor en el proyecto $PROYECTO (y solo en ese proyecto):
podrá ver registros, cambiar y subir el clasificador, reprogramarlo, y crear o borrar cosas
dentro del proyecto. No podrá tocar otros proyectos, la organización, la facturación ni los permisos.
La clave se guarda en la configuración del entorno de Claude Code. Para quitar el acceso:
  gcloud iam service-accounts delete $SA
EOF
read -r -p "¿Continuar? (s/N): " R
[[ "$R" =~ ^[sS] ]] || { echo "Cancelado, no se hizo nada."; exit 0; }

echo "== Cuenta para Claude"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create claude-operador --display-name "Claude: operación del clasificador" >/dev/null
for _ in 1 2 3 4 5; do   # una cuenta recién creada tarda unos segundos en poder recibir permisos
  gcloud projects add-iam-policy-binding "$PROYECTO" --member "serviceAccount:$SA" --role roles/editor \
    --condition None >/dev/null 2>&1 && break
  sleep 10
done
gcloud projects add-iam-policy-binding "$PROYECTO" --member "serviceAccount:$SA" --role roles/editor \
  --condition None >/dev/null
echo "   claude-operador: Editor en $PROYECTO"

echo "== Clave (queda una sola: las anteriores se borran)"
for K in $(gcloud iam service-accounts keys list --iam-account "$SA" --managed-by user --format 'value(name.basename())'); do
  gcloud iam service-accounts keys delete "$K" --iam-account "$SA" --quiet >/dev/null
done
crear_clave() {
  rm -f "$DIR/clave.json"
  gcloud iam service-accounts keys create "$DIR/clave.json" --iam-account "$SA" >/dev/null 2>"$DIR/error"
}
if ! crear_clave; then
  RESTRICCION=$(grep -o 'constraints/[A-Za-z.]*' "$DIR/error" | head -1 | sed 's#constraints/##; s/\.$//' || true)
  if [ -z "$RESTRICCION" ]; then cat "$DIR/error"; exit 1; fi
  cat <<EOF

La organización bloquea por defecto las claves de cuentas de servicio ($RESTRICCION).
Para seguir hay que permitirlas SOLO en el proyecto $PROYECTO (el resto de la organización queda igual).
Para eso tu usuario recibe el rol de administrador de políticas de la organización.
EOF
  read -r -p "¿Permitir las claves en $PROYECTO? (s/N): " R
  [[ "$R" =~ ^[sS] ]] || { echo "Cancelado. La cuenta quedó creada pero sin clave."; exit 0; }
  YO=$(gcloud config get-value account 2>/dev/null)
  ORG=$(gcloud projects get-ancestors "$PROYECTO" --format 'value(id,type)' | awk '$2=="organization"{print $1}')
  gcloud services enable orgpolicy.googleapis.com >/dev/null
  if [ -n "$ORG" ]; then
    gcloud organizations add-iam-policy-binding "$ORG" --member "user:$YO" \
      --role roles/orgpolicy.policyAdmin --condition None >/dev/null
  fi
  printf 'name: projects/%s/policies/%s\nspec:\n  rules:\n  - enforce: false\n' "$PROYECTO" "$RESTRICCION" > "$DIR/politica.yaml"
  for _ in $(seq 12); do gcloud org-policies set-policy "$DIR/politica.yaml" >/dev/null 2>&1 && break; sleep 10; done
  echo "   Esperando que Google aplique el cambio (hasta 3 minutos)..."
  for _ in $(seq 18); do crear_clave && break; sleep 10; done
  [ -s "$DIR/clave.json" ] || { echo "   No se pudo crear la clave:"; cat "$DIR/error"; exit 1; }
fi
base64 -w0 "$DIR/clave.json" > "$ARCHIVO"

cat <<'EOF'

Clave creada. Ahora:
 1. Arriba se abre el archivo clave-claude.txt: selecciona todo (Cmd+A) y copia (Cmd+C).
 2. NO la pegues en el chat de Claude: va en la CONFIGURACIÓN DEL ENTORNO de Claude Code.
    Arriba, en la barra de título de la sesión, haz clic en el nombre del entorno (ícono de nube) → Edit
    → Variables de entorno. Agrega una línea que empiece con  GCP_SA_KEY=  y pega la clave justo
    después del =, sin espacios. Guarda.
 3. Vuelve aquí y aprieta Enter: el archivo se borra de Cloud Shell. Cierra la pestaña del archivo sin guardar.
EOF
cloudshell edit "$ARCHIVO" 2>/dev/null || echo "   (No se abrió solo: ábrelo con  cloudshell edit ~/clave-claude.txt)"
read -r -p "Enter cuando la hayas pegado en Claude Code... " _
rm -f "$ARCHIVO"
echo "Listo, archivo borrado. Abre una sesión nueva de Claude Code en el mismo entorno: ahí Claude ya tiene acceso."
