"""Visor de señal original mediante API; carga únicamente por solicitud explícita."""

import httpx
import pandas as pd
import streamlit as st

from eegflow import webview


def render(detail, request):
    if detail["validation_status"] != "valid":
        return
    metadata = detail["metadata"]
    with st.expander(":material/ssid_chart: Señal original multicanal"):
        st.caption(
            "Señal original en µV, sin filtros. Hasta 16 canales y 60 segundos por consulta."
        )
        with st.form(f"signal-{detail['id']}"):
            channels = st.multiselect(
                "Canales",
                metadata["channel_names"],
                default=metadata["channel_names"][:4],
                max_selections=16,
            )
            extra = st.text_input(
                "Otros canales (nombres separados por coma)",
                help="Incluye canales excluidos del procesamiento y marcados bad.",
            )
            left, right = st.columns(2)
            start = left.number_input("Inicio (s)", min_value=0.0, value=0.0)
            duration = right.number_input(
                "Duración (s)",
                min_value=0.01,
                max_value=60.0,
                value=min(10.0, metadata["duration_s"]),
            )
            submitted = st.form_submit_button("Mostrar señal", icon=":material/visibility:")
        if submitted:
            channels = list(
                dict.fromkeys(channels + [c.strip() for c in extra.split(",") if c.strip()])
            )
            if not channels or len(channels) > 16 or start + duration > metadata["duration_s"]:
                st.warning("Seleccioná canales y un intervalo dentro del registro.")
                return
            try:
                data = request(
                    "GET",
                    f"/api/v1/recordings/{detail['id']}/signal",
                    timeout=120,
                    params={"start": start, "duration": duration, "channels": channels},
                )
            except httpx.HTTPStatusError as error:
                # Un canal mal escrito no tiene que ocultar el resto del catálogo.
                st.error(webview.api_error_text(error))
                return
            st.caption(
                f"Envolvente mínimo/máximo de {data['aggregation_samples']} muestras. "
                "Los intervalos con valores no finitos se muestran vacíos."
            )
            if data["bad_channels"]:
                st.warning("Canales pedidos marcados bad: " + ", ".join(data["bad_channels"]))
            st.vega_lite_chart(
                # Un dict {"values": ...} llega como una sola columna y el gráfico sale vacío.
                pd.DataFrame(data["items"]),
                {
                    # El navegador no redibuja si sólo cambian los datos y la especificación es la
                    # misma: título y descripción cambian con el tramo, el registro y los canales.
                    "title": f"Tramo de {start:g} s a {start + duration:g} s",
                    "description": f"{detail['id']}: {', '.join(channels)}",
                    "facet": {"row": {"field": "channel", "type": "nominal", "title": "Canal"}},
                    # Cada canal con su escala: con una sola, los de baja amplitud se ven planos.
                    "resolve": {"scale": {"y": "independent"}},
                    "spec": {
                        "mark": {"type": "rule", "color": webview.SERIES_COLOR},
                        "width": 650,
                        "height": 60,
                        "encoding": {
                            "x": {
                                "field": "start_s",
                                "type": "quantitative",
                                "title": "Tiempo (s)",
                                "scale": {"zero": False},
                            },
                            "y": {
                                "field": "min_uv",
                                "type": "quantitative",
                                "title": "µV",
                                "scale": {"zero": False},
                            },
                            "y2": {"field": "max_uv"},
                        },
                    },
                },
            )
            if data["events"]:
                st.dataframe(data["events"], hide_index=True)
            st.caption("Digest de entrada: " + data["input_digest"])
