"""Banderas de CLI para automatización (T219–T222, FR-118/119/120/121).

La prueba de seguridad de este archivo es `test_dry_run_no_ejecuta_...`:
`--dry-run` no puede ser un camino alternativo de ejecución, sino la misma
frontera de autorización de siempre sin conceder permiso.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qa_agent.cli.main import app

# El ancho fijo evita que Rich trunque los nombres de opción según el terminal
# del runner: el contrato es qué opciones existen, no cómo se envuelven (FR-103).
_ENTORNO = {"COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"}

_BANDERAS_NUEVAS = (
    "--json",
    "--no-color",
    "--max-steps",
    "--model",
    "--base-url",
    "--dry-run",
    "--trace-file",
)


def _proyecto(tmp_path: Path) -> Path:
    raiz = tmp_path / "proyecto"
    (raiz / "src").mkdir(parents=True)
    (raiz / "src" / "app.py").write_text("def hola():\n    return 1\n", encoding="utf-8")
    return raiz


# --- Contrato de la ayuda (FR-121) ----------------------------------------


@pytest.mark.parametrize("bandera", _BANDERAS_NUEVAS)
def test_la_bandera_aparece_en_la_ayuda(bandera):
    resultado = CliRunner().invoke(app, ["--help"], env=_ENTORNO)

    assert resultado.exit_code == 0
    assert bandera in resultado.output


def test_sigue_habiendo_un_solo_punto_de_entrada():
    """T129: la ampliación no introduce subcomandos."""
    resultado = CliRunner().invoke(app, ["--help"], env=_ENTORNO)

    assert "commands" not in resultado.output.lower()


# --- --json (FR-120) -------------------------------------------------------


def test_json_produce_json_valido(tmp_path):
    raiz = _proyecto(tmp_path)
    resultado = CliRunner().invoke(
        app,
        ["--ruta", str(raiz), "--demo", "--json", "--pregunta", "estructura"],
        env=_ENTORNO,
    )

    # El logger escribe en stderr; la última llave cierra el objeto de stdout.
    datos = json.loads(resultado.stdout[resultado.stdout.index("{") :])
    assert datos["solicitud_id"]
    assert "texto" in datos
    assert "acciones" in datos


def test_json_no_contiene_secuencias_ansi(tmp_path):
    raiz = _proyecto(tmp_path)
    resultado = CliRunner().invoke(
        app,
        ["--ruta", str(raiz), "--demo", "--json", "--pregunta", "estructura"],
        env=_ENTORNO,
    )

    assert "\x1b[" not in resultado.stdout


def test_json_sin_pregunta_falla_de_forma_explicita():
    """Un REPL interactivo y una salida machine-readable son incompatibles."""
    resultado = CliRunner().invoke(app, ["--demo", "--json"], env=_ENTORNO)

    assert resultado.exit_code == 2
    assert "--pregunta" in resultado.stdout


# --- --dry-run (FR-119) ----------------------------------------------------


def test_dry_run_no_ejecuta_accion_sensible(tmp_path):
    """La acción queda suspendida por la frontera de T126, no por un atajo."""
    raiz = _proyecto(tmp_path)
    marcador = raiz / ".pytest_cache"

    resultado = CliRunner().invoke(
        app,
        [
            "--ruta",
            str(raiz),
            "--demo",
            "--dry-run",
            "--json",
            "--pregunta",
            "ejecuta las pruebas del proyecto",
        ],
        env=_ENTORNO,
    )

    datos = json.loads(resultado.stdout[resultado.stdout.index("{") :])
    assert datos["pendiente_autorizacion"] is True
    # Nada se ejecutó: pytest no llegó a crear su caché en el proyecto.
    assert not marcador.exists()


def test_sin_dry_run_y_sin_tty_tampoco_se_autoriza_sola(tmp_path):
    """Defecto seguro: la ausencia de decisión NUNCA equivale a un sí."""
    raiz = _proyecto(tmp_path)

    resultado = CliRunner().invoke(
        app,
        [
            "--ruta",
            str(raiz),
            "--demo",
            "--json",
            "--pregunta",
            "ejecuta las pruebas del proyecto",
        ],
        env=_ENTORNO,
    )

    datos = json.loads(resultado.stdout[resultado.stdout.index("{") :])
    assert datos["pendiente_autorizacion"] is True


# --- --trace-file (FR-110/111) --------------------------------------------


def test_trace_file_escribe_jsonl(tmp_path):
    raiz = _proyecto(tmp_path)
    traza = tmp_path / "traza.jsonl"

    CliRunner().invoke(
        app,
        [
            "--ruta",
            str(raiz),
            "--demo",
            "--trace-file",
            str(traza),
            "--pregunta",
            "estructura",
        ],
        env=_ENTORNO,
    )

    assert traza.exists()
    lineas = [linea for linea in traza.read_text(encoding="utf-8").splitlines() if linea]
    assert lineas
    for linea in lineas:
        assert json.loads(linea)["solicitud_id"]


def test_json_incluye_resumen_de_traza_si_hay_trazador(tmp_path):
    raiz = _proyecto(tmp_path)
    traza = tmp_path / "traza.jsonl"

    resultado = CliRunner().invoke(
        app,
        [
            "--ruta",
            str(raiz),
            "--demo",
            "--json",
            "--trace-file",
            str(traza),
            "--pregunta",
            "estructura",
        ],
        env=_ENTORNO,
    )

    datos = json.loads(resultado.stdout[resultado.stdout.index("{") :])
    assert datos["traza"]["razon_parada"]


# --- --max-steps -----------------------------------------------------------


def test_max_steps_acota_el_presupuesto(tmp_path):
    raiz = _proyecto(tmp_path)

    resultado = CliRunner().invoke(
        app,
        [
            "--ruta",
            str(raiz),
            "--demo",
            "--json",
            "--max-steps",
            "1",
            "--pregunta",
            "estructura",
        ],
        env=_ENTORNO,
    )

    datos = json.loads(resultado.stdout[resultado.stdout.index("{") :])
    assert len(datos["acciones"]) <= 1


# --- --eval ----------------------------------------------------------------


def test_eval_emite_informe_json():
    resultado = CliRunner().invoke(app, ["--demo", "--eval", "--json"], env=_ENTORNO)

    datos = json.loads(resultado.stdout[resultado.stdout.index("{") :])
    assert datos["resumen"]["tareas"] > 0
    assert 0.0 <= datos["resumen"]["puntuacion_global"] <= 1.0
