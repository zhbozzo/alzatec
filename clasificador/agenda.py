"""Agenda de camiones en Google Sheets, paralela al Excel de Pato.

La llena el clasificador con los despachos y las devoluciones acordadas. Pato marca en la columna Estado qué
pasó con cada camión. Si marca "No llegó", el clasificador avisa en la casilla de pendientes con
[REAGENDAMIENTO] para que Andrea o Javier lo vuelvan a agendar.

- Una fila por movimiento acordado. Si en el mismo hilo se acuerda otra fecha, la fila anterior queda como
  "Reagendado" (Pato la puede volver a "Agendado" si era otro despacho).
- Un pedido de cambio o anulación en el mismo hilo deja la fila en "Revisar".
- La planilla es del usuario y está compartida con la cuenta del clasificador; sin AGENDA_ID no hace nada.
"""

import datetime
import json
import re
import urllib.parse
import urllib.request

HOJA = "Agenda"
COLUMNAS = ["Fecha", "Hora", "Tipo", "Cliente", "Obra", "Cotización", "Camión", "Estado", "Nota de bodega",
            "Resumen", "Correo", "Historial", "Hilo", "UID", "Aviso"]
ESTADOS = ["Agendado", "Llegó", "No llegó", "Reagendado", "Anulado", "Revisar"]
TIPOS = {"despacho_acordado": "Despacho", "recepcion_acordada": "Devolución"}
CHILE = datetime.timezone(datetime.timedelta(hours=-3))
COL = {nombre: i for i, nombre in enumerate(COLUMNAS)}
ULTIMA = chr(ord("A") + len(COLUMNAS) - 1)


def _letra(nombre):
    return chr(ord("A") + COL[nombre])


# --- Datos de cada fila ---------------------------------------------------------------------------------

