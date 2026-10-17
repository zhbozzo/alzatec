"""Llamadas a los modelos con salida JSON estructurada.

Cada clasificador recibe un Correo y devuelve (resultado, uso). Hay dos tipos
de error:
- ErrorModelo: falla con ESTE correo (rechazo, respuesta cortada, JSON malo).
  El correo va a pendientes con "revisar".
- ErrorServicio: el servicio no está disponible para ningún correo (sin saldo,
  API key inválida, caída). Se detiene la corrida, los correos quedan en
  agente@ sin tocar y se manda una alerta que dice qué hacer.
"""

import base64
import json
from dataclasses import dataclass

from .prompt import ESQUEMA, INSTRUCCIONES, texto_del_correo


class ErrorModelo(Exception):
    pass


class ErrorServicio(Exception):
    def __init__(self, tipo, titulo, que_hacer, detalle=""):
        super().__init__(f"{titulo}: {detalle}")
        self.tipo, self.titulo, self.que_hacer, self.detalle = tipo, titulo, que_hacer, detalle


@dataclass
class Uso:
    modelo: str
    entrada: int = 0
    entrada_cache: int = 0
    salida: int = 0


PANELES = {"openai": "https://platform.openai.com", "anthropic": "https://console.anthropic.com"}
SECRETOS = {"openai": "openai-api-key", "anthropic": "anthropic-api-key"}


def diagnosticar(e, proveedor, modelo, sdk):
    """Traduce una excepción del SDK a ErrorServicio (para todos) o ErrorModelo (solo este correo)."""
    nombre = "OpenAI" if proveedor == "openai" else "Anthropic"
    panel, secreto = PANELES[proveedor], SECRETOS[proveedor]
    detalle = f"{type(e).__name__}: {e}"[:500]
    codigo = str(getattr(e, "code", "") or "")
    texto = (codigo + " " + str(e)).lower()

    if any(p in texto for p in ("insufficient_quota", "billing", "credit balance", "quota")):
        return ErrorServicio(f"{proveedor}_sin_saldo", f"Sin saldo en {nombre}",
                             f"Recargar créditos en {panel} (Billing) o subir el tope de gasto. "
                             "Apenas haya saldo, el clasificador sigue solo.", detalle)
    if isinstance(e, sdk.AuthenticationError):
        return ErrorServicio(f"{proveedor}_clave", f"La API key de {nombre} no es válida",
                             f"Crear una nueva en {panel} y actualizar el secreto '{secreto}' en Google Cloud "
                             "(Secret Manager → nueva versión).", detalle)
    if isinstance(e, (sdk.PermissionDeniedError, sdk.NotFoundError)):
        return ErrorServicio(f"{proveedor}_acceso", f"{nombre} no da acceso al modelo {modelo}",
                             f"Revisar en {panel} que la cuenta tenga acceso a {modelo}, o cambiar la "
                             "variable MODELO del job.", detalle)
    if isinstance(e, sdk.RateLimitError):
        return ErrorServicio(f"{proveedor}_limite", f"{nombre} está limitando la cantidad de pedidos",
                             "Se reintenta solo. Si este aviso se repite varias horas, subir el límite "
                             f"(tier) de la cuenta en {panel}.", detalle)
    if isinstance(e, (sdk.APIConnectionError, sdk.APITimeoutError, sdk.InternalServerError)):
        return ErrorServicio(f"{proveedor}_caido", f"{nombre} no responde",
                             "Suele ser una caída temporal del proveedor; se reintenta solo. "
                             "Si dura más de unas horas, revisar el estado del servicio.", detalle)
    if isinstance(e, sdk.APIStatusError) and getattr(e, "status_code", 0) >= 500:
        return ErrorServicio(f"{proveedor}_caido", f"{nombre} no responde", "Se reintenta solo.", detalle)
    return ErrorModelo(detalle)  # por ejemplo, un 400 por una imagen que el modelo no acepta


def _validar(resultado):
    faltan = [k for k in ESQUEMA["required"] if k not in resultado]
    if faltan:
        raise ErrorModelo(f"respuesta sin los campos {faltan}")
    return resultado


