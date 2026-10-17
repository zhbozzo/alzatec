"""Pruebas sin red: buzón, SMTP y modelos falsos."""

import base64
from email.message import EmailMessage
from email import message_from_bytes, policy

import pytest

from clasificador.config import Config
from clasificador.correo import leer
from clasificador.modelos import ErrorModelo, Uso
from clasificador.principal import procesar, resumen_diario
from clasificador.reglas import decidir

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC")


def correo_crudo(asunto="Re: Cotización Alzatec N°27801 - CYPCO - ECOPARK", de="Cliente <cliente@obra.cl>",
                 texto="Muchas gracias, se aprueba. Por favor despachar.", mid="<a1@obra.cl>", imagen=None):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = de, "asistentetecnico@alzatec.com", asunto
    m["Date"], m["Message-ID"] = "Thu, 13 Aug 2026 16:37:50 -0400", mid
    m.set_content(texto + "\n\nDe: Andrea Salcedo\nEnviado: jueves\nAsunto: Cotización\nAdjunto cotización.")
    if imagen:
        m.add_attachment(imagen, maintype="image", subtype="png", filename="agenda.png")
    return m.as_bytes()


def resultado(categoria="pendiente", falta=("fecha_hora",), confianza="alta", movimiento="despacho"):
    return {"categoria": categoria, "movimiento": movimiento, "falta": list(falta),
            "fecha_movimiento": "", "n_cotizacion": "27801", "cliente": "CYPCO", "obra": "ECOPARK",
            "resumen": "Cliente aprueba y pide despachar; falta fecha.", "motivo": "\"Por favor despachar\"",
            "confianza": confianza}


class ModeloFalso:
    def __init__(self, r=None, error=None, nombre="falso"):
        self.r, self.error, self.nombre, self.llamadas = r, error, nombre, 0

    def clasificar(self, correo):
        self.llamadas += 1
        if self.error:
            raise ErrorModelo(self.error)
        return dict(self.r), Uso(self.nombre, 1000, 0, 200)


class BuzonFalso:
    def __init__(self, crudos):
        self.crudos = dict(enumerate(crudos, 1))
        self.marcas = {uid: set() for uid in self.crudos}

    def pendientes(self):
        return [u for u in self.crudos if "Clasificado" not in self.marcas[u]]

    def leer(self, uid):
        return self.crudos[uid]

    def tomar(self, uid, ahora_min):
        return "Clasificado" not in self.marcas[uid]

    def soltar(self, uid):
        self.marcas[uid].add("Soltado")

    def ya_procesado(self, mid):
        return any("Clasificado" in self.marcas[u] and f"Message-ID: {mid}".encode() in c
                   for u, c in self.crudos.items())

    def marcar(self, uid, *m):
        self.marcas[uid].update(m)

    def descartados_sin_resumir(self):
        return [u for u, m in self.marcas.items() if "NoAplica" in m and "Resumido" not in m]

    def encabezados(self, uid):
        return self.crudos[uid].split(b"\n\n")[0]


@pytest.fixture
def cfg():
    c = Config(contrasena="x", modo="sombra", casilla_prueba="prueba@ejemplo.cl")
    c.resumen_a = c.alertas_a = "prueba@ejemplo.cl"
    return c


def test_leer_separa_texto_citado_e_imagen():
    c = leer(correo_crudo(imagen=PNG * 100))
    assert "Por favor despachar" in c.texto_nuevo
    assert "Andrea Salcedo" in c.texto_citado and "Andrea Salcedo" not in c.texto_nuevo
    assert len(c.imagenes) == 1 and c.imagenes[0].tipo == "image/png"
    assert c.message_id == "<a1@obra.cl>" and c.remitente_correo == "cliente@obra.cl"


def test_imagen_muy_chica_se_ignora():
    assert leer(correo_crudo(imagen=PNG)).imagenes == []


def test_rebote_se_descarta_sin_llamar_al_modelo():
    m = ModeloFalso(resultado())
    d = decidir(leer(correo_crudo(asunto="Mail delivery failed: returning message to sender")), m)
    assert d.categoria == "no_aplica" and d.fuente == "regla" and m.llamadas == 0


def test_agenda_de_javier_es_recepcion_acordada_aunque_el_modelo_dude():
    crudo = correo_crudo(asunto="RE: Solicitud devolución", de="Devoluciones Alzatec <devoluciones@alzatec.com>",
                         texto="Buen dia estimado, según lo conversado, agendo su hora de devolución:")
    d = decidir(leer(crudo), ModeloFalso(resultado("pendiente", ("confirmacion",))))
    assert d.categoria == "recepcion_acordada" and d.fuente == "regla"


def test_error_del_modelo_va_a_pendientes_para_revisar():
    d = decidir(leer(correo_crudo()), ModeloFalso(error="timeout"))
    assert d.categoria == "pendiente" and d.revisar


