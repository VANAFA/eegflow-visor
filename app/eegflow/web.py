"""Webapp Streamlit: registros, trabajos con sus resultados y modelos, en páginas separadas.

Es un cliente HTTP de la API: la clave queda del lado servidor y nunca accede a la base ni a
los archivos (ADR-0006). Cada página pide a la API sólo lo que muestra.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import streamlit as st

from eegflow import webview
from eegflow.web_api import request

ASSETS = Path(__file__).parent / "assets"
PAGES = [
    st.Page("paginas/registros.py", title="Registros", icon=":material/database:", default=True),
    st.Page("paginas/trabajos.py", title="Trabajos", icon=":material/play_circle:"),
    st.Page("paginas/modelos.py", title="Modelos", icon=":material/model_training:"),
    st.Page("paginas/visor.py", title="Visor 3D", icon=":material/view_in_ar:"),
]


@st.fragment(run_every="30s")
def render_status() -> None:
    try:
        workers = request("GET", "/api/v1/status")["workers"]
    except (httpx.HTTPError, KeyError, ValueError):
        st.markdown(":red-badge[:material/cloud_off: Sin conexión]")
        st.caption("No se pudo consultar la API.")
        return
    if any(worker["healthy"] for worker in workers):
        st.markdown(":green-badge[:material/check_circle: En línea]")
        st.caption("API, base de datos y worker conectados")
    else:
        st.markdown(":orange-badge[:material/warning: Worker inactivo]")
        st.caption("API disponible; no hay un worker con actividad reciente")


def render_sidebar() -> None:
    st.logo(ASSETS / "logo.svg", size="large", icon_image=ASSETS / "icon.svg")
    with st.sidebar:
        st.caption("Catálogo y procesamiento reproducible de EEG e iEEG")
        st.markdown(":blue-badge[:material/inventory_2: Demo estática]")
        st.caption("Datos congelados de un stack local con registros de RESPect (CC0). Para procesar, corré EEGFlow localmente.")
        if st.button("Actualizar", icon=":material/refresh:", type="tertiary", key="refresh"):
            st.rerun()
        st.caption(
            ":material/info: Uso experimental. No destinado a diagnóstico ni decisiones clínicas."
        )


def main() -> None:
    st.set_page_config(page_title="EEGFlow", page_icon="🧠", layout="wide")
    navigation = st.navigation(PAGES)
    render_sidebar()
    try:
        navigation.run()
    except httpx.HTTPStatusError as error:
        st.error(f"{webview.api_error_text(error)}. Revisá el estado.")
    except (httpx.HTTPError, KeyError, ValueError):
        st.error(
            "No se pudo consultar la API. Actualizá el listado antes de volver a enviar un trabajo."
        )


main()
