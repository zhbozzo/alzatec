FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY clasificador ./clasificador
# Uso: procesar (cada pocos minutos) o resumen (una vez al día)
ENTRYPOINT ["python", "-m", "clasificador"]
CMD ["procesar"]
