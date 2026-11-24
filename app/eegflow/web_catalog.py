"""Página de registros: catálogo, ficha del registro elegido y lanzamiento de trabajos."""

import httpx
import streamlit as st

from eegflow import web_signal, webview
from eegflow.web_api import request, selected_row, show_api_error

CATALOG_COLUMNS = {
    "frecuencia (Hz)": st.column_config.NumberColumn(format="%g"),
    "duración (min)": st.column_config.NumberColumn(format="%.1f"),
    "digest de entrada": st.column_config.TextColumn(help="Primeros caracteres del SHA-256"),
}


def render() -> None:
    st.title("Registros")
    recordings = request("GET", "/api/v1/recordings", params={"limit": 100})["items"]
    if not recordings:
        st.info(
            "Todavía no hay registros. Incorporá un dataset con la CLI de ingesta, por ejemplo "
            "`cli ingest data/incoming/respect/manifest-….json`."
        )
        return
    valid = sum(r["validation_status"] == "valid" for r in recordings)
    st.caption(f"{len(recordings)} registros · {valid} válidos. Elegí una fila para ver su ficha.")
    event = st.dataframe(
        webview.catalog_rows(recordings),
        hide_index=True,
        key="catalog",
        on_select="rerun",
        selection_mode="single-row",
        column_config=CATALOG_COLUMNS,
    )
    render_recording(recordings[selected_row(event, len(recordings))])


def render_recording(recording: dict) -> None:
    detail = request("GET", f"/api/v1/recordings/{recording['id']}")
    metadata = detail["metadata"]
    with st.container(border=True):
        validation = (
            ":green-badge[:material/check: válido]"
            if detail["validation_status"] == "valid"
            else ":red-badge[:material/close: inválido]"
        )
        st.subheader(webview.recording_label(detail))
        st.markdown(f"{validation} &nbsp; `{detail['id']}`")
        for error in detail["validation_errors"]:
            st.warning(f"Validación: {error}")
        if metadata:
            columns = st.columns(4)
            columns[0].metric("Frecuencia", f"{metadata['sampling_hz']:g} Hz", border=True)
            columns[1].metric("Duración", f"{metadata['duration_s'] / 60:.1f} min", border=True)
            columns[2].metric(
                "Canales útiles",
                f"{metadata['usable_channel_count']} / {metadata['channel_count']}",
                border=True,
            )
            columns[3].metric("Eventos anotados", len(metadata["events"]), border=True)
            counts = webview.event_counts(metadata)
            if counts:
                st.caption(
                    "Eventos por tipo: "
                    + ", ".join(f"{k} ({v})" for k, v in sorted(counts.items()))
                )
        if detail["validation_status"] == "valid":
            render_new_run_form(detail)
        else:
            st.caption("Un registro inválido no admite trabajos.")
        if st.button(
            "Ver sus trabajos", icon=":material/filter_list:", type="tertiary", key="its-runs"
        ):
            # Llega a la página de trabajos con el filtro de registro ya puesto.
            st.session_state["filter-recording"] = detail["id"]
            st.switch_page("paginas/trabajos.py")
    web_signal.render(detail, request)
    with st.expander(":material/verified: Integridad de los archivos (SHA-256)"):
        st.markdown(f"**Digest de entrada:** `{detail['input_digest']}`")
        st.dataframe(webview.file_rows(detail["files"]), hide_index=True, key="recording-files")


def render_new_run_form(detail: dict) -> None:
    options = [c["id"] for c in request("GET", "/api/v1/configurations")["items"]]
    with st.form(f"new-run-{detail['id']}", border=False):
        config, submit = st.columns([3, 1], vertical_alignment="bottom")
        chosen = config.selectbox("Configuración del procesamiento", options, key="run-config")
        submitted = submit.form_submit_button(
            "Iniciar procesamiento", type="primary", icon=":material/play_arrow:", width="stretch"
        )
    if submitted:
        try:
            created = request(
                "POST", "/api/v1/runs", json={"recording_id": detail["id"], "config_id": chosen}
            )
        except httpx.HTTPStatusError as error:
            show_api_error(error)
            return
        # La página de trabajos abre directamente el que se acaba de crear.
        st.session_state["run-focus"] = created["id"]
        st.success("Trabajo creado. Se procesa en segundo plano.")
        st.page_link(
            "paginas/trabajos.py", label="Seguirlo en Trabajos", icon=":material/arrow_forward:"
        )
