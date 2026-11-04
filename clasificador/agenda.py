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
from email.utils import getaddresses

from . import memoria

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
        m = re.search(r"\bobra\s*:?\s+(.+?)(?:\s*(?://|\s-\s|,|;|\.\s|\s(?:para|con|el|en|de \d)\s)|$)", texto, re.I)
        if m:
            obra = m.group(1).strip()[:60]
            break
    return cliente, obra


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
        req = urllib.request.Request(url, data=datos, method=metodo, headers={
            "Authorization": f"Bearer {self._valor_token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def info(self):
        return self._pedir("GET", "", params={"fields": "sheets(properties(sheetId,title))"})

    def info_locale(self):
        return self._pedir("GET", "", params={"fields": "properties(locale)"}).get("properties", {}).get("locale")

    def leer(self):
        """Filas como texto: fechas en ISO y horas HH:MM, sin importar cómo se muestren en la planilla."""
        rango = urllib.parse.quote(f"{HOJA}!A2:{ULTIMA}")
        filas = self._pedir("GET", f"/values/{rango}", params={"valueRenderOption": "UNFORMATTED_VALUE",
                                                               "dateTimeRenderOption": "SERIAL_NUMBER"}).get("values", [])
        return [[_a_texto(v, COLUMNAS[i]) for i, v in enumerate(f)] + [""] * (len(COLUMNAS) - len(f)) for f in filas]

    def agregar(self, filas):
        """Se escribe tal cual (RAW): nada de lo que venga en un correo se interpreta como fórmula. La fecha va
        como número de día para que la planilla la trate como fecha."""
        filas = [[_serial(v) if i == COL["Fecha"] else v for i, v in enumerate(f)] for f in filas]
        rango = urllib.parse.quote(f"{HOJA}!A1")
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
    for t in ("Hoy", "Próximos 7 días"):
        if t in hojas:
            rango = urllib.parse.quote(f"'{t}'!A1:I8")
            vistas[t] = planilla._pedir("GET", f"/values/{rango}").get("values", [])
    como_se_ve = planilla._pedir("GET", "/values/" + urllib.parse.quote(f"{HOJA}!A1:C3")).get("values", [])
    return {"hojas": hojas, "locale": planilla.info_locale(), "filas": len(filas),
            "estados": {e: sum(1 for f in filas if f[COL["Estado"]] == e) for e in ESTADOS},
            "por_fecha": {d: sum(1 for f in filas if f[COL["Fecha"]] == d) for d in sorted({f[COL["Fecha"]] for f in filas})},
            "ultimas": [f[:9] for f in filas[-5:]], "como_se_ve": como_se_ve, "vistas": vistas}


def tocada_por_bodega(filas):
    """True si bodega ya marcó algo (estado o nota): entonces la agenda no se puede vaciar."""
    return any(f[COL["Estado"]] in ("Llegó", "No llegó", "Anulado") or
               (f[COL["Nota de bodega"]] and not f[COL["Nota de bodega"]].startswith("No se entendió")) for f in filas)


def preparar(planilla):
    """Deja la planilla lista: hoja Agenda con títulos, lista de estados y colores, y las hojas Hoy y
    Próximos 7 días con fórmulas que ordenan por fecha y hora. Se puede correr más de una vez."""
    hojas = {h["properties"]["title"]: h["properties"]["sheetId"] for h in planilla.info()["sheets"]}
    pedidos = [{"addSheet": {"properties": {"title": t}}} for t in (HOJA, "Hoy", "Próximos 7 días") if t not in hojas]
    if pedidos:
        planilla.lote(pedidos)
        hojas = {h["properties"]["title"]: h["properties"]["sheetId"] for h in planilla.info()["sheets"]}
    agenda = hojas[HOJA]
    # Hora de Chile para TODAY(); la hoja vacía que trae una planilla nueva se borra; orden: Hoy, Próximos, Agenda
    pedidos = [{"updateSpreadsheetProperties": {"properties": {"timeZone": "America/Santiago"}, "fields": "timeZone"}}]
    pedidos += [{"deleteSheet": {"sheetId": i}} for t, i in hojas.items()
                if t not in (HOJA, "Hoy", "Próximos 7 días") and t in ("Hoja 1", "Sheet1", "Hoja1")]
    pedidos += [{"updateSheetProperties": {"properties": {"sheetId": hojas[t], "index": k}, "fields": "index"}}
                for k, t in enumerate(("Hoy", "Próximos 7 días", HOJA))]
    # Los colores se vuelven a crear: se borran los que dejó una corrida anterior
    reglas = planilla._pedir("GET", "", params={"fields": "sheets(properties(sheetId),conditionalFormats)"})
    previas = next((len(h.get("conditionalFormats", [])) for h in reglas.get("sheets", [])
                    if h["properties"]["sheetId"] == agenda), 0)
    pedidos += [{"deleteConditionalFormatRule": {"sheetId": agenda, "index": 0}} for _ in range(previas)]
    planilla.lote(pedidos)
    planilla._pedir("PUT", "/values/" + urllib.parse.quote(f"{HOJA}!A1:{ULTIMA}1"), {"values": [COLUMNAS]},
                    {"valueInputOption": "RAW"})
    # Las vistas filtran por el número de día (no dependen del formato de la fecha). En planillas en español
    # los argumentos de las fórmulas se separan con punto y coma.
    idioma = (planilla.info_locale() or "en").split("_")[0]
    sep = ";" if idioma in ("es", "pt", "de", "fr", "it", "nl", "ru", "tr", "pl") else ","
    datos, fechas = f"{HOJA}!A2:I", f"{HOJA}!A2:A"
    for titulo, condicion in (("Hoy", f"{fechas}=TODAY()"),
                              ("Próximos 7 días", f"{fechas}>=TODAY(){sep}{fechas}<=TODAY()+7")):
        formula = f'=IFERROR(SORT(FILTER({datos}{sep}{condicion}){sep}1{sep}TRUE{sep}2{sep}TRUE){sep}"Sin movimientos")'
        planilla._pedir("PUT", "/values/" + urllib.parse.quote(f"'{titulo}'!A1:I3"),
                        {"values": [[f"{titulo} (se actualiza sola; el estado se cambia en la hoja Agenda)"] + [""] * 8,
                                    COLUMNAS[:9], [formula] + [""] * 8]}, {"valueInputOption": "USER_ENTERED"})
        vista = hojas[titulo]
        planilla.lote([
            {"updateSheetProperties": {"properties": {"sheetId": vista, "gridProperties": {"frozenRowCount": 2}},
                                       "fields": "gridProperties.frozenRowCount"}},
            {"repeatCell": {"range": {"sheetId": vista, "startRowIndex": 0, "endRowIndex": 2},
                            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                            "fields": "userEnteredFormat.textFormat.bold"}},
            {"repeatCell": {"range": {"sheetId": vista, "startRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 1},
                            "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "ddd dd-mm"}}},
                            "fields": "userEnteredFormat.numberFormat"}},
        ])
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
    celdas, agregar = {}, []
    for nueva in nuevas:
        previa = next(((n, f) for n, f in hilo if nueva[COL["Fecha"]] and f[COL["Fecha"]] == nueva[COL["Fecha"]]
                       and f[COL["Estado"]] in ("Agendado", "Reagendado", "Revisar")), None)
        if not previa:
            agregar.append(nueva)
            continue
        n, f = previa
        if nueva[COL["Hora"]] and f[COL["Hora"]] != nueva[COL["Hora"]]:
            celdas[(n, "Hora")] = nueva[COL["Hora"]]
        if f[COL["Estado"]] != "Agendado":
            celdas[(n, "Estado")] = "Agendado"
        celdas[(n, "Historial")] = _historial(f, f"confirmado de nuevo (UID {uid})", ahora)
    reagendadas = 0
    if agregar and REAGENDA.search(decision.resultado.get("resumen") or ""):
        nuevas_fechas = {f[COL["Fecha"]] for f in nuevas}
        texto = ", ".join(f"{f[COL['Fecha']]} {f[COL['Hora']]}".strip() for f in agregar)
        for n, f in hilo:
            if f[COL["Estado"]] == "Agendado" and hoy <= f[COL["Fecha"]] and f[COL["Fecha"]] not in nuevas_fechas \
                    and (n, "Estado") not in celdas:
                celdas[(n, "Estado")] = "Reagendado"
                celdas[(n, "Historial")] = _historial(f, f"se cambió a {texto} (UID {uid})", ahora)
                reagendadas += 1
    planilla.escribir(celdas)
    if agregar:
        planilla.agregar(agregar)
    if not agregar:
        return "repetido"
    return ("reagendado" if reagendadas else "agregado") + (f" x{len(agregar)}" if len(agregar) > 1 else "")


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
