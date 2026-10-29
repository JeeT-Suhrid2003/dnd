"""API Gateway: single entry point that routes to the other services."""
import asyncio
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

UPSTREAMS = {
    "dice": os.getenv("DICE_URL", "http://localhost:8001"),
    "characters": os.getenv("CHARACTER_URL", "http://localhost:8002"),
    "combat": os.getenv("COMBAT_URL", "http://localhost:8003"),
}
# Path prefix -> upstream key. "dice" and "combat" strip the prefix; characters keeps it.
STRIP_PREFIX = {"dice": True, "combat": True, "characters": False}

app = FastAPI(title="D&D API Gateway", version="0.1.0")
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
async def game():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/style.css", include_in_schema=False)
async def frontend_styles():
    return FileResponse(FRONTEND_DIR / "style.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
async def frontend_script():
    return FileResponse(FRONTEND_DIR / "app.js", media_type="text/javascript")


@app.get("/health")
async def health():
    async def check(name: str, base: str):
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                r = await c.get(f"{base}/health")
            return name, "ok" if r.status_code == 200 else f"http {r.status_code}"
        except httpx.RequestError:
            return name, "down"

    results = dict(await asyncio.gather(*(check(n, b) for n, b in UPSTREAMS.items())))
    return {"service": "gateway", "status": "ok", "upstreams": results}


@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.api_route("/{service}", methods=["GET", "POST"])
async def proxy(service: str, request: Request, path: str = ""):
    if service not in UPSTREAMS:
        return Response(
            content=f'{{"detail":"Unknown service {service!r}. Try: {", ".join(UPSTREAMS)}"}}',
            status_code=404, media_type="application/json",
        )
    target_path = f"/{path}" if STRIP_PREFIX[service] else f"/{service}" + (f"/{path}" if path else "")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            upstream = await client.request(
                request.method,
                f"{UPSTREAMS[service]}{target_path}",
                params=request.query_params,
                content=await request.body(),
                headers={"content-type": request.headers.get("content-type", "application/json")},
            )
    except httpx.RequestError:
        return Response(
            content=f'{{"detail":"{service} service is unavailable"}}',
            status_code=502, media_type="application/json",
        )
    return Response(
        content=upstream.content, status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
