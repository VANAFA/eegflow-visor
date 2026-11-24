"""Cliente HTTP de la webapp y piezas de interfaz que comparten sus páginas.

La clave queda del lado servidor y la web nunca accede a la base ni a los archivos (ADR-0006).
"""

import os

import httpx
import streamlit as st

from eegflow import webview

PAGE_SIZE = 100


def _client(timeout: float) -> httpx.Client:
    return httpx.Client(
        base_url=os.environ["EEGFLOW_API_URL"],
        timeout=timeout,
        headers={"X-API-Key": os.environ["EEGFLOW_API_KEY"]},
    )


def request(method: str, path: str, timeout: float = 10, **kwargs):
    with _client(timeout) as client:
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()


def request_text(method: str, path: str, **kwargs) -> str:
    """Como `request`, para respuestas que no son JSON (el CSV)."""
    with _client(60) as client:
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.text


def pager(total: int, key: str, size: int = PAGE_SIZE) -> int:
    """Offset elegido; el control aparece sólo si hay más de una página."""
    pages = max(1, -(-total // size))
    if pages == 1:
        return 0
    page = st.number_input(f"Página (de {pages})", min_value=1, max_value=pages, step=1, key=key)
    return (int(page) - 1) * size


def selected_row(event, count: int, fallback: int = 0) -> int:
    """Fila elegida en una tabla con selección; sin elección, la de `fallback`."""
    rows = event.selection.rows if event else []
    return rows[0] if rows and rows[0] < count else min(fallback, count - 1)


def show_api_error(error: httpx.HTTPStatusError) -> None:
    st.error(webview.api_error_text(error))


# Demo estática: las consultas salen del snapshot.
from eegflow.demo_api import request, request_text  # noqa: E402, F811
