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
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import getaddresses

from . import memoria

HOJA = "Agenda"
COLUMNAS = ["Fecha", "Hora", "Tipo", "Cliente", "Obra", "Cotización", "Camión", "Toneladas", "Estado", "Nota de bodega",
            "Resumen", "Correo", "Historial", "Hilo", "UID", "Aviso"]
SIN_TONELADAS = [c for c in COLUMNAS if c != "Toneladas"]  # cómo era la hoja antes del 5-nov
CORREOS = "Correos"  # pestaña con una copia de cada correo, para verlo desde la Agenda
COLUMNAS_CORREO = ["UID", "Fecha", "De", "Para", "CC", "Asunto", "Adjuntos", "Texto"]
LARGO_TEXTO = 12000
ENLACE = "Ver correo"  # última columna de la Agenda (una fórmula; el clasificador no escribe ahí)
ESTADOS = ["Agendado", "Llegó", "No llegó", "Reagendado", "Anulado", "Revisar"]
TIPOS = {"despacho_acordado": "Despacho", "recepcion_acordada": "Devolución"}
try:  # hora de Chile con su horario de invierno (UTC-4) y de verano (UTC-3)
    from zoneinfo import ZoneInfo
    CHILE = ZoneInfo("America/Santiago")
except Exception:  # sin base de zonas horarias
    CHILE = datetime.timezone(datetime.timedelta(hours=-3))
COL = {nombre: i for i, nombre in enumerate(COLUMNAS)}
ULTIMA = chr(ord("A") + len(COLUMNAS) - 1)


def _letra(nombre):
    return chr(ord("A") + COL[nombre])


# --- Datos de cada fila ---------------------------------------------------------------------------------

FECHA = re.compile(r"(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?")


def _hora(resto):
    h = re.search(r"(\d{1,2})[:.](\d{2})", resto)
    if h:
        return f"{int(h.group(1)):02d}:{h.group(2)}"
    franja = re.search(r"\b(AM|PM|mañana|tarde)\b", resto, re.I)
    if franja:
        return franja.group(1).upper() if franja.group(1).lower() in ("am", "pm") else franja.group(1)
    return re.sub(r"^[\s,;:y]+|[\s,;:]+$", "", resto)[:25]


def fechas_horas(texto, hoy=None):
    """Todas las fechas del texto del modelo, cada una con su hora:
    "mié 04-11-2026 11:00; mié 11-11-2026 11:00" -> [(4-nov, "11:00"), (11-nov, "11:00")]. Sin fecha: []."""
    texto, hoy = texto or "", hoy or datetime.datetime.now(CHILE).date()
    marcas, salida = list(FECHA.finditer(texto)), []
    for i, m in enumerate(marcas):
        anio = int(m.group(3)) if m.group(3) else hoy.year
        anio = anio + 2000 if anio < 100 else anio
        try:
            fecha = datetime.date(anio, int(m.group(2)), int(m.group(1)))
        except ValueError:
            continue
        resto = texto[m.end():marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)]
        if fecha not in [f for f, _ in salida]:
            salida.append((fecha, _hora(resto)))
    return salida


def fecha_hora(texto, hoy=None):
    """La primera fecha con su hora. Sin fecha clara devuelve (None, texto)."""
    todas = fechas_horas(texto, hoy)
    return todas[0] if todas else (None, (texto or "").strip()[:40])


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


def toneladas(*textos):
    """Las toneladas como número, para poder sumarlas: "camión 10 toneladas" -> 10, "1.000 kg" -> 1.
    Si no se dicen ("camión 3/4"), queda vacío."""
    for t in textos:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:ton(?:elada)?s?\b|t\b)", t or "", re.I)
        if m:
            n = float(m.group(1).replace(",", "."))
            return int(n) if n.is_integer() else n
        m = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)\s*(?:kg|kilos?)\b", t or "", re.I)
        if m:
            n = int(m.group(1).replace(".", "")) / 1000
            return int(n) if n.is_integer() else n
    return ""


GENERICOS = ("gmail.", "hotmail.", "outlook.", "yahoo.", "live.", "icloud.")


def cliente_y_obra(correo, resumen=""):
    """Cuando el modelo no los da: del asunto "Cotización … - CLIENTE - OBRA"; si no, el cliente sale del dominio
    de su correo (ebco.cl -> EBCO) y la obra de "obra X" en el asunto o en el resumen."""
    asunto = memoria.PREFIJOS.sub("", correo.asunto or "")
    partes = [p.strip() for p in re.split(r"\s+-\s+", asunto) if p.strip()]
    if len(partes) >= 3 and memoria.COTIZACION.search(partes[0]):
        return partes[1], partes[2]
    cliente = ""
    for _, direccion in getaddresses([correo.remitente, correo.para, correo.cc]):
        dominio = direccion.split("@")[-1].lower() if "@" in direccion else ""
        if dominio and not dominio.endswith(memoria.DOMINIO_PROPIO) and not dominio.startswith(GENERICOS):
            cliente = dominio.split(".")[0].upper()
            break
    obra = ""
    for texto in (asunto, resumen or ""):
        for m in re.finditer(r"\bobra\s*:?\s+(.+?)(?:\s*(?://|\s-\s|,|;|\.(?:\s|$)|\s(?:para|con|el|en|de \d)\s)|$)",
                             texto, re.I):
            # "la obra de procedencia", "la obra en curso": no es el nombre de la obra
            if not re.match(r"(?:de|del|la|el|en|que|y|a|con|para|donde|ya)\b", m.group(1)):
                obra = m.group(1).strip()[:60]
                break
        if obra:
            break
    return cliente, obra


