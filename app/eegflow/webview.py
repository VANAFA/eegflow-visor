"""Transformaciones puras de respuestas de la API a filas y gráficos de la webapp.

No importa Streamlit ni hace I/O, así que se prueba sin levantar la interfaz.
"""

from collections import Counter
from datetime import datetime

STATUS_LABELS = {
    "pending": "⏳ pendiente",
    "running": "⚙️ en ejecución",
    "succeeded": "✅ exitoso",
    "failed": "❌ fallido",
}
VALIDATION_LABELS = {"valid": "✅ válido", "invalid": "❌ inválido"}
VERIFICATION_LABELS = {"matched": "✅ coincide", "mismatch": "❌ no coincide"}
# Badges de Markdown de Streamlit: el mismo color para un estado en toda la interfaz.
STATUS_BADGES = {
    "pending": ":gray-badge[:material/schedule: pendiente]",
    "running": ":orange-badge[:material/progress_activity: en ejecución]",
    "succeeded": ":green-badge[:material/check: exitoso]",
    "failed": ":red-badge[:material/close: fallido]",
}
REASON_LABELS = {
    "ANNOTATED_ARTIFACT": "artefacto anotado",
    "NONFINITE_CONTEXT": "señal no finita en el contexto",
    "UNDEFINED_SPECTRUM": "canal plano: espectro indefinido",
    "ICTAL": "crisis",
    "POSTICTAL": "después de la crisis",
    "PREICTAL_GUARD": "guarda previa al horizonte",
    "SAME_RECORD_INTERICTAL_DISABLED": "interictal del mismo registro desactivado",
    "PREICTAL_HORIZON": "dentro del horizonte preictal",
    "OUTSIDE_SEIZURE_INTERVALS": "fuera de los intervalos de crisis",
    "NO_SEIZURE_RECORD": "registro sin crisis",
    "NONFINITE_FEATURES": "features no finitas",
}
LABEL_TEXTS = {"preictal": "preictal", "interictal": "interictal", "excluded": "excluida"}
# Una ventana excluida no recibe clase: el resumen de inferencia la cuenta como "sin clase".
CLASS_TEXTS = {"preictal": "preictal", "interictal": "interictal", "excluded": "sin clase"}

FEATURE_LABELS = {
    "line_length_uv": "Longitud de línea (µV)",
    "variance_uv2": "Varianza (µV²)",
    "spectral_entropy": "Entropía espectral (0–1)",
    "relative_power_low": "Potencia relativa baja (0–1)",
    "relative_power_high": "Potencia relativa alta (0–1)",
    "line_length_z": "Longitud de línea normalizada (z)",
    "variance_z": "Varianza normalizada (z)",
}


# Serie 1 de la paleta categórica de referencia; franjas de exclusión en gris neutro.
SERIES_COLOR = "#2a78d6"
EXCLUDED_FILL = "#8a8985"


def short_hash(value: str | None, length: int = 12) -> str:
    return f"{value[:length]}…" if value else "—"


def human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size_bytes < 1000:
            return f"{size_bytes:.0f} {unit}" if unit == "B" else f"{size_bytes:.1f} {unit}"
        size_bytes /= 1000
    return f"{size_bytes:.2f} GB"


def recording_label(recording: dict) -> str:
    return f"{recording['subject']} · {recording['task']} · run {recording['run']}"


def _parse(timestamp: str | None) -> datetime | None:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else None


def elapsed_s(started: str | None, finished: str | None) -> float | None:
    start, end = _parse(started), _parse(finished)
    return round((end - start).total_seconds(), 2) if start and end else None


def catalog_rows(recordings: list[dict]) -> list[dict]:
    rows = []
    for record in recordings:
        metadata = record["metadata"] or {}
        duration = metadata.get("duration_s")
        rows.append(
            {
                "registro": recording_label(record),
                "validación": VALIDATION_LABELS.get(record["validation_status"]),
                "canales útiles": metadata.get("usable_channel_count"),
                "canales totales": metadata.get("channel_count"),
                "frecuencia (Hz)": metadata.get("sampling_hz"),
                "duración (min)": round(duration / 60, 1) if duration else None,
                "digest de entrada": short_hash(record["input_digest"]),
                "errores": ", ".join(record["validation_errors"]) or "—",
            }
        )
    return rows


