import datetime


from clasificador import agenda
from clasificador.agenda import COL, COLUMNAS
from clasificador.correo import leer
from clasificador.reglas import Decision

from tests.test_clasificador import BuzonFalso, ModeloFalso, cfg, correo_crudo, resultado  # noqa: F401

AHORA = datetime.datetime(2026, 11, 4, 10, 0, tzinfo=agenda.CHILE)


class PlanillaFalsa:
    def __init__(self):
        self.filas = []

    def leer(self):
        return [list(f) for f in self.filas]

    def agregar(self, filas):
        self.filas += [list(f) for f in filas]

    def escribir(self, celdas):
        for (n, col), v in celdas.items():
            self.filas[n - 2][COL[col]] = v


def acordado(fecha="jue 06-11-2026 10:00", categoria="despacho_acordado", resumen="Se agenda con camión 3/4."):
    r = resultado(categoria, falta=(), movimiento="despacho" if categoria == "despacho_acordado" else "recepcion")
    r.update(fecha_movimiento=fecha, resumen=resumen)
    return Decision(categoria, r)


def test_fecha_y_hora_desde_el_texto_del_modelo():
    assert agenda.fecha_hora("jue 22-10-2026 12:00") == (datetime.date(2026, 10, 22), "12:00")
    assert agenda.fecha_hora("mié 21-10-2026 11:00 a 12:00") == (datetime.date(2026, 10, 21), "11:00")
    assert agenda.fecha_hora("lun 19-10-2026 AM (sobrecupo)") == (datetime.date(2026, 10, 19), "AM")
    assert agenda.fecha_hora("vie 23/10/26 9.30 hrs") == (datetime.date(2026, 10, 23), "09:30")
    assert agenda.fecha_hora("") == (None, "")
    assert agenda.fecha_hora("mañana sin hora")[0] is None


def test_camion_desde_el_resumen():
    assert agenda.camion("Debe enviar camión 3/4 a las 10.") == "camión 3/4"
    assert agenda.camion("con camión de 6 toneladas") == "camión 6 toneladas"
    assert agenda.camion("sin datos del transporte") == ""


def test_un_acordado_nuevo_agrega_una_fila_agendada():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    assert agenda.registrar_acordado(p, correo, acordado(), 7, ["c:27801"], AHORA) == "agregado"
    f = p.filas[0]
    assert len(f) == len(COLUMNAS)
    assert (f[COL["Fecha"]], f[COL["Hora"]], f[COL["Tipo"]], f[COL["Estado"]]) == ("2026-11-06", "10:00", "Despacho", "Agendado")
    assert f[COL["Camión"]] == "camión 3/4" and f[COL["UID"]] == "7"


def test_la_misma_fecha_en_el_mismo_hilo_no_se_repite():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado(), 7, ["c:27801"], AHORA)
    assert agenda.registrar_acordado(p, correo, acordado("jue 06-11-2026 11:30"), 9, ["c:27801"], AHORA) == "repetido"
    assert len(p.filas) == 1 and p.filas[0][COL["Hora"]] == "11:30"


def test_si_el_modelo_dice_que_se_reagendo_la_fecha_anterior_queda_como_reagendado():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado(), 7, ["c:27801"], AHORA)
    nueva = acordado("lun 10-11-2026 09:00", resumen="Javier reagenda la devolución para el lunes 10-11.")
    assert agenda.registrar_acordado(p, correo, nueva, 9, ["c:27801", "h:x"], AHORA) == "reagendado"
    assert [f[COL["Estado"]] for f in p.filas] == ["Reagendado", "Agendado"]
    assert "se cambió a 2026-11-10 09:00" in p.filas[0][COL["Historial"]]


def test_si_de_dos_fechas_queda_una_la_otra_queda_como_reagendado():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado("lun 09-11-2026 10:00; mar 10-11-2026 10:00", "recepcion_acordada",
                                                  "Javier confirma dos devoluciones."), 7, ["h:a"], AHORA)
    queda = acordado("mar 10-11-2026 10:00", "recepcion_acordada", "Queda sin efecto la fecha del lunes 9.")
    assert agenda.registrar_acordado(p, correo, queda, 9, ["h:a"], AHORA) == "repetido y reagendado"
    assert [f[COL["Estado"]] for f in p.filas] == ["Reagendado", "Agendado"]


