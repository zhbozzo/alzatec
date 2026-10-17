"""Acceso IMAP a la casilla embudo.

El estado se guarda en la misma casilla con marcas IMAP (keywords), así el
clasificador no necesita base de datos:
- Clasificado: ya procesado.
- NoAplica: descartado (entra al resumen diario).
- Resumido: ya incluido en un resumen diario.
- Duplicado: copia de un correo que llegó por dos casillas.
- Toma0 a Toma5: una corrida lo está procesando, con el tramo de 10 minutos
  en que lo tomó. Evita que dos corridas tomen el mismo correo; si la corrida
  se cae, se libera a los 30 minutos. Son solo 6 marcas que rotan, porque
  Dovecot (el servidor de cPanel) admite pocas marcas distintas por casilla.
No marca nada como leído: si alguien abre agente@ por webmail, ve todo igual.

La carpeta "Alertas" de agente@ guarda cuándo se avisó cada problema, para no
mandar el mismo aviso cada 3 minutos y para avisar cuando se resuelve. En cPanel
las carpetas van dentro de la bandeja de entrada, así que se llama "INBOX.Alertas".
"""

import imaplib
import re
import ssl
import time
from email.utils import formatdate

CLASIFICADO, NO_APLICA, RESUMIDO, DUPLICADO = "Clasificado", "NoAplica", "Resumido", "Duplicado"


