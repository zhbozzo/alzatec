# Alzatec · Clasificador de correos

**Etapa 1 (actual):** un agente recibe una copia de los correos de Andrea y de Javier en `agente@alzatec.com`, que funciona como embudo. Los clasifica y los reenvía a tres casillas:

| Categoría | Casilla |
|---|---|
| Despacho acordado | `despachosconfirmados@alzatec.com` |
| Recepción acordada | `devolucionesconfirmadas@alzatec.com` (hasta el 19-oct, `retirosconfirmados@`) |
| Pendiente (le falta algo) | `pendientesdespachoyrecepcion@alzatec.com` |

Las cotizaciones y el resto no se mueven. No hay agenda ni Excel en esta etapa. No toca MADA ni responde a clientes.

**Etapa 2 (futuro):** agenda de camiones en el Excel de Pato, con alerta de día copado.

## Documentos

- **Etapa 1**
  - [Requerimientos](docs/04-requerimientos.md): el documento para gerencia.
  - [Cómo funciona el clasificador](docs/07-agente-v1.md): flujo, JSON, reglas, reenvío y puesta en marcha.
  - [Notas de la reunión](docs/08-notas-reunion.md): lo confirmado y las preguntas abiertas.
  - [Análisis de la base de correos](docs/09-analisis-correos.md): volúmenes, hallazgos críticos y señales de cada categoría.
- **Contexto y etapa 2**
  - [Diagnóstico](docs/01-diagnostico.md)
  - [Propuesta de agenda](docs/02-propuesta.md)
  - [Guía de reunión](docs/03-reunion.md)
  - [Implementación (correo, OneDrive, n8n)](docs/05-implementacion.md)
  - [Clasificación](docs/06-clasificacion.md)
  - Ejemplo de agenda: [`ejemplos/agenda-camiones-ejemplo.xlsx`](ejemplos/agenda-camiones-ejemplo.xlsx)

## Clasificador (código)

- [`clasificador/`](clasificador): el agente. Usa un solo modelo (GPT-6.1 Sol) y avisa por correo a `lbpiphone4@gmail.com` si algo falla, con qué pasó y qué hacer. Se corre con `python -m clasificador procesar` (cada 3 minutos) y `python -m clasificador resumen` (una vez al día). Cómo funciona: [07](docs/07-agente-v1.md).
- Prueba con los 200 correos etiquetados (necesita las API keys y los datos en `datos/`):
  ```
  python -m clasificador.evaluar --modelo openai:gpt-6.1-sol
  ```
- Pruebas automáticas, sin red: `pip install -r requirements-dev.txt && python -m pytest`.
- Puesta en marcha en Google Cloud: [`deploy/README.md`](deploy/README.md).

## Herramientas

- [`herramientas/contar_embudo.py`](herramientas/contar_embudo.py): cuenta los correos que llegaron a `agente@`, por casilla de origen (incluidos los que llegan por la regla CC de lo que envían Andrea y Javier) y por día. Abre la bandeja en solo lectura: no descarga cuerpos ni marca nada como leído. Pide la contraseña al ejecutarlo.
  ```
  python3 herramientas/contar_embudo.py --desde 15-Oct-2026
  ```

## Estado

- **Reunión de levantamiento hecha.** Se definió la etapa 1.
- **Casillas creadas por Informática** ✓
- **Pendiente:**
  - ~~recibir los `.pst`~~ ✓ analizados (ver [09](docs/09-analisis-correos.md));
  - ~~reenvío `asistentetecnico@ → agente@`~~ ✓ listo (se mantiene también el de `departamentotecnico@`);
  - ~~reglas CC en Outlook~~ ✓ Víctor configuró la copia a `agente@` de todo lo que **envían** Andrea (`asistentetecnico@`) y Javier (`devoluciones@`). Las reglas corren en el Outlook del PC; Víctor confirmó que ambos envían siempre desde el PC y no usan el correo en el celular ✓;
  - **antes de que Javier use el celular de Alzatec:** que el servidor copie a `agente@` todo lo que sale de `devoluciones@` (funciona desde cualquier aparato). Víctor dice que lo puede hacer él desde el hosting; si cPanel no lo permite, lo hace el soporte de HostingPlus. Plan B: que Javier envíe las confirmaciones siempre desde el PC;
  - respaldo de los **Elementos enviados** de Andrea (pedido a Víctor, cuando ella tenga tiempo);
  - validación de Andrea y Javier: el **archivo de validación** está listo (200 correos clasificados, con 8 preguntas de criterio). Ver [09 §5](docs/09-analisis-correos.md#5-archivo-de-validación).
  - comparación preliminar de modelos: **Sonnet** coincide en 95% y tiene 0 errores graves claros; Haiku perdería 3 correos. Ver [09 §6](docs/09-analisis-correos.md#6-comparación-de-modelos-preliminar).

## Datos

Los correos reales de clientes **no se suben a este repositorio**. Van en `datos/`, que está ignorado por git.