def test_en_una_serie_de_fechas_no_se_adivina_cual_se_reagendo():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado("jue 05-11-2026 10:00; jue 12-11-2026 10:00; jue 19-11-2026 10:00",
                                                  "recepcion_acordada", "Javier confirma tres devoluciones."), 7, ["h:a"], AHORA)
    cambio = acordado("vie 13-11-2026 10:00", "recepcion_acordada", "Javier reagenda una devolución para el viernes 13.")
    assert agenda.registrar_acordado(p, correo, cambio, 9, ["h:a"], AHORA) == "agregado"
    assert [f[COL["Estado"]] for f in p.filas] == ["Agendado"] * 4
    assert "si era esta fecha, marcar Reagendado" in p.filas[1][COL["Historial"]]


def test_otra_fecha_sin_decir_que_se_reagendo_puede_ser_otro_movimiento():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado(), 7, ["c:27801"], AHORA)
    segunda = acordado("lun 10-11-2026 09:00", resumen="Javier agenda la segunda devolución para el 10-11.")
    assert agenda.registrar_acordado(p, correo, segunda, 9, ["c:27801"], AHORA) == "agregado"
    assert [f[COL["Estado"]] for f in p.filas] == ["Agendado", "Agendado"]


def test_un_recordatorio_de_la_misma_fecha_no_se_repite_y_reactiva_la_fila():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado(), 7, ["c:27801"], AHORA)
    p.filas[0][COL["Estado"]] = "Revisar"
    recordatorio = acordado("jue 06-11-2026 10:00", resumen="Javier recuerda la devolución de mañana.")
    assert agenda.registrar_acordado(p, correo, recordatorio, 9, ["c:27801"], AHORA) == "repetido"
    assert len(p.filas) == 1 and p.filas[0][COL["Estado"]] == "Agendado"


def test_varias_fechas_en_un_correo_son_varias_filas():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    varias = acordado("mié 04-11-2026 11:00; mié 11-11-2026 11:00; mié 18-11-2026 11:00", "recepcion_acordada",
                      "Javier reagenda y confirma tres devoluciones.")
    assert agenda.registrar_acordado(p, correo, varias, 7, ["h:a"], AHORA) == "agregado x3"
    assert [(f[COL["Fecha"]], f[COL["Estado"]]) for f in p.filas] == [
        ("2026-11-04", "Agendado"), ("2026-11-11", "Agendado"), ("2026-11-18", "Agendado")]
    assert agenda.fechas_horas("05-11-2026 12:00 y 06-11-2026 11:00") == [
        (datetime.date(2026, 11, 5), "12:00"), (datetime.date(2026, 11, 6), "11:00")]
    assert agenda.fecha_hora("vie 06-11-2026 a primera hora") == (datetime.date(2026, 11, 6), "a primera hora")


def test_la_agenda_diaria_de_javier_no_se_carga():
    p = PlanillaFalsa()
    correo = leer(correo_crudo(asunto="AGENDA 04-11-2026"))
    assert agenda.registrar_acordado(p, correo, acordado(categoria="recepcion_acordada"), 7, ["h:b"], AHORA) == "agenda_diaria"
    assert p.filas == []


def test_cliente_y_obra_cuando_el_modelo_no_los_da():
    correo = leer(correo_crudo(asunto="RE: SOLICITUD HORA DEVOLUCION OBRA SEMINARIO", de="Juan <juan@santolaya.cl>"))
    assert agenda.cliente_y_obra(correo) == ("SANTOLAYA", "SEMINARIO")
    correo = leer(correo_crudo(asunto="RE: Devolución // Obra Santa Elena de Chicureo // Constructora Calan SpA",
                               de="Pedro <p@gmail.com>"))
    assert agenda.cliente_y_obra(correo) == ("", "Santa Elena de Chicureo")
    correo = leer(correo_crudo(asunto="RE: hora devolucion", de="Ana <ana@ebco.cl>"))
    assert agenda.cliente_y_obra(correo, "Javier confirma la devolución de Ebco, obra Entrelomas V, para el 04-11.") == (
        "EBCO", "Entrelomas V")


def test_la_planilla_lee_fechas_y_horas_como_texto_y_escribe_sin_formulas():
    pedidos = []

    class Probar(agenda.Planilla):
        def _pedir(self, metodo, ruta, cuerpo=None, params=None):
            pedidos.append((ruta, cuerpo, params))
            return {"values": [[46331, 0.4583333333, "Devolución", "EBCO", "", 28794, "", "Agendado"]]}

    p = Probar("x", token=lambda: "t")
    f = p.leer()[0]
    assert (f[COL["Fecha"]], f[COL["Hora"]], f[COL["Cotización"]], f[COL["Aviso"]]) == ("2026-11-05", "11:00", "28794", "")
    p.agregar([["2026-11-05", "11:00", "Despacho", "=IMPORTXML(1)"] + [""] * 11])
    ruta, cuerpo, params = pedidos[-1]
    assert params["valueInputOption"] == "RAW" and cuerpo["values"][0][0] == 46331