def fila_correo(correo, uid):
    """La copia del correo para la pestaña Correos (texto nuevo y, debajo, el hilo citado)."""
    texto = (correo.texto_nuevo or "").strip()
    if (correo.texto_citado or "").strip():
        texto += "\n\n──── Mensajes anteriores del hilo ────\n" + correo.texto_citado.strip()
    if len(texto) > LARGO_TEXTO:
        texto = texto[:LARGO_TEXTO] + "\n[… cortado]"
    try:
        fecha = datetime.datetime.fromisoformat(correo.fecha).astimezone(CHILE).strftime("%d-%m-%Y %H:%M")
    except (TypeError, ValueError):
        fecha = correo.fecha or ""
    return [str(uid), fecha, correo.remitente or "", correo.para or "", correo.cc or "", correo.asunto or "",
            ", ".join(correo.adjuntos or []), texto]


def guardar_correos(planilla, pares, ya=None):
    """Guarda en la pestaña Correos los que todavía no están (por UID). pares: [(correo, uid)]."""
    ya = set(ya) if ya is not None else planilla.uids_con_correo()
    filas = []
    for correo, uid in pares:
        if str(uid) not in ya:
            ya.add(str(uid))
            filas.append(fila_correo(correo, uid))
    if filas:
        planilla.agregar_correos(filas)
    return len(filas)


def es_agenda_diaria(correo):
    """El correo diario "AGENDA 04-11-2026" de Javier repite lo que ya se acordó en cada hilo."""
    return bool(re.match(r"agenda \d{1,2} \d{1,2} \d{2,4}$", memoria.asunto_normal(correo.asunto)))


def filas_nuevas(correo, decision, uid, claves, ahora=None):
    """Una fila por cada fecha acordada en el correo (Javier a veces agenda varias devoluciones en uno)."""
    r = decision.resultado
    ahora = ahora or datetime.datetime.now(CHILE)
    cliente, obra = r.get("cliente", ""), r.get("obra", "")
    if not (cliente and obra):
        c, o = cliente_y_obra(correo, r.get("resumen"))
        cliente, obra = cliente or c, obra or o
    base = {
        "Tipo": TIPOS[decision.categoria], "Cliente": cliente, "Obra": obra, "Cotización": r.get("n_cotizacion", ""),
        "Camión": camion(r.get("resumen"), correo.texto_nuevo), "Resumen": (r.get("resumen") or "")[:300],
        "Toneladas": toneladas(camion(r.get("resumen"), correo.texto_nuevo), r.get("resumen"), correo.texto_nuevo),
        "Correo": f"{(correo.asunto or '')[:120]} · {(correo.fecha or '')[:16]}",
        "Historial": f"{ahora:%d-%m %H:%M} agregado desde el correo", "Hilo": " ".join(claves), "UID": str(uid),
        "Aviso": "",
    }
    fechas = fechas_horas(r.get("fecha_movimiento"), ahora.date())
    if not fechas:
        fila = dict(base, Fecha="", Hora="", Estado="Revisar",
                    **{"Nota de bodega": "No se entendió la fecha: " + (r.get("fecha_movimiento") or "")[:60]})
        return [[fila[c] for c in COLUMNAS]]
    return [[dict(base, Fecha=f.isoformat(), Hora=h, Estado="Agendado", **{"Nota de bodega": ""})[c] for c in COLUMNAS]
            for f, h in fechas]


def fila_nueva(correo, decision, uid, claves, ahora=None):
    return filas_nuevas(correo, decision, uid, claves, ahora)[0]


# --- Planilla -------------------------------------------------------------------------------------------

DIA_CERO = datetime.date(1899, 12, 30)  # día 0 de las planillas


def _serial(iso):
    try:
        return (datetime.date.fromisoformat(iso) - DIA_CERO).days
    except (TypeError, ValueError):
        return iso


