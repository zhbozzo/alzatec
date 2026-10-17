#!/usr/bin/env bash
# Muestra qué ha hecho el clasificador: últimas corridas, correos clasificados, errores y gasto.
# Correr en Cloud Shell:  bash alzatec/deploy/ver.sh        (últimas 24 horas)
#                         HORAS=72 bash alzatec/deploy/ver.sh
set -euo pipefail
unset CLOUDSDK_AUTH_ACCESS_TOKEN   # en Claude Code el entorno pone un token de relleno que tapa la cuenta activa
REGION=${REGION:-southamerica-west1}
HORAS=${HORAS:-24}
DESDE=$(date -u -d "-$HORAS hours" +%Y-%m-%dT%H:%M:%SZ)

echo "== Últimas corridas (una cada 3 minutos; ✔ = salió bien)"
gcloud run jobs executions list --job clasificador --region "$REGION" --limit 5

echo
echo "== Correos de las últimas $HORAS horas (hora de Chile)"
PY=$(cat <<'EOF'
import json, sys
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

chile = ZoneInfo("America/Santiago")
entradas = json.load(sys.stdin)
categorias, costo, revisar, errores = Counter(), 0.0, 0, []
for e in entradas:
    p = e.get("jsonPayload") or {}
    hora = datetime.strptime(e["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    hora = hora.astimezone(chile).strftime("%d/%m %H:%M")
    if p.get("evento") == "error":
        errores.append(f"{hora}  {p.get('error', '')[:150]}")
        continue
    cat = p.get("categoria", "?")
    categorias[cat] += 1
    costo += p.get("costo_usd") or 0
    revisar += bool(p.get("revisar"))
    marca = " [REVISAR]" if p.get("revisar") else ""
    print(f"{hora}  {cat:<19}{marca:<10} {(p.get('asunto') or '')[:70]}")
if not categorias:
    print("(ningún correo en este período)")
print()
print("Total:", ", ".join(f"{c} {n}" for c, n in categorias.most_common()) or "0")
print(f"Para revisar a mano: {revisar}")
print(f"Gasto en OpenAI: US$ {costo:.2f}")
if errores:
    print(f"\nErrores ({len(errores)}):")
    print("\n".join(errores[-10:]))
EOF
)
gcloud logging read "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"clasificador\" \
  AND timestamp>=\"$DESDE\" AND (jsonPayload.evento=\"clasificado\" OR jsonPayload.evento=\"error\")" \
  --order asc --limit 2000 --format json | python3 -c "$PY"
