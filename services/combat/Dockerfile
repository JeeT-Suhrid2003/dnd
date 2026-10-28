from python:3.11-slim
workdir /app
run pip install uvicorn httpx fastapi
copy . .
env DICE_URL=http://dice:8001
env CHARACTER_URL=http://character:8002
expose 8003
cmd ["python", "-m", "uvicorn", "main:app", "--app-dir", "services/combat", "--host", "0.0.0.0", "--port", "8003"]