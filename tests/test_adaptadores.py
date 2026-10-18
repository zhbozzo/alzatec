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
        self.messages = self

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
    assert "fallbacks" not in p and p["system"][0]["cache_control"] == {"type": "ephemeral"}
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



def _error_openai(clase, status, body):
    import httpx2
    import openai
    pedido = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    return getattr(openai, clase)("error", response=httpx2.Response(status, request=pedido), body=body)


def test_diagnostico_sin_saldo_clave_y_error_de_un_correo():
    import openai
    from clasificador.modelos import ErrorServicio, diagnosticar
    sin_saldo = diagnosticar(_error_openai("RateLimitError", 429, {"code": "insufficient_quota"}), "openai", "gpt-6.1-sol", openai)
    assert isinstance(sin_saldo, ErrorServicio) and sin_saldo.tipo == "openai_sin_saldo"
    assert "Recargar créditos" in sin_saldo.que_hacer
    clave = diagnosticar(_error_openai("AuthenticationError", 401, None), "openai", "gpt-6.1-sol", openai)
    assert isinstance(clave, ErrorServicio) and clave.tipo == "openai_clave"
    limite = diagnosticar(_error_openai("RateLimitError", 429, {"code": "rate_limit_exceeded"}), "openai", "m", openai)
    assert limite.tipo == "openai_limite"
    caido = diagnosticar(_error_openai("InternalServerError", 503, None), "openai", "m", openai)
    assert caido.tipo == "openai_caido"
    solo_este = diagnosticar(_error_openai("BadRequestError", 400, {"code": "invalid_image"}), "openai", "m", openai)
    assert isinstance(solo_este, ErrorModelo)


def test_openai_sin_saldo_llega_como_error_de_servicio():
    from clasificador.modelos import ErrorServicio

    class SinSaldo:
        responses = None

        def __init__(self):
            self.responses = self

        def create(self, **kw):
            raise _error_openai("RateLimitError", 429, {"code": "insufficient_quota"})

    with pytest.raises(ErrorServicio) as e:
        ClasificadorOpenAI("gpt-6.1-sol", cliente=SinSaldo()).clasificar(leer(correo_crudo()))
    assert e.value.tipo == "openai_sin_saldo"


class ImapAlertas(ImapFalso):
    """Como el Dovecot de cPanel: las carpetas van dentro de INBOX ("INBOX.Alertas")."""
    CARPETA = "INBOX.Alertas"

    def __init__(self, fecha_alerta):
        super().__init__()
        self.fecha_alerta, self.seleccionada, self.agregados = fecha_alerta, "INBOX", []

    def namespace(self):
        return "OK", [b'(("INBOX." ".")) NIL NIL']

    def create(self, carpeta):
        return "NO", [b"ya existe" if carpeta == self.CARPETA else b"nonexistent namespace"]

    def select(self, carpeta):
        if carpeta not in ("INBOX", self.CARPETA):
            return "NO", [b"Mailbox doesn't exist"]
        self.seleccionada = carpeta
        return "OK", [b"1"]

    def append(self, carpeta, flags, fecha, texto):
        self.agregados.append((carpeta, texto))
        return "OK", [b""]

    def uid(self, comando, *args):
        if self.seleccionada == self.CARPETA and comando == "SEARCH":
            return "OK", [b"7"]
        if self.seleccionada == self.CARPETA and comando == "FETCH":
            meta = f'7 (UID 7 INTERNALDATE "{self.fecha_alerta}" BODY[HEADER.FIELDS (SUBJECT)] {{30}}'.encode()
            return "OK", [(meta, b"Subject: alerta:openai_sin_saldo\r\n\r\n"), b")"]
        return super().uid(comando, *args)


class ImapAlertasSinPrefijo(ImapAlertas):
    CARPETA = "Alertas"

    def namespace(self):
        return "OK", [b'(("" "/")) NIL NIL']


