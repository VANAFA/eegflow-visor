"""Arma el sitio estático: la web de EEGFlow corriendo en el navegador (stlite) sobre un snapshot.

    python3 tools/build.py [--repo ../EEGFlow] [--ref origin/main]

Toma la web tal cual de la ref indicada, le suma la API congelada (tools/overlay) y la página
del visor, y deja index.html, app/ y visor/. El snapshot se toma aparte con tools/snapshot.py.
"""

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
STLITE = "https://cdn.jsdelivr.net/npm/@stlite/browser@1.12.3/build"
WEB = [
    "__init__.py",
    "web.py",
    "web_api.py",
    "web_catalog.py",
    "web_runs.py",
    "web_ml.py",
    "web_signal.py",
    "webview.py",
    "paginas/registros.py",
    "paginas/trabajos.py",
    "paginas/modelos.py",
    "assets/logo.svg",
    "assets/icon.svg",
]
SUBJECTS = ["resp0779", "resp0699"]


def patch(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"no encuentro una sola vez: {old!r}"
    return text.replace(old, new)


def copy_web(repo: Path, ref: str, app: Path) -> None:
    for name in WEB:
        target = app / "eegflow" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            subprocess.run(
                ["git", "-C", repo, "show", f"{ref}:src/eegflow/{name}"],
                check=True,
                capture_output=True,
            ).stdout
        )
    web = app / "eegflow" / "web.py"
    text = web.read_text()
    # stlite agrega al path la carpeta del script, no la del paquete.
    text = patch(
        text,
        "from pathlib import Path\n",
        "import sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).parent.parent))\n",
    )
    text = patch(
        text,
        '    st.Page("paginas/modelos.py", title="Modelos", icon=":material/model_training:"),\n',
        '    st.Page("paginas/modelos.py", title="Modelos", icon=":material/model_training:"),\n'
        '    st.Page("paginas/visor.py", title="Visor 3D", icon=":material/view_in_ar:"),\n',
    )
    text = patch(
        text,
        "        render_status()\n",
        '        st.markdown(":blue-badge[:material/inventory_2: Demo estática]")\n'
        '        st.caption("Datos congelados de un stack local con registros de RESPect '
        '(CC0). Para procesar, corré EEGFlow localmente.")\n',
    )
    web.write_text(text)
    api = app / "eegflow" / "web_api.py"
    api.write_text(
        api.read_text() + "\n\n# Demo estática: las consultas salen del snapshot.\n"
        "from eegflow.demo_api import request, request_text  # noqa: E402, F811\n"
    )
    shutil.copytree(SITE / "tools" / "overlay", app, dirs_exist_ok=True)


def copy_visor() -> None:
    """Los visores sin su barra de navegación: van embebidos en la página Visor 3D."""
    for subject in SUBJECTS:
        visor = SITE / "visor" / f"{subject}.html"
        visor.write_text(
            re.sub(r"<body><style>\n\.sitebar.*?</nav>\n", "<body>\n", visor.read_text(), flags=re.S)
        )
        # Los enlaces viejos del visor llevan a la web.
        (SITE / f"{subject}.html").write_text(
            '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=./">'
            '<link rel="canonical" href="./"><title>EEGFlow</title><a href="./">EEGFlow</a>\n'
        )


def write_index(app: Path) -> None:
    files = {
        str(path.relative_to(app)): {"url": f"app/{path.relative_to(app)}"}
        for path in sorted(app.rglob("*"))
        if path.is_file() and path.parent != app and "__pycache__" not in path.parts
    }
    files["eegflow/snapshot.json"] = {"url": "app/snapshot.json"}
    options = {
        "requirements": ["httpx", "pandas"],
        "entrypoint": "eegflow/web.py",
        "files": files,
        "streamlitConfig": {
            "client.toolbarMode": "viewer",
            "theme.baseRadius": "0.5rem",
            "theme.showWidgetBorder": True,
            "theme.light.primaryColor": "#2a78d6",
            "theme.light.linkColor": "#2a78d6",
            "theme.dark.primaryColor": "#4c93e6",
            "theme.dark.linkColor": "#6aa8ee",
        },
    }
    (SITE / "index.html").write_text(
        f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
<title>EEGFlow</title>
<link rel="icon" href="app/eegflow/assets/icon.svg">
<link rel="stylesheet" href="{STLITE}/stlite.css">
</head>
<body>
<div id="root"></div>
<noscript>EEGFlow necesita JavaScript: la web corre en el navegador con stlite.</noscript>
<script type="module">
import {{ mount }} from "{STLITE}/stlite.js";
mount({json.dumps(options, indent=1)}, document.getElementById("root"));
</script>
</body>
</html>
"""
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=SITE.parent / "EEGFlow")
    parser.add_argument("--ref", default="origin/main")
    args = parser.parse_args()
    app = SITE / "app"
    shutil.rmtree(app / "eegflow", ignore_errors=True)
    copy_web(args.repo, args.ref, app)
    copy_visor()
    write_index(app)


main()
