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
    correo = leer(correo_crudo(asunto="RE: Hora de devolución", de="Ana <ana@sacyr.cl>"))
    resumen = "Javier agenda la devolución. Llevar guía con la dirección de la obra de procedencia."
    assert agenda.cliente_y_obra(correo, resumen) == ("SACYR", "")
    resumen = "Lleva guía de la obra de procedencia; es de la obra Parque Sur, con camión de 5 t."
    assert agenda.cliente_y_obra(correo, resumen) == ("SACYR", "Parque Sur")


def test_la_planilla_lee_fechas_y_horas_como_texto_y_escribe_sin_formulas():
    pedidos = []

    class Probar(agenda.Planilla):
        def _pedir(self, metodo, ruta, cuerpo=None, params=None):
            pedidos.append((ruta, cuerpo, params))
            if params and params.get("valueRenderOption") == "UNFORMATTED_VALUE":
                return {"values": [[46331, 0.4583333333]]}
            return {"values": [COLUMNAS, ["jue 05-11-2026", "11:00", "Devolución", "EBCO", "", "28794", "", "",
                                          "Agendado", "14:30"]]}

    p = Probar("x", token=lambda: "t")
    f = p.leer()[0]
    assert (f[COL["Fecha"]], f[COL["Hora"]], f[COL["Cotización"]], f[COL["Aviso"]]) == ("2026-11-05", "11:00", "28794", "")
    assert f[COL["Nota de bodega"]] == "14:30"  # una nota escrita a mano que parece hora se lee como se ve
    p.agregar([["2026-11-05", "11:00", "Despacho", "=IMPORTXML(1)"] + [""] * 11])
    ruta, cuerpo, params = pedidos[-1]
    assert params["valueInputOption"] == "RAW" and cuerpo["values"][0][0] == 46331


def test_si_google_dice_demasiadas_lecturas_espera_y_reintenta(monkeypatch):
    import io
    import urllib.error
    import urllib.request
    respuestas = [429, 429, 503, None]
    esperas = []

    def abrir(req, timeout=None):
        codigo = respuestas.pop(0)
        if codigo:
            raise urllib.error.HTTPError(req.full_url, codigo, "limite", {}, io.BytesIO(b""))
        return io.BytesIO(b'{"ok": 1}')

    monkeypatch.setattr(urllib.request, "urlopen", abrir)
    monkeypatch.setattr(agenda.Planilla, "_esperar", staticmethod(esperas.append))
    assert agenda.Planilla("x", token=lambda: "t")._pedir("GET", "") == {"ok": 1}
    assert esperas == [2, 4, 8]
    respuestas[:] = [403]
    import pytest
    with pytest.raises(urllib.error.HTTPError):  # sin permiso: no se reintenta
        agenda.Planilla("x", token=lambda: "t")._pedir("GET", "")


def test_si_movieron_las_columnas_la_planilla_falla_en_vez_de_escribir_mal():
    import pytest

    class Movida(agenda.Planilla):
        def _pedir(self, metodo, ruta, cuerpo=None, params=None):
            return {"values": [COLUMNAS[:7] + ["Patente"] + COLUMNAS[7:]]}

    with pytest.raises(ValueError, match="Patente"):
        Movida("x", token=lambda: "t").leer()


