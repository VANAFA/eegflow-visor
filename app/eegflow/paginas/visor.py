"""Visor 3D de la propagación de una crisis entre contactos de iEEG (extra de la demo)."""

import streamlit as st
import streamlit.components.v1 as components

SUBJECTS = {
    "RESP0779": "35 de 68 contactos · 60 min de registro · crisis anotada a las 48:57",
    "RESP0699": "64 de 133 contactos · 55 min de registro · crisis anotada a las 48:42",
}

st.title("Visor 3D")
st.caption(
    "Cómo se propaga una crisis epiléptica entre los contactos de electrodos intracraneales, "
    "ventana a ventana."
)
subject = st.segmented_control(
    "Sujeto", list(SUBJECTS), default="RESP0779", key="visor-subject", required=True
)
st.caption(SUBJECTS[subject])
components.iframe(f"visor/{subject.lower()}.html", height=980, scrolling=True)

with st.expander(":material/info: Qué muestra"):
    st.markdown(
        "Cada esfera es un contacto de electrodo, no una neurona: registra la actividad sumada "
        "de una población grande de neuronas. Los contactos se dibujan en las coordenadas del "
        "propio paciente, sobre una corteza plantilla (fsaverage) ajustada por la región "
        "anotada de cada uno; orienta, pero no es la anatomía del paciente.\n\n"
        "El color indica cuántas desviaciones robustas (σ) está la longitud de línea de cada "
        "ventana de 10 s sobre la mediana del mismo contacto: tenue en lo habitual, amarillo en "
        "el umbral, rojo desde 6 σ. Con **Reproducir** o un clic en la línea de tiempo se "
        "recorre el registro; la crisis anotada es la región roja.\n\n"
        "Las anotaciones de crisis, zona de inicio, resección y región vienen del dataset; no "
        "son resultados del sistema ni una predicción."
    )
with st.expander(":material/dataset: Datos"):
    st.markdown(
        "RESPect long-term iEEG (OpenNeuro "
        "[ds003848 v1.0.3](https://doi.org/10.18112/openneuro.ds003848.v1.0.3)), licencia CC0. "
        "Demuru M., van Blooijs D., Zweiphenning W. et al. 2021, *A practical workflow for "
        "organizing clinical intraoperative and long-term iEEG data in BIDS*.\n\n"
        "Features calculadas con EEGFlow (configuración `visor-features-v1`)."
    )
