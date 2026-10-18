"""Pruebas de la memoria entre correos (hilos, historial y regla de "repite")."""

from clasificador import memoria
from clasificador.correo import leer
from clasificador.principal import procesar
from clasificador.prompt import texto_del_correo
from clasificador.reglas import decidir
from tests.test_clasificador import BuzonFalso, ModeloFalso, cfg, correo_crudo, resultado  # noqa: F401


def acordado(fecha="2026-10-16T13:16:00", movimiento="recepcion"):
    return {"fecha": fecha, "categoria": "recepcion_acordada" if movimiento == "recepcion" else "despacho_acordado",
            "movimiento": movimiento, "fecha_movimiento": "lun 26-10-2026 15:00", "resumen": "Javier agenda la devolución."}


def test_asunto_generico_de_clientes_distintos_no_se_mezcla():
    a = leer(correo_crudo(asunto="RE: Hora devolucion", de="Pedro <p@cypco.cl>"))
    b = leer(correo_crudo(asunto="Hora devolución", de="Juan <j@hcpro.cl>"))
    c = leer(correo_crudo(asunto="RV: RE: Hora devolucion", de="Otro <o@cypco.cl>"))
    ha, hb, hc = ([k for k in memoria.claves_guardar(x) if k.startswith("h:")] for x in (a, b, c))
    assert ha != hb and ha == hc


def test_claves_por_cotizacion_y_por_referencias():
    crudo = correo_crudo(asunto="RE: Cotización Alzatec N°28204 - CYPCO - UDD").replace(
        b"Message-ID:", b"In-Reply-To: <previo@alzatec.com>\nReferences: <raiz@obra.cl> <previo@alzatec.com>\nMessage-ID:")
    c = leer(crudo)
    assert c.referencias == ["<raiz@obra.cl>", "<previo@alzatec.com>", "<previo@alzatec.com>"]
    assert "c:28204" in memoria.claves_buscar(c)
    padre = leer(correo_crudo(mid="<previo@alzatec.com>"))
    assert set(memoria.claves_guardar(padre)) & set(memoria.claves_buscar(c))


def test_el_historial_va_en_el_texto_para_el_modelo():
    c = leer(correo_crudo(texto="ok gracias"))
    assert "HISTORIAL" not in texto_del_correo(c)
    c.historial = [acordado()]
    assert "HISTORIAL" in texto_del_correo(c) and "lun 26-10-2026 15:00" in texto_del_correo(c)


def test_repite_un_acuerdo_ya_reenviado_no_se_reenvia():
    c = leer(correo_crudo(texto="Gracias, ahí estaremos"))
    c.historial = [acordado()]
    d = decidir(c, ModeloFalso(resultado("recepcion_acordada", falta=(), movimiento="recepcion", repite=True)))
    assert d.categoria == "no_aplica" and d.fuente == "memoria" and "ya se reenvió" in d.nota


def test_repite_sin_acuerdo_en_el_historial_no_cambia_nada():
    c = leer(correo_crudo(texto="Confirmo"))
    c.historial = [dict(acordado(), categoria="pendiente")]          # antes solo estaba pendiente
    d = decidir(c, ModeloFalso(resultado("recepcion_acordada", falta=(), movimiento="recepcion", repite=True)))
    assert d.categoria == "recepcion_acordada"
    c.historial = [acordado(movimiento="despacho")]                  # otro tipo de movimiento
    d = decidir(c, ModeloFalso(resultado("recepcion_acordada", falta=(), movimiento="recepcion", repite=True)))
    assert d.categoria == "recepcion_acordada"


def test_repite_pero_el_modelo_ve_algo_pendiente_se_reenvia():
    c = leer(correo_crudo(texto="Gracias, pero ¿podemos cambiar al martes?"))
    c.historial = [acordado()]
    d = decidir(c, ModeloFalso(resultado("pendiente", falta=("cambio_o_anulacion",), movimiento="recepcion", repite=True)))
    assert d.categoria == "pendiente"


class BuzonConMemoria(BuzonFalso):
    def __init__(self, crudos):
        super().__init__(crudos)
        self.memoria = memoria.MemoriaLocal()

    def historial(self, claves):
        return self.memoria.historial(claves)

    def registrar_decision(self, claves, datos):
        self.memoria.registrar_decision(claves, datos)


def test_procesar_recuerda_lo_reenviado_y_no_repite(cfg):
    primero = correo_crudo(asunto="Cotización Alzatec N°28204 - CYPCO", mid="<1@x.cl>", texto="Se agenda retiro jueves 8:00")
    segundo = correo_crudo(asunto="RE: Cotización Alzatec N°28204 - CYPCO", mid="<2@x.cl>", texto="Gracias!")
    buzon, enviados = BuzonConMemoria([primero, segundo]), []

    class Modelo(ModeloFalso):
        def clasificar(self, correo):
            self.llamadas += 1
            r = resultado("despacho_acordado", falta=(), repite=bool(correo.historial))
            return r, ModeloFalso(r).clasificar(correo)[1]

    procesar(cfg, buzon, Modelo(), None, enviados.append)
    assert len(enviados) == 1                                   # el "gracias" no se reenvía
    assert "NoAplica" in buzon.marcas[2] and len(buzon.memoria.entradas) == 1


def test_un_correo_no_se_ve_a_si_mismo_ni_a_lo_posterior():
    c = leer(correo_crudo())                                   # fecha 13-08-2026 16:37 -04:00
    propio = dict(acordado(fecha="2026-08-13T16:37:50-04:00"), uid=7)
    posterior = dict(acordado(fecha="2026-08-14T09:00:00-03:00"), uid=8)
    anterior = dict(acordado(fecha="2026-08-12T10:00:00-03:00"), uid=6)
    assert memoria.anteriores([anterior, propio, posterior], c, uid=7) == [anterior]