def fecha_hora(texto, hoy=None):
    """De "jue 22-10-2026 12:00" saca (fecha, hora). Sin fecha clara devuelve (None, texto)."""
    texto = texto or ""
    m = re.search(r"(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?", texto)
    if not m:
        return None, texto.strip()[:40]
    hoy = hoy or datetime.datetime.now(CHILE).date()
    anio = int(m.group(3)) if m.group(3) else hoy.year
    anio = anio + 2000 if anio < 100 else anio
    try:
        fecha = datetime.date(anio, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None, texto.strip()[:40]
    resto = texto[m.end():]
    h = re.search(r"(\d{1,2})[:.](\d{2})", resto)
    if h:
        hora = f"{int(h.group(1)):02d}:{h.group(2)}"
    else:
        franja = re.search(r"\b(AM|PM|mañana|tarde)\b", resto, re.I)
        hora = franja.group(1).upper() if franja and franja.group(1).lower() in ("am", "pm") else (
            franja.group(1) if franja else "")
    return fecha, hora


def camion(*textos):
    """Tipo de camión si el correo lo dice ("camión 3/4", "camión de 6 toneladas", "5T")."""
    for t in textos:
        m = re.search(r"cami[oó]n(?:\s+(?:de|abierto|cerrado|rampla))*\s+([^\s,.;]{1,12}(?:\s*(?:ton\w*|kg|kilos|t))?)",
                      t or "", re.I)
        if m:
            return "camión " + m.group(1)
        m = re.search(r"\b(\d{1,2}(?:[.,]\d)?\s*(?:ton(?:eladas)?|T))\b", t or "")
        if m:
            return m.group(1)
    return ""


def fila_nueva(correo, decision, uid, claves, ahora=None):
    r = decision.resultado
    fecha, hora = fecha_hora(r.get("fecha_movimiento"))
    ahora = ahora or datetime.datetime.now(CHILE)
    valores = {
        "Fecha": fecha.isoformat() if fecha else "",
        "Hora": hora,
        "Tipo": TIPOS[decision.categoria],
        "Cliente": r.get("cliente", ""),
        "Obra": r.get("obra", ""),
        "Cotización": r.get("n_cotizacion", ""),
        "Camión": camion(r.get("resumen"), correo.texto_nuevo),
        "Estado": "Agendado" if fecha else "Revisar",
        "Nota de bodega": "" if fecha else "No se entendió la fecha: " + (r.get("fecha_movimiento") or "")[:60],
        "Resumen": (r.get("resumen") or "")[:300],
        "Correo": f"{(correo.asunto or '')[:120]} · {(correo.fecha or '')[:16]}",
        "Historial": f"{ahora:%d-%m %H:%M} agregado desde el correo",
        "Hilo": " ".join(claves),
        "UID": str(uid),
        "Aviso": "",
    }
    return [valores[c] for c in COLUMNAS]


# --- Planilla -------------------------------------------------------------------------------------------

def token_metadata():
    """Token de la cuenta del job de Cloud Run, con permiso solo para planillas."""
    url = ("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
           "?scopes=https://www.googleapis.com/auth/spreadsheets")
    req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["access_token"]


class Planilla:
    """Lo mínimo de la API de Google Sheets que usa la agenda."""

    def __init__(self, id_planilla, token=token_metadata):
        self.id = id_planilla
        self._token = token
        self._valor_token = None

    def _pedir(self, metodo, ruta, cuerpo=None, params=None):
        if self._valor_token is None:
            self._valor_token = self._token()
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.id}{ruta}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(url, data=datos, method=metodo, headers={
            "Authorization": f"Bearer {self._valor_token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def info(self):
        return self._pedir("GET", "", params={"fields": "sheets(properties(sheetId,title))"})

    def info_locale(self):
        return self._pedir("GET", "", params={"fields": "properties(locale)"}).get("properties", {}).get("locale")

    def leer(self):
        rango = urllib.parse.quote(f"{HOJA}!A2:{ULTIMA}")
        filas = self._pedir("GET", f"/values/{rango}").get("values", [])
        return [f + [""] * (len(COLUMNAS) - len(f)) for f in filas]

    def agregar(self, filas):
        rango = urllib.parse.quote(f"{HOJA}!A1")
        self._pedir("POST", f"/values/{rango}:append", {"values": filas},
                    {"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"})

    def escribir(self, celdas):
        """celdas: {(n_fila, columna): valor}, con n_fila contando desde 2 (la 1 son los títulos)."""
        if celdas:
            datos = [{"range": f"{HOJA}!{_letra(c)}{n}", "values": [[v]]} for (n, c), v in celdas.items()]
            self._pedir("POST", "/values:batchUpdate", {"valueInputOption": "USER_ENTERED", "data": datos})

    def lote(self, pedidos):
        self._pedir("POST", ":batchUpdate", {"requests": pedidos})


def ver(planilla):
    """Resumen de solo lectura para revisar la planilla a distancia."""
    hojas = [h["properties"]["title"] for h in planilla.info()["sheets"]]
    filas = planilla.leer()
    vistas = {}
    for t in ("Hoy", "Próximos 7 días"):
        if t in hojas:
            rango = urllib.parse.quote(f"'{t}'!A1:I6")
            vistas[t] = planilla._pedir("GET", f"/values/{rango}").get("values", [])
    return {"hojas": hojas, "locale": planilla.info_locale(), "filas": len(filas),
            "estados": {e: sum(1 for f in filas if f[COL["Estado"]] == e) for e in ESTADOS},
            "ultimas": [f[:9] for f in filas[-5:]], "vistas": vistas}


def preparar(planilla):
    """Deja la planilla lista: hoja Agenda con títulos, lista de estados y colores, y las hojas Hoy y
    Próximos 7 días con fórmulas que ordenan por fecha y hora. Se puede correr más de una vez."""
    hojas = {h["properties"]["title"]: h["properties"]["sheetId"] for h in planilla.info()["sheets"]}
    pedidos = [{"addSheet": {"properties": {"title": t}}} for t in (HOJA, "Hoy", "Próximos 7 días") if t not in hojas]
    if pedidos:
        planilla.lote(pedidos)
        hojas = {h["properties"]["title"]: h["properties"]["sheetId"] for h in planilla.info()["sheets"]}
    agenda = hojas[HOJA]
    planilla._pedir("PUT", "/values/" + urllib.parse.quote(f"{HOJA}!A1:{ULTIMA}1"), {"values": [COLUMNAS]},
                    {"valueInputOption": "RAW"})
    # Las fórmulas se escriben como las escribiría una persona: en planillas en español los argumentos se
    # separan con punto y coma.
    idioma = (planilla.info_locale() or "en").split("_")[0]
    sep = ";" if idioma in ("es", "pt", "de", "fr", "it", "nl", "ru", "tr", "pl") else ","
    hoy = f'YEAR(TODAY())&"-"&TEXT(MONTH(TODAY()){sep}"00")&"-"&TEXT(DAY(TODAY()){sep}"00")'
    en7 = f'YEAR(TODAY()+7)&"-"&TEXT(MONTH(TODAY()+7){sep}"00")&"-"&TEXT(DAY(TODAY()+7){sep}"00")'
    columnas = "Col1, Col2, Col3, Col4, Col5, Col6, Col7, Col8, Col9"
    for titulo, condicion in (("Hoy", f"Col1 = date '\"&{hoy}&\"'"),
                              ("Próximos 7 días", f"Col1 >= date '\"&{hoy}&\"' and Col1 <= date '\"&{en7}&\"'")):
        formula = (f'=IFERROR(QUERY({{{HOJA}!A1:I}}{sep}"select {columnas} where {condicion} '
                   f'order by Col1, Col2"{sep}1){sep}"Sin movimientos")')
        planilla._pedir("PUT", "/values/" + urllib.parse.quote(f"'{titulo}'!A1:A2"),
                        {"values": [[f"{titulo} (se actualiza sola; el estado se cambia en la hoja Agenda)"],
                                    [formula]]}, {"valueInputOption": "USER_ENTERED"})
    rango = {"sheetId": agenda, "startRowIndex": 1, "startColumnIndex": COL["Estado"], "endColumnIndex": COL["Estado"] + 1}
    colores = {"Llegó": (0.85, 0.94, 0.83), "No llegó": (0.96, 0.8, 0.8), "Reagendado": (1, 0.9, 0.7),
               "Anulado": (0.85, 0.85, 0.85), "Revisar": (1, 0.95, 0.6)}
    pedidos = [
        {"updateSheetProperties": {"properties": {"sheetId": agenda, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": {"sheetId": agenda, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}},
        {"repeatCell": {"range": {"sheetId": agenda, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 1},
                        "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "ddd dd-mm-yyyy"}}},
                        "fields": "userEnteredFormat.numberFormat"}},
        {"setDataValidation": {"range": rango, "rule": {
            "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": e} for e in ESTADOS]},
            "strict": True, "showCustomUi": True}}},
    ] + [{"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": [{"sheetId": agenda, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(COLUMNAS)}],
        "booleanRule": {"condition": {"type": "CUSTOM_FORMULA",
                                      "values": [{"userEnteredValue": f'=${_letra("Estado")}2="{estado}"'}]},
                        "format": {"backgroundColor": {"red": r, "green": g, "blue": b}}}}}}
        for estado, (r, g, b) in colores.items()]
    planilla.lote(pedidos)