def file_rows(files: list[dict]) -> list[dict]:
    return [
        {
            "rol": file["role"],
            "archivo": file["relative_key"].rsplit("/", 1)[-1],
            "tamaño": human_size(file["size_bytes"]),
            "SHA-256 observado": file["observed_sha256"],
            "verificación": VERIFICATION_LABELS.get(
                file["verification_status"], file["verification_status"]
            ),
        }
        for file in files
    ]


def event_counts(metadata: dict | None) -> dict[str, int]:
    return dict(Counter(event["trial_type"] for event in (metadata or {}).get("events", [])))


def run_rows(runs: list[dict], recordings_by_id: dict[str, dict]) -> list[dict]:
    rows = []
    for run in runs:
        recording = recordings_by_id.get(run["recording_id"])
        rows.append(
            {
                "estado": STATUS_LABELS.get(run["status"], run["status"]),
                "registro": recording_label(recording) if recording else run["recording_id"],
                "configuración": run["config_id"],
                "creado (UTC)": run["created_at"][:19].replace("T", " "),
                "duración (s)": elapsed_s(run["started_at"], run["finished_at"]),
                "error": run["error_code"] or "—",
                "id": run["id"],
            }
        )
    return rows


def status_badge(status: str) -> str:
    return STATUS_BADGES.get(status, f":gray-badge[{status}]")


STAGE_ICONS = {
    "pending": ":gray[:material/schedule:]",
    "running": ":orange[:material/progress_activity:]",
    "succeeded": ":green[:material/check_circle:]",
    "failed": ":red[:material/cancel:]",
}


def stage_line(stages: list[dict]) -> str:
    """Las etapas en orden, cada una con el ícono de su estado y su duración."""
    parts = []
    for stage in stages:
        seconds = (
            f" {stage['duration_ms'] / 1000:.2f} s" if stage["duration_ms"] is not None else ""
        )
        icon = STAGE_ICONS.get(stage["status"], stage["status"])
        error = f" :red[{stage['error_code']}]" if stage.get("error_code") else ""
        parts.append(f"{icon} `{stage['name']}`{seconds}{error}")
    return " → ".join(parts) or "Sin etapas registradas."


def page_range_text(offset: int, count: int, total: int) -> str:
    return f"{offset + 1}–{offset + count} de {total}" if count else f"0 de {total}"


def api_error_text(error) -> str:
    """Mensaje de la API para la persona, con el código HTTP; nunca la traza."""
    try:
        message = error.response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        message = "La API rechazó la operación"
    return f"{message} (HTTP {error.response.status_code})"


def comparison_rows(result: dict) -> list[dict]:
    """Resumen lado a lado de dos corridas: ventanas, exclusiones, etiquetas y clases."""
    rows = []
    for side in ("left", "right"):
        summary = result["summaries"][side]
        rows.append(
            {
                "corrida": summary["id"],
                "configuración": summary["config_id"],
                "ventanas": summary["windows"],
                "excluidas": summary["excluded"],
                "etiquetas": ", ".join(
                    f"{LABEL_TEXTS.get(k, k)} {v}"
                    for k, v in (summary["label_counts"] or {}).items()
                )
                or "—",
                "clases predichas": ", ".join(
                    f"{CLASS_TEXTS.get(k, k)} {v}"
                    for k, v in (summary["class_counts"] or {}).items()
                )
                or "—",
            }
        )
    return rows


def utc_text(timestamp: str) -> str:
    """Fecha ISO de la API como se muestra en la web: hasta los segundos, en UTC."""
    return timestamp[:19].replace("T", " ") + " UTC"


def reasons_text(reasons) -> str:
    return ", ".join(REASON_LABELS.get(r, r) for r in reasons)


def window_rows(windows: list[dict], feature_names=None) -> list[dict]:
    rows = []
    for window in windows:
        row = {
            "ventana": window["window_index"],
            "inicio (s)": window["start_s"],
            "fin (s)": window["end_s"],
            "longitud de línea (µV)": None
            if window["line_length_uv"] is None
            else round(window["line_length_uv"], 2),
        }
        for name, label in FEATURE_LABELS.items():
            if name != "line_length_uv" and (
                name in (feature_names or ()) or window.get(name) is not None
            ):
                row[label] = window.get(name)
        # Las corridas de esquema 1 no tienen etiqueta: se conserva su tabla original.
        if window.get("label"):
            row["etiqueta"] = LABEL_TEXTS[window["label"]]
            # Distingue, por ejemplo, un interictal de un registro sin crisis de uno lejos de ella.
            reason = window.get("label_reason")
            row["motivo de la etiqueta"] = REASON_LABELS.get(reason, reason) if reason else "—"
        rows.append(
            row
            | {
                "excluida": window["excluded"],
                "motivo": reasons_text(window["exclusion_reasons"]),
            }
        )
    return rows