def test_si_ya_llego_o_estaba_anulada_no_se_duplica_y_si_no_llego_se_agrega_la_nueva_hora():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    for uid, fecha in ((1, "jue 06-11-2026 10:00"), (2, "vie 07-11-2026 10:00"), (3, "lun 10-11-2026 10:00")):
        agenda.registrar_acordado(p, correo, acordado(fecha), uid, ["c:1"], AHORA)
    p.filas[0][COL["Estado"]], p.filas[1][COL["Estado"]], p.filas[2][COL["Estado"]] = "Llegó", "Anulado", "No llegó"
    assert agenda.registrar_acordado(p, correo, acordado("jue 06-11-2026 10:00"), 4, ["c:1"], AHORA) == "repetido"
    assert agenda.registrar_acordado(p, correo, acordado("vie 07-11-2026 12:00"), 5, ["c:1"], AHORA) == "repetido"
    assert agenda.registrar_acordado(p, correo, acordado("lun 10-11-2026 15:00"), 6, ["c:1"], AHORA) == "agregado"
    assert [(f[COL["Fecha"]], f[COL["Hora"]], f[COL["Estado"]]) for f in p.filas] == [
        ("2026-11-06", "10:00", "Llegó"), ("2026-11-07", "12:00", "Agendado"), ("2026-11-10", "10:00", "No llegó"),
        ("2026-11-10", "15:00", "Agendado")]
    assert "ya había llegado" in p.filas[0][COL["Historial"]] and "vuelve a quedar agendado" in p.filas[1][COL["Historial"]]


def test_las_escrituras_releen_la_fila_si_ordenaron_la_hoja_o_pato_la_marco():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado("jue 06-11-2026 10:00"), 1, ["c:1"], AHORA)
    agenda.registrar_acordado(p, correo, acordado("vie 07-11-2026 10:00"), 2, ["c:2"], AHORA)
    leidas = p.leer()
    p.filas.reverse()  # alguien ordenó la hoja entre la lectura y la escritura
    p.filas[0][COL["Historial"]] += " | 04-11 10:05 pfarias: nota: \"ok\""  # y alguien agregó algo al Historial
    assert agenda._aplicar(p, [(3, leidas[1], {"Hora": "11:00"}, "prueba", None)], AHORA) == 1
    assert p.filas[0][COL["Hora"]] == "11:00" and p.filas[1][COL["Hora"]] == "10:00"
    assert 'pfarias: nota: "ok" | 04-11 10:00 prueba' in p.filas[0][COL["Historial"]]
    p.filas[1][COL["Estado"]] = "Llegó"  # Pato la marcó: no se pisa con un Revisar leído antes
    assert agenda._aplicar(p, [(2, leidas[0], {"Estado": "Revisar"}, "x", None)], AHORA) == 0
    assert p.filas[1][COL["Estado"]] == "Llegó"


def test_el_aviso_se_reserva_antes_de_mandar_y_si_el_correo_falla_se_reintenta(cfg, monkeypatch):
    import pytest
    from clasificador import principal
    p = PlanillaFalsa()
    agenda.registrar_acordado(p, leer(correo_crudo()), acordado(), 1, ["c:27801"], AHORA)
    p.filas[0][COL["Estado"]] = "No llegó"
    cfg.agenda_id = "planilla-de-prueba"
    monkeypatch.setattr(principal, "_planilla", lambda c: p)
    monkeypatch.setattr(principal, "avisar", lambda *a, **k: None)

    def falla(m):
        assert p.filas[0][COL["Aviso"]].startswith("enviando")  # se anotó antes de mandar
        raise OSError("SMTP caído")

    principal._reagendamientos(cfg, BuzonFalso([correo_crudo()]), falla)
    assert p.filas[0][COL["Aviso"]] == ""  # se soltó: la próxima corrida reintenta
    enviados = []
    principal._reagendamientos(cfg, BuzonFalso([correo_crudo()]), enviados.append)
    assert len(enviados) == 1 and p.filas[0][COL["Aviso"]] and not p.filas[0][COL["Aviso"]].startswith("enviando")

    class SinEscritura(PlanillaFalsa):
        def escribir(self, celdas):
            raise PermissionError("403: la cuenta quedó como Lector")

    q = SinEscritura()
    q.filas = [list(f) for f in p.filas]
    q.filas[0][COL["Aviso"]] = ""
    monkeypatch.setattr(principal, "_planilla", lambda c: q)
    otros = []
    for _ in range(3):
        principal._reagendamientos(cfg, BuzonFalso([correo_crudo()]), otros.append)
    assert otros == []  # si no se puede anotar el aviso, no se manda (antes se mandaba cada 3 minutos)
    with pytest.raises(PermissionError):
        agenda.reservar_aviso(q, 2, q.filas[0])


