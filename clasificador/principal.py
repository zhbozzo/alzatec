"""Orquestación: procesar la casilla y enviar el resumen diario."""

import json
import sys
import time
from email import message_from_bytes, policy

from . import memoria, modelos
from .buzon import CLASIFICADO, DUPLICADO, NO_APLICA, RESUMIDO
from .modelos import ErrorServicio
from .correo import Correo, leer
from .envio import ETIQUETAS, armar_aviso, armar_correccion, armar_reenvio
from .reglas import Decision, VACIO, decidir

# US$ por millón de tokens: entrada, entrada en caché, salida
PRECIOS = {
    "gpt-6.1-sol": (2.0, 0.10, 10.0),
    "claude-sonnet-5-5": (2.0, 0.20, 10.0),
    "claude-haiku-5-5": (0.10, 0.01, 0.50),
}


def costo(uso):
    p = PRECIOS.get(uso.modelo)
    if not p:
        return None
    sin_cache = max(uso.entrada - uso.entrada_cache, 0)
    return (sin_cache * p[0] + uso.entrada_cache * p[1] + uso.salida * p[2]) / 1e6


def registrar(**datos):
    """Una línea JSON por evento (Cloud Logging la indexa; "severity" marca los errores)."""
    if datos.get("evento") in ("error", "alerta"):
        datos.setdefault("severity", "ERROR")
    print(json.dumps(datos, ensure_ascii=False), flush=True)


def _correo_ilegible(crudo):
    return Correo(message_id="", asunto="(no se pudo leer el correo)", remitente="", remitente_correo="",
                  para="", cc="", fecha="", texto_nuevo="", texto_citado="", crudo=crudo, ilegible=True)


def _explicacion(resultado):
    """Lo que dijo el modelo, para poder revisar después por qué clasificó así."""
    campos = ("movimiento", "fecha_movimiento", "cliente", "obra", "falta", "resumen", "motivo")
    return {c: (resultado.get(c)[:300] if isinstance(resultado.get(c), str) else resultado.get(c)) for c in campos}


def _historial(buzon, correo):
    """Lo que ya se reenvió en el hilo de este correo. Si la memoria falla, se sigue sin ella."""
    try:
        return buzon.historial(memoria.claves_buscar(correo))
    except Exception as e:
        registrar(evento="memoria_fallida", severity="WARNING", accion="leer", error=f"{type(e).__name__}: {e}")
        return []


def _recordar(buzon, correo, decision, uid):
    try:
        buzon.registrar_decision(memoria.claves_guardar(correo), memoria.entrada(correo, decision, uid))
    except Exception as e:
        registrar(evento="memoria_fallida", severity="WARNING", accion="guardar", error=f"{type(e).__name__}: {e}")


def simular(cfg, buzon, principal, desde=None, hasta=None):
    """Clasifica de nuevo, en orden de llegada y con memoria, los correos del rango. No reenvía, no marca y
    no escribe en la memoria real: sirve para probar cambios antes de subirlos."""
    local = memoria.MemoriaLocal()
    for uid in buzon.todos_desde(desde, hasta):
        try:
            correo = leer(buzon.leer(uid), cfg.max_imagenes)
        except Exception:
            continue
        if correo.remitente_correo == cfg.usuario.lower() or es_rebote_de_reenvio(cfg, correo):
            continue
        correo.historial = local.historial(memoria.claves_buscar(correo))
        decision = decidir(correo, principal)
        if cfg.destino(decision.categoria):
            local.registrar_decision(memoria.claves_guardar(correo), memoria.entrada(correo, decision, uid))
        registrar(evento="simulacion", uid=uid, asunto=correo.asunto[:200], remitente=correo.remitente_correo,
                  categoria=decision.categoria, fuente=decision.fuente, nota=decision.nota[:300],
                  historial=len(correo.historial), repite=decision.resultado.get("repite"),
                  confianza=decision.resultado.get("confianza"), **_explicacion(decision.resultado))


