FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx

COPY services/gateway ./services/gateway
COPY frontend ./frontend

ENV DICE_URL=http://dice:8001 \
    CHARACTER_URL=http://character:8002 \
    COMBAT_URL=http://combat:8003

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--app-dir", "services/gateway", "--host", "0.0.0.0", "--port", "8000"]
