FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY dashboard.html .

# Render inyecta PORT automáticamente; server.py lo detecta y corre por
# streamable-http en vez de stdio cuando existe. El mismo proceso también
# sirve el panel web ("GTM Fixer") en "/" y sus endpoints en "/api/*".
CMD ["python", "server.py"]
