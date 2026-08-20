FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# Render inyecta PORT automáticamente; server.py lo detecta y corre por
# streamable-http en vez de stdio cuando existe.
CMD ["python", "server.py"]
