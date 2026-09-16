# Una sola imagen para todo: nodos, clientes, herramientas y tests.
FROM python:3.10-slim

# TZ: hora argentina en los logs, sin depender de tzdata
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TERM=xterm-256color \
    TZ="<-03>3"

WORKDIR /app

# las dependencias primero: cambiar el codigo no las reinstala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY juego/ juego/
COPY nodo/ nodo/
COPY cliente/ cliente/
COPY tests/ tests/
COPY run_tests.py demo.py ./

# docker compose stop equivale a un Ctrl+C: el nodo cierra sus puertos y sale
STOPSIGNAL SIGINT
CMD ["python", "-m", "nodo.servidor"]