def _a_texto(v, columna):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if columna == "Fecha":
        return (DIA_CERO + datetime.timedelta(days=int(v))).isoformat()
    if columna == "Hora" and 0 <= v < 1:
        minutos = round(v * 24 * 60)
        return f"{minutos // 60:02d}:{minutos % 60:02d}"
    return str(int(v)) if float(v).is_integer() else str(v)


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
        for intento in range(6):
            req = urllib.request.Request(url, data=datos, method=metodo, headers={
                "Authorization": f"Bearer {self._valor_token}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                # 429: Google limita a ~60 lecturas por minuto (una carga grande las pasa); 5xx: falla pasajera
                if (e.code != 429 and e.code < 500) or intento == 5:
                    raise
                self._esperar(min(2 ** intento * 2, 40))

    @staticmethod
    def _esperar(segundos):
        time.sleep(segundos)

    def info(self):
        return self._pedir("GET", "", params={"fields": "sheets(properties(sheetId,title))"})

    def info_locale(self):
        return self._pedir("GET", "", params={"fields": "properties(locale)"}).get("properties", {}).get("locale")

    def leer(self):
        """Filas como texto. Fecha (AAAA-MM-DD) y Hora (HH:MM) se leen sin formato, así no importa cómo se vean;
        el resto, como se ve (una nota "14:30" escrita a mano sigue siendo "14:30"). Si alguien movió o cambió
        las columnas, falla en vez de escribir en la columna equivocada."""
        vistos = self._pedir("GET", "/values/" + urllib.parse.quote(f"{HOJA}!A1:{ULTIMA}")).get("values", [])
        titulos = [str(t).strip() for t in (vistos[0] if vistos else [])]
        if titulos[:len(COLUMNAS)] != COLUMNAS:
            raise ValueError(f"La hoja {HOJA} no tiene las columnas esperadas ({', '.join(COLUMNAS)}); "
                             f"tiene: {', '.join(titulos) or 'nada'}. ¿Alguien movió o renombró una columna?")
        crudos = self._pedir("GET", "/values/" + urllib.parse.quote(f"{HOJA}!A2:B"),
                             params={"valueRenderOption": "UNFORMATTED_VALUE",
                                     "dateTimeRenderOption": "SERIAL_NUMBER"}).get("values", [])
        filas = []
        for i, f in enumerate(vistos[1:]):
            fila = [str(v) for v in f[:len(COLUMNAS)]] + [""] * (len(COLUMNAS) - len(f))
            c = crudos[i] if i < len(crudos) else []
            fila[COL["Fecha"]] = _a_texto(c[0], "Fecha") if c else ""
            fila[COL["Hora"]] = _a_texto(c[1], "Hora") if len(c) > 1 else ""
            filas.append(fila)
        return filas

    def agregar(self, filas):
        """Se escribe tal cual (RAW): nada de lo que venga en un correo se interpreta como fórmula. La fecha va
        como número de día para que la planilla la trate como fecha."""
        filas = [[_serial(v) if i == COL["Fecha"] else v for i, v in enumerate(f)] for f in filas]
        rango = urllib.parse.quote(f"{HOJA}!A1:{ULTIMA}")  # sin la columna del enlace (es una fórmula)
        self._pedir("POST", f"/values/{rango}:append", {"values": filas},
                    {"valueInputOption": "RAW", "insertDataOption": "OVERWRITE"})

    def uids_con_correo(self):
        filas = self._pedir("GET", "/values/" + urllib.parse.quote(f"{CORREOS}!A2:A")).get("values", [])
        return {str(f[0]) for f in filas if f}

    def agregar_correos(self, filas):
        rango = urllib.parse.quote(f"{CORREOS}!A1:H")
        self._pedir("POST", f"/values/{rango}:append", {"values": filas},
                    {"valueInputOption": "RAW", "insertDataOption": "OVERWRITE"})

    def escribir(self, celdas):
        """celdas: {(n_fila, columna): valor}, con n_fila contando desde 2 (la 1 son los títulos)."""
        if celdas:
            datos = [{"range": f"{HOJA}!{_letra(c)}{n}", "values": [[_serial(v) if c == "Fecha" else v]]}
                     for (n, c), v in celdas.items()]
            self._pedir("POST", "/values:batchUpdate", {"valueInputOption": "RAW", "data": datos})

    def vaciar(self):
        rango = urllib.parse.quote(f"{HOJA}!A2:{ULTIMA}")
        self._pedir("POST", f"/values/{rango}:clear", {})

    def lote(self, pedidos):
        self._pedir("POST", ":batchUpdate", {"requests": pedidos})


def ver(planilla):
    """Resumen de solo lectura para revisar la planilla a distancia."""
    hojas = [h["properties"]["title"] for h in planilla.info()["sheets"]]
    filas = planilla.leer()
    vistas = {}
    for t, celdas in ((SEMANA, "A1:G8"), ("Hoy", "A1:I8")):
        if t in hojas:
            rango = urllib.parse.quote(f"'{t}'!{celdas}")
            vistas[t] = planilla._pedir("GET", f"/values/{rango}").get("values", [])
    como_se_ve = planilla._pedir("GET", "/values/" + urllib.parse.quote(f"{HOJA}!A1:C3")).get("values", [])
    celdas = planilla._pedir("GET", "", params={"ranges": f"{HOJA}!A2:{ULTIMA}2",
                                                "fields": "sheets(data(rowData(values(dataValidation))))"})
    fila2 = ((((celdas.get("sheets") or [{}])[0].get("data") or [{}])[0].get("rowData") or [{}])[0].get("values") or [])
    con_lista = [COLUMNAS[i] for i, c in enumerate(fila2[:len(COLUMNAS)]) if c.get("dataValidation")]
    enlace = chr(ord(ULTIMA) + 1)
    enlaces = planilla._pedir("GET", "/values/" + urllib.parse.quote(f"{HOJA}!{enlace}1:{enlace}3"),
                              params={"valueRenderOption": "FORMULA"}).get("values", []) if CORREOS in hojas else []
    correos = len(planilla.uids_con_correo()) if CORREOS in hojas else 0
    return {"hojas": hojas, "locale": planilla.info_locale(), "filas": len(filas),
            "estados": {e: sum(1 for f in filas if f[COL["Estado"]] == e) for e in ESTADOS},
            "por_fecha": {d: sum(1 for f in filas if f[COL["Fecha"]] == d) for d in sorted({f[COL["Fecha"]] for f in filas})},
            "ultimas": [f[:COL["Nota de bodega"] + 1] for f in filas[-5:]], "como_se_ve": como_se_ve, "con_lista": con_lista, "correos": correos,
            "marcadas": [[f[COL[c]] for c in ("Fecha", "Hora", "Tipo", "Cliente", "Estado", "Nota de bodega", "Aviso")]
                         for f in filas if f[COL["Estado"]] in ("Llegó", "No llegó", "Anulado") or
                         (f[COL["Nota de bodega"]] and not f[COL["Nota de bodega"]].startswith("No se entendió"))],
            "sin_marcar_pasadas": sum(1 for f in filas if f[COL["Estado"]] == "Agendado" and f[COL["Fecha"]] and
                                      f[COL["Fecha"]] < datetime.datetime.now(CHILE).date().isoformat()),
            "enlaces": enlaces, "vistas": vistas}


def tocada_por_bodega(filas):
    """True si bodega ya marcó algo (estado o nota): entonces la agenda no se puede vaciar."""
    return any(f[COL["Estado"]] in ("Llegó", "No llegó", "Anulado") or f[COL["Aviso"]] or
               (f[COL["Nota de bodega"]] and not f[COL["Nota de bodega"]].startswith("No se entendió")) or
               re.search(r"→|: nota|borró la nota", f[COL["Historial"]]) for f in filas)  # cambios con historial de quién marcó


SEMANA = "Semana"
OPCIONES_SEMANA = ["Esta semana", "Semana siguiente", "Semana anterior", "En 2 semanas", "Hace 2 semanas"]
VISTAS = (SEMANA, "Hoy", HOJA, CORREOS)  # orden de las pestañas
VIEJAS = ("Próximos 7 días", "Hoja 1", "Sheet1", "Hoja1")  # se borran si están


def _rgb(r, g, b):
    return {"red": r, "green": g, "blue": b}


def preparar(planilla):
    """Deja la planilla lista. Se puede correr más de una vez (no toca las filas de la Agenda).
    - Agenda: títulos, lista de estados y colores.
    - Semana: lunes a domingo en columnas, con lo de cada día ordenado por hora. Arriba se elige la semana
      ("Esta semana" por defecto; el domingo ya muestra la siguiente), así que avanza sola.
    - Hoy: lo de hoy."""
    hojas = {h["properties"]["title"]: h["properties"]["sheetId"] for h in planilla.info()["sheets"]}
    semana_nueva = SEMANA not in hojas
    pedidos = [{"addSheet": {"properties": {"title": t}}} for t in VISTAS if t not in hojas]
    if pedidos:
        planilla.lote(pedidos)
        hojas = {h["properties"]["title"]: h["properties"]["sheetId"] for h in planilla.info()["sheets"]}
    agenda, semana, hoy, correos = hojas[HOJA], hojas[SEMANA], hojas["Hoy"], hojas[CORREOS]
    # Hora de Chile para TODAY(); se borran las hojas que ya no se usan; orden: Semana, Hoy, Agenda
    pedidos = [{"updateSpreadsheetProperties": {"properties": {"timeZone": "America/Santiago"}, "fields": "timeZone"}}]
    pedidos += [{"deleteSheet": {"sheetId": i}} for t, i in hojas.items() if t in VIEJAS]
    pedidos += [{"updateSheetProperties": {"properties": {"sheetId": hojas[t], "index": k}, "fields": "index"}}
                for k, t in enumerate(VISTAS)]
    # Los colores se vuelven a crear: se borran los que dejó una corrida anterior
    reglas = planilla._pedir("GET", "", params={"fields": "sheets(properties(sheetId),conditionalFormats)"})
    for h in reglas.get("sheets", []):
        if h["properties"]["sheetId"] in (agenda, semana):
            pedidos += [{"deleteConditionalFormatRule": {"sheetId": h["properties"]["sheetId"], "index": 0}}
                        for _ in h.get("conditionalFormats", [])]
    planilla.lote(pedidos)
    nueva_columna = _agregar_toneladas(planilla, agenda)
    planilla._pedir("PUT", "/values/" + urllib.parse.quote(f"{HOJA}!A1:{ULTIMA}1"), {"values": [COLUMNAS]},
                    {"valueInputOption": "RAW"})
    if nueva_columna:
        _llenar_toneladas(planilla)
    # En planillas en español los argumentos de las fórmulas se separan con punto y coma
    idioma = (planilla.info_locale() or "en").split("_")[0]
    sep = ";" if idioma in ("es", "pt", "de", "fr", "it", "nl", "ru", "tr", "pl") else ","
    _preparar_hoy(planilla, hoy, sep)
    _preparar_semana(planilla, semana, sep, semana_nueva)
    _preparar_agenda(planilla, agenda)
    _preparar_correos(planilla, correos, agenda, sep)


def _preparar_correos(planilla, hoja, agenda, sep):
    """Pestaña Correos (una fila por correo) y, en la última columna de la Agenda, un enlace "Ver correo" que
    salta a esa fila. El enlace es una sola fórmula que busca el UID: sigue funcionando si se ordenan las hojas."""
    planilla._pedir("PUT", "/values/" + urllib.parse.quote(f"{CORREOS}!A1:H1"), {"values": [COLUMNAS_CORREO]},
                    {"valueInputOption": "RAW"})
    uid, columna = _letra("UID"), chr(ord(ULTIMA) + 1)
    formula = (f'={{"{ENLACE}";ARRAYFORMULA(IF({uid}2:{uid}=""{sep}""{sep}HYPERLINK("#gid={hoja}&range=A"&'
               f'IFERROR(MATCH({uid}2:{uid}{sep}{CORREOS}!$A:$A{sep}0){sep}1){sep}"{ENLACE}")))}}')
    planilla._pedir("PUT", "/values/" + urllib.parse.quote(f"{HOJA}!{columna}1"), {"values": [[formula]]},
                    {"valueInputOption": "USER_ENTERED"})
    anchos = [70, 125, 230, 230, 160, 320, 200, 700]
    planilla.lote([
        {"updateSheetProperties": {"properties": {"sheetId": hoja, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 1},
                        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
    ] + [{"updateDimensionProperties": {"range": {"sheetId": hoja, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                        "properties": {"pixelSize": ancho}, "fields": "pixelSize"}}
         for i, ancho in enumerate(anchos)] + [
        {"updateDimensionProperties": {"range": {"sheetId": agenda, "dimension": "COLUMNS",
                                                 "startIndex": len(COLUMNAS), "endIndex": len(COLUMNAS) + 1},
                                       "properties": {"pixelSize": 95}, "fields": "pixelSize"}},
    ])


def _agregar_toneladas(planilla, agenda):
    """Si la hoja Agenda es de antes del 5-nov (sin "Toneladas"), le inserta la columna al lado de Camión."""
    titulos = planilla._pedir("GET", "/values/" + urllib.parse.quote(f"{HOJA}!1:1")).get("values", [[]])
    titulos = [str(t).strip() for t in (titulos[0] if titulos else [])]
    if "Toneladas" in titulos or not titulos:
        return False
    if titulos[:len(SIN_TONELADAS)] != SIN_TONELADAS:
        raise ValueError(f"La hoja {HOJA} no tiene las columnas esperadas: {', '.join(titulos)}")
    planilla.lote([{"insertDimension": {"range": {"sheetId": agenda, "dimension": "COLUMNS",
                                                  "startIndex": COL["Toneladas"], "endIndex": COL["Toneladas"] + 1},
                                        "inheritFromBefore": True}}])  # el formato de Camión, no la lista de Estado
    return True


def _llenar_toneladas(planilla):
    """Llena Toneladas en las filas que ya estaban, con lo que dicen Camión y Resumen."""
    filas = planilla.leer()
    if filas:
        letra = _letra("Toneladas")
        planilla._pedir("PUT", "/values/" + urllib.parse.quote(f"{HOJA}!{letra}2:{letra}{len(filas) + 1}"),
                        {"values": [[toneladas(f[COL["Camión"]], f[COL["Resumen"]])] for f in filas]},
                        {"valueInputOption": "RAW"})


def _preparar_hoy(planilla, hoja, sep):
    """Las vistas filtran por el número de día: no dependen de cómo se vea la fecha."""
    n, fin = COL["Nota de bodega"] + 1, _letra("Nota de bodega")  # de Fecha a Nota de bodega
    formula = (f'=IFERROR(SORT(FILTER({HOJA}!A2:{fin}{sep}{HOJA}!A2:A=TODAY()){sep}1{sep}TRUE{sep}2{sep}TRUE)'
               f'{sep}"Sin movimientos")')
    planilla._pedir("PUT", "/values/" + urllib.parse.quote(f"'Hoy'!A1:{fin}3"),
                    {"values": [["Hoy (se actualiza sola; el estado se cambia en la hoja Agenda)"] + [""] * (n - 1),
                                COLUMNAS[:n], [formula] + [""] * (n - 1)]}, {"valueInputOption": "USER_ENTERED"})
    planilla.lote([
        {"updateSheetProperties": {"properties": {"sheetId": hoja, "gridProperties": {"frozenRowCount": 2}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 0, "endRowIndex": 2},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 1},
                        "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "ddd dd-mm"}}},
                        "fields": "userEnteredFormat.numberFormat"}},
    ])


def _preparar_semana(planilla, hoja, sep, nueva):
    """Una columna por día (lunes a domingo). Cada movimiento en una línea: "08:00  Devolución · EBCO · obra ·
    camión", y el estado entre corchetes si no es Agendado. Colores por estado y por tipo; hoy en azul."""
    a = lambda nombre: f"{HOJA}!${_letra(nombre)}$2:${_letra(nombre)}"  # noqa: E731
    hora = f'IF(ISNUMBER({a("Hora")}){sep}TEXT({a("Hora")}{sep}"hh:mm"){sep}{a("Hora")})'
    texto = (f'ARRAYFORMULA({hora}&"  "&{a("Tipo")}&" · "&{a("Cliente")}&IF({a("Obra")}=""{sep}""{sep}" · "&{a("Obra")})'
             f'&IF({a("Camión")}=""{sep}""{sep}" · "&{a("Camión")})&IF({a("Estado")}="Agendado"{sep}""{sep}"   ["&{a("Estado")}&"]"))')
    corrimiento = (f'SWITCH($B$1{sep}"Semana siguiente"{sep}1{sep}"Semana anterior"{sep}-1{sep}"En 2 semanas"{sep}2'
                   f'{sep}"Hace 2 semanas"{sep}-2{sep}0)')
    lunes = f"=TODAY()-WEEKDAY(TODAY(){sep}3)+IF(WEEKDAY(TODAY(){sep}2)=7{sep}7{sep}0)+7*{corrimiento}"
    columnas = "ABCDEFG"
    dias = [lunes] + [f"=$A$3+{k}" for k in range(1, 7)]
    cuentas = [f'=COUNTIFS({a("Fecha")}{sep}{c}$3{sep}{a("Estado")}{sep}"<>Anulado"{sep}{a("Estado")}{sep}"<>Reagendado")&" mov"'
               for c in columnas]
    listas = [f'=IFERROR(SORT(FILTER({texto}{sep}{a("Fecha")}={c}$3)){sep}"—")' for c in columnas]
    rango_txt = f'="del "&TEXT($A$3{sep}"d mmm")&" al "&TEXT($A$3+6{sep}"d mmm yyyy")'
    explicacion = ("Elige la semana en la celda B1 (si la dejas en \"Esta semana\", avanza sola; el domingo ya "
                   "muestra la siguiente). Los estados se marcan en la hoja Agenda, columna Estado.")
    pon = lambda celdas, valores: planilla._pedir(  # noqa: E731
        "PUT", "/values/" + urllib.parse.quote(f"'{SEMANA}'!{celdas}"), {"values": valores},
        {"valueInputOption": "USER_ENTERED"})
    pon("A1", [["Semana"]])
    pon("C1", [[rango_txt]])
    pon("A2:G5", [[explicacion] + [""] * 6, dias, cuentas, listas])
    if nueva:  # B1 se escribe solo la primera vez: no se pisa la semana que alguien eligió
        pon("B1", [["Esta semana"]])
    lista = {"sheetId": hoja, "startRowIndex": 4, "endRowIndex": 120, "startColumnIndex": 0, "endColumnIndex": 7}
    reglas = [  # primero las de más prioridad
        ("[No llegó]", _rgb(0.99, 0.85, 0.84), None), ("[Llegó]", _rgb(0.85, 0.94, 0.85), None),
        ("[Anulado]", _rgb(0.93, 0.93, 0.93), {"strikethrough": True, "foregroundColor": _rgb(0.5, 0.5, 0.5)}),
        ("[Reagendado]", _rgb(1, 0.92, 0.8), {"strikethrough": True}), ("[Revisar]", _rgb(1, 0.96, 0.7), None),
        ("Devolución", _rgb(0.9, 0.97, 0.95), None), ("Despacho", _rgb(0.92, 0.94, 1), None),
    ]
    pedidos = [
        {"updateSheetProperties": {"properties": {"sheetId": hoja, "gridProperties": {"frozenRowCount": 4}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"updateDimensionProperties": {"range": {"sheetId": hoja, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 7},
                                       "properties": {"pixelSize": 235}, "fields": "pixelSize"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 14}}},
                        "fields": "userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 1, "endColumnIndex": 2},
                        "cell": {"userEnteredFormat": {"backgroundColor": _rgb(0.91, 0.94, 1),
                                                       "textFormat": {"bold": True, "foregroundColor": _rgb(0.1, 0.4, 0.85)}}},
                        "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 3},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 12}}},
                        "fields": "userEnteredFormat.textFormat"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"italic": True, "foregroundColor": _rgb(0.4, 0.42, 0.45)},
                                                       "wrapStrategy": "OVERFLOW_CELL"}},
                        "fields": "userEnteredFormat(textFormat,wrapStrategy)"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 0, "endColumnIndex": 7},
                        "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "dddd d mmm"},
                                                       "horizontalAlignment": "CENTER",
                                                       "textFormat": {"bold": True, "fontSize": 11}}},
                        "fields": "userEnteredFormat(numberFormat,horizontalAlignment,textFormat)"}},
        {"repeatCell": {"range": {"sheetId": hoja, "startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": 0, "endColumnIndex": 7},
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER",
                                                       "textFormat": {"foregroundColor": _rgb(0.4, 0.42, 0.45)}}},
                        "fields": "userEnteredFormat(horizontalAlignment,textFormat)"}},
        {"repeatCell": {"range": lista, "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
        {"setDataValidation": {"range": {"sheetId": hoja, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 1,
                                         "endColumnIndex": 2},
                               "rule": {"condition": {"type": "ONE_OF_LIST",
                                                      "values": [{"userEnteredValue": o} for o in OPCIONES_SEMANA]},
                                        "strict": True, "showCustomUi": True}}},
        {"addConditionalFormatRule": {"index": 0, "rule": {
            "ranges": [{"sheetId": hoja, "startRowIndex": 2, "endRowIndex": 4, "startColumnIndex": 0, "endColumnIndex": 7}],
            "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": "=A$3=TODAY()"}]},
                            "format": {"backgroundColor": _rgb(0.1, 0.4, 0.85),
                                       "textFormat": {"foregroundColor": _rgb(1, 1, 1), "bold": True}}}}}},
    ]
    for k, (contiene, fondo, letra) in enumerate(reglas, start=1):
        formato = {"backgroundColor": fondo}
        if letra:
            formato["textFormat"] = letra
        pedidos.append({"addConditionalFormatRule": {"index": k, "rule": {
            "ranges": [lista], "booleanRule": {"condition": {"type": "TEXT_CONTAINS", "values": [{"userEnteredValue": contiene}]},
                                               "format": formato}}}})
    planilla.lote(pedidos)


