"""Vistas de modelos e inferencias: sólo consultan la API autenticada."""

import httpx
import streamlit as st

from eegflow import webview
from eegflow.web_api import PAGE_SIZE, pager
from eegflow.web_api import request as api_request


def active_model(request):
    try:
        return request("GET", "/api/v1/models/active")
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 409:
            return None
        raise


def render_model(model, request, key):
    st.warning(model["warning"])
    st.caption(f"Versión: {model['id']} · creada: {webview.utc_text(model['created_at'])}")
    metrics = model["metrics"]
    columns = st.columns(3)
    for column, name, label in zip(
        columns,
        ["balanced_accuracy", "roc_auc", "average_precision"],
        ["Exactitud balanceada", "ROC-AUC", "Average precision"],
        strict=True,
    ):
        value = metrics.get(name)
        column.metric(label, f"{value:.3f}" if value is not None else "—", border=True)
    st.caption(metrics.get("limitation", "Evaluación demostrativa, sin validez clínica."))
    st.dataframe(
        [{"clase": name, **values} for name, values in metrics.get("per_class", {}).items()],
        hide_index=True,
        key=f"{key}-metrics",
    )
    st.caption(
        f"Ventanas evaluadas: {metrics.get('included_windows', '—')} · "
        f"Excluidas: {metrics.get('excluded_windows', '—')} · "
        f"Umbral preictal: {metrics.get('threshold', '—')}"
    )
    with st.expander("Datos, configuración y código del modelo"):
        st.markdown(f"**SHA-256 del modelo:** `{model['sha256']}`")
        st.json(model["training_config"], expanded=False)
        provenance = model["provenance"]
        st.caption(f"Commit de entrenamiento: {provenance.get('code_commit', '—')}")
        sources = provenance.get("sources", [])
        st.dataframe(
            [
                {
                    "sujeto": s["subject"],
                    "registro": s["recording_id"],
                    "corrida": s["run_id"],
                    "SHA-256 features": s["feature_sha256"],
                }
                for s in sources
            ],
            hide_index=True,
            key=f"{key}-sources",
        )
        if sources:
            source_ids = [s["run_id"] for s in sources]
            chosen = st.selectbox("Corrida fuente del modelo", source_ids, key=f"{key}-source")
            if st.button("Ver procedencia de esta corrida", key=f"{key}-lineage"):
                lineage = request("GET", f"/api/v1/runs/{chosen}/provenance")
                for section, values in webview.provenance_summary(lineage).items():
                    st.markdown(f"**{section}**")
                    st.dataframe(
                        [{"campo": k, "valor": str(v)} for k, v in values.items()],
                        hide_index=True,
                        key=f"{key}-{section}",
                    )
        st.json(provenance, expanded=False)


def render_models(request=api_request):
    st.title("Modelos")
    first = request("GET", "/api/v1/models", params={"limit": PAGE_SIZE, "offset": 0})
    if not first["items"]:
        st.info("Todavía no hay modelos publicados. El entrenamiento se realiza desde la CLI.")
        return
    active = active_model(request)
    st.caption(
        f"{first['total']} versiones publicadas · "
        + (f"activa: {active['id']}" if active else "todavía no hay una versión activa")
    )
    offset = pager(first["total"], "models-page")
    page = (
        first
        if offset == 0
        else request("GET", "/api/v1/models", params={"limit": PAGE_SIZE, "offset": offset})
    )
    by_id = {m["id"]: m for m in page["items"]}
    active_id = active["id"] if active else None
    # Arranca en la versión activa si está en esta página, y la marca en la lista.
    chosen = st.selectbox(
        "Versión del modelo",
        list(by_id),
        index=list(by_id).index(active_id) if active_id in by_id else 0,
        format_func=lambda key: f"{key} · activa" if key == active_id else key,
        key="model-detail",
    )
    with st.container(border=True):
        if chosen == active_id:
            st.markdown(":green-badge[:material/star: versión activa]")
        render_model(by_id[chosen], request, "catalog-model")


