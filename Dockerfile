FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY api.py .

RUN mkdir -p /downloads /manga /config /logs

CMD ["python", "/app/api.py"]