class Buzon:
    def __init__(self, cfg):
        self.cfg = cfg
        self.imap = None
        self._carpeta_alertas = None

    def conectar(self):
        self.imap = imaplib.IMAP4_SSL(self.cfg.imap_host, self.cfg.imap_puerto,
                                      ssl_context=ssl.create_default_context(), timeout=60)
        self.imap.login(self.cfg.usuario, self.cfg.contrasena)
        typ, _ = self.imap.select("INBOX")
        if typ != "OK":
            raise RuntimeError("No se pudo abrir la bandeja de entrada de agente@")
        permanentes = self.imap.untagged_responses.get("PERMANENTFLAGS", [b""])[0] or b""
        if b"\\*" not in permanentes:
            raise RuntimeError("El servidor no permite marcas propias (keywords) en agente@; avisar al mantenedor")
        return self

    def cerrar(self):
        if self.imap is not None:
            try:
                self.imap.logout()
            except Exception:
                pass

    def _buscar(self, *criterio):
        typ, data = self.imap.uid("SEARCH", None, *criterio)
        if typ != "OK":
            raise RuntimeError(f"Búsqueda IMAP falló: {criterio}")
        return [int(x) for x in (data[0] or b"").split()]

    def pendientes(self):
        """UIDs aún no procesados, del más antiguo al más nuevo."""
        criterio = ["UNKEYWORD", CLASIFICADO, "NOT", "DELETED"]
        if self.cfg.desde:
            criterio += ["SINCE", self.cfg.desde]
        return sorted(self._buscar(*criterio))

    def leer(self, uid):
        typ, data = self.imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
        for parte in data or []:
            if isinstance(parte, tuple):
                return parte[1]
        raise RuntimeError(f"No se pudo leer el correo UID {uid}")

    def tomar(self, uid, ahora_min):
        """Reserva el correo para esta corrida. False si ya está procesado o tomado hace menos de 30 min."""
        typ, data = self.imap.uid("FETCH", str(uid), "(FLAGS)")
        texto = b" ".join(d if isinstance(d, bytes) else d[0] for d in (data or []) if d).decode(errors="replace")
        m = re.search(r"FLAGS \(([^)]*)\)", texto)
        marcas = m.group(1).split() if m else []
        if CLASIFICADO in marcas:
            return False
        tramo = (ahora_min // 10) % 6
        tomas = [f for f in marcas if re.fullmatch(r"Toma[0-5]", f)]
        if tomas and min((tramo - int(f[4])) % 6 for f in tomas) < 3:
            return False
        if tomas:
            self.imap.uid("STORE", str(uid), "-FLAGS", "(" + " ".join(tomas) + ")")
        self.marcar(uid, f"Toma{tramo}")
        return True

    def ya_procesado(self, message_id):
        if not message_id:
            return False
        mid = message_id.replace('"', "")
        return bool(self._buscar("KEYWORD", CLASIFICADO, "HEADER", "Message-ID", f'"{mid}"'))

    def marcar(self, uid, *marcas):
        typ, _ = self.imap.uid("STORE", str(uid), "+FLAGS", "(" + " ".join(marcas) + ")")
        if typ != "OK":
            raise RuntimeError(f"No se pudo marcar el correo UID {uid}")

    def descartados_sin_resumir(self):
        return sorted(self._buscar("KEYWORD", NO_APLICA, "UNKEYWORD", RESUMIDO))

    def encabezados(self, uid):
        typ, data = self.imap.uid("FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        for parte in data or []:
            if isinstance(parte, tuple):
                return parte[1]
        return b""

    def estado(self, n=8):
        """Cuántos correos hay en la bandeja y cuáles son los últimos, para revisar a distancia."""
        from email import message_from_bytes, policy
        todos = sorted(self._buscar("ALL"))
        ultimos = []
        for uid in todos[-n:]:
            typ, data = self.imap.uid("FETCH", str(uid), "(FLAGS INTERNALDATE BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            meta = next((d[0] for d in data or [] if isinstance(d, tuple)), b"").decode(errors="replace")
            h = message_from_bytes(next((d[1] for d in data or [] if isinstance(d, tuple)), b""), policy=policy.default)
            fecha = re.search(r'INTERNALDATE "([^"]+)"', meta)
            ultimos.append({"uid": uid, "llegada": fecha.group(1) if fecha else "", "de": str(h.get("From", ""))[:80],
                            "asunto": str(h.get("Subject", ""))[:80], "clasificado": CLASIFICADO in meta})
        return {
            "total": len(todos),
            "sin_clasificar": len(self._buscar("UNKEYWORD", CLASIFICADO, "NOT", "DELETED")),
            "sin_clasificar_desde": len(self.pendientes()) if self.cfg.desde else None,
            "clasificados": len(self._buscar("KEYWORD", CLASIFICADO)),
            "no_aplica": len(self._buscar("KEYWORD", NO_APLICA)),
            "ultimos": ultimos,
        }

    def soltar(self, uid):
        """Libera la reserva para que la próxima corrida lo vuelva a tomar."""
        self.imap.uid("STORE", str(uid), "-FLAGS", "(" + " ".join(f"Toma{i}" for i in range(6)) + ")")

    # --- Alertas -------------------------------------------------------------
    def _nombres_alertas(self):
        """Nombres posibles de la carpeta, empezando por el que indica el servidor (NAMESPACE)."""
        prefijo = ""
        try:
            typ, data = self.imap.namespace()
            m = re.match(rb'\(\("([^"]*)"', (data or [b""])[0] or b"")
            if typ == "OK" and m:
                prefijo = m.group(1).decode()
        except Exception:
            pass
        return list(dict.fromkeys([prefijo + "Alertas", "INBOX.Alertas", "INBOX/Alertas", "Alertas"]))

    def _en_alertas(self, funcion):
        try:
            for nombre in [self._carpeta_alertas] if self._carpeta_alertas else self._nombres_alertas():
                self.imap.create(nombre)  # si ya existe, el servidor responde NO y no pasa nada
                typ, _ = self.imap.select(nombre)
                if typ == "OK":
                    self._carpeta_alertas = nombre
                    return funcion()
            raise RuntimeError("No se pudo abrir la carpeta Alertas")
        finally:
            self.imap.select("INBOX")

    def _alertas(self):
        """[(uid, tipo, epoch)] de las alertas no resueltas."""
        salida = []
        for uid in self._buscar("UNKEYWORD", "Resuelta"):
            typ, data = self.imap.uid("FETCH", str(uid), "(INTERNALDATE BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
            meta = next((d[0] for d in data or [] if isinstance(d, tuple)), b"")
            asunto = next((d[1] for d in data or [] if isinstance(d, tuple)), b"").decode(errors="replace")
            m = re.search(r"alerta:(\S+)", asunto)
            fecha = imaplib.Internaldate2tuple(meta)
            if m and fecha:
                salida.append((uid, m.group(1), time.mktime(fecha)))
        return salida

    def alerta_reciente(self, tipo, ahora, horas=3):
        """True si este problema ya se avisó en las últimas `horas`."""
        return self._en_alertas(lambda: any(t == tipo and ahora - f < horas * 3600 for _, t, f in self._alertas()))

    def registrar_alerta(self, tipo, ahora):
        texto = f"Subject: alerta:{tipo}\r\nDate: {formatdate(ahora)}\r\n\r\n{tipo}\r\n".encode()
        self._en_alertas(lambda: self.imap.append(self._carpeta_alertas, None,
                                                  imaplib.Time2Internaldate(ahora), texto))

    def alertas_abiertas(self):
        return self._en_alertas(lambda: sorted({t for _, t, _ in self._alertas()}))

    def cerrar_alertas(self):
        def f():
            for uid, _, _ in self._alertas():
                self.marcar(uid, "Resuelta")
        self._en_alertas(f)