def _preparar_agenda(planilla, agenda):
    rango = {"sheetId": agenda, "startRowIndex": 1, "startColumnIndex": COL["Estado"], "endColumnIndex": COL["Estado"] + 1}
    colores = {"Llegó": (0.85, 0.94, 0.83), "No llegó": (0.96, 0.8, 0.8), "Reagendado": (1, 0.9, 0.7),
               "Anulado": (0.85, 0.85, 0.85), "Revisar": (1, 0.95, 0.6)}
    pedidos = [
        {"updateSheetProperties": {"properties": {"sheetId": agenda, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": {"sheetId": agenda, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}},
        {"repeatCell": {"range": {"sheetId": agenda, "startRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": False}}},
                        "fields": "userEnteredFormat.textFormat.bold"}},
        {"repeatCell": {"range": {"sheetId": agenda, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 1},
                        "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "ddd dd-mm-yyyy"}}},
                        "fields": "userEnteredFormat.numberFormat"}},
        # la lista de estados va solo en Estado: se borra de cualquier otra columna (sin "rule" se borra)
        {"setDataValidation": {"range": {"sheetId": agenda, "startRowIndex": 1, "startColumnIndex": 0,
                                         "endColumnIndex": COL["Estado"]}}},
        {"setDataValidation": {"range": {"sheetId": agenda, "startRowIndex": 1, "startColumnIndex": COL["Estado"] + 1}}},
        {"setDataValidation": {"range": rango, "rule": {
            "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": e} for e in ESTADOS]},
            "strict": True, "showCustomUi": True}}},
    ] + [{"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": [{"sheetId": agenda, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(COLUMNAS)}],
        "booleanRule": {"condition": {"type": "CUSTOM_FORMULA",
                                      "values": [{"userEnteredValue": f'=${_letra("Estado")}2="{estado}"'}]},
                        "format": {"backgroundColor": _rgb(r, g, b)}}}}}
        for estado, (r, g, b) in colores.items()]
    planilla.lote(pedidos)