def test_otro_hilo_o_otro_tipo_no_se_toca():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado(), 7, ["c:27801"], AHORA)
    agenda.registrar_acordado(p, correo, acordado("lun 10-11-2026 09:00"), 9, ["c:99999"], AHORA)
    agenda.registrar_acordado(p, correo, acordado("lun 10-11-2026 09:00", "recepcion_acordada"), 10, ["c:27801"], AHORA)
    assert [f[COL["Estado"]] for f in p.filas] == ["Agendado", "Agendado", "Agendado"]
    assert p.filas[2][COL["Tipo"]] == "Devolución"


def test_sin_fecha_queda_para_revisar():
    p = PlanillaFalsa()
    agenda.registrar_acordado(p, leer(correo_crudo()), acordado("según historial"), 7, ["c:1"], AHORA)
    assert p.filas[0][COL["Estado"]] == "Revisar" and "No se entendió la fecha" in p.filas[0][COL["Nota de bodega"]]


def test_cambio_o_anulacion_deja_en_revisar_lo_agendado():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado(), 7, ["c:27801"], AHORA)
    pendiente = Decision("pendiente", resultado(falta=("cambio_o_anulacion",)))
    assert agenda.marcar_cambio(p, correo, pendiente, 9, ["c:27801"], AHORA) == 1
    assert p.filas[0][COL["Estado"]] == "Revisar"


def test_no_llego_vuelve_a_pendientes_con_reagendamiento_una_sola_vez(cfg, monkeypatch):
    from clasificador import principal
    p = PlanillaFalsa()
    agenda.registrar_acordado(p, leer(correo_crudo()), acordado(), 1, ["c:27801"], AHORA)
    p.filas[0][COL["Estado"]] = "No llegó"
    cfg.agenda_id = "planilla-de-prueba"
    monkeypatch.setattr(principal, "_planilla", lambda c: p)
    buzon, enviados = BuzonFalso([correo_crudo()]), []
    principal._reagendamientos(cfg, buzon, enviados.append)
    principal._reagendamientos(cfg, buzon, enviados.append)
    assert len(enviados) == 1
    m = enviados[0]
    assert m["Subject"].startswith("[PENDIENTE DESPACHO] [REAGENDAMIENTO]")
    assert m["To"] == cfg.destino("pendiente")
    assert "NO LLEGÓ" in m.get_body(("plain",)).get_content()
    assert p.filas[0][COL["Aviso"]]


def test_procesar_agrega_los_acordados_a_la_agenda(cfg, monkeypatch):
    from clasificador import principal
    p = PlanillaFalsa()
    cfg.agenda_id = "planilla-de-prueba"
    monkeypatch.setattr(principal, "_planilla", lambda c: p)
    r = resultado("despacho_acordado", falta=())
    r.update(fecha_movimiento="vie 07-11-2026 08:00")
    principal.procesar(cfg, BuzonFalso([correo_crudo()]), ModeloFalso(r), None, [].append)
    assert len(p.filas) == 1 and p.filas[0][COL["Fecha"]] == "2026-11-07"


def test_si_la_agenda_falla_igual_se_reenvia(cfg, monkeypatch):
    from clasificador import principal

    class Rota:
        def leer(self):
            raise RuntimeError("sin permiso")

    cfg.agenda_id = "planilla-de-prueba"
    monkeypatch.setattr(principal, "_planilla", lambda c: Rota())
    monkeypatch.setattr(principal, "avisar", lambda *a, **k: None)
    enviados = []
    principal.procesar(cfg, BuzonFalso([correo_crudo()]), ModeloFalso(resultado("despacho_acordado", falta=())), None,
                       enviados.append)
    assert len(enviados) == 1 and "[DESPACHO ACORDADO]" in enviados[0]["Subject"]


def test_cargar_agenda_usa_la_memoria_y_saca_cliente_y_obra_del_asunto(cfg, monkeypatch):
    from clasificador import principal
    from tests.test_clasificador import BuzonConMemoria
    p = PlanillaFalsa()
    cfg.agenda_id = "planilla-de-prueba"
    monkeypatch.setattr(principal, "_planilla", lambda c: p)
    previo = {"uid": 1, "categoria": "despacho_acordado", "movimiento": "despacho", "fecha_movimiento": "lun 09-11-2026 10:00",
              "n_cotizacion": "27801", "resumen": "Se agenda retiro con camión 3/4."}
    principal.cargar_agenda(cfg, BuzonConMemoria([correo_crudo()], [previo]), [1])
    f = p.filas[0]
    assert (f[COL["Cliente"]], f[COL["Obra"]], f[COL["Fecha"]]) == ("CYPCO", "ECOPARK", "2026-11-09")