def precargar(cfg, buzon, decisiones):
    """Carga en la memoria decisiones ya revisadas (uid, categoria, movimiento, fecha_movimiento, resumen)."""
    from .reglas import Decision as D
    for d in decisiones:
        correo = leer(buzon.leer(int(d["uid"])), cfg.max_imagenes)
        decision = D(d["categoria"], {k: d.get(k, "") for k in ("movimiento", "fecha_movimiento", "n_cotizacion", "resumen")})
        buzon.registrar_decision(memoria.claves_guardar(correo), memoria.entrada(correo, decision, int(d["uid"])))
    registrar(evento="precarga", decisiones=len(decisiones))


def explicar(cfg, buzon, principal, texto="", uids=None, maximo=5):
    """Vuelve a clasificar los correos indicados (por UID, o los últimos cuyo asunto contiene `texto`)
    y registra el detalle.

    No reenvía ni marca nada: sirve para revisar a distancia por qué un correo quedó como quedó y para
    la prueba de regresión.
    """
    uids = uids or buzon.buscar_asunto(texto)[-maximo:]
    for uid in uids:
        correo = leer(buzon.leer(uid), cfg.max_imagenes)
        correo.historial = _historial(buzon, correo)
        decision = decidir(correo, principal)
        registrar(evento="explicacion", uid=uid, asunto=correo.asunto[:200], remitente=correo.remitente_correo,
                  fecha=correo.fecha, categoria=decision.categoria, revisar=decision.revisar, nota=decision.nota[:300],
                  confianza=decision.resultado.get("confianza"), **_explicacion(decision.resultado),
                  texto=correo.texto_nuevo[:1500], citado=correo.texto_citado[:800],
                  adjuntos=correo.adjuntos[:10], imagenes=len(correo.imagenes))
    return len(uids)


AVISO_REBOTE = "aviso_reenvio_rebotado"  # los tipos "aviso_" no esperan un "resuelto"


def es_rebote_de_reenvio(cfg, correo):
    """El servidor devolvió un reenvío del propio clasificador (no llegó a su casilla)."""
    if not correo.remitente_correo.startswith(("mailer-daemon@", "postmaster@")):
        return False
    texto = f"{correo.asunto}\n{correo.texto_nuevo}\n{correo.texto_citado}".lower()
    return any(d.lower() in texto for d in cfg.destinos.values())


def corregir(cfg, buzon, principal, enviar, uid, ahora, antes, nota=""):
    """Corrige un correo mal clasificado, después de revisarlo.

    Lo reenvía a la casilla correcta con [CORREGIDO] y, si antes se reenvió a otra casilla, manda ahí
    un aviso para ignorar ese reenvío.
    """
    if ahora not in ETIQUETAS or antes not in ETIQUETAS or ahora == antes:
        raise ValueError(f"Corrección no válida: {antes} -> {ahora}")
    correo = leer(buzon.leer(uid), cfg.max_imagenes)
    base = decidir(correo, principal).resultado  # fecha, resumen y datos para el reenvío
    resultado = dict(base, categoria=ahora, falta=base.get("falta", []) if ahora == "pendiente" else [])
    decision = Decision(ahora, resultado, fuente="correccion",
                        nota=f"se había clasificado como {ETIQUETAS[antes]}. {nota}".strip())
    destino, destino_antes = cfg.destino(ahora), cfg.destino(antes)
    if destino:
        enviar(armar_reenvio(cfg, correo, decision, destino))
    if destino_antes:
        enviar(armar_correccion(cfg, correo, antes, ahora, destino, nota))
    buzon.marcar(uid, CLASIFICADO, *([NO_APLICA] if ahora == "no_aplica" else []))
    if ahora != "no_aplica":
        buzon.desmarcar(uid, NO_APLICA)
        _recordar(buzon, correo, decision, uid)
    registrar(evento="correccion", uid=uid, asunto=correo.asunto[:200], antes=antes, ahora=ahora,
              destino=destino, aviso_a=destino_antes, nota=nota[:300])


