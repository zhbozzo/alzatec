"""Armado y envío de los reenvíos por SMTP."""

import smtplib
import ssl
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

ETIQUETAS = {
    "despacho_acordado": "DESPACHO ACORDADO",
    "recepcion_acordada": "RECEPCIÓN ACORDADA",
    "pendiente": "PENDIENTE",
    "no_aplica": "NO APLICA",
}
FALTAS = {
    "fecha_hora": "fecha u hora", "confirmacion": "confirmación", "orden_compra": "orden de compra",
    "condicion_comercial": "condición comercial", "cotizacion_final": "cotización final",
    "stock": "stock", "cambio_o_anulacion": "cambio o anulación", "otro": "otro",
}


def asunto_reenvio(cfg, correo, decision):
    partes = []
    if cfg.prefijo:
        partes.append(cfg.prefijo)
    if cfg.modo == "sombra":
        partes.append("[SOMBRA]")
    partes.append(f"[{ETIQUETAS[decision.categoria]}]")
    if decision.revisar:
        partes.append("[REVISAR]")
    return " ".join(partes) + " " + (correo.asunto or "(sin asunto)")


def cuerpo_reenvio(correo, decision):
    r = decision.resultado
    lineas = [f"Categoría: {ETIQUETAS[decision.categoria]}"]
    if decision.revisar:
        lineas.append(f"REVISAR: {decision.nota}")
    if decision.categoria == "pendiente" and r.get("falta"):
        lineas.append("Falta: " + ", ".join(FALTAS.get(f, f) for f in r["falta"]))
    for etiqueta, clave in (("Fecha del movimiento", "fecha_movimiento"), ("Cotización", "n_cotizacion"),
                            ("Cliente", "cliente"), ("Obra", "obra")):
        if r.get(clave):
            lineas.append(f"{etiqueta}: {r[clave]}")
    if r.get("resumen"):
        lineas.append("")
        lineas.append(f"Resumen: {r['resumen']}")
    if r.get("motivo"):
        lineas.append(f"Por qué: {r['motivo']}")
    if decision.nota and not decision.revisar:
        lineas.append(f"Nota: {decision.nota}")
    lineas += [
        "",
        "--",
        f"Correo original adjunto. De: {correo.remitente} · Fecha: {correo.fecha}",
        "Clasificado automáticamente por agente@alzatec.com. Si la categoría está mal, avisar al mantenedor.",
    ]
    return "\n".join(lineas)


def armar_reenvio(cfg, correo, decision, destino):
    m = EmailMessage()
    m["From"] = f"Clasificador Alzatec <{cfg.usuario}>"
    m["To"] = destino
    m["Subject"] = asunto_reenvio(cfg, correo, decision)
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=cfg.usuario.split("@")[-1])
    m.set_content(cuerpo_reenvio(correo, decision))
    try:
        # Como mensaje adjunto (message/rfc822): Outlook lo abre como correo y se puede responder desde ahí
        m.add_attachment(message_from_bytes(correo.crudo, policy=policy.SMTP), filename="correo-original.eml")
        m.as_bytes()  # verifica que se pueda serializar
    except Exception:
        m.get_payload().pop()
        m.add_attachment(correo.crudo, maintype="application", subtype="octet-stream", filename="correo-original.eml")
    return m


def armar_aviso(cfg, destino, asunto, texto):
    m = EmailMessage()
    m["From"] = f"Clasificador Alzatec <{cfg.usuario}>"
    m["To"] = destino
    m["Subject"] = asunto
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=cfg.usuario.split("@")[-1])
    m.set_content(texto)
    return m


class EnviadorSMTP:
    def __init__(self, cfg):
        self.cfg = cfg
        self._smtp = None

    def __call__(self, mensaje):
        if self._smtp is None:
            self._smtp = smtplib.SMTP_SSL(self.cfg.smtp_host, self.cfg.smtp_puerto,
                                          context=ssl.create_default_context(), timeout=60)
            self._smtp.login(self.cfg.usuario, self.cfg.contrasena)
        self._smtp.send_message(mensaje)

    def cerrar(self):
        if self._smtp is not None:
            try:
                self._smtp.quit()
            except Exception:
                pass
            self._smtp = None
