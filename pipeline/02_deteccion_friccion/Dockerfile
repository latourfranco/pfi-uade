# Imagen del Cloud Run Job trabajo-deteccion-friccion (módulo 2). Una tarea = un cliente. Sin datos.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu
COPY modulo/requirements.txt modulo/requirements.txt
RUN pip install -r modulo/requirements.txt

COPY preprocesamiento/*.py preprocesamiento/
COPY ingesta/*.py ingesta/
COPY modulo/*.py modulo/

CMD ["python", "-m", "modulo.principal"]
