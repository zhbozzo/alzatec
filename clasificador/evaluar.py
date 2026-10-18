"""Evaluación offline con los correos etiquetados (no se envía nada).

Usa el mismo código que producción (reglas, modelo, segunda opinión) sobre la
muestra de validación y compara con las etiquetas. Los datos reales están en
datos/ (fuera del repositorio).

    python -m clasificador.evaluar --modelo openai:gpt-6.1-sol
    python -m clasificador.evaluar --modelo openai:gpt-6.1-sol --limite 10      # prueba rápida
"""

import argparse
import collections
import json
import mimetypes
import os
from concurrent.futures import ThreadPoolExecutor
from email.utils import getaddresses

from . import memoria, modelos
from .correo import Correo, Imagen
from .principal import costo
from .reglas import ACORDADOS, decidir

DATOS = os.environ.get("DATOS_VALIDACION", "datos/validacion")
MOV = ACORDADOS | {"pendiente"}


def tipo_de_error(etiqueta, prediccion):
    if etiqueta == prediccion:
        return None
    if etiqueta in MOV and prediccion == "no_aplica":
        return "GRAVE: se pierde"
    if prediccion in ACORDADOS:
        return "GRAVE: falso confirmado"
    if etiqueta in ACORDADOS and prediccion == "pendiente":
        return "leve: acordado a pendientes"
    if etiqueta == "no_aplica" and prediccion == "pendiente":
        return "leve: ruido en pendientes"
    return "otro"


def correo_de_muestra(x, rutas_imagenes):
    remitentes = getaddresses([x["remitente"]])
    correo_rem = remitentes[0][1].lower() if remitentes else ""
    imagenes = []
    # Las rutas guardadas son absolutas de la máquina donde se armó la muestra: se buscan dentro de DATOS
    rutas_imagenes = [r if os.path.exists(r) else os.path.join(DATOS, r.split("datos/validacion/", 1)[-1])
                      for r in rutas_imagenes]
    for ruta in rutas_imagenes:
        tipo = mimetypes.guess_type(ruta)[0]
        if tipo in ("image/png", "image/jpeg", "image/gif", "image/webp"):
            imagenes.append(Imagen(tipo, open(ruta, "rb").read(), os.path.basename(ruta)))
    return Correo(message_id=x["id"], asunto=x["asunto"], remitente=x["remitente"], remitente_correo=correo_rem,
                  para=x.get("para", ""), cc=x.get("cc", ""), fecha=x["fecha"],
                  texto_nuevo=x["texto_nuevo"], texto_citado=x["contexto_citado"], imagenes=imagenes[:8],
                  adjuntos=[a for a in rutas_imagenes if a.endswith(".pdf")])


