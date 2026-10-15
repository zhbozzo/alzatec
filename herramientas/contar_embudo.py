"""Cuenta los correos que llegaron a agente@ (el embudo), sin abrir ni marcar nada.

Abre la bandeja en modo solo lectura (EXAMINE) y lee únicamente los
encabezados Para/CC/Fecha/Message-ID. No descarga cuerpos ni adjuntos y no
cambia el estado "leído" de ningún correo.

Uso (Python 3.9+, sin dependencias):
    python3 contar_embudo.py                 # pide la contraseña
    python3 contar_embudo.py --desde 15-Oct-2026

La contraseña también se puede pasar por la variable de entorno AGENTE_PW.
"""

import argparse
import collections
import getpass
import imaplib
import os
import re
from datetime import datetime
from email import message_from_bytes
from email.utils import getaddresses

SERVIDOR = "mail.alzatec.com"
PUERTO = 993
CUENTA = "agente@alzatec.com"
ORIGENES = ("asistentetecnico@alzatec.com", "departamentotecnico@alzatec.com", "devoluciones@alzatec.com")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--desde", help="solo correos desde esta fecha, formato IMAP: 15-Oct-2026")
    args = ap.parse_args()

    pw = os.environ.get("AGENTE_PW") or getpass.getpass(f"Contraseña de {CUENTA}: ")
    M = imaplib.IMAP4_SSL(SERVIDOR, PUERTO)
    M.login(CUENTA, pw)
    typ, data = M.select("INBOX", readonly=True)
    print(f"Conexión OK. Correos en la bandeja: {data[0].decode()}")

    criterio = f'(SINCE "{args.desde}")' if args.desde else "ALL"
    typ, ids = M.search(None, criterio)
    ids = ids[0].split()
    if not ids:
        print("No hay correos en el período.")
        return

    por_dia = collections.Counter()
    por_origen = collections.Counter()
    vistos = collections.Counter()
    campos = "(INTERNALDATE BODY.PEEK[HEADER.FIELDS (TO CC MESSAGE-ID)])"
    for i in range(0, len(ids), 200):
        typ, resp = M.fetch(b",".join(ids[i:i + 200]), campos)
        for parte in resp:
            if not isinstance(parte, tuple):
                continue
            meta = parte[0].decode()
            m = re.search(r'INTERNALDATE "(\d+-\w+-\d+)', meta)
            if m:
                por_dia[m.group(1)] += 1
            h = message_from_bytes(parte[1])
            dest = {a.lower() for _, a in getaddresses(h.get_all("To", []) + h.get_all("Cc", []))}
            origen = [o.split("@")[0] + "@" for o in ORIGENES if o in dest]
            por_origen[" + ".join(origen) or "otro (CCO o reenvío manual)"] += 1
            vistos[(h.get("Message-ID") or "").strip()] += 1
    M.logout()

    print(f"\nCorreos contados: {len(ids)}")
    print(f"Repetidos por Message-ID (llegaron por dos casillas): {sum(n - 1 for k, n in vistos.items() if k and n > 1)}")
    print("\nPor casilla de origen (según Para/CC):")
    for k, n in por_origen.most_common():
        print(f"  {n:5d}  {k}")
    print("\nPor día de llegada:")
    for k, n in sorted(por_dia.items(), key=lambda x: datetime.strptime(x[0], "%d-%b-%Y")):
        print(f"  {k}: {n}")


if __name__ == "__main__":
    main()