# --- Lógica ---------------------------------------------------------------------------------------------

def _mismo_hilo(fila, claves):
    return bool(set(fila[COL["Hilo"]].split()) & set(claves))


def _historial(fila, texto, ahora):
    previo = fila[COL["Historial"]]
    return (previo + " | " if previo else "") + f"{ahora:%d-%m %H:%M} {texto}"


def registrar_acordado(planilla, correo, decision, uid, claves, ahora=None):
    """Agrega el movimiento acordado. Si en el mismo hilo había otro del mismo tipo todavía agendado para
    otra fecha futura, lo deja como Reagendado. Si ya estaba la misma fecha, no lo repite."""
    ahora = ahora or datetime.datetime.now(CHILE)
    nueva = fila_nueva(correo, decision, uid, claves, ahora)
    filas = planilla.leer()
    celdas = {}
    for n, f in enumerate(filas, start=2):
        if not _mismo_hilo(f, claves) or f[COL["Tipo"]] != nueva[COL["Tipo"]]:
            continue
        if f[COL["Fecha"]] == nueva[COL["Fecha"]] and f[COL["Estado"]] in ("Agendado", "Reagendado", "Revisar"):
            if nueva[COL["Hora"]] and f[COL["Hora"]] != nueva[COL["Hora"]]:
                celdas[(n, "Hora")] = nueva[COL["Hora"]]
            celdas[(n, "Historial")] = _historial(f, f"confirmado de nuevo (UID {uid})", ahora)
            planilla.escribir(celdas)
            return "repetido"
        if f[COL["Estado"]] == "Agendado" and f[COL["Fecha"]] >= ahora.date().isoformat() and nueva[COL["Fecha"]]:
            celdas[(n, "Estado")] = "Reagendado"
            celdas[(n, "Historial")] = _historial(f, f"nueva fecha {nueva[COL['Fecha']]} {nueva[COL['Hora']]} "
                                                     f"(UID {uid}); si era otro movimiento, volver a Agendado", ahora)
    planilla.escribir(celdas)
    planilla.agregar([nueva])
    return "agregado"