def test_acordado_con_algo_que_falta_baja_a_pendiente():
    d = decidir(leer(correo_crudo()), ModeloFalso(resultado("despacho_acordado", ("orden_compra",))))
    assert d.categoria == "pendiente" and d.revisar


def test_desacuerdo_entre_modelos_va_a_pendientes():
    principal = ModeloFalso(resultado("despacho_acordado", ()))
    verificador = ModeloFalso(resultado("pendiente", ("confirmacion",)))
    d = decidir(leer(correo_crudo()), principal, verificador)
    assert d.categoria == "pendiente" and d.revisar and verificador.llamadas == 1


def test_acuerdo_entre_modelos_se_respeta():
    principal = ModeloFalso(resultado("despacho_acordado", ()))
    verificador = ModeloFalso(resultado("despacho_acordado", ()))
    d = decidir(leer(correo_crudo()), principal, verificador)
    assert d.categoria == "despacho_acordado" and not d.revisar and d.fuente == "verificado"


def test_no_aplica_con_senal_de_movimiento_se_verifica():
    principal = ModeloFalso(resultado("no_aplica", (), movimiento="ninguno"))
    verificador = ModeloFalso(resultado("pendiente", ("fecha_hora",)))
    d = decidir(leer(correo_crudo()), principal, verificador)  # el texto dice "despachar"
    assert d.categoria == "pendiente" and d.revisar


def test_pendiente_no_gasta_segunda_opinion():
    verificador = ModeloFalso(resultado())
    decidir(leer(correo_crudo()), ModeloFalso(resultado()), verificador)
    assert verificador.llamadas == 0


def test_procesar_reenvia_marca_y_descarta_duplicados(cfg):
    original = correo_crudo()
    buzon = BuzonFalso([original, original, correo_crudo(asunto="Mail delivery failed", mid="<b2@x>")])
    enviados = []
    procesar(cfg, buzon, ModeloFalso(resultado()), None, enviados.append)
    assert len(enviados) == 1  # el duplicado no se reenvía y el rebote no aplica
    assert enviados[0]["To"] == "prueba@ejemplo.cl"
    assert enviados[0]["Subject"].startswith("[SOMBRA] [PENDIENTE]")
    assert "Duplicado" in buzon.marcas[2] and "NoAplica" in buzon.marcas[3]
    assert all("Clasificado" in m for m in buzon.marcas.values())
    adjunto = [p for p in enviados[0].iter_attachments()][0]
    assert adjunto.get_content_type() == "message/rfc822"


def test_en_vivo_va_a_la_casilla_real(cfg):
    cfg.modo = "vivo"
    enviados = []
    procesar(cfg, BuzonFalso([correo_crudo()]), ModeloFalso(resultado("despacho_acordado", ())), None, enviados.append)
    assert enviados[0]["To"] == "despachosconfirmados@alzatec.com"


def test_si_falla_el_smtp_no_se_marca(cfg):
    buzon = BuzonFalso([correo_crudo()])

    def falla(_):
        raise OSError("smtp caído")

    with pytest.raises(OSError):
        procesar(cfg, buzon, ModeloFalso(resultado()), None, falla)
    assert "Clasificado" not in buzon.marcas[1]


def test_correo_ilegible_va_a_pendientes(cfg, monkeypatch):
    import clasificador.principal as p

    def explota(*a, **k):
        raise ValueError("formato raro")

    monkeypatch.setattr(p, "leer", explota)
    enviados = []
    procesar(cfg, BuzonFalso([b"basura"]), ModeloFalso(resultado()), None, enviados.append)
    assert "[REVISAR]" in enviados[0]["Subject"]


def test_resumen_diario_lista_los_descartados(cfg):
    buzon = BuzonFalso([correo_crudo(asunto="Mail delivery failed", mid="<b2@x>")])
    enviados = []
    procesar(cfg, buzon, ModeloFalso(resultado()), None, enviados.append)
    assert resumen_diario(cfg, buzon, enviados.append) == 1
    assert "Resumen diario" in enviados[-1]["Subject"] and "Resumido" in buzon.marcas[1]
    assert resumen_diario(cfg, buzon, enviados.append) == 0


def test_regla_fija_se_respeta_aunque_falle_el_modelo():
    crudo = correo_crudo(asunto="RE: Solicitud devolución", de="Devoluciones Alzatec <devoluciones@alzatec.com>",
                         texto="Buen dia estimado, según lo conversado, agendo su hora de devolución:")
    d = decidir(leer(crudo), ModeloFalso(error="timeout"))
    assert d.categoria == "recepcion_acordada" and d.revisar


