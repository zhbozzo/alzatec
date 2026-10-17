"""Configuración leída de variables de entorno.

Las contraseñas y API keys nunca van en el repositorio: en Google Cloud se
cargan desde Secret Manager como variables de entorno.
"""

import os
from dataclasses import dataclass, field


def _env(nombre, defecto=None, obligatoria=False):
    valor = os.environ.get(nombre, defecto)
    if obligatoria and not valor:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return valor


@dataclass
class Config:
    # Casilla embudo
    imap_host: str = "mail.alzatec.com"
    imap_puerto: int = 993
    smtp_host: str = "mail.alzatec.com"
    smtp_puerto: int = 465
    usuario: str = "agente@alzatec.com"
    contrasena: str = ""

    # Modo: "sombra" reenvía todo a la casilla de prueba; "vivo" a las casillas reales
    modo: str = "sombra"
    casilla_prueba: str = ""
    destinos: dict = field(default_factory=lambda: {
        "despacho_acordado": "despachosconfirmados@alzatec.com",
        "recepcion_acordada": "retirosconfirmados@alzatec.com",
        "pendiente": "pendientesdespachoyrecepcion@alzatec.com",
    })
    # A quién va el resumen diario de lo descartado ("no aplica")
    resumen_a: str = ""
    # A quién avisar si algo falla (separados por coma en ALERTAS_A)
    alertas_a: list = field(default_factory=lambda: ["lbozzo@fen.uchile.cl", "lbpiphone4@gmail.com"])

    # Modelo principal y segunda opinión opcional ("openai:gpt-6.1-sol", "anthropic:claude-sonnet-5-5" o "")
    modelo: str = "openai:gpt-6.1-sol"
    verificador: str = ""
    esfuerzo: str = "medium"

    # Límites por corrida
    max_por_corrida: int = 40
    max_segundos: int = 240       # la corrida deja de tomar correos nuevos pasado este tiempo
    max_imagenes: int = 8
    # Solo procesar correos llegados desde esta fecha (formato IMAP: 19-Oct-2026). Vacío = todos.
    desde: str = ""

    @classmethod
    def desde_entorno(cls):
        c = cls()
        c.imap_host = _env("IMAP_HOST", c.imap_host)
        c.imap_puerto = int(_env("IMAP_PUERTO", c.imap_puerto))
        c.smtp_host = _env("SMTP_HOST", c.smtp_host)
        c.smtp_puerto = int(_env("SMTP_PUERTO", c.smtp_puerto))
        c.usuario = _env("AGENTE_USUARIO", c.usuario)
        c.contrasena = _env("AGENTE_PW", obligatoria=True)
        c.modo = _env("MODO", c.modo)
        if c.modo not in ("sombra", "vivo"):
            raise RuntimeError("MODO debe ser 'sombra' o 'vivo'")
        c.casilla_prueba = _env("CASILLA_PRUEBA", "")
        if c.modo == "sombra" and not c.casilla_prueba:
            raise RuntimeError("En modo sombra hay que definir CASILLA_PRUEBA")
        c.resumen_a = _env("RESUMEN_A", c.casilla_prueba)
        alertas = _env("ALERTAS_A", "")
        if alertas:
            c.alertas_a = [a.strip() for a in alertas.split(",") if a.strip()]
        c.modelo = _env("MODELO", c.modelo)
        c.verificador = _env("VERIFICADOR", c.verificador)
        c.esfuerzo = _env("ESFUERZO", c.esfuerzo)
        c.max_por_corrida = int(_env("MAX_POR_CORRIDA", c.max_por_corrida))
        c.max_segundos = int(_env("MAX_SEGUNDOS", c.max_segundos))
        c.max_imagenes = int(_env("MAX_IMAGENES", c.max_imagenes))
        c.desde = _env("DESDE", c.desde)
        return c

    def destino(self, categoria):
        """Casilla a la que se reenvía una categoría, o None si no se reenvía."""
        if categoria not in self.destinos:
            return None
        return self.casilla_prueba if self.modo == "sombra" else self.destinos[categoria]
