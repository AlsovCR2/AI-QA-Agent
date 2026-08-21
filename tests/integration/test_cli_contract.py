"""Regresión E2E del contrato CLI instalado (T129)."""

from __future__ import annotations

import subprocess
import sysconfig
from pathlib import Path

from typer.testing import CliRunner

from qa_agent.cli.main import app


# Rich (vía Typer) formatea la ayuda al ancho del terminal y trunca los nombres
# de opción cuando es estrecho. En un runner de CI el ancho por defecto es 80,
# lo que hacía fallar este contrato por el entorno y no por el producto. Se fija
# un ancho explícito: el test verifica QUÉ opciones existen, no cómo se envuelven
# (FR-103).
_ENTORNO_ANCHO = {"COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"}


def test_t129_flags_documentados_son_opciones_del_punto_de_entrada():
    resultado = CliRunner().invoke(app, ["--help"], env=_ENTORNO_ANCHO)

    assert resultado.exit_code == 0
    for opcion in (
        "--version",
        "--ruta",
        "--pregunta",
        "--demo",
        "--mostrar-historial",
    ):
        assert opcion in resultado.output
    assert "commands" not in resultado.output.lower()
    assert CliRunner().invoke(app, ["main"]).exit_code != 0
    assert CliRunner().invoke(app, ["chat"]).exit_code != 0


def test_t129_version_funciona_en_nivel_superior():
    resultado = CliRunner().invoke(app, ["--version"])

    assert resultado.exit_code == 0
    assert "0.1.0" in resultado.output


def test_t129_consulta_documentada_funciona_sin_token_main(tmp_path):
    resultado = CliRunner().invoke(
        app,
        [
            "--ruta",
            str(tmp_path),
            "--pregunta",
            "hola",
            "--demo",
            "--mostrar-historial",
        ],
    )

    assert resultado.exit_code == 0
    assert resultado.output.strip()


def test_t129_repl_documentado_funciona_sin_token_main(tmp_path):
    resultado = CliRunner().invoke(
        app,
        ["--ruta", str(tmp_path), "--demo"],
        input="salir\n",
    )

    assert resultado.exit_code == 0
    assert "Fin de la sesión" in resultado.output


def test_t129_entry_point_instalado_responde_version():
    scripts = Path(sysconfig.get_path("scripts"))
    candidatos = list(scripts.glob("qa-agent*"))
    assert candidatos, "El paquete editable no instaló el entry point qa-agent"

    resultado = subprocess.run(
        [str(candidatos[0]), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert resultado.returncode == 0
    assert "0.1.0" in resultado.stdout
