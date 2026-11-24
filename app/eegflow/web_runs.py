"""Página de trabajos: listado filtrable y ficha del trabajo con resultados, inferencias,
comparación y procedencia."""

from datetime import timedelta

import httpx
import pandas as pd
import streamlit as st

from eegflow import web_ml, webview
from eegflow.web_api import pager, request, request_text, selected_row, show_api_error

RESULTS_PAGE_SIZE = 100
CHART_PAGE_SIZE = 1000  # Máximo permitido por la API.
CHART_MAX_PAGES = 20
ACTIVE = ("pending", "running")


def run_filters(recordings: list[dict]) -> dict:
    """RF13: registro, estado y fechas, combinables; vacío no filtra."""
    columns = st.columns(4)
    names = {"": "Todos los registros"} | {r["id"]: webview.recording_label(r) for r in recordings}
    recording = columns[0].selectbox(
        "Registro", list(names), format_func=names.get, key="filter-recording"
    )
    states = {"": "Todos los estados"} | webview.STATUS_LABELS
    status = columns[1].selectbox(
        "Estado", list(states), format_func=states.get, key="filter-status"
    )
    since = columns[2].date_input("Creados desde", value=None, key="filter-from")
    until = columns[3].date_input("Creados hasta", value=None, key="filter-to")
    params = {"limit": 100}
    if recording:
        params["recording_id"] = recording
    if status:
        params["status"] = status
    if since:
        params["created_from"] = since.isoformat()
    if until:
        params["created_to"] = (until + timedelta(days=1)).isoformat()
    return params


def render() -> None:
    st.title("Trabajos")
    recordings = request("GET", "/api/v1/recordings", params={"limit": 100})["items"]
    params = run_filters(recordings)
    if {"created_from", "created_to"} <= params.keys() and (
        params["created_from"] >= params["created_to"]
    ):
        st.warning("La fecha inicial tiene que ser anterior a la final.")
        return
    runs = request("GET", "/api/v1/runs", params=params)["items"]
    if not runs:
        st.info(
            "Ningún trabajo cumple los filtros."
            if len(params) > 1
            else "Todavía no hay trabajos. Se inician desde la ficha de un registro."
        )
        return
    rows = webview.run_rows(runs, {r["id"]: r for r in recordings})
    ids = [run["id"] for run in runs]
    focus = st.session_state.get("run-focus")
    event = st.dataframe(
        rows,
        hide_index=True,
        key="runs",
        column_order=list(rows[0])[:-1],
        on_select="rerun",
        selection_mode="single-row",
    )
    labels = {
        row["id"]: f"{row['estado']} · {row['registro']} · {row['creado (UTC)']} · {row['id']}"
        for row in rows
    }
    chosen = ids[selected_row(event, len(ids), ids.index(focus) if focus in ids else 0)]
    names = {r["id"]: webview.recording_label(r) for r in recordings}
    render_run(chosen, runs, labels, names)


def render_run(run_id: str, runs: list[dict], labels: dict, names: dict) -> None:
    detail = request("GET", f"/api/v1/runs/{run_id}")
    with st.container(border=True):
        name = names.get(detail["recording_id"], detail["recording_id"])
        st.subheader(f"{name} · {detail['config_id']}")
        duration = webview.elapsed_s(detail["started_at"], detail["finished_at"])
        st.markdown(
            f"{webview.status_badge(detail['status'])} &nbsp; `{run_id}` &nbsp; "
            f"creado {webview.utc_text(detail['created_at'])}"
            + (f" · {duration:g} s" if duration is not None else "")
        )
        if detail.get("repeated_from"):
            model = detail.get("model_id") or "sin modelo"
            st.caption(
                f"Repetición de la corrida {detail['repeated_from']} · modelo conservado: {model}"
            )
        if detail["status"] in ACTIVE:
            render_progress(run_id, detail["status"])
            return
        st.markdown(webview.stage_line(detail["stages"]))
        if detail["status"] == "failed":
            st.error(f"{detail['error_code']}: {detail['error_message']}")
        render_actions(run_id, detail["status"])
    if detail["status"] == "succeeded":
        results, inferences, compare, provenance = st.tabs(
            [
                ":material/show_chart: Resultados",
                ":material/psychology: Inferencias",
                ":material/compare_arrows: Comparar",
                ":material/account_tree: Procedencia",
            ]
        )
        with results:
            render_results(run_id)
        with inferences:
            web_ml.render_inferences(run_id, request)
        with compare:
            render_compare(run_id, runs, labels)
        with provenance:
            render_provenance(run_id)


@st.fragment(run_every="3s")
def render_progress(run_id: str, status: str) -> None:
    """Sigue al trabajo sin recargar la página; al cambiar de estado, la redibuja entera."""
    detail = request("GET", f"/api/v1/runs/{run_id}")
    if detail["status"] != status:
        st.rerun()
    st.markdown(
        webview.stage_line(detail["stages"])
        if detail["stages"]
        else "Esperando a que un worker tome el trabajo…"
    )
    st.caption(":material/autorenew: Se actualiza solo hasta que el trabajo termine.")


def render_actions(run_id: str, status: str) -> None:
    repeat, csv, _ = st.columns([1, 1, 3])
    if repeat.button(
        "Repetir corrida",
        key=f"repeat-{run_id}",
        icon=":material/replay:",
        help="Conserva los parámetros guardados y usa el código instalado actualmente.",
        width="stretch",
    ):
        try:
            created = request("POST", f"/api/v1/runs/{run_id}/repeat")
        except httpx.HTTPStatusError as error:
            show_api_error(error)
        else:
            st.success(f"Nueva corrida: {created['id']}. Original: {run_id}.")
    if status == "succeeded":
        render_csv(run_id, csv)


