"""Memoria entre correos: qué se reenvió antes en el mismo hilo o cotización.

Cada reenvío deja una entrada corta en la carpeta Registro de agente@ (sin base de datos). Cuando llega un
correo, se buscan las entradas de su hilo y se le pasan al modelo como contexto. Así entiende respuestas
cortas ("ok", "recibido") y no vuelve a reenviar un acuerdo que ya se reenvió.

Un hilo se reconoce por:
- c: el número de cotización del asunto (N°28204).
- h: el asunto sin RE/RV/FW, junto con los dominios externos de la conversación. Asuntos genéricos como
  "Hora devolución" los usan muchos clientes: el dominio evita mezclar hilos de clientes distintos.
- m: los Message-ID: el propio al guardar y los de In-Reply-To/References al buscar.
"""

import hashlib
import re
import unicodedata
from email.utils import getaddresses

PREFIJOS = re.compile(r"^\s*((re|rv|fw|fwd|tr|aw|r)\s*:\s*|\[[^\]]*\]\s*)+", re.I)
COTIZACION = re.compile(r"(?:N\s*[°ºo]\.?\s*|cotizaci[oó]n\s+(?:alzatec\s+)?)(\d{5})(?!\d)", re.I)
DOMINIO_PROPIO = "alzatec.com"
MAXIMO = 6          # decisiones anteriores que se le pasan al modelo


def _hash(texto):
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12]


def asunto_normal(asunto):
    a = PREFIJOS.sub("", asunto or "")
    a = unicodedata.normalize("NFKD", a).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", a).strip()


def dominios_externos(correo):
    direcciones = getaddresses([correo.remitente, correo.para, correo.cc])
    dominios = {d.split("@")[-1].lower() for _, d in direcciones if "@" in d}
    return sorted(d for d in dominios if not d.endswith(DOMINIO_PROPIO)) or ["interno"]


def _claves_hilo(correo):
    claves = [f"c:{n}" for n in sorted(set(COTIZACION.findall(correo.asunto or "")))]
    asunto = asunto_normal(correo.asunto)
    if asunto:
        claves.append("h:" + _hash(asunto + "|" + ",".join(dominios_externos(correo))))
    return claves


def claves_guardar(correo):
    propias = [f"m:{_hash(correo.message_id)}"] if correo.message_id else []
    return _claves_hilo(correo) + propias


def claves_buscar(correo):
    return _claves_hilo(correo) + [f"m:{_hash(r)}" for r in correo.referencias[-10:]]


def entrada(correo, decision, uid=None):
    r = decision.resultado
    return {
        "fecha": correo.fecha, "uid": uid, "categoria": decision.categoria,
        "movimiento": r.get("movimiento", ""), "fecha_movimiento": r.get("fecha_movimiento", ""),
        "n_cotizacion": r.get("n_cotizacion", ""), "resumen": (r.get("resumen") or "")[:250],
        "asunto": (correo.asunto or "")[:120],
    }


def _instante(fecha):
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(fecha)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def anteriores(historial, correo, uid=None):
    """Solo lo decidido ANTES de este correo y nunca su propia decisión (al reprocesar o en pruebas
    el correo ya puede estar en el registro)."""
    propio, salida = _instante(correo.fecha), []
    for h in historial:
        if uid is not None and h.get("uid") == uid:
            continue
        cuando = _instante(h.get("fecha"))
        if propio and cuando and cuando > propio:
            continue
        salida.append(h)
    return salida


def texto_historial(historial):
    if not historial:
        return ""
    lineas = []
    for h in historial[-MAXIMO:]:
        lineas.append(f"- {(h.get('fecha') or '')[:16]} | {h.get('categoria')} | movimiento: {h.get('movimiento') or '-'}"
                      f" | fecha del movimiento: {h.get('fecha_movimiento') or '-'} | {h.get('resumen') or ''}")
    return "\n".join(lineas)


class MemoriaLocal:
    """La misma memoria pero en memoria del proceso: para simular y evaluar sin escribir en la casilla."""

    def __init__(self):
        self.entradas = []   # (claves, datos)

    def historial(self, claves):
        claves = set(claves)
        vistos = [d for c, d in self.entradas if claves & set(c)]
        return sorted(vistos, key=lambda d: d.get("fecha") or "")[-MAXIMO:]

    def registrar_decision(self, claves, datos):
        self.entradas.append((list(claves), datos))