def render_inferences(run_id, request=api_request):
    active = active_model(request)
    selection_key = f"inference-selected-{run_id}"
    history_key = f"history-page-{run_id}"
    action, note = st.columns([1, 3], vertical_alignment="center")
    if action.button(
        "Calcular inferencia",
        key=f"infer-{run_id}",
        disabled=active is None,
        type="primary",
        icon=":material/psychology:",
        width="stretch",
    ):
        try:
            created = request("POST", f"/api/v1/runs/{run_id}/inferences")
        except httpx.HTTPStatusError as error:
            st.error(webview.api_error_text(error))
        else:
            st.session_state[selection_key] = created["id"]
            st.session_state[history_key] = 1
            st.success("Inferencia disponible; se conserva la versión usada.")
    note.caption(
        f"Con la versión activa: {active['id']}"
        if active
        else "No hay modelo activo. Se puede consultar el historial existente."
    )
    params = {"limit": PAGE_SIZE, "offset": 0}
    history = request("GET", f"/api/v1/runs/{run_id}/inferences", params=params)
    # El botón vuelve a la página 1 por estado de sesión: el widget no lleva value propio.
    offset = pager(history["total"], history_key)
    if offset:
        params["offset"] = offset
        history = request("GET", f"/api/v1/runs/{run_id}/inferences", params=params)
    if not history["items"]:
        st.info("Esta corrida todavía no tiene inferencias guardadas.")
        return
    options = {b["id"]: b for b in history["items"]}
    if st.session_state.get(selection_key) not in options:
        st.session_state[selection_key] = next(iter(options))
    chosen = st.selectbox(
        "Inferencia guardada",
        list(options),
        key=selection_key,
        format_func=lambda key: (
            f"{webview.utc_text(options[key]['created_at'])} · modelo {options[key]['model_id']}"
        ),
    )
    params = {"limit": PAGE_SIZE, "offset": 0}
    page = request("GET", f"/api/v1/inferences/{chosen}", params=params)
    offset = pager(page["total"], f"inference-page-{chosen}")
    if offset:
        params["offset"] = offset
        page = request("GET", f"/api/v1/inferences/{chosen}", params=params)
    st.warning(page["warning"])
    st.caption(f"{page['total']} ventanas · modelo utilizado: {page['inference']['model_id']}")
    # CE07: las métricas de la versión, siempre a la vista junto a la salida.
    metrics = page["model"]["metrics"]
    counts = page.get("class_counts") or {}
    columns = st.columns(3)
    columns[0].metric("Preictal", counts.get("preictal", "—"), border=True)
    columns[1].metric("Interictal", counts.get("interictal", "—"), border=True)
    columns[2].metric("Sin clase", counts.get("excluded", "—"), border=True)
    st.caption(
        "Métricas de esta versión en el sujeto reservado: exactitud balanceada "
        f"{metrics.get('balanced_accuracy', float('nan')):.3f} · ROC-AUC "
        f"{metrics.get('roc_auc', float('nan')):.3f}."
    )
    st.dataframe(
        [
            {
                "ventana": w["window_index"],
                "inicio (s)": w["start_s"],
                "fin (s)": w["end_s"],
                "clase predicha": w["predicted_class"],
                "probabilidad preictal": w["probability_preictal"],
                "excluida": w["excluded"],
                "motivo": webview.reasons_text(w["exclusion_reasons"]),
            }
            for w in page["items"]
        ],
        hide_index=True,
        key=f"inference-table-{run_id}",
        column_config={
            "probabilidad preictal": st.column_config.ProgressColumn(
                min_value=0.0, max_value=1.0, format="%.2f"
            )
        },
    )
    with st.expander("Modelo y trazabilidad de esta inferencia"):
        st.json(page["inference"], expanded=False)
        render_model(page["model"], request, f"inference-model-{run_id}")
