"""Llamadas a los modelos (OpenAI y Anthropic) con salida JSON estructurada.

Cada clasificador recibe un Correo y devuelve (resultado, uso). Si el modelo
rechaza el pedido, corta la respuesta o falla la API, lanza ErrorModelo: el
que llama decide mandar el correo a pendientes para que nadie lo pierda.
"""

import base64
import json
from dataclasses import dataclass

from .prompt import ESQUEMA, INSTRUCCIONES, texto_del_correo


class ErrorModelo(Exception):
    pass


@dataclass
class Uso:
    modelo: str
    entrada: int = 0
    entrada_cache: int = 0
    salida: int = 0


def _validar(resultado):
    faltan = [k for k in ESQUEMA["required"] if k not in resultado]
    if faltan:
        raise ErrorModelo(f"respuesta sin los campos {faltan}")
    return resultado


class ClasificadorOpenAI:
    def __init__(self, modelo, esfuerzo="medium", cliente=None):
        if cliente is None:
            from openai import OpenAI
            cliente = OpenAI(timeout=120, max_retries=2)
        self.cliente, self.modelo, self.esfuerzo = cliente, modelo, esfuerzo

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
        except Exception as e:  # errores de red o de la API, ya reintentados por el SDK
            raise ErrorModelo(f"{type(e).__name__}: {e}") from e
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
    def __init__(self, modelo, esfuerzo="medium", cliente=None):
        if cliente is None:
            import anthropic
            cliente = anthropic.Anthropic(timeout=120.0, max_retries=2)
        self.cliente, self.modelo, self.esfuerzo = cliente, modelo, esfuerzo

    def clasificar(self, correo):
        contenido = []
        for i, img in enumerate(correo.imagenes, 1):
            contenido.append({"type": "text", "text": f"Imagen {i}:"})
            contenido.append({"type": "image", "source": {
                "type": "base64", "media_type": img.tipo,
                "data": base64.standard_b64encode(img.datos).decode()}})
        contenido.append({"type": "text", "text": texto_del_correo(correo)})
        try:
            # fallbacks "default": si el modelo declina por error, la API reintenta con otro modelo
            r = self.cliente.beta.messages.create(
                model=self.modelo,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=[{"type": "text", "text": INSTRUCCIONES, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": contenido}],
                output_config={"format": {"type": "json_schema", "schema": ESQUEMA}, "effort": self.esfuerzo},
            )
        except Exception as e:
            raise ErrorModelo(f"{type(e).__name__}: {e}") from e
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
