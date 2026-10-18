"""Lectura de un correo (RFC 822) a una estructura simple."""

import html
import re
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.utils import getaddresses, parsedate_to_datetime

# Dónde empieza el mensaje citado en una respuesta (Outlook, Gmail, celulares)
CITA = re.compile(
    r"(\n\s*(De|From)\s*:.*"
    r"|\n\s*El\s.{5,120}escribi[oó]:"
    r"|-----\s*(Original Message|Mensaje original)\s*-----"
    r"|\n_{10,}"
    r"|\nEnviado desde mi"
    r"|\n\s*On .{5,120} wrote:)",
    re.I,
)
TIPOS_IMAGEN = {"image/png", "image/jpeg", "image/gif", "image/webp"}
IMAGEN_MIN = 2_500           # bajo esto suelen ser íconos
IMAGEN_MAX = 5_000_000       # límite de los proveedores por imagen


@dataclass
class Imagen:
    tipo: str
    datos: bytes
    nombre: str = ""


@dataclass
class Correo:
    message_id: str
    asunto: str
    remitente: str           # "Nombre <correo>"
    remitente_correo: str    # solo el correo, en minúsculas
    para: str
    cc: str
    fecha: str               # ISO 8601, o "" si no se pudo leer
    texto_nuevo: str
    texto_citado: str
    imagenes: list = field(default_factory=list)
    adjuntos: list = field(default_factory=list)  # nombres de los adjuntos que no son imagen
    crudo: bytes = b""
    ilegible: bool = False
    referencias: list = field(default_factory=list)  # Message-ID de In-Reply-To y References
    historial: list = field(default_factory=list)    # decisiones anteriores del mismo hilo (memoria.py)


def html_a_texto(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", h)
    h = re.sub(r"(?i)</td>|</th>", " | ", h)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\s*\n\s*", "\n", t).strip()


def separar_cita(texto):
    """Devuelve (texto nuevo, texto citado)."""
    t = texto.replace("\r", "")
    m = CITA.search(t)
    if not m:
        return t.strip(), ""
    return t[:m.start()].strip(), t[m.start():].strip()


def _texto_del_cuerpo(msg):
    plano, html_ = None, None
    for parte in msg.walk():
        if parte.is_multipart() or parte.get_content_disposition() == "attachment":
            continue
        tipo = parte.get_content_type()
        try:
            contenido = parte.get_content()
        except Exception:
            continue
        if tipo == "text/plain" and plano is None:
            plano = contenido
        elif tipo == "text/html" and html_ is None:
            html_ = contenido
    if plano and plano.strip():
        return plano
    return html_a_texto(html_) if html_ else ""


def leer(crudo, max_imagenes=8):
    msg = message_from_bytes(crudo, policy=policy.default)
    remitentes = getaddresses([str(msg.get("From", ""))])
    nombre, correo_rem = remitentes[0] if remitentes else ("", "")
    try:
        fecha = parsedate_to_datetime(str(msg.get("Date"))).isoformat()
    except Exception:
        fecha = ""

    imagenes, adjuntos = [], []
    for parte in msg.walk():
        if parte.is_multipart():
            continue
        tipo = parte.get_content_type()
        nombre_archivo = parte.get_filename() or ""
        if tipo in TIPOS_IMAGEN:
            datos = parte.get_payload(decode=True) or b""
            if IMAGEN_MIN <= len(datos) <= IMAGEN_MAX and len(imagenes) < max_imagenes:
                imagenes.append(Imagen(tipo, datos, nombre_archivo))
        elif parte.get_content_disposition() == "attachment" and nombre_archivo:
            adjuntos.append(nombre_archivo)

    nuevo, citado = separar_cita(_texto_del_cuerpo(msg))
    return Correo(
        message_id=str(msg.get("Message-ID", "")).strip(),
        asunto=str(msg.get("Subject", "")).strip(),
        remitente=f"{nombre} <{correo_rem}>".strip(),
        remitente_correo=correo_rem.lower(),
        para=str(msg.get("To", "")),
        cc=str(msg.get("Cc", "")),
        fecha=fecha,
        texto_nuevo=nuevo,
        texto_citado=citado,
        imagenes=imagenes,
        adjuntos=adjuntos,
        crudo=crudo,
        referencias=re.findall(r"<[^<>\s]+>", f"{msg.get('References', '')} {msg.get('In-Reply-To', '')}"),
    )