class ClasificadorOpenAI:
    proveedor = "openai"

    def __init__(self, modelo, esfuerzo="medium", cliente=None):
        import openai
        self.sdk = openai
        self.cliente = cliente or openai.OpenAI(timeout=120, max_retries=2)
        self.modelo, self.esfuerzo = modelo, esfuerzo

    def clasificar(self, correo):
        contenido = []
        for i, img in enumerate(correo.imagenes, 1):
            datos = base64.b64encode(img.datos).decode()
            contenido.append({"type": "input_text", "text": f"Imagen {i}:"})
            contenido.append({"type": "input_image", "image_url": f"data:{img.tipo};base64,{datos}", "detail": "high"})
        contenido.append({"type": "input_text", "text": texto_del_correo(correo)})
        try:
            r = self.cliente.responses.create(
                model=self.modelo,
                input=[
                    {"role": "system", "content": INSTRUCCIONES},
                    {"role": "user", "content": contenido},
                ],
                text={"format": {"type": "json_schema", "name": "clasificacion", "schema": ESQUEMA, "strict": True}},
                reasoning={"effort": self.esfuerzo},
                max_output_tokens=16000,
                prompt_cache_key="alzatec-clasificador",
            )
        except Exception as e:  # el SDK ya reintentó los errores transitorios
            raise diagnosticar(e, self.proveedor, self.modelo, self.sdk) from e
        if getattr(r, "status", None) == "incomplete":
            raise ErrorModelo(f"respuesta incompleta: {getattr(r, 'incomplete_details', None)}")
        for item in r.output or []:
            if getattr(item, "type", None) != "message":
                continue
            for parte in item.content or []:
                if getattr(parte, "type", None) == "refusal":
                    raise ErrorModelo(f"el modelo rechazó: {parte.refusal}")
        try:
            resultado = json.loads(r.output_text)
        except Exception as e:
            raise ErrorModelo(f"JSON inválido: {e}") from e
        u = r.usage
        detalles = getattr(u, "input_tokens_details", None)
        uso = Uso(self.modelo, u.input_tokens, getattr(detalles, "cached_tokens", 0) or 0, u.output_tokens)
        return _validar(resultado), uso


class ClasificadorAnthropic:
    proveedor = "anthropic"

    def __init__(self, modelo, esfuerzo="medium", cliente=None):
        import anthropic
        self.sdk = anthropic
        self.cliente = cliente or anthropic.Anthropic(timeout=120.0, max_retries=2)
        self.modelo, self.esfuerzo = modelo, esfuerzo

    def clasificar(self, correo):
        contenido = []
        for i, img in enumerate(correo.imagenes, 1):
            contenido.append({"type": "text", "text": f"Imagen {i}:"})
            contenido.append({"type": "image", "source": {
                "type": "base64", "media_type": img.tipo,
                "data": base64.standard_b64encode(img.datos).decode()}})
        contenido.append({"type": "text", "text": texto_del_correo(correo)})
        try:
            r = self.cliente.messages.create(
                model=self.modelo,
                max_tokens=16000,
                system=[{"type": "text", "text": INSTRUCCIONES, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": contenido}],
                output_config={"format": {"type": "json_schema", "schema": ESQUEMA}, "effort": self.esfuerzo},
            )
        except Exception as e:
            raise diagnosticar(e, self.proveedor, self.modelo, self.sdk) from e
        if r.stop_reason == "refusal":
            detalle = getattr(r, "stop_details", None)
            raise ErrorModelo(f"el modelo rechazó: {getattr(detalle, 'category', None)}")
        if r.stop_reason == "max_tokens":
            raise ErrorModelo("respuesta cortada por max_tokens")
        texto = next((b.text for b in r.content if b.type == "text"), None)
        if texto is None:
            raise ErrorModelo("respuesta sin texto")
        try:
            resultado = json.loads(texto)
        except Exception as e:
            raise ErrorModelo(f"JSON inválido: {e}") from e
        u = r.usage
        uso = Uso(self.modelo, u.input_tokens, getattr(u, "cache_read_input_tokens", 0) or 0, u.output_tokens)
        return _validar(resultado), uso


def crear(especificacion, esfuerzo="medium"):
    """'openai:gpt-6.1-sol' o 'anthropic:claude-sonnet-5-5' -> clasificador. '' -> None."""
    if not especificacion:
        return None
    proveedor, _, modelo = especificacion.partition(":")
    if proveedor == "openai":
        return ClasificadorOpenAI(modelo, esfuerzo)
    if proveedor == "anthropic":
        return ClasificadorAnthropic(modelo, esfuerzo)
    raise ValueError(f"Proveedor desconocido: {proveedor}")