def test_corregir_de_despacho_a_devolucion_anula_la_fila_del_despacho():
    p, correo = PlanillaFalsa(), leer(correo_crudo())
    agenda.registrar_acordado(p, correo, acordado(), 7, ["c:27801"], AHORA)
    assert agenda.anular_uid(p, 7, "corregido", "Despacho", AHORA) == 1
    agenda.registrar_acordado(p, correo, acordado(categoria="recepcion_acordada"), 7, ["c:27801"], AHORA)
    assert [(f[COL["Tipo"]], f[COL["Estado"]]) for f in p.filas] == [("Despacho", "Anulado"), ("Devolución", "Agendado")]


def test_lo_que_se_marco_en_la_app_cuenta_como_tocado_por_bodega():
    fila = [""] * len(COLUMNAS)
    fila[COL["Estado"]], fila[COL["Historial"]] = "Agendado", "04-11 10:00 agregado desde el correo"
    assert not agenda.tocada_por_bodega([fila])
    fila[COL["Historial"]] += " | 04-11 12:00 pfarias: No llegó → Agendado"
    assert agenda.tocada_por_bodega([fila])


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


class PlanillaGrabadora(agenda.Planilla):
    """Planilla que no sale a internet: guarda los pedidos y contesta lo mínimo."""

    def __init__(self, hojas, locale="es_ES"):
        super().__init__("x", token=lambda: "t")
        self.hojas, self.locale, self.pedidos = dict(hojas), locale, []

    def _pedir(self, metodo, ruta, cuerpo=None, params=None):
        self.pedidos.append((metodo, ruta, cuerpo, params))
        campos = (params or {}).get("fields", "")
        if metodo == "GET" and campos.startswith("sheets(properties(sheetId,title))"):
            return {"sheets": [{"properties": {"sheetId": i, "title": t}} for t, i in self.hojas.items()]}
        if metodo == "GET" and campos == "properties(locale)":
            return {"properties": {"locale": self.locale}}
        if metodo == "GET" and "conditionalFormats" in campos:
            return {"sheets": [{"properties": {"sheetId": i}, "conditionalFormats": [{}, {}]} for i in self.hojas.values()]}
        if metodo == "POST" and ruta == ":batchUpdate":
            for p in cuerpo["requests"]:
                if "addSheet" in p:
                    self.hojas[p["addSheet"]["properties"]["title"]] = 100 + len(self.hojas)
        return {}

    def escrito(self, celdas):
        import urllib.parse
        for metodo, ruta, cuerpo, _ in self.pedidos:
            if metodo == "PUT" and urllib.parse.unquote(ruta) == f"/values/{celdas}":
                return cuerpo["values"]
        return None


def test_preparar_arma_semana_hoy_y_agenda_con_formulas_en_espanol():
    p = PlanillaGrabadora({"Hoja 1": 0, "Agenda": 1, "Hoy": 2, "Próximos 7 días": 3})
    agenda.preparar(p)
    lotes = [r for m, ruta, c, _ in p.pedidos if ruta == ":batchUpdate" for r in c["requests"]]
    borradas = {r["deleteSheet"]["sheetId"] for r in lotes if "deleteSheet" in r}
    assert borradas == {0, 3}  # la hoja vacía y la vieja "Próximos 7 días"
    orden = [(r["updateSheetProperties"]["properties"]["sheetId"], r["updateSheetProperties"]["properties"]["index"])
             for r in lotes if "updateSheetProperties" in r and "index" in r["updateSheetProperties"]["properties"]]
    assert orden == [(p.hojas["Semana"], 0), (2, 1), (1, 2)]
    dias = p.escrito("'Semana'!A2:G5")[1]
    assert dias[0].startswith("=TODAY()-WEEKDAY(TODAY();3)+IF(WEEKDAY(TODAY();2)=7;7;0)+7*SWITCH($B$1;")
    assert dias[6] == "=$A$3+6"
    lista = p.escrito("'Semana'!A2:G5")[3][0]
    assert lista.startswith("=IFERROR(SORT(FILTER(ARRAYFORMULA(") and "Agenda!$A$2:$A=A$3" in lista and "," not in lista
    assert p.escrito("'Semana'!B1") == [["Esta semana"]]
    assert "," not in p.escrito("'Hoy'!A1:J3")[2][0] and "Agenda!A2:J;" in p.escrito("'Hoy'!A1:J3")[2][0]
    # los colores viejos se borran antes de crear los nuevos (2 por hoja, en Agenda y Semana)
    assert sum(1 for r in lotes if "deleteConditionalFormatRule" in r) == 4