# --- Lógica ---------------------------------------------------------------------------------------------

def _mismo_hilo(fila, claves):
    return bool(set(fila[COL["Hilo"]].split()) & set(claves))


def _historial(fila, texto, ahora):
    previo = fila[COL["Historial"]]
    return (previo + " | " if previo else "") + f"{ahora:%d-%m %H:%M} {texto}"


def _identidad(f):
    return f[COL["UID"]], f[COL["Fecha"]], f[COL["Tipo"]], f[COL["Hilo"]]


def _aplicar(planilla, cambios, ahora):
    """Escribe cambios en filas leídas antes. Vuelve a leer la hoja justo antes de escribir: ubica cada fila por
    su identidad (por si alguien ordenó la hoja), arma el Historial con lo último que tiene (alguien pudo
    escribir ahí) y no toca una fila cuyo Estado cambió entremedio (alguien la marcó) o que no cumple `si`.
    cambios: [(n, fila_leída, {columna: valor}, texto_para_historial, si)]. Devuelve cuántas filas cambió."""
    if not cambios:
        return 0
    actuales, celdas, hechas = planilla.leer(), {}, 0
    for n, vieja, valores, historia, si in cambios:
        ident = _identidad(vieja)
        m = n if n - 2 < len(actuales) and _identidad(actuales[n - 2]) == ident else next(
            (k for k, f in enumerate(actuales, start=2) if _identidad(f) == ident), None)
        if m is None:
            continue
        fresca = actuales[m - 2]
        if fresca[COL["Estado"]] != vieja[COL["Estado"]] or (si and not si(fresca)):
            continue
        for columna, valor in valores.items():
            celdas[(m, columna)] = valor
        if historia:
            celdas[(m, "Historial")] = _historial(fresca, historia, ahora)
        hechas += 1
    planilla.escribir(celdas)
    return hechas