def render_csv(run_id: str, column) -> None:
    """RF11: se pide explícitamente, porque recorre todas las ventanas."""
    key = f"csv-text-{run_id}"
    if key not in st.session_state:
        if column.button(
            "Preparar CSV", key=f"csv-{run_id}", icon=":material/table_view:", width="stretch"
        ):
            try:
                st.session_state[key] = request_text("GET", f"/api/v1/runs/{run_id}/export.csv")
            except httpx.HTTPStatusError as error:
                show_api_error(error)
                return
            st.rerun()
        return
    column.download_button(
        "Descargar CSV",
        st.session_state[key],
        file_name=f"run-{run_id}.csv",
        mime="text/csv",
        key=f"download-{run_id}",
        icon=":material/download:",
        type="primary",
        width="stretch",
    )


def fetch_all_windows(run_id: str) -> tuple[list[dict], int, dict]:
    windows, total, offset = [], None, 0
    for _ in range(CHART_MAX_PAGES):
        page = request(
            "GET",
            f"/api/v1/runs/{run_id}/features",
            params={"limit": CHART_PAGE_SIZE, "offset": offset},
        )
        windows.extend(page["items"])
        total = page["total"]
        offset += CHART_PAGE_SIZE
        if offset >= total:
            break
    return windows, total, page.get("metadata", {})


def render_results(run_id: str) -> None:
    windows, total, metadata = fetch_all_windows(run_id)
    excluded = metadata.get("excluded_count", sum(w["excluded"] for w in windows))
    columns = st.columns(3)
    columns[0].metric("Ventanas de 10 s", total, border=True)
    columns[1].metric("Excluidas", excluded, border=True)
    columns[2].metric("Incluidas", total - excluded, border=True)
    available = [
        name
        for name in webview.FEATURE_LABELS
        if name in metadata.get("feature_names", [])
        or any(w.get(name) is not None for w in windows)
    ] or ["line_length_uv"]
    feature = st.selectbox(
        "Feature a graficar",
        available,
        format_func=webview.FEATURE_LABELS.get,
        key=f"feature-{run_id}",
    )
    st.markdown(f"**{webview.FEATURE_LABELS[feature]} por ventana** (media entre canales)")
    if len(windows) < total:
        st.info(
            f"El gráfico muestra las primeras {len(windows)} de {total} ventanas. "
            "La tabla permite consultar todas las páginas."
        )
    st.vega_lite_chart(
        pd.DataFrame(webview.chart_rows(windows, feature)),
        webview.feature_chart_spec(feature),
        width="stretch",
        key="features-chart",
    )
    st.caption(
        "Franjas grises: ventanas excluidas; el motivo de cada una está en la tabla. "
        "Se conservan para inspección; una feature alta no es una predicción de crisis."
    )
    st.markdown("**Ventanas**")
    start = pager(total, f"results-page-{run_id}", RESULTS_PAGE_SIZE)
    if start + RESULTS_PAGE_SIZE <= len(windows) or len(windows) == total:
        items = windows[start : start + RESULTS_PAGE_SIZE]
    else:
        items = request(
            "GET",
            f"/api/v1/runs/{run_id}/features",
            params={"limit": RESULTS_PAGE_SIZE, "offset": start},
        )["items"]
    st.caption(webview.page_range_text(start, len(items), total))
    st.dataframe(webview.window_rows(items, available), hide_index=True, key="results-table")


def render_compare(run_id: str, runs: list[dict], labels: dict) -> None:
    others = [r["id"] for r in runs if r["id"] != run_id and r["status"] == "succeeded"]
    if not others:
        st.info("No hay otra corrida exitosa en el listado para comparar.")
        return
    with st.form(f"compare-{run_id}", border=False):
        other = st.selectbox("Comparar con otra corrida", others, format_func=labels.get)
        compare = st.form_submit_button("Comparar resultados", icon=":material/compare_arrows:")
    if compare:
        try:
            result = request("GET", f"/api/v1/runs/{run_id}/comparison/{other}", timeout=120)
        except httpx.HTTPStatusError as error:
            show_api_error(error)
        else:
            render_comparison(result)


def render_comparison(result: dict) -> None:
    if result["equal"]:
        st.success("Resultados iguales dentro de la tolerancia: misma configuración y clases.")
    elif not result["windows_compared"]:
        st.info(result["reason"])
    else:
        st.warning("Se encontraron diferencias entre los resultados.")
    st.dataframe(webview.comparison_rows(result), hide_index=True, key="comparison-summary")
    differences = result["configuration_differences"]
    if differences:
        st.caption("Diferencias de configuración")
        st.dataframe(differences, hide_index=True, key="comparison-config")
    else:
        st.caption("Misma configuración.")
    with st.expander("Detalle de la comparación"):
        st.json(result, expanded=False)


def render_provenance(run_id: str) -> None:
    provenance = request("GET", f"/api/v1/runs/{run_id}/provenance")
    st.caption("Del resultado a los archivos, la configuración y el código que lo produjeron.")
    sections = list(webview.provenance_summary(provenance).items())
    for start in range(0, len(sections), 2):
        for column, (section, fields) in zip(
            st.columns(2), sections[start : start + 2], strict=False
        ):
            with column.container(border=True):
                st.markdown(f"**{section}**")
                st.dataframe(
                    [{"campo": k, "valor": str(v)} for k, v in fields.items()],
                    hide_index=True,
                    key=f"provenance-{section}",
                )
    with st.expander("Parámetros de la configuración"):
        st.json(provenance["run"]["config_json"], expanded=False)
    with st.expander("Respuesta completa de la API"):
        st.json(provenance, expanded=False)