@pytest.mark.parametrize("imap", [ImapAlertas, ImapAlertasSinPrefijo])
def test_cuenta_de_alertas_en_la_carpeta_alertas(imap):
    import imaplib
    import time
    hace_una_hora = time.time() - 3600
    b = Buzon(Config(contrasena="x"))
    b.imap = imap(imaplib.Time2Internaldate(hace_una_hora).strip('"'))
    ahora = time.time()
    assert b.alerta_reciente("openai_sin_saldo", ahora) is True
    assert b.alerta_reciente("openai_clave", ahora) is False
    assert b.alerta_reciente("openai_sin_saldo", ahora + 3 * 3600) is False
    assert b.alertas_abiertas() == ["openai_sin_saldo"]
    assert b.imap.seleccionada == "INBOX"          # siempre vuelve a la bandeja de entrada
    b.registrar_alerta("openai_clave", ahora)
    assert b.imap.agregados[0][0] == imap.CARPETA and b"alerta:openai_clave" in b.imap.agregados[0][1]
    assert b.imap.seleccionada == "INBOX"
    b.cerrar_alertas()
    assert ("STORE", "7", "+FLAGS", "(Resuelta)") in b.imap.llamadas


def test_estado_cuenta_y_lista_los_ultimos_sin_tocar_nada():
    b = Buzon(Config(contrasena="x"))
    b.imap = ImapFalso()
    e = b.estado(n=2)
    assert e["total"] == 3 and len(e["ultimos"]) == 2 and e["sin_clasificar_desde"] is None
    assert not any(c[0] == "STORE" for c in b.imap.llamadas)


def test_cambiar_marcas_solo_las_del_clasificador():
    b = Buzon(Config(contrasena="x"))
    b.imap = ImapFalso()
    b.cambiar_marcas(["-Clasificado", "+Resumido"], [7])
    assert ("STORE", "7", "-FLAGS", "(Clasificado)") in b.imap.llamadas
    assert ("STORE", "7", "+FLAGS", "(Resumido)") in b.imap.llamadas
    with pytest.raises(ValueError):
        b.cambiar_marcas(["+\\Deleted"], [7])


class ImapRegistro(ImapFalso):
    """Carpeta INBOX.Registro con búsqueda por asunto, como Dovecot."""

    def __init__(self):
        super().__init__()
        self.seleccionada, self.mensajes = "INBOX", {}

    def namespace(self):
        return "OK", [b'(("INBOX." ".")) NIL NIL']

    def create(self, carpeta):
        return "NO", [b"ya existe"]

    def select(self, carpeta):
        if carpeta not in ("INBOX", "INBOX.Registro"):
            return "NO", [b"no existe"]
        self.seleccionada = carpeta
        return "OK", [b"1"]

    def append(self, carpeta, flags, fecha, texto):
        self.mensajes[len(self.mensajes) + 1] = texto
        return "OK", [b""]

    def uid(self, comando, *args):
        if self.seleccionada == "INBOX.Registro" and comando == "SEARCH":
            buscado = args[-1].strip('"').encode()
            return "OK", [b" ".join(str(u).encode() for u, t in self.mensajes.items() if buscado in t.split(b"\r\n")[0])]
        if self.seleccionada == "INBOX.Registro" and comando == "FETCH":
            cuerpo = self.mensajes[int(args[0])].split(b"\r\n\r\n", 1)[1]
            return "OK", [(b"1 (BODY[TEXT] {10}", cuerpo), b")"]
        return super().uid(comando, *args)


def test_registro_guarda_y_encuentra_por_clave():
    b = Buzon(Config(contrasena="x"))
    b.imap = ImapRegistro()
    b.registrar_decision(["c:28204", "h:abc"], {"fecha": "2026-10-16T10:00", "categoria": "despacho_acordado"})
    b.registrar_decision(["c:99999"], {"fecha": "2026-10-16T11:00", "categoria": "pendiente"})
    assert [h["categoria"] for h in b.historial(["c:28204"])] == ["despacho_acordado"]
    assert b.historial(["c:11111"]) == [] and b.imap.seleccionada == "INBOX"
    assert b.historial([]) == []