REAGENDA = re.compile(r"reagend|reprogram|en reemplazo|en vez de|posterg|adelant|nueva fecha|nuevo d[ií]a|"
                      r"sin efecto|cambi\w* (?:de |la |el )?(?:fecha|hora|d[ií]a)", re.I)


def registrar_acordado(planilla, correo, decision, uid, claves, ahora=None):
    """Agrega el movimiento acordado (una fila por fecha). En el mismo hilo y del mismo tipo:
    - una fecha que ya estaba (un recordatorio, una confirmación) no se repite: se actualiza la hora;
    - si el resumen del modelo dice que se reagendó ("reagenda", "reprogramación", "en reemplazo"...), lo que
      estaba agendado a futuro para otra fecha queda como Reagendado. Si no lo dice, puede ser otro movimiento
      (una segunda devolución) y se deja como estaba."""
    ahora = ahora or datetime.datetime.now(CHILE)
    if es_agenda_diaria(correo):
        return "agenda_diaria"
    nuevas = filas_nuevas(correo, decision, uid, claves, ahora)
    tipo, hoy = nuevas[0][COL["Tipo"]], ahora.date().isoformat()
    hilo = [(n, f) for n, f in enumerate(planilla.leer(), start=2)
            if _mismo_hilo(f, claves) and f[COL["Tipo"]] == tipo]
    cambios, agregar, repetidas = [], [], 0
    for nueva in nuevas:
        mismas = [(n, f) for n, f in hilo if nueva[COL["Fecha"]] and f[COL["Fecha"]] == nueva[COL["Fecha"]]]
        activa = next(((n, f) for n, f in mismas if f[COL["Estado"]] in ("Agendado", "Reagendado", "Revisar")), None)
        llego = next(((n, f) for n, f in mismas if f[COL["Estado"]] == "Llegó"), None)
        anulada = next(((n, f) for n, f in mismas if f[COL["Estado"]] == "Anulado"), None)
        if activa or anulada:
            # la misma fecha otra vez (recordatorio, confirmación, o una corrección que la devuelve): no se repite
            n, f = activa or anulada
            valores = {}
            if nueva[COL["Hora"]] and f[COL["Hora"]] != nueva[COL["Hora"]]:
                valores["Hora"] = nueva[COL["Hora"]]
            if f[COL["Estado"]] != "Agendado":
                valores["Estado"] = "Agendado"
            texto = "confirmado de nuevo" if activa else "vuelve a quedar agendado"
            cambios.append((n, f, valores, f"{texto} (UID {uid})", None))
        elif llego:  # ya vino: un correo que lo repite no agrega otra fila
            n, f = llego
            cambios.append((n, f, {}, f"confirmado de nuevo, ya había llegado (UID {uid})", None))
        else:  # nueva, o la anterior quedó "No llegó" y esta es la nueva hora
            agregar.append(nueva)
            continue
        repetidas += 1
    # Reagendado: solo si el modelo dice que se cambió la fecha y hay UNA sola fecha futura que pudo ser la
    # cambiada. Si hay varias (una serie de devoluciones semanales), no se adivina: queda la nota.
    reagendadas = 0
    fechas_correo = {f[COL["Fecha"]] for f in nuevas if f[COL["Fecha"]]}
    if fechas_correo and REAGENDA.search(decision.resultado.get("resumen") or ""):
        texto = ", ".join(f"{f[COL['Fecha']]} {f[COL['Hora']]}".strip() for f in nuevas)
        tocadas = {c[0] for c in cambios}
        otras = [(n, f) for n, f in hilo if f[COL["Estado"]] == "Agendado" and hoy <= f[COL["Fecha"]]
                 and f[COL["Fecha"]] not in fechas_correo and n not in tocadas]
        for n, f in otras:
            if len(otras) == 1:
                cambios.append((n, f, {"Estado": "Reagendado"}, f"se cambió a {texto} (UID {uid})", None))
                reagendadas += 1
            else:
                cambios.append((n, f, {}, f"en el hilo se reagendó algo para {texto} (UID {uid}); "
                                           "si era esta fecha, marcar Reagendado", None))
    _aplicar(planilla, cambios, ahora)
    if agregar:
        planilla.agregar(agregar)
    if not agregar:
        return "repetido y reagendado" if reagendadas else "repetido"
    return ("reagendado" if reagendadas else "agregado") + (f" x{len(agregar)}" if len(agregar) > 1 else "")


