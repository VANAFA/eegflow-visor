"""API de EEGFlow congelada para la demo estática: responde desde app/snapshot.json.

Reemplaza a `request` y `request_text` de web_api. Pagina y filtra como la API; lo que
escribiría (procesar, repetir, inferir) responde con un aviso, como un rechazo de la API.
"""

import json
from pathlib import Path

import httpx

SNAPSHOT = json.loads((Path(__file__).parent / "snapshot.json").read_text())
DEMO = "Demo estática con datos congelados: para procesar, corré EEGFlow localmente"


def fail(method: str, path: str, status: int, message: str):
    request = httpx.Request(method, f"https://demo.eegflow{path}")
    response = httpx.Response(status, json={"error": {"message": message}}, request=request)
    raise httpx.HTTPStatusError(message, request=request, response=response)


def page(listing: dict, items: list, params: dict) -> dict:
    limit = int(params.get("limit", 100))
    offset = int(params.get("offset", 0))
    return listing | {
        "items": items[offset : offset + limit],
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }


def runs(listing: dict, params: dict) -> list:
    items = listing["items"]
    if params.get("recording_id"):
        items = [r for r in items if r["recording_id"] == params["recording_id"]]
    if params.get("status"):
        items = [r for r in items if r["status"] == params["status"]]
    if params.get("created_from"):
        items = [r for r in items if r["created_at"][:10] >= params["created_from"]]
    if params.get("created_to"):
        items = [r for r in items if r["created_at"][:10] < params["created_to"]]
    return items


def signal(path: str, stored: dict, params: dict) -> dict:
    channels = params.get("channels") or []
    if float(params.get("start", 0)) != 0 or float(params.get("duration", 10)) != 10:
        fail("GET", path, 404, f"{DEMO}. Está disponible el tramo de 0 a 10 s")
    missing = [c for c in channels if c not in stored]
    if missing:
        fail("GET", path, 404, f"{DEMO}. Canales sin tramo guardado: {', '.join(missing)}")
    parts = [stored[c] for c in channels]
    return parts[0] | {
        "items": [item for part in parts for item in part["items"]],
        "bad_channels": sorted({c for part in parts for c in part["bad_channels"]}),
    }


def request(method: str, path: str, timeout: float = 10, **kwargs):
    params = kwargs.get("params") or {}
    if method != "GET":
        fail(method, path, 403, DEMO)
    stored = SNAPSHOT.get(f"GET {path}")
    if stored is None:
        fail(method, path, 404, f"{DEMO}. Esta consulta no está en el snapshot")
    if path.endswith("/signal"):
        return signal(path, stored, params)
    if isinstance(stored, dict) and "error" in stored and "body" in stored:
        request = httpx.Request(method, f"https://demo.eegflow{path}")
        response = httpx.Response(stored["error"], json=stored["body"], request=request)
        raise httpx.HTTPStatusError("API", request=request, response=response)
    if isinstance(stored, dict) and isinstance(stored.get("items"), list) and "total" in stored:
        items = runs(stored, params) if path == "/api/v1/runs" else stored["items"]
        return page(stored, items, params)
    return stored


def request_text(method: str, path: str, **kwargs) -> str:
    return request(method, path, **kwargs)
