"""Orquestación: procesar la casilla y enviar el resumen diario."""

import json
import sys
import time
from email import message_from_bytes, policy

from . import modelos
from .buzon import CLASIFICADO, DUPLICADO, NO_APLICA, RESUMIDO
from .correo import Correo, leer
from .envio import ETIQUETAS, armar_aviso, armar_reenvio
from .reglas import Decision, VACIO, decidir

# US$ por millón de tokens: entrada, entrada en caché, salida
PRECIOS = {
    "gpt-6.1-sol": (2.0, 0.10, 10.0),
    "claude-sonnet-5-5": (2.0, 0.20, 10.0),
    "claude-haiku-5-5": (0.10, 0.01, 0.50),
}


def costo(uso):
    p = PRECIOS.get(uso.modelo)
    if not p:
        return None
    sin_cache = max(uso.entrada - uso.entrada_cache, 0)
    return (sin_cache * p[0] + uso.entrada_cache * p[1] + uso.salida * p[2]) / 1e6


def registrar(**datos):
    """Una línea JSON por evento (Cloud Logging la indexa)."""
    print(json.dumps(datos, ensure_ascii=False), flush=True)


def _correo_ilegible(crudo):
    return Correo(message_id="", asunto="(no se pudo leer el correo)", remitente="", remitente_correo="",
                  para="", cc="", fecha="", texto_nuevo="", texto_citado="", crudo=crudo, ilegible=True)


def procesar(cfg, buzon, principal, verificador, enviar):
    """Procesa los correos nuevos de agente@. Devuelve cuántos procesó."""
    uids = buzon.pendientes()[: cfg.max_por_corrida]
    vistos = set()
    t0 = time.time()
    hechos = 0
    for uid in uids:
        if time.time() - t0 > cfg.max_segundos:
            registrar(evento="corte_por_tiempo", procesados=hechos, pendientes=len(uids) - hechos)
            break
        if not buzon.tomar(uid, int(time.time() // 60)):
            continue
        hechos += 1
        crudo = buzon.leer(uid)
        try:
            correo = leer(crudo, cfg.max_imagenes)
        except Exception:
            correo = _correo_ilegible(crudo)

        mid = correo.message_id
        if mid and (mid in vistos or buzon.ya_procesado(mid)):
            buzon.marcar(uid, CLASIFICADO, DUPLICADO)
            registrar(evento="duplicado", uid=uid, message_id=mid)
            continue
        vistos.add(mid)

        if correo.remitente_correo == cfg.usuario.lower():
            buzon.marcar(uid, CLASIFICADO)  # nunca reprocesar lo que envía el propio agente
            continue

        inicio = time.time()
        if correo.ilegible:
            decision = Decision("pendiente", dict(VACIO), revisar=True, fuente="error",
                                nota="No se pudo leer el formato del correo. Revisar a mano.")
        else:
            try:
                decision = decidir(correo, principal, verificador)
            except Exception as e:  # cualquier error inesperado: a pendientes, nunca se pierde
                decision = Decision("pendiente", dict(VACIO), revisar=True, fuente="error",
                                    nota=f"Error interno del clasificador ({type(e).__name__}: {e}). Revisar a mano.")

        destino = cfg.destino(decision.categoria)
        if destino:
            enviar(armar_reenvio(cfg, correo, decision, destino))  # si falla el SMTP, no se marca y se reintenta
        buzon.marcar(uid, CLASIFICADO, *([NO_APLICA] if decision.categoria == "no_aplica" else []))

        costos = [costo(u) for u in decision.usos]
        registrar(
            evento="clasificado", uid=uid, message_id=mid, fecha=correo.fecha,
            remitente=correo.remitente_correo, asunto=correo.asunto[:200],
            categoria=decision.categoria, revisar=decision.revisar, fuente=decision.fuente,
            nota=decision.nota[:300], confianza=decision.resultado.get("confianza"),
            n_cotizacion=decision.resultado.get("n_cotizacion"), destino=destino,
            modelos=[u.modelo for u in decision.usos],
            tokens=[[u.entrada, u.entrada_cache, u.salida] for u in decision.usos],
            costo_usd=round(sum(c for c in costos if c), 5),
            segundos=round(time.time() - inicio, 1),
        )
    return hechos


def resumen_diario(cfg, buzon, enviar):
    """Manda la lista de lo descartado como "no aplica" desde el último resumen."""
    uids = buzon.descartados_sin_resumir()
    if not uids:
        return 0
    lineas = []
    for uid in uids:
        h = message_from_bytes(buzon.encabezados(uid), policy=policy.default)
        lineas.append(f"- {h.get('Date', '')} | {h.get('From', '')} | {h.get('Subject', '')}")
    texto = (
        f"Estos {len(uids)} correos se clasificaron como \"no aplica\" y NO se reenviaron.\n"
        "Si alguno era un despacho o una devolución, avisar al mantenedor.\n\n" + "\n".join(lineas)
    )
    prefijo = "[SOMBRA] " if cfg.modo == "sombra" else ""
    enviar(armar_aviso(cfg, cfg.resumen_a, f"{prefijo}Resumen diario: {len(uids)} correos descartados", texto))
    for uid in uids:
        buzon.marcar(uid, RESUMIDO)
    registrar(evento="resumen", correos=len(uids))
    return len(uids)


def main(argv=None):
    from .buzon import Buzon
    from .config import Config
    from .envio import EnviadorSMTP

    argv = argv if argv is not None else sys.argv[1:]
    accion = argv[0] if argv else "procesar"
    cfg = Config.desde_entorno()
    buzon = Buzon(cfg)
    enviar = EnviadorSMTP(cfg)
    try:
        buzon.conectar()
        if accion == "procesar":
            principal = modelos.crear(cfg.modelo, cfg.esfuerzo)
            verificador = modelos.crear(cfg.verificador, cfg.esfuerzo)
            procesar(cfg, buzon, principal, verificador, enviar)
        elif accion == "resumen":
            resumen_diario(cfg, buzon, enviar)
        else:
            raise SystemExit(f"Acción desconocida: {accion} (usar 'procesar' o 'resumen')")
    except Exception as e:
        registrar(evento="error", accion=accion, error=f"{type(e).__name__}: {e}")
        try:
            if cfg.alertas_a:
                enviar(armar_aviso(cfg, cfg.alertas_a, "[ALERTA] Falla del clasificador de correos",
                                   f"Acción: {accion}\nError: {type(e).__name__}: {e}\n\n"
                                   "Los correos no se pierden: siguen en agente@ y se reprocesan en la próxima corrida."))
        except Exception:
            pass
        raise
    finally:
        enviar.cerrar()
        buzon.cerrar()
