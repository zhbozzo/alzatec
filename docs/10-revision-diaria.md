# Revisión y arreglo a pedido ("revisa hoy")

Cuando el usuario pide **"revisa hoy"** (o "revisa del lunes al miércoles"), Claude revisa todo lo que el clasificador hizo ese día, corrige los correos mal clasificados y, si el error puede repetirse, arregla la causa. El objetivo es que fallen solo los casos donde las personas escriben mal.

## 0. Conectarse

- `bash deploy/claude-login.sh` (lee `GCP_SA_KEY` del entorno). Antes de cada `gcloud` suelto: `unset CLOUDSDK_AUTH_ACCESS_TOKEN;`.
- Si la variable no está (la sesión se abrió antes de agregarla), pedir al usuario que abra una sesión nueva. Nunca pedir la clave por el chat.

## 1. Exportar el día

```bash
python3 herramientas/revision.py exportar --dia AAAA-MM-DD --salida <carpeta de scratchpad>/revision --lotes 2
```

Deja los correos del día (texto, hilo citado, adjuntos, cuántas imágenes) junto con lo que decidió GPT, en archivos `revision_N.json` **fuera del repositorio**. Además imprime la **cobertura**: cuántos correos enviados por Andrea y Javier (los que aparecen citados en los hilos) llegaron como copia a agente@. Si faltan, la copia de enviados no está funcionando y se pierden justo las confirmaciones: avisar al usuario para que lo vea Víctor. No llama al modelo ni marca nada. Ojo: los correos reales nunca van a git, porque el repositorio es público.

## 2. Revisar

- Leer la rúbrica: `clasificador/prompt.py` (`INSTRUCCIONES`) y las reglas fijas de `clasificador/reglas.py`.
- Por cada correo, decidir la categoría **antes** de mirar la de GPT, y compararlas.
- Con más de ~60 correos, repartir los lotes entre 2 a 4 revisores en paralelo, con las mismas instrucciones. Al usuario no le gusta que se usen muchos agentes.
- Gravedad:
  - **grave**: un movimiento real que quedó como `no_aplica`, un "acordado" falso, o despacho↔recepción cambiados (van a la casilla equivocada).
  - **leve**: acordado↔pendiente del mismo tipo en un caso discutible.
- Los revisores no ven las imágenes (GPT sí). Si la decisión pudo depender de ellas, la duda corre a favor de GPT, salvo que el texto la contradiga.

## 3. Verificar

Cada desacuerdo se verifica leyendo el correo. Si hace falta saber por qué decidió GPT con la rúbrica actual:

```bash
gcloud run jobs execute clasificador --region southamerica-west1 --args "explicar,UID,UID" --wait
```

Después, leer el evento `explicacion` en los registros. Solo cuenta como error lo que queda verificado. **Si un caso es dudoso de verdad, no se corrige: se le pregunta al usuario.**

## 4. Arreglar cada correo

```bash
gcloud run jobs execute clasificador --region southamerica-west1 --args "corregir,UID,CORRECTA,ANTERIOR,motivo breve" --wait
```

- Reenvía a la casilla correcta con `[CORREGIDO]` y una nota.
- Si antes se había reenviado a otra casilla, manda ahí un `[CORRECCIÓN] Ignorar: …`.
- Si lo correcto es `no_aplica`, solo manda el aviso de ignorar.

Luego se guarda como caso verificado, en un bucket privado del proyecto:

```bash
python3 herramientas/revision.py caso UID CATEGORIA "descripción breve del patrón"
```

Conviene guardar también uno o dos aciertos difíciles del día, para que un arreglo futuro no los rompa.

## 5. Arreglar la causa (si el error puede repetirse)

1. Cambio mínimo en la rúbrica (`clasificador/prompt.py`) o, si el texto siempre se escribe igual, una regla fija en `reglas.py` con su prueba.
2. `python3 -m pytest -q`, luego commit y push.
3. `bash deploy/actualizar.sh`
4. `python3 herramientas/revision.py regresion` tiene que dar **todos los casos bien**. Si alguno falla, ajustar o revertir antes de dar por terminado.
5. `python3 herramientas/revision.py evaluar` corre los 200 correos históricos de validación con memoria (unos 10 minutos y US$0,75). El resultado no puede quedar bajo **198/200**. Los casos límite conocidos, que cambian de una corrida a otra, son J047, A086 y A092. Si aparecen otros, revisarlos antes de dejar el cambio.
6. Para probar un cambio grande con correos reales sin tocar producción, está el job `clasificador-prueba`: `gcloud run jobs deploy clasificador-prueba --source . --region southamerica-west1 --quiet`, y luego `gcloud run jobs execute clasificador-prueba --region southamerica-west1 --args "simular,15-Oct-2026,17-Oct-2026" --wait`. Reclasifica con memoria y en orden de llegada, sin reenviar ni marcar. El resultado queda en los eventos `simulacion` de los registros.

## 6. Informe al usuario

- Correos del día, **% de coincidencia** (correctos / total), errores graves y leves, correcciones enviadas, cambios en la rúbrica, resultado de la regresión y gasto del día (`bash deploy/ver.sh`).
- Agregar una línea a `docs/11-revisiones.md`, solo con números y patrones generales, sin nombres de clientes ni contenido de correos.

## Límites

- No tocar las casillas de Andrea ni de Javier, no responder a clientes y no tocar MADA.
- No cambiar el modelo ni agregar un segundo modelo sin que el usuario lo pida.
