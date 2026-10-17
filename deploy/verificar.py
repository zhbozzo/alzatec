"""Prueba las claves antes de guardarlas en Google Cloud.

    CLAVE=... python3 deploy/verificar.py agente
    CLAVE=... python3 deploy/verificar.py openai gpt-6.1-sol

Solo usa la biblioteca estándar, así corre en Cloud Shell sin instalar nada. La clave se lee de la
variable CLAVE para que no quede en el historial de la terminal.

Sale con:
  0  funciona
  1  la clave está mala (hay que escribirla de nuevo)
  2  no se pudo probar (red o servidor caído); se guarda igual
  3  la clave está bien pero falta algo en la cuenta (por ejemplo, saldo en OpenAI)
"""

import imaplib
import json
import os
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.request

HOST = "mail.alzatec.com"
USUARIO = "agente@alzatec.com"
BIEN, MALA, NO_SE_PUDO, FALTA_ALGO = 0, 1, 2, 3


def agente(clave):
    ctx = ssl.create_default_context()
    try:
        with imaplib.IMAP4_SSL(HOST, 993, ssl_context=ctx, timeout=30) as m:
            m.login(USUARIO, clave)
            typ, _ = m.select("INBOX")
            if typ != "OK":
                print("   No se pudo abrir la bandeja de entrada de agente@.")
                return NO_SE_PUDO
            permanentes = m.untagged_responses.get("PERMANENTFLAGS", [b""])[0] or b""
            hoy = time.strftime("%d-%b-%Y")
            _, sin = m.search(None, "UNKEYWORD", "Clasificado", "SINCE", hoy)
            nuevos = len((sin[0] or b"").split())
    except imaplib.IMAP4.error as e:
        print(f"   La contraseña de agente@ no funciona (el servidor dijo: {e}).")
        return MALA
    except OSError as e:
        print(f"   No se pudo conectar a {HOST} para probar la contraseña ({type(e).__name__}: {e}).")
        return NO_SE_PUDO
    if b"\\*" not in permanentes:
        print("   Ojo: el servidor de agente@ no permite marcas propias; el clasificador no va a poder llevar la cuenta.")
        return FALTA_ALGO
    try:
        with smtplib.SMTP_SSL(HOST, 465, context=ctx, timeout=30) as s:
            s.login(USUARIO, clave)
    except smtplib.SMTPAuthenticationError as e:
        print(f"   La contraseña sirve para leer agente@ pero no para enviar desde ella ({e}).")
        return FALTA_ALGO
    except (smtplib.SMTPException, OSError) as e:
        print(f"   La contraseña sirve para leer, pero no se pudo probar el envío ({type(e).__name__}: {e}).")
        return NO_SE_PUDO
    print(f"   OK: la contraseña de agente@ funciona para leer y enviar. Correos de hoy sin clasificar: {nuevos}.")
    return BIEN


def _pedir(metodo, ruta, clave, cuerpo=None):
    pedido = urllib.request.Request(
        "https://api.openai.com/v1" + ruta, method=metodo,
        data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(pedido, timeout=120) as r:
        return json.load(r)


def _modelos_disponibles(clave):
    try:
        ids = sorted(m["id"] for m in _pedir("GET", "/models", clave)["data"])
    except Exception:
        return []
    return [i for i in ids if i.startswith("gpt-6")] or ids[-15:]


def openai(clave, modelo):
    # Una consulta mínima al mismo modelo que usa el clasificador (cuesta menos de US$0,01)
    cuerpo = {"model": modelo, "input": "Responde solo: ok", "max_output_tokens": 200, "reasoning": {"effort": "low"}}
    try:
        _pedir("POST", "/responses", clave, cuerpo)
    except urllib.error.HTTPError as e:
        try:
            error = json.load(e).get("error") or {}
        except Exception:
            error = {}
        codigo = f"{error.get('code') or ''} {error.get('type') or ''}"
        mensaje = error.get("message") or ""
        detalle = f"(OpenAI respondió {e.code}: {mensaje[:300]})"
        if e.code == 401:
            print(f"   La API key no es válida; revisa que se haya copiado completa. {detalle}")
            return MALA
        if "insufficient_quota" in codigo or "billing" in mensaje.lower() or "quota" in mensaje.lower():
            print("   La API key está bien, pero la cuenta de OpenAI no tiene saldo. Carga créditos en "
                  "platform.openai.com → Settings → Billing y vuelve a correr el mismo comando. " + detalle)
            return FALTA_ALGO
        if e.code == 404 or "model_not_found" in codigo or "does not exist" in mensaje:
            print(f"   La API key funciona, pero no tiene acceso al modelo {modelo}. {detalle}")
            disponibles = _modelos_disponibles(clave)
            if disponibles:
                print("   Modelos a los que sí tiene acceso: " + ", ".join(disponibles))
            return FALTA_ALGO
        if e.code == 403:
            print("   La API key no tiene permiso para usar el modelo. Crea otra con permisos 'All' "
                  f"en el mismo proyecto de OpenAI. {detalle}")
            return MALA
        if e.code == 400:
            print(f"   OK: la API key funciona (la prueba devolvió un aviso que no afecta: {mensaje[:200]}).")
            return BIEN
        print(f"   No se pudo probar la API key ahora. {detalle}")
        return NO_SE_PUDO
    except OSError as e:
        print(f"   No se pudo conectar a OpenAI para probar la API key ({type(e).__name__}: {e}).")
        return NO_SE_PUDO
    print(f"   OK: la API key funciona y tiene acceso a {modelo}.")
    return BIEN


def main(argv):
    clave = os.environ.get("CLAVE", "").strip()
    if not clave:
        print("   Falta la clave.")
        return MALA
    if argv[:1] == ["agente"]:
        return agente(clave)
    if argv[:1] == ["openai"] and len(argv) == 2:
        return openai(clave, argv[1])
    print(__doc__)
    return NO_SE_PUDO


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
