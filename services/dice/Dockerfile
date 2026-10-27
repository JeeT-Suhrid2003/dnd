from python:3.11-slim
workdir /app

run pip install uvicorn httpx2 fastapi
copy . .
cmd ["python", "-m", "uvicorn", "main:app", "--app-dir", "services/dice", "--port", "8001"]