"""Reglas fijas y decisión final.

Orden:
1. Reglas fijas sin IA para lo que siempre se escribe igual (rebotes,
   informes de recepción ya hecha, plantilla de agenda de Javier).
2. Modelo principal.
3. Reglas de consistencia (acordado con algo que falta, confianza baja).
4. Segunda opinión de otro modelo cuando un error saldría caro:
   cuando dice "acordado", o cuando descarta un correo que menciona un
   movimiento. Si no coinciden, el correo va a pendientes con "revisar".
Ante cualquier falla, el correo va a pendientes con "revisar": nunca se pierde.
"""

import re
from dataclasses import dataclass, field

from .modelos import ErrorModelo

ACORDADOS = {"despacho_acordado", "recepcion_acordada"}
JAVIER = "devoluciones@alzatec.com"

REBOTE_ASUNTO = re.compile(r"mail delivery (failed|failure)|undeliver|delivery status notification|no se (pudo|puede) entregar|returned mail", re.I)
REBOTE_REMITENTE = re.compile(r"mailer-daemon|postmaster", re.I)
MARCA_ASISTENCIA = re.compile(r"marca\s+(de\s+)?asistencia", re.I)
INFORME_RECEPCION = re.compile(r"^\s*RECEPCI[OÓ]N\s+\d+\s*-\s*GU[IÍ]A", re.I)
AGENDA_JAVIER = re.compile(
    r"agendo su hora de devoluci|se reagenda su hora de devoluci|se asigna sobre\s*cupo|confirmar devoluci[oó]n para el d[ií]a", re.I)
# Reacción de Outlook ("[like] Fulano reacted to your message:") sin texto propio: no agrega nada al hilo
REACCION = re.compile(r"^\s*(\[[^\]]{1,20}\]\s*)?.{0,80}\b(reacted to your message|reaccion[oó] a (su|tu) mensaje)\s*:?\s*$", re.I)
SENAL_MOVIMIENTO = re.compile(
    r"retir|despach|devoluci|devolver|cami[oó]n|agend|cupo|anul|reagend|posterg|hora para|orden de compra|\bo\.?c\b|aprob|acept",
    re.I)

VACIO = {"categoria": "pendiente", "movimiento": "ninguno", "falta": [], "fecha_movimiento": "",
         "n_cotizacion": "", "cliente": "", "obra": "", "resumen": "", "motivo": "", "confianza": "baja"}


@dataclass
class Decision:
    categoria: str
    resultado: dict
    revisar: bool = False
    nota: str = ""
    fuente: str = "modelo"            # regla | modelo | verificado | error
    usos: list = field(default_factory=list)


def prefiltro(correo):
    """Devuelve (categoria, motivo, definitiva) o None.

    definitiva=True: se resuelve sin llamar al modelo (descartes seguros).
    definitiva=False: la categoría es segura, pero el modelo igual extrae fecha y resumen.
    """
    if REBOTE_REMITENTE.search(correo.remitente_correo) or REBOTE_ASUNTO.search(correo.asunto):
        return "no_aplica", "Rebote automático de correo.", True
    if REACCION.match(correo.texto_nuevo.strip().split("\n")[0]) and len(correo.texto_nuevo.strip()) < 200:
        return "no_aplica", "Reacción (me gusta) a un mensaje anterior, sin texto nuevo.", True
    if MARCA_ASISTENCIA.search(correo.asunto):
        return "no_aplica", "Aviso automático de marca de asistencia.", True
    if correo.remitente_correo == JAVIER and INFORME_RECEPCION.search(correo.asunto):
        return "no_aplica", "Informe de una recepción ya realizada.", True
    if correo.remitente_correo == JAVIER and AGENDA_JAVIER.search(correo.texto_nuevo):
        return "recepcion_acordada", "Javier agenda o confirma la hora de devolución.", False
    return None


def senal_de_movimiento(correo):
    return bool(SENAL_MOVIMIENTO.search(correo.asunto) or SENAL_MOVIMIENTO.search(correo.texto_nuevo))


def decidir(correo, principal, verificador=None):
    pre = prefiltro(correo)
    if pre and pre[2]:
        resultado = dict(VACIO, categoria=pre[0], motivo=pre[1], resumen=pre[1], confianza="alta")
        return Decision(pre[0], resultado, fuente="regla")

    try:
        r, uso = principal.clasificar(correo)
    except ErrorModelo as e:
        if pre:  # la regla ya fija la categoría; solo faltan los datos que iba a extraer el modelo
            resultado = dict(VACIO, categoria=pre[0], motivo=pre[1], resumen=pre[1], confianza="alta")
            return Decision(pre[0], resultado, revisar=True, fuente="regla",
                            nota=f"No se pudo extraer la fecha con el modelo ({e}); revisar la fecha en el correo original.")
        return Decision("pendiente", dict(VACIO), revisar=True, fuente="error",
                        nota=f"El clasificador no pudo procesar este correo ({e}). Revisar a mano.")
    usos = [uso]
    cat, revisar, notas = r["categoria"], False, []

    if pre:  # categoría fijada por regla; el modelo solo aporta los datos
        if cat != pre[0]:
            notas.append(f"El modelo decía {cat}; se aplicó la regla fija ({pre[1]}).")
        cat = r["categoria"] = pre[0]
        return Decision(cat, r, nota=" ".join(notas), fuente="regla", usos=usos)

    if cat in ACORDADOS and r["falta"]:
        notas.append(f"El modelo marcó {cat} pero indicó que falta: {', '.join(r['falta'])}.")
        cat, revisar = "pendiente", True
    if r["confianza"] == "baja" and r["movimiento"] != "ninguno" and cat != "pendiente":
        notas.append(f"El modelo no está seguro (decía {cat}).")
        cat, revisar = "pendiente", True

    necesita = verificador is not None and (
        cat in ACORDADOS
        or (cat == "no_aplica" and senal_de_movimiento(correo))
        or r["confianza"] == "baja"
    )
    fuente = "modelo"
    if necesita:
        try:
            r2, uso2 = verificador.clasificar(correo)
            usos.append(uso2)
            fuente = "verificado"
            if r2["categoria"] != cat:
                notas.append(f"Los dos modelos no coinciden: uno dice {cat} y el otro {r2['categoria']} ({r2['motivo']}).")
                cat, revisar = "pendiente", True
        except ErrorModelo as e:
            if cat in ACORDADOS or cat == "no_aplica":
                notas.append(f"No se pudo confirmar con el segundo modelo ({e}); decía {cat}.")
                cat, revisar = "pendiente", True

    return Decision(cat, r, revisar=revisar, nota=" ".join(notas), fuente=fuente, usos=usos)