def marcar_cambio(planilla, correo, decision, uid, claves, ahora=None):
    """Un pendiente de cambio o anulación deja en Revisar lo agendado a futuro en el mismo hilo."""
    ahora = ahora or datetime.datetime.now(CHILE)
    tipo = {"despacho": "Despacho", "recepcion": "Devolución"}.get(decision.resultado.get("movimiento"))
    celdas = {}
    for n, f in enumerate(planilla.leer(), start=2):
        if (_mismo_hilo(f, claves) and (tipo is None or f[COL["Tipo"]] == tipo) and f[COL["Estado"]] == "Agendado"
                and f[COL["Fecha"]] >= ahora.date().isoformat()):
            celdas[(n, "Estado")] = "Revisar"
            celdas[(n, "Historial")] = _historial(f, f"piden cambio o anulación (UID {uid})", ahora)
    planilla.escribir(celdas)
    return len(celdas) // 2


def anular_uid(planilla, uid, motivo, ahora=None):
    """Una corrección que saca un acordado deja su fila como Anulado (no se borra)."""
    ahora = ahora or datetime.datetime.now(CHILE)
    celdas = {}
    for n, f in enumerate(planilla.leer(), start=2):
        if f[COL["UID"]] == str(uid) and f[COL["Estado"]] not in ("Anulado", "Llegó"):
            celdas[(n, "Estado")] = "Anulado"
            celdas[(n, "Historial")] = _historial(f, motivo, ahora)
    planilla.escribir(celdas)
    return len(celdas) // 2


def no_llegaron(planilla):
    """Filas que Pato marcó "No llegó" y que todavía no se avisaron: [(n_fila, fila)]."""
    return [(n, f) for n, f in enumerate(planilla.leer(), start=2) if f[COL["Estado"]] == "No llegó" and not f[COL["Aviso"]]]


def marcar_avisado(planilla, n, fila, ahora=None):
    ahora = ahora or datetime.datetime.now(CHILE)
    planilla.escribir({(n, "Aviso"): f"{ahora:%d-%m %H:%M}",
                       (n, "Historial"): _historial(fila, "aviso de reagendamiento enviado a pendientes", ahora)})


def texto_aviso(fila):
    return (
        f"Bodega marcó en la agenda que el camión NO LLEGÓ. Hay que volver a agendar.\n\n"
        f"Tipo: {fila[COL['Tipo']]}\nFecha que estaba agendada: {fila[COL['Fecha']]} {fila[COL['Hora']]}\n"
        f"Cliente: {fila[COL['Cliente']]}\nObra: {fila[COL['Obra']]}\nCotización: {fila[COL['Cotización']]}\n"
        f"Camión: {fila[COL['Camión']]}\nNota de bodega: {fila[COL['Nota de bodega']]}\n\n"
        f"Resumen del acuerdo: {fila[COL['Resumen']]}\nCorreo original: {fila[COL['Correo']]} (adjunto si está disponible)\n\n"
        "Cuando se acuerde la nueva fecha por correo, el agente la agrega sola a la agenda."
    )