def con_memoria(muestra, adjuntos, principal, verificador, a):
    """Agrupa los correos por hilo (claves de memoria.py) y procesa cada hilo en orden cronológico."""
    correos = {x["id"]: correo_de_muestra(x, adjuntos.get(x["id"], [])) for x in muestra}
    padre = {i: i for i in correos}

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i
    duenos = {}
    for i, c in correos.items():
        for k in memoria.claves_buscar(c) + memoria.claves_guardar(c):
            if k in duenos:
                padre[raiz(i)] = raiz(duenos[k])
            else:
                duenos[k] = i
    hilos = {}
    for i in sorted(correos, key=lambda i: correos[i].fecha or ""):
        hilos.setdefault(raiz(i), []).append(i)

    def hilo(ids):
        local, salida = memoria.MemoriaLocal(), []
        for i in ids:
            c = correos[i]
            c.historial = local.historial(memoria.claves_buscar(c))
            d = decidir(c, principal, verificador)
            if d.categoria != "no_aplica":
                local.registrar_decision(memoria.claves_guardar(c), memoria.entrada(c, d))
            p = {"id": i, "categoria": d.categoria, "revisar": d.revisar, "fuente": d.fuente, "nota": d.nota,
                 "historial": len(c.historial), "resultado": d.resultado,
                 "costo": sum(x for x in (costo(u) for u in d.usos) if x)}
            if a.registrar:
                print(json.dumps(dict(p, evento="evaluacion"), ensure_ascii=False), flush=True)
            salida.append(p)
        return salida
    with ThreadPoolExecutor(a.hilos) as ex:
        resultados = [p for grupo in ex.map(hilo, hilos.values()) for p in grupo]
    print(f"Hilos: {len(hilos)} (con más de un correo: {sum(len(v) > 1 for v in hilos.values())})")
    orden = {x["id"]: n for n, x in enumerate(muestra)}
    return sorted(resultados, key=lambda p: orden[p["id"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--verificador", default="")
    ap.add_argument("--esfuerzo", default="medium")
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--hilos", type=int, default=6)
    ap.add_argument("--salida", default="")
    ap.add_argument("--registrar", action="store_true", help="imprimir cada predicción como JSON (para Cloud Run)")
    ap.add_argument("--memoria", action="store_true",
                    help="cada hilo en orden cronológico, con memoria de lo reenviado antes (como en producción)")
    a = ap.parse_args()

    muestra = [json.loads(l) for l in open(f"{DATOS}/muestra.jsonl", encoding="utf-8")]
    adjuntos = json.load(open(f"{DATOS}/adjuntos.json")) if os.path.exists(f"{DATOS}/adjuntos.json") else {}
    etiquetas = {x["id"]: x for x in json.load(open(f"{DATOS}/clasificacion.json", encoding="utf-8"))["items"]}
    if a.limite:
        muestra = muestra[: a.limite]
    principal = modelos.crear(a.modelo, a.esfuerzo)
    verificador = modelos.crear(a.verificador, a.esfuerzo)

    def uno(x):
        d = decidir(correo_de_muestra(x, adjuntos.get(x["id"], [])), principal, verificador)
        p = {"id": x["id"], "categoria": d.categoria, "revisar": d.revisar, "fuente": d.fuente, "nota": d.nota,
             "resultado": d.resultado, "costo": sum(c for c in (costo(u) for u in d.usos) if c)}
        if a.registrar:
            print(json.dumps(dict(p, evento="evaluacion"), ensure_ascii=False), flush=True)
        return p

    if a.memoria:
        preds = con_memoria(muestra, adjuntos, principal, verificador, a)
    else:
        with ThreadPoolExecutor(a.hilos) as ex:
            preds = list(ex.map(uno, muestra))

    salida = a.salida or f"{DATOS}/eval_{a.modelo.replace(':', '_')}_{a.verificador.replace(':', '_') or 'solo'}.json"
    json.dump(preds, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    errores = collections.Counter()
    graves = []
    for p in preds:
        g = etiquetas[p["id"]]
        t = tipo_de_error(g["categoria"], p["categoria"])
        if t:
            errores[t] += 1
            if t.startswith("GRAVE"):
                graves.append((p["id"], g["categoria"], p["categoria"], bool(g.get("caso_a_validar")), p["resultado"].get("motivo", "")))
    n = len(preds)
    total_costo = sum(p["costo"] for p in preds)
    print(f"Modelo: {a.modelo}  Segunda opinión: {a.verificador or 'no'}  Esfuerzo: {a.esfuerzo}")
    print(f"Coincide con la etiqueta: {n - sum(errores.values())}/{n}")
    print(f"Errores: {dict(errores)}")
    print(f"Marcados para revisar: {sum(p['revisar'] for p in preds)}")
    print(f"Costo de la corrida: US${total_costo:.2f} (≈ US${total_costo / n * 2000:.0f} por 2.000 correos)")
    for g in graves:
        print(f"  GRAVE {g[0]}: etiqueta {g[1]} -> {g[2]}{' (duda de criterio)' if g[3] else ''} | {g[4][:120]}")
    print(f"Predicciones guardadas en {salida}")


if __name__ == "__main__":
    main()