def chart_rows(windows: list[dict], feature="line_length_uv") -> list[dict]:
    """Una fila por ventana con el motivo legible, para el gráfico y su tooltip."""
    return [
        {
            "window_index": window["window_index"],
            "start_s": window["start_s"],
            "end_s": window["end_s"],
            "mid_s": (window["start_s"] + window["end_s"]) / 2,
            feature: window.get(feature),
            "excluded": window["excluded"],
            "reason": ", ".join(REASON_LABELS.get(r, r) for r in window["exclusion_reasons"])
            or "incluida",
        }
        for window in windows
    ]


def feature_chart_spec(feature="line_length_uv") -> dict:
    """Vega-Lite: longitud de línea por ventana y franjas grises en las ventanas excluidas.

    Los valores nulos (señal no finita) cortan la línea en vez de interpolarse.
    """
    # La franja cubre [inicio, fin) de la ventana; el valor se dibuja en su centro.
    band_x = {"field": "start_s", "type": "quantitative", "title": "Tiempo desde el inicio (s)"}
    x = band_x | {"field": "mid_s"}
    y = {"field": feature, "type": "quantitative", "title": FEATURE_LABELS[feature]}
    tooltip = [
        {"field": "window_index", "title": "Ventana"},
        {"field": "start_s", "title": "Inicio (s)"},
        {"field": feature, "title": FEATURE_LABELS[feature], "format": ".6g"},
        {"field": "reason", "title": "Estado"},
    ]
    return {
        "height": 280,
        "layer": [
            {
                "transform": [{"filter": "datum.excluded"}],
                "mark": {"type": "rect", "color": EXCLUDED_FILL, "opacity": 0.25},
                "encoding": {"x": band_x, "x2": {"field": "end_s"}, "tooltip": tooltip},
            },
            {
                "mark": {
                    "type": "line",
                    "color": SERIES_COLOR,
                    "strokeWidth": 2,
                    "strokeJoin": "round",
                    "strokeCap": "round",
                    "invalid": "break-paths-show-domains",
                },
                "encoding": {"x": x, "y": y},
            },
            {
                # Objetivo de hover invisible y más grande que la línea: un tooltip por ventana.
                "mark": {"type": "point", "size": 120, "opacity": 0, "filled": True},
                "encoding": {"x": x, "y": y, "tooltip": tooltip},
            },
        ],
    }


def provenance_summary(provenance: dict) -> dict:
    """Agrupa la procedencia en las secciones que se muestran en la interfaz."""
    run, dataset, artifact = provenance["run"], provenance["dataset"], provenance["artifact"]
    metadata = (artifact or {}).get("metadata") or {}
    peak = metadata.get("peak_rss_bytes")
    return {
        "Fuente": {
            "Dataset": f"{dataset['source']} v{dataset['version']}",
            "Licencia": dataset["license"],
            "Cita": dataset["citation"],
            "SHA-256 del manifiesto": dataset["manifest_sha256"],
        },
        "Entrada": {
            "Registro": recording_label(provenance["recording"]),
            "Digest de entrada": run["input_digest"],
            "Archivos verificados": len(provenance["files"]),
        },
        "Configuración": {
            "ID": run["config_id"],
            "SHA-256": run["config_sha256"],
        },
        "Código": {
            "Commit": run["code_commit"],
            "SHA-256 de uv.lock": run["dependency_lock_sha256"],
        },
        "Resultado": {
            "Artefacto": artifact["artifact_key"] if artifact else "—",
            "SHA-256": artifact["sha256"] if artifact else "—",
            "Ventanas / excluidas": (
                f"{artifact['row_count']} / {artifact['excluded_count']}" if artifact else "—"
            ),
            "Tiempo del worker (s)": round(metadata["elapsed_s"], 2)
            if metadata.get("elapsed_s") is not None
            else "—",
            "Pico RSS del worker (MiB)": round(peak / 2**20, 1) if peak else "—",
        },
    }
