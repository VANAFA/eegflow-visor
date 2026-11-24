"""Congela las respuestas de la API de EEGFlow que usa la web, para la demo estática.

Corre dentro del contenedor web de un stack levantado (tiene la URL y la clave de la API):
    docker exec -i eegflow-video-web-1 python - < tools/snapshot.py > app/snapshot.json
Los listados se guardan completos; la demo los pagina y filtra como la API.
"""

import json
import os
import sys

import httpx

SIGNAL_CHANNELS = 16  # Tramo 0-10 s de los primeros 16 canales de cada registro.

api = httpx.Client(
    base_url=os.environ["EEGFLOW_API_URL"],
    headers={"X-API-Key": os.environ["EEGFLOW_API_KEY"]},
    timeout=180,
)
snapshot = {}


def get(path, **params):
    response = api.get(path, params=params)
    response.raise_for_status()
    return response.json()


def every(path, limit, **params):
    """Todas las páginas de un listado, en una sola respuesta."""
    first = get(path, limit=limit, offset=0, **params)
    items = list(first["items"])
    while len(items) < first["total"]:
        items += get(path, limit=limit, offset=len(items), **params)["items"]
    first["items"] = items
    return first


def keep(path, value):
    snapshot[f"GET {path}"] = value
    print(path, file=sys.stderr)


keep("/api/v1/status", get("/api/v1/status"))
keep("/api/v1/configurations", get("/api/v1/configurations"))
keep("/api/v1/models", every("/api/v1/models", 100))
try:
    keep("/api/v1/models/active", get("/api/v1/models/active"))
except httpx.HTTPStatusError:
    pass

recordings = every("/api/v1/recordings", 100)
keep("/api/v1/recordings", recordings)
for recording in recordings["items"]:
    path = f"/api/v1/recordings/{recording['id']}"
    detail = get(path)
    keep(path, detail)
    if detail["validation_status"] != "valid":
        continue
    signal = {}
    for channel in detail["metadata"]["channel_names"][:SIGNAL_CHANNELS]:
        signal[channel] = get(f"{path}/signal", start=0, duration=10, channels=[channel])
    keep(f"{path}/signal", signal)

runs = every("/api/v1/runs", 100)
keep("/api/v1/runs", runs)
done = [run["id"] for run in runs["items"] if run["status"] == "succeeded"]
for run in runs["items"]:
    path = f"/api/v1/runs/{run['id']}"
    keep(path, get(path))
    if run["id"] not in done:
        continue
    keep(f"{path}/features", every(f"{path}/features", 1000))
    keep(f"{path}/provenance", get(f"{path}/provenance"))
    csv = api.get(f"{path}/export.csv")
    csv.raise_for_status()
    keep(f"{path}/export.csv", csv.text)
    inferences = every(f"{path}/inferences", 100)
    keep(f"{path}/inferences", inferences)
    for inference in inferences["items"]:
        inference_path = f"/api/v1/inferences/{inference['id']}"
        keep(inference_path, every(inference_path, 1000))
    for other in done:
        if other == run["id"]:
            continue
        response = api.get(f"{path}/comparison/{other}")
        keep(
            f"{path}/comparison/{other}",
            response.json()
            if response.is_success
            else {"error": response.status_code, "body": response.json()},
        )

json.dump(snapshot, sys.stdout, separators=(",", ":"))
