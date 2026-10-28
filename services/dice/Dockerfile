from python:3.11-slim
workdir /app

run pip install uvicorn httpx fastapi

copy . .
expose 8001
cmd ["python", "-m", "uvicorn", "main:app", "--app-dir", "services/dice", "--host", "0.0.0.0", "--port", "8001"]