def test_preparar_otra_vez_no_pisa_la_semana_elegida_y_en_ingles_usa_comas():
    p = PlanillaGrabadora({"Agenda": 1, "Hoy": 2, "Semana": 5}, locale="en_US")
    agenda.preparar(p)
    assert p.escrito("'Semana'!B1") is None
    assert "WEEKDAY(TODAY(),3)" in p.escrito("'Semana'!A2:G5")[1][0]


def test_toneladas_como_numero_para_poder_sumar():
    assert [agenda.toneladas(t) for t in ("camión 10 toneladas", "5 toneladas", "camión 10 t", "1.000 kg", "5T",
                                          "1,5 toneladas", "camión 3/4", "")] == [10, 5, 10, 1, 5, 1.5, "", ""]
    assert agenda.toneladas("camión 3/4", "con carga de 2 toneladas") == 2  # si el camión no lo dice, el resumen
    p = PlanillaFalsa()
    agenda.registrar_acordado(p, leer(correo_crudo()), acordado(resumen="Se agenda con camión de 6 toneladas."), 7,
                              ["c:1"], AHORA)
    f = p.filas[0]
    assert (f[COL["Camión"]], f[COL["Toneladas"]], f[COL["Estado"]]) == ("camión 6 toneladas", 6, "Agendado")


def test_preparar_agrega_la_columna_toneladas_a_una_hoja_vieja_y_la_llena():
    import urllib.parse

    class Vieja(PlanillaGrabadora):
        def _pedir(self, metodo, ruta, cuerpo=None, params=None):
            if metodo == "GET" and urllib.parse.unquote(ruta) == "/values/Agenda!1:1":
                self.pedidos.append((metodo, ruta, cuerpo, params))
                return {"values": [agenda.SIN_TONELADAS]}
            return super()._pedir(metodo, ruta, cuerpo, params)

        def leer(self):
            fila = [""] * len(COLUMNAS)
            fila[COL["Camión"]], fila[COL["Resumen"]] = "camión 10 toneladas", ""
            otra = [""] * len(COLUMNAS)
            otra[COL["Camión"]], otra[COL["Resumen"]] = "camión 3/4", "Javier agenda con carga de 2 toneladas."
            return [fila, otra]

    p = Vieja({"Agenda": 1, "Hoy": 2, "Semana": 5})
    agenda.preparar(p)
    lotes = [r for m, ruta, c, _ in p.pedidos if ruta == ":batchUpdate" for r in c["requests"]]
    insertada = [r["insertDimension"]["range"] for r in lotes if "insertDimension" in r]
    assert insertada == [{"sheetId": 1, "dimension": "COLUMNS", "startIndex": 7, "endIndex": 8}]
    assert p.escrito("Agenda!H2:H3") == [[10], [2]]
    otra = Vieja({"Agenda": 1, "Hoy": 2, "Semana": 5})
    otra._pedir = PlanillaGrabadora._pedir.__get__(otra)  # una hoja que ya tiene Toneladas no se toca
    agenda.preparar(otra)
    assert not any("insertDimension" in r for m, ruta, c, _ in otra.pedidos if ruta == ":batchUpdate" for r in c["requests"])