def marcar_cambio(planilla, correo, decision, uid, claves, ahora=None):
    """Un pendiente de cambio o anulación deja en Revisar lo agendado a futuro en el mismo hilo."""
    ahora = ahora or datetime.datetime.now(CHILE)
    tipo = {"despacho": "Despacho", "recepcion": "Devolución"}.get(decision.resultado.get("movimiento"))
    cambios = [(n, f, {"Estado": "Revisar"}, f"piden cambio o anulación (UID {uid})", None)
               for n, f in enumerate(planilla.leer(), start=2)
               if _mismo_hilo(f, claves) and (tipo is None or f[COL["Tipo"]] == tipo) and f[COL["Estado"]] == "Agendado"
               and f[COL["Fecha"]] >= ahora.date().isoformat()]
    return _aplicar(planilla, cambios, ahora)


def anular_uid(planilla, uid, motivo, tipo=None, ahora=None):
    """Una corrección que saca un acordado (o le cambia el tipo) deja sus filas como Anulado (no se borran).
    Con tipo, solo las de ese tipo."""
    ahora = ahora or datetime.datetime.now(CHILE)
    cambios = [(n, f, {"Estado": "Anulado"}, motivo, None) for n, f in enumerate(planilla.leer(), start=2)
               if f[COL["UID"]] == str(uid) and f[COL["Estado"]] not in ("Anulado", "Llegó")
               and (tipo is None or f[COL["Tipo"]] == tipo)]
    return _aplicar(planilla, cambios, ahora)


