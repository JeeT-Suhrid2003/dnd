from python:3.11-slim
workdir /app
run pip install uvicorn httpx fastapi
copy . .
expose 8002
cmd ["python", "-m", "uvicorn", "main:app", "--app-dir", "services/character", "--host", "0.0.0.0", "--port", "8002"]