"""Revisión a pedido ("revisa hoy"): exporta los correos de un día, guarda los casos verificados y corre la
prueba de regresión.

Corre en una sesión de Claude Code con gcloud conectado (deploy/claude-login.sh). No guarda correos en el
repositorio (es público): los lotes de revisión van a la carpeta que se indique, fuera de git, y los casos
verificados a un bucket privado del proyecto.

    python3 herramientas/revision.py exportar --dia 2026-10-19 --salida /ruta/fuera/de/git
    python3 herramientas/revision.py caso 93 pendiente "Saldo pendiente de despacho (OT de MADA)"
    python3 herramientas/revision.py casos
    python3 herramientas/revision.py regresion
    python3 herramientas/revision.py evaluar        # los 200 correos históricos de validación
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

REGION = "southamerica-west1"
JOB = "clasificador"
CATEGORIAS = ("despacho_acordado", "recepcion_acordada", "pendiente", "no_aplica")
# En Claude Code el entorno define un token de relleno que tapa la cuenta activa de gcloud
ENTORNO = {k: v for k, v in os.environ.items() if k != "CLOUDSDK_AUTH_ACCESS_TOKEN"}


def gcloud(*args):
    r = subprocess.run(["gcloud", *args], env=ENTORNO, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"Falló: gcloud {' '.join(args[:4])}\n{r.stderr[-2000:]}")
    return r.stdout


def ahora():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ejecutar(*argumentos):
    """Corre el job con estos argumentos y espera a que termine."""
    gcloud("run", "jobs", "execute", JOB, "--region", REGION, "--args", ",".join(argumentos), "--wait", "--quiet")


def registros(filtro, desde, limite=5000, job=JOB):
    f = (f'resource.type="cloud_run_job" AND resource.labels.job_name="{job}" '
         f'AND timestamp>="{desde}" AND {filtro}')
    return [e["jsonPayload"] for e in json.loads(gcloud("logging", "read", f, "--limit", str(limite), "--format", "json"))]


def esperar_registros(filtro, desde, cuantos=None, maximo=240, job=JOB):
    """Los registros tardan unos segundos en aparecer: espera a tener `cuantos` o a que dejen de llegar."""
    fin, antes = time.time() + maximo, -1
    while True:
        r = registros(filtro, desde, job=job)
        if (cuantos is not None and len(r) >= cuantos) or (cuantos is None and len(r) == antes and r) \
                or time.time() > fin:
            return r
        antes = len(r)
        time.sleep(15)


def fecha_imap(dia):
    return dia.strftime("%d-%b-%Y")


# --- Exportar un día para revisarlo ------------------------------------------------------------

def exportar(dia, hasta, salida, lotes):
    d = datetime.date.fromisoformat(dia)
    h = datetime.date.fromisoformat(hasta) if hasta else d + datetime.timedelta(days=1)
    t0 = ahora()
    ejecutar("exportar", fecha_imap(d), fecha_imap(h))
    textos = {p["uid"]: p for p in esperar_registros('jsonPayload.evento="export"', t0)}
    # Última clasificación o corrección de cada correo (los registros vienen del más nuevo al más viejo)
    decisiones = {}
    filtro = ('(jsonPayload.evento="clasificado" OR jsonPayload.evento="correccion" '
              'OR jsonPayload.evento="duplicado")')
    for p in registros(filtro, (d - datetime.timedelta(days=1)).isoformat() + "T00:00:00Z"):
        decisiones.setdefault(p["uid"], p)
    filas = []
    for uid in sorted(textos):
        x, c = textos[uid], decisiones.get(uid, {})
        if "mailer-daemon" in (x.get("remitente") or "").lower() and "alzatec.com" in (x.get("texto") or ""):
            continue  # rebotes de reenvíos del propio clasificador: se revisan aparte
        gpt = {"evento": c.get("evento")}
        gpt.update({k: c.get(k) for k in ("categoria", "ahora", "confianza", "revisar", "fuente", "movimiento",
                                          "fecha_movimiento", "falta", "resumen", "motivo", "nota", "destino")})
        filas.append({"uid": uid, "fecha": x.get("fecha"), "de": x.get("remitente"), "para": x.get("para"),
                      "cc": x.get("cc"), "asunto": x.get("asunto"), "texto": x.get("texto"),
                      "citado": (x.get("citado") or "")[:1500], "adjuntos": x.get("adjuntos"),
                      "imagenes": x.get("imagenes"), "marcas": x.get("marcas"), "gpt": gpt})
    os.makedirs(salida, exist_ok=True)
    tam = max(1, -(-len(filas) // lotes))
    for i in range(0, len(filas), tam):
        ruta = os.path.join(salida, f"revision_{i // tam + 1}.json")
        with open(ruta, "w") as f:
            json.dump(filas[i:i + tam], f, ensure_ascii=False, indent=1)
        print(f"{ruta}: {len(filas[i:i + tam])} correos")
    categorias = {}
    for f in filas:
        cat = f["gpt"].get("ahora") or f["gpt"].get("categoria") or f["gpt"].get("evento") or "sin clasificar"
        categorias[cat] = categorias.get(cat, 0) + 1
    print(f"Total {len(filas)} correos del {d} al {h - datetime.timedelta(days=1)}: {categorias}")


# --- Casos verificados (bucket privado) --------------------------------------------------------

def bucket():
    proyecto = gcloud("config", "get-value", "project").strip()
    numero = gcloud("projects", "describe", proyecto, "--format", "value(projectNumber)").strip()
    nombre = os.environ.get("REVISION_BUCKET") or f"gs://{proyecto}-{numero}-revision"
    r = subprocess.run(["gcloud", "storage", "buckets", "describe", nombre], env=ENTORNO, capture_output=True)
    if r.returncode != 0:
        gcloud("storage", "buckets", "create", nombre, "--location", REGION, "--uniform-bucket-level-access",
               "--public-access-prevention")
    return nombre


def leer_casos():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "casos.json")
        r = subprocess.run(["gcloud", "storage", "cp", f"{bucket()}/casos.json", ruta], env=ENTORNO,
                           capture_output=True, text=True)
        if r.returncode != 0:
            return {}
        with open(ruta) as f:
            return json.load(f)


def guardar_casos(casos):
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "casos.json")
        with open(ruta, "w") as f:
            json.dump(casos, f, ensure_ascii=False, indent=1, sort_keys=True)
        gcloud("storage", "cp", ruta, f"{bucket()}/casos.json")


def caso(uid, categoria, nota):
    if categoria not in CATEGORIAS:
        raise SystemExit(f"Categoría no válida: {categoria}")
    casos = leer_casos()
    casos[str(uid)] = {"categoria": categoria, "nota": nota, "verificado": datetime.date.today().isoformat()}
    guardar_casos(casos)
    print(f"Caso {uid} → {categoria} guardado ({len(casos)} casos en total)")


def listar():
    for uid, c in sorted(leer_casos().items(), key=lambda x: int(x[0])):
        print(f"{uid:>6}  {c['categoria']:<19} {c['verificado']}  {c['nota']}")


# --- Regresión: los casos verificados tienen que seguir saliendo bien --------------------------

def regresion(por_ejecucion=20):
    casos = leer_casos()
    if not casos:
        raise SystemExit("No hay casos verificados todavía.")
    uids = sorted(casos, key=int)
    t0 = ahora()
    grupos = [uids[i:i + por_ejecucion] for i in range(0, len(uids), por_ejecucion)]
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda g: ejecutar("explicar", *g), grupos))
    obtenidos = {}
    for p in esperar_registros('jsonPayload.evento="explicacion"', t0, cuantos=len(uids)):
        obtenidos.setdefault(str(p["uid"]), p)
    malos = []
    for uid in uids:
        p, esperado = obtenidos.get(uid), casos[uid]["categoria"]
        cat = p["categoria"] if p else "(sin resultado)"
        if cat != esperado:
            malos.append(uid)
            print(f"FALLA {uid}: esperaba {esperado}, salió {cat}. Caso: {casos[uid]['nota']}"
                  + (f" | motivo del modelo: {p.get('motivo')}" if p else ""))
    print(f"Regresión: {len(uids) - len(malos)} de {len(uids)} casos bien.")
    return 1 if malos else 0


# --- Evaluación con los 200 correos históricos ------------------------------------------------

EVAL = "clasificador-eval"


def evaluar():
    """Sube el código actual al job de evaluación y lo corre sobre los 200 correos de validación.

    Los correos y sus etiquetas viven dentro de la imagen del job (privada, en el proyecto), no en git:
    la imagen nueva parte de la anterior y solo reemplaza el código.
    """
    base = gcloud("run", "jobs", "describe", EVAL, "--region", REGION, "--format",
                  "value(spec.template.spec.template.spec.containers[0].image)").strip()
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(os.path.join(raiz, "clasificador"), os.path.join(tmp, "clasificador"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        with open(os.path.join(tmp, "Dockerfile"), "w") as f:
            f.write(f"FROM {base}\nCOPY clasificador /app/clasificador\n")
        gcloud("run", "jobs", "deploy", EVAL, "--source", tmp, "--region", REGION, "--quiet")
    t0 = ahora()
    gcloud("run", "jobs", "execute", EVAL, "--region", REGION, "--wait", "--quiet")
    lineas = esperar_registros('textPayload:"Coincide con la etiqueta"', t0, cuantos=1, job=EVAL)
    resumen = [e for e in json.loads(gcloud("logging", "read",
               f'resource.type="cloud_run_job" AND resource.labels.job_name="{EVAL}" AND timestamp>="{t0}" '
               'AND (textPayload:"Coincide" OR textPayload:"Errores" OR textPayload:"GRAVE" OR textPayload:"Costo")',
               "--limit", "50", "--format", "json"))]
    for e in sorted(resumen, key=lambda e: e["timestamp"]):
        print(e.get("textPayload", "").rstrip())
    if not lineas:
        print("No llegó el resumen de la evaluación; revisar los registros del job clasificador-eval.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="accion", required=True)
    e = sub.add_parser("exportar")
    e.add_argument("--dia", required=True, help="primer día, AAAA-MM-DD")
    e.add_argument("--hasta", help="último día (incluido), AAAA-MM-DD; por defecto solo --dia")
    e.add_argument("--salida", required=True, help="carpeta fuera del repositorio")
    e.add_argument("--lotes", type=int, default=2, help="en cuántos archivos repartir los correos")
    c = sub.add_parser("caso")
    c.add_argument("uid", type=int)
    c.add_argument("categoria")
    c.add_argument("nota")
    sub.add_parser("casos")
    sub.add_parser("regresion")
    sub.add_parser("evaluar")
    a = ap.parse_args()
    if a.accion == "exportar":
        hasta = (datetime.date.fromisoformat(a.hasta) + datetime.timedelta(days=1)).isoformat() if a.hasta else None
        exportar(a.dia, hasta, a.salida, a.lotes)
    elif a.accion == "caso":
        caso(a.uid, a.categoria, a.nota)
    elif a.accion == "casos":
        listar()
    elif a.accion == "evaluar":
        evaluar()
    else:
        sys.exit(regresion())


if __name__ == "__main__":
    main()