def no_llegaron(planilla):
    """Filas que Pato marcó "No llegó" y que todavía no se avisaron: [(n_fila, fila)]."""
    return [(n, f) for n, f in enumerate(planilla.leer(), start=2) if f[COL["Estado"]] == "No llegó" and not f[COL["Aviso"]]]


def reservar_aviso(planilla, n, fila, ahora=None):
    """Antes de mandar el correo se anota "enviando" en Aviso. Si no se puede anotar (o la fila ya no está en
    "No llegó" sin aviso), no se manda: así nunca se manda dos veces ni cada 3 minutos."""
    ahora = ahora or datetime.datetime.now(CHILE)
    return _aplicar(planilla, [(n, fila, {"Aviso": f"enviando {ahora:%d-%m %H:%M}"}, "",
                                lambda f: f[COL["Estado"]] == "No llegó" and not f[COL["Aviso"]])], ahora) == 1


def soltar_aviso(planilla, n, fila, ahora=None):
    """El correo no salió: se borra la reserva para reintentar en la próxima corrida."""
    ahora = ahora or datetime.datetime.now(CHILE)
    _aplicar(planilla, [(n, fila, {"Aviso": ""}, "", lambda f: f[COL["Aviso"]].startswith("enviando"))], ahora)


def marcar_avisado(planilla, n, fila, ahora=None):
    ahora = ahora or datetime.datetime.now(CHILE)
    _aplicar(planilla, [(n, fila, {"Aviso": f"{ahora:%d-%m %H:%M}"}, "aviso de reagendamiento enviado a pendientes",
                         None)], ahora)


def texto_aviso(fila):
    return (
        f"Bodega marcó en la agenda que el camión NO LLEGÓ. Hay que volver a agendar.\n\n"
        f"Tipo: {fila[COL['Tipo']]}\nFecha que estaba agendada: {fila[COL['Fecha']]} {fila[COL['Hora']]}\n"
        f"Cliente: {fila[COL['Cliente']]}\nObra: {fila[COL['Obra']]}\nCotización: {fila[COL['Cotización']]}\n"
        f"Camión: {fila[COL['Camión']]}\nNota de bodega: {fila[COL['Nota de bodega']]}\n\n"
        f"Resumen del acuerdo: {fila[COL['Resumen']]}\nCorreo original: {fila[COL['Correo']]} (adjunto si está disponible)\n\n"
        "Cuando se acuerde la nueva fecha por correo, el agente la agrega sola a la agenda."
    )