def exportar(cfg, buzon, desde=None, hasta=None):
    """Registra el texto de los correos (desde la fecha de inicio, o del rango dado en formato IMAP:
    19-Oct-2026), para revisar a distancia la clasificación. No llama al modelo ni marca nada.
    """
    uids = buzon.todos_desde(desde, hasta)
    for uid in uids:
        try:
            correo = leer(buzon.leer(uid), cfg.max_imagenes)
        except Exception as e:
            registrar(evento="export", uid=uid, error=f"{type(e).__name__}: {e}")
            continue
        registrar(evento="export", uid=uid, message_id=correo.message_id, fecha=correo.fecha,
                  remitente=correo.remitente, para=correo.para[:300], cc=correo.cc[:300], asunto=correo.asunto[:200],
                  marcas=[m for m in buzon.marcas(uid) if not m.startswith("\\")],
                  texto=correo.texto_nuevo[:4000], citado=correo.texto_citado[:2500],
                  adjuntos=correo.adjuntos[:10], imagenes=len(correo.imagenes))
    return len(uids)


def procesar(cfg, buzon, principal, verificador, enviar):
    """Procesa los correos nuevos de agente@. Devuelve cuántos procesó."""
    todos = buzon.pendientes()
    uids = todos[: cfg.max_por_corrida]
    vistos = set()
    rebotes = []
    t0 = time.time()
    hechos = 0
    for uid in uids:
        if time.time() - t0 > cfg.max_segundos:
            registrar(evento="corte_por_tiempo", procesados=hechos, pendientes=len(uids) - hechos)
            break
        if not buzon.tomar(uid, int(time.time() // 60)):
            continue
        hechos += 1
        crudo = buzon.leer(uid)
        try:
            correo = leer(crudo, cfg.max_imagenes)
        except Exception:
            correo = _correo_ilegible(crudo)

        mid = correo.message_id
        if mid and (mid in vistos or buzon.ya_procesado(mid)):
            buzon.marcar(uid, CLASIFICADO, DUPLICADO)
            registrar(evento="duplicado", uid=uid, message_id=mid)
            continue
        vistos.add(mid)

        if correo.remitente_correo == cfg.usuario.lower():
            buzon.marcar(uid, CLASIFICADO)  # nunca reprocesar lo que envía el propio agente
            continue

        if es_rebote_de_reenvio(cfg, correo):
            buzon.marcar(uid, CLASIFICADO, RESUMIDO)  # no va al resumen diario: se avisa aparte
            rebotes.append(f"{correo.fecha}: {' '.join(correo.texto_nuevo.split())[:400]}")
            registrar(evento="rebote_reenvio", severity="WARNING", uid=uid, asunto=correo.asunto[:200],
                      texto=correo.texto_nuevo[:500])
            continue

        inicio = time.time()
        if correo.ilegible:
            decision = Decision("pendiente", dict(VACIO), revisar=True, fuente="error",
                                nota="No se pudo leer el formato del correo. Revisar a mano.")
        else:
            correo.historial = _historial(buzon, correo)
            try:
                decision = decidir(correo, principal, verificador)
            except ErrorServicio:
                buzon.soltar(uid)  # el servicio no está disponible: el correo espera en agente@
                raise
            except Exception as e:  # cualquier error inesperado con este correo: a pendientes, nunca se pierde
                decision = Decision("pendiente", dict(VACIO), revisar=True, fuente="error",
                                    nota=f"Error interno del clasificador ({type(e).__name__}: {e}). Revisar a mano.")

        destino = cfg.destino(decision.categoria)
        if destino:
            try:
                enviar(armar_reenvio(cfg, correo, decision, destino))
            except Exception:
                buzon.soltar(uid)  # si falla el envío, no se marca y se reintenta en la próxima corrida
                raise
        buzon.marcar(uid, CLASIFICADO, *([NO_APLICA] if decision.categoria == "no_aplica" else []))
        if destino:
            _recordar(buzon, correo, decision, uid)

        costos = [costo(u) for u in decision.usos]
        registrar(
            evento="clasificado", uid=uid, message_id=mid, fecha=correo.fecha,
            remitente=correo.remitente_correo, asunto=correo.asunto[:200],
            categoria=decision.categoria, revisar=decision.revisar, fuente=decision.fuente,
            nota=decision.nota[:300], confianza=decision.resultado.get("confianza"),
            n_cotizacion=decision.resultado.get("n_cotizacion"), destino=destino,
            historial=len(correo.historial), repite=decision.resultado.get("repite"),
            **_explicacion(decision.resultado),
            modelos=[u.modelo for u in decision.usos],
            tokens=[[u.entrada, u.entrada_cache, u.salida] for u in decision.usos],
            costo_usd=round(sum(c for c in costos if c), 5),
            segundos=round(time.time() - inicio, 1),
        )
    registrar(evento="corrida", procesados=hechos, en_espera=len(todos) - hechos)
    if rebotes:
        avisar(cfg, buzon, enviar, AVISO_REBOTE, f"{len(rebotes)} reenvíos fueron devueltos por el servidor",
               "Esos correos NO llegaron a su casilla. Avisar al mantenedor para revisar el motivo y volver a "
               "enviarlos (siguen en agente@).", "\n\n".join(rebotes[:5]), "procesar",
               pie="Este aviso no se repite por 3 horas.")
    return hechos


def resumen_diario(cfg, buzon, enviar):
    """Manda la lista de lo descartado como "no aplica" desde el último resumen."""
    uids = buzon.descartados_sin_resumir()
    if not uids:
        return 0
    lineas = []
    for uid in uids:
        h = message_from_bytes(buzon.encabezados(uid), policy=policy.default)
        lineas.append(f"- {h.get('Date', '')} | {h.get('From', '')} | {h.get('Subject', '')}")
    texto = (
        f"Estos {len(uids)} correos se clasificaron como \"no aplica\" y NO se reenviaron.\n"
        "Si alguno era un despacho o una devolución, avisar al mantenedor.\n\n" + "\n".join(lineas)
    )
    prefijo = "[SOMBRA] " if cfg.modo == "sombra" else ""
    enviar(armar_aviso(cfg, cfg.resumen_a, f"{prefijo}Resumen diario: {len(uids)} correos descartados", texto))
    for uid in uids:
        buzon.marcar(uid, RESUMIDO)
    registrar(evento="resumen", correos=len(uids))
    return len(uids)


def _destinatarios(cfg):
    return ", ".join(cfg.alertas_a)


PIE_ALERTA = ("Los correos NO se pierden: quedan en agente@ y se procesan apenas se arregle. "
              "Este aviso no se repite por 3 horas; cuando se resuelva llega un correo de confirmación.")


def avisar(cfg, buzon, enviar, tipo, titulo, que_hacer, detalle, accion, pie=PIE_ALERTA):
    """Manda una alerta con qué pasó y qué hacer. El mismo problema se avisa como máximo cada 3 horas."""
    ahora = time.time()
    try:
        if buzon.alerta_reciente(tipo, ahora):
            registrar(evento="alerta_omitida", tipo=tipo)
            return
    except Exception:
        # Sin acceso al registro de alertas no se puede llevar la cuenta: para no mandar un correo
        # cada 3 minutos, se avisa solo en la primera corrida de cada hora (la alerta de Google Cloud
        # avisa de inmediato igual).
        if (ahora // 60) % 60 >= 3:
            registrar(evento="alerta_omitida", tipo=tipo, motivo="sin registro de alertas")
            return
    texto = (
        f"Qué pasó: {titulo}.\n\n"
        f"Qué hacer: {que_hacer}\n\n"
        f"{pie}\n\n"
        f"Detalle técnico ({accion}): {detalle}"
    )
    enviar(armar_aviso(cfg, _destinatarios(cfg), f"[ALERTA] Clasificador de correos: {titulo}", texto))
    registrar(evento="alerta", tipo=tipo, titulo=titulo)
    try:
        buzon.registrar_alerta(tipo, ahora)
    except Exception:
        pass


def avisar_si_se_resolvio(cfg, buzon, enviar):
    abiertas = [t for t in buzon.alertas_abiertas() if not t.startswith("aviso_")]
    if not abiertas:
        return
    enviar(armar_aviso(cfg, _destinatarios(cfg), "[RESUELTO] Clasificador de correos funcionando de nuevo",
                       "El clasificador volvió a funcionar y está procesando los correos que quedaron esperando.\n\n"
                       f"Problemas resueltos: {', '.join(abiertas)}"))
    buzon.cerrar_alertas(abiertas)
    registrar(evento="resuelto", tipos=abiertas)


def main(argv=None):
    from .buzon import Buzon
    from .config import Config
    from .envio import EnviadorSMTP

    argv = argv if argv is not None else sys.argv[1:]
    accion = argv[0] if argv else "procesar"
    cfg = Config.desde_entorno()
    buzon = Buzon(cfg)
    enviar = EnviadorSMTP(cfg)
    try:
        try:
            buzon.conectar()
        except Exception as e:
            raise ErrorServicio(
                "correo_imap", "No se pudo entrar a la casilla agente@",
                "Revisar si cambió la contraseña de agente@ y, si cambió, actualizar el secreto 'agente-pw' en "
                "Google Cloud. Si la contraseña está bien, puede ser una caída del hosting (HostingPlus).",
                f"{type(e).__name__}: {e}") from e
        if accion == "procesar":
            principal = modelos.crear(cfg.modelo, cfg.esfuerzo)
            verificador = modelos.crear(cfg.verificador, cfg.esfuerzo)
            procesar(cfg, buzon, principal, verificador, enviar)
        elif accion == "resumen":
            resumen_diario(cfg, buzon, enviar)
        elif accion == "estado":  # solo informa, no toca ningún correo
            registrar(evento="estado", desde=cfg.desde, **buzon.estado())
            return
        elif accion == "marcas":  # mantención: marcas +Resumido -Clasificado 120 121 ...
            cambios = [a for a in argv[1:] if a[:1] in "+-"]
            uids = [int(a) for a in argv[1:] if a.isdigit()]
            buzon.cambiar_marcas(cambios, uids)
            registrar(evento="marcas", cambios=cambios, uids=uids)
            return
        elif accion == "exportar":  # exportar [desde] [hasta]: registra el texto, sin llamar al modelo ni marcar
            exportar(cfg, buzon, *(argv[1:3]))
            return
        elif accion == "explicar":  # explicar UID UID... | explicar TEXTO DEL ASUNTO (sin reenviar ni marcar)
            principal = modelos.crear(cfg.modelo, cfg.esfuerzo)
            if argv[1:] and all(a.isdigit() for a in argv[1:]):
                explicar(cfg, buzon, principal, uids=[int(a) for a in argv[1:]])
            else:
                explicar(cfg, buzon, principal, " ".join(argv[1:]))
            return
        elif accion == "simular":  # simular [desde] [hasta]: reclasifica con memoria sin reenviar ni marcar
            simular(cfg, buzon, modelos.crear(cfg.modelo, cfg.esfuerzo), *(argv[1:3]))
            return
        elif accion == "precargar":  # precargar BASE64(JSON con decisiones revisadas)
            import base64
            precargar(cfg, buzon, json.loads(base64.b64decode("".join(argv[1:])).decode()))
            return
        elif accion == "corregir":  # corregir UID CATEGORIA_CORRECTA CATEGORIA_ANTERIOR [motivo]
            corregir(cfg, buzon, modelos.crear(cfg.modelo, cfg.esfuerzo), enviar,
                     int(argv[1]), argv[2], argv[3], ", ".join(argv[4:]))
            return
        else:
            raise SystemExit(f"Acción desconocida: {accion} (usar 'procesar', 'resumen' o 'estado')")
        try:
            avisar_si_se_resolvio(cfg, buzon, enviar)
        except Exception as e:  # el registro de alertas no debe frenar la clasificación
            registrar(evento="aviso_resuelto_fallido", severity="WARNING", error=f"{type(e).__name__}: {e}")
    except Exception as e:
        registrar(evento="error", accion=accion, error=f"{type(e).__name__}: {e}")
        if isinstance(e, ErrorServicio):
            tipo, titulo, que_hacer, detalle = e.tipo, e.titulo, e.que_hacer, e.detalle
        else:
            tipo, titulo = f"otro_{type(e).__name__}", "Error inesperado del clasificador"
            que_hacer = ("Revisar los registros en Google Cloud (Cloud Run → Jobs → clasificador → Registros) "
                         "o avisar al mantenedor.")
            detalle = f"{type(e).__name__}: {e}"
        try:
            avisar(cfg, buzon, enviar, tipo, titulo, que_hacer, detalle, accion)
        except Exception:
            pass  # si tampoco se puede enviar correo, avisa la alerta de Google Cloud
        raise
    finally:
        enviar.cerrar()
        buzon.cerrar()
