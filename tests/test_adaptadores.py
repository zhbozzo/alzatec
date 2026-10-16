"""Pruebas de la conexión IMAP y de los adaptadores de modelos, con clientes falsos."""

import json
from types import SimpleNamespace as NS

import pytest

from clasificador.buzon import Buzon
from clasificador.config import Config
from clasificador.correo import leer
from clasificador.modelos import ClasificadorAnthropic, ClasificadorOpenAI, ErrorModelo
from tests.test_clasificador import PNG, correo_crudo, resultado


class ImapFalso:
    def __init__(self):
        self.llamadas = []
        self.flags = b"1 (UID 1 FLAGS (\\Seen))"
        self.untagged_responses = {"PERMANENTFLAGS": [b"(\\Answered \\Flagged \\Deleted \\Seen \\Draft \\*)"]}

    def uid(self, comando, *args):
        self.llamadas.append((comando,) + args)
        if comando == "SEARCH":
            return "OK", [b"3 1 2"]
        if comando == "FETCH" and args[1] == "(FLAGS)":
            return "OK", [self.flags]
        if comando == "FETCH":
            return "OK", [(b"1 (BODY[] {10}", b"contenido"), b")"]
        return "OK", [b""]


def test_buzon_busca_lee_y_marca_sin_marcar_leido():
    b = Buzon(Config(contrasena="x"))
    b.imap = ImapFalso()
    assert b.pendientes() == [1, 2, 3]
    assert b.leer(1) == b"contenido"
    b.marcar(1, "Clasificado", "NoAplica")
    comandos = b.imap.llamadas
    assert ("SEARCH", None, "UNKEYWORD", "Clasificado", "NOT", "DELETED") in comandos
    assert ("FETCH", "1", "(BODY.PEEK[])") in comandos            # PEEK: no marca como leído
    assert ("STORE", "1", "+FLAGS", "(Clasificado NoAplica)") in comandos
    assert b.ya_procesado("<a1@obra.cl>")
    assert ("SEARCH", None, "KEYWORD", "Clasificado", "HEADER", "Message-ID", '"<a1@obra.cl>"') in comandos


class OpenAIFalso:
    def __init__(self, respuesta):
        self.respuesta, self.pedido = respuesta, None
        self.responses = self

    def create(self, **kw):
        self.pedido = kw
        return self.respuesta


def _resp_openai(texto=None, rechazo=None, status="completed"):
    contenido = [NS(type="refusal", refusal=rechazo)] if rechazo else [NS(type="output_text", text=texto)]
    return NS(status=status, incomplete_details=None, output=[NS(type="reasoning"), NS(type="message", content=contenido)],
              output_text=texto or "", usage=NS(input_tokens=2000, output_tokens=300,
                                                input_tokens_details=NS(cached_tokens=1500)))


def test_openai_arma_pedido_y_lee_json():
    cliente = OpenAIFalso(_resp_openai(json.dumps(resultado())))
    r, uso = ClasificadorOpenAI("gpt-6.1-sol", "high", cliente).clasificar(leer(correo_crudo(imagen=PNG * 100)))
    assert r["categoria"] == "pendiente" and uso.entrada_cache == 1500
    p = cliente.pedido
    assert p["model"] == "gpt-6.1-sol" and p["reasoning"] == {"effort": "high"}
    assert p["text"]["format"]["type"] == "json_schema" and p["text"]["format"]["strict"] is True
    tipos = [c["type"] for c in p["input"][1]["content"]]
    assert "input_image" in tipos and tipos[-1] == "input_text"


def test_openai_rechazo_o_incompleto_es_error():
    with pytest.raises(ErrorModelo):
        ClasificadorOpenAI("m", cliente=OpenAIFalso(_resp_openai(rechazo="no"))).clasificar(leer(correo_crudo()))
    with pytest.raises(ErrorModelo):
        ClasificadorOpenAI("m", cliente=OpenAIFalso(_resp_openai("{}", status="incomplete"))).clasificar(leer(correo_crudo()))


class AnthropicFalso:
    def __init__(self, respuesta):
        self.respuesta, self.pedido = respuesta, None
        self.beta = NS(messages=self)

    def create(self, **kw):
        self.pedido = kw
        return self.respuesta


def _resp_anthropic(texto, stop="end_turn"):
    return NS(stop_reason=stop, stop_details=None,
              content=[NS(type="thinking", thinking=""), NS(type="text", text=texto)],
              usage=NS(input_tokens=500, output_tokens=200, cache_read_input_tokens=1700))


def test_anthropic_arma_pedido_y_lee_json():
    cliente = AnthropicFalso(_resp_anthropic(json.dumps(resultado("despacho_acordado", ()))))
    r, uso = ClasificadorAnthropic("claude-sonnet-5-5", "medium", cliente).clasificar(leer(correo_crudo(imagen=PNG * 100)))
    assert r["categoria"] == "despacho_acordado" and uso.entrada_cache == 1700
    p = cliente.pedido
    assert p["output_config"]["format"]["type"] == "json_schema" and p["output_config"]["effort"] == "medium"
    assert p["fallbacks"] == "default" and p["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert p["messages"][0]["content"][1]["type"] == "image"


def test_anthropic_rechazo_es_error():
    with pytest.raises(ErrorModelo):
        ClasificadorAnthropic("m", cliente=AnthropicFalso(_resp_anthropic("", stop="refusal"))).clasificar(leer(correo_crudo()))


def test_tomar_respeta_procesados_y_tomas_recientes():
    b = Buzon(Config(contrasena="x"))
    b.imap = ImapFalso()
    assert b.tomar(1, 1000) is True                      # tramo (1000//10)%6 = 4
    assert ("STORE", "1", "+FLAGS", "(Toma4)") in b.imap.llamadas
    b.imap.flags = b"1 (UID 1 FLAGS (Toma4))"
    assert b.tomar(1, 1015) is False                     # otra corrida lo tomó hace ~10 min
    assert b.tomar(1, 1030) is True                      # pasaron 30 min: la toma venció
    assert ("STORE", "1", "-FLAGS", "(Toma4)") in b.imap.llamadas
    b.imap.flags = b"1 (UID 1 FLAGS (Clasificado Toma4))"
    assert b.tomar(1, 1100) is False
