# EEGFlow · demo estática

La web de EEGFlow (Registros, Trabajos, Modelos) corriendo en el navegador con
[stlite](https://github.com/whitphx/stlite), sobre datos congelados de un stack local con
registros de RESPect (OpenNeuro ds003848, CC0). Suma el Visor 3D de la propagación de crisis.
Uso experimental, no clínico. Para procesar registros hay que correr EEGFlow localmente.

Sitio: https://vanafa.github.io/eegflow-visor/

## Regenerar

    docker exec -i eegflow-video-web-1 python - < tools/snapshot.py > app/snapshot.json
    python3 tools/build.py --repo ../EEGFlow --ref origin/main