def test_adjunto_original_es_un_mensaje_valido(cfg):
    from clasificador.envio import armar_reenvio
    from clasificador.reglas import Decision, VACIO
    c = leer(correo_crudo(texto="Ñandú, despachar mañana", imagen=PNG * 100))
    m = armar_reenvio(cfg, c, Decision("pendiente", dict(VACIO)), "p@x.cl")
    vuelta = message_from_bytes(m.as_bytes(), policy=policy.default)
    adjunto = list(vuelta.iter_attachments())[0]
    assert adjunto.get_content_type() == "message/rfc822"
    assert adjunto["Content-Transfer-Encoding"] in (None, "7bit", "8bit")
    interno = adjunto.get_content()
    assert "despachar" in interno.get_body(("plain",)).get_content()



def test_sin_servicio_el_correo_queda_esperando(cfg):
    from clasificador.modelos import ErrorServicio

    class SinSaldo:
        def clasificar(self, correo):
            raise ErrorServicio("openai_sin_saldo", "Sin saldo en OpenAI", "Recargar créditos")

    buzon = BuzonFalso([correo_crudo()])
    enviados = []
    with pytest.raises(ErrorServicio):
        procesar(cfg, buzon, SinSaldo(), None, enviados.append)
    assert enviados == [] and "Clasificado" not in buzon.marcas[1] and "Soltado" in buzon.marcas[1]


class BuzonAlertas:
    def __init__(self, reciente=False, abiertas=()):
        self.reciente, self.abiertas, self.registradas, self.cerradas = reciente, list(abiertas), [], False

    def alerta_reciente(self, tipo, ahora):
        return self.reciente

    def registrar_alerta(self, tipo, ahora):
        self.registradas.append(tipo)

    def alertas_abiertas(self):
        return self.abiertas

    def cerrar_alertas(self):
        self.cerradas = True


def test_alerta_llega_a_los_dos_correos_con_que_hacer(cfg):
    from clasificador.principal import avisar
    cfg.alertas_a = ["lbozzo@fen.uchile.cl", "lbpiphone4@gmail.com"]
    buzon, enviados = BuzonAlertas(), []
    avisar(cfg, buzon, enviados.append, "openai_sin_saldo", "Sin saldo en OpenAI",
           "Recargar créditos en https://platform.openai.com", "RateLimitError", "procesar")
    m = enviados[0]
    assert m["To"] == "lbozzo@fen.uchile.cl, lbpiphone4@gmail.com"
    assert "Sin saldo en OpenAI" in m["Subject"] and "Recargar créditos" in m.get_content()
    assert buzon.registradas == ["openai_sin_saldo"]


def test_alerta_no_se_repite_antes_de_3_horas(cfg):
    from clasificador.principal import avisar
    enviados = []
    avisar(cfg, BuzonAlertas(reciente=True), enviados.append, "x", "t", "h", "d", "procesar")
    assert enviados == []


def test_sin_registro_de_alertas_avisa_solo_una_vez_por_hora(cfg, monkeypatch):
    from clasificador import principal

    class SinRegistro(BuzonAlertas):
        def alerta_reciente(self, tipo, ahora):
            raise RuntimeError("No se pudo abrir la carpeta Alertas")

        def registrar_alerta(self, tipo, ahora):
            raise RuntimeError("No se pudo abrir la carpeta Alertas")

    enviados = []
    for minuto, avisa in [(0, True), (3, False), (30, False), (61, True)]:
        monkeypatch.setattr(principal.time, "time", lambda m=minuto: 1_800_000_000 - 1_800_000_000 % 3600 + m * 60)
        antes = len(enviados)
        principal.avisar(cfg, SinRegistro(), enviados.append, "x", "t", "h", "d", "procesar")
        assert (len(enviados) > antes) is avisa


def test_aviso_de_resuelto(cfg):
    from clasificador.principal import avisar_si_se_resolvio
    buzon, enviados = BuzonAlertas(abiertas=["openai_sin_saldo"]), []
    avisar_si_se_resolvio(cfg, buzon, enviados.append)
    assert "[RESUELTO]" in enviados[0]["Subject"] and buzon.cerradas
    enviados.clear()
    avisar_si_se_resolvio(cfg, BuzonAlertas(), enviados.append)
    assert enviados == []



def test_en_vivo_sin_casilla_de_prueba_el_resumen_va_a_las_alertas(monkeypatch):
    monkeypatch.setenv("AGENTE_PW", "x")
    monkeypatch.setenv("MODO", "vivo")
    monkeypatch.setenv("PREFIJO", "[PRUEBA]")
    c = Config.desde_entorno()
    assert c.resumen_a == "lbozzo@fen.uchile.cl, lbpiphone4@gmail.com"
    enviados = []
    procesar(c, BuzonFalso([correo_crudo()]), ModeloFalso(resultado()), None, enviados.append)
    assert enviados[0]["To"] == "pendientesdespachoyrecepcion@alzatec.com"
    assert enviados[0]["Subject"].startswith("[PRUEBA] [PENDIENTE]")
