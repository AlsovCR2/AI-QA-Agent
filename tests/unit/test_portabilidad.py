"""Portabilidad de la ejecución de subprocesos y de la resolución de reportes
(T201/T202, FR-101/FR-102).

Regresión de dos defectos detectados en la auditoría del 2026-08-21:

1. `run_tests` y `analyze_coverage` construían el comando con el literal
   `"python"`. En macOS y en las distribuciones Linux que solo instalan
   `python3` ese binario no existe, así que la herramienta fallaba con
   `FileNotFoundError` y reportaba `no_ejecutado` sin poder ejecutar nada.
2. `analyze_coverage` reescribía `/` a `\\` al resolver la ruta del informe
   JaCoCo anunciada por Maven, lo que solo resolvía en Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

from qa_agent.tools.analyze_coverage import (
    AnalyzeCoverageHerramienta,
    _ruta_desde_referencia,
)
from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.run_tests import RunTestsHerramienta


# --- FR-101: intérprete portable ------------------------------------------


def test_run_tests_usa_el_interprete_actual_no_el_literal_python():
    herramienta = RunTestsHerramienta([])

    for comando in ("pytest", "pytest -v", "python -m pytest"):
        argv = herramienta._normalizar_comando(comando)
        assert argv[0] == sys.executable, comando
        assert "python" not in argv[:1]


def test_coverage_usa_el_interprete_actual_no_el_literal_python():
    herramienta = AnalyzeCoverageHerramienta([])

    for comando in (
        "pytest --cov=src",
        "coverage run -m pytest",
        "python -m pytest --cov=src",
    ):
        argv = herramienta._normalizar_comando(comando)
        assert argv[0] == sys.executable, comando


def test_coverage_no_pasa_el_operador_shell_como_argumento():
    """`&&` no es un operador con shell=False: sería un argumento literal."""
    argv = AnalyzeCoverageHerramienta([])._normalizar_comando(
        "coverage run -m pytest && coverage report"
    )

    assert "&&" not in argv
    assert argv == [sys.executable, "-m", "coverage", "run", "-m", "pytest"]


def test_run_tests_ejecuta_de_verdad_en_esta_plataforma(tmp_path):
    """Prueba end-to-end del defecto: antes fallaba con FileNotFoundError."""
    (tmp_path / "test_ok.py").write_text(
        "def test_pasa():\n    assert True\n", encoding="utf-8"
    )

    resultado = RunTestsHerramienta([str(tmp_path)]).ejecutar(
        {
            "ruta": str(tmp_path),
            "conjunto_autorizado": True,
            "comando_pruebas": "pytest -v",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["estado_global"] == "exito"
    assert resultado.datos["pasadas"] == 1


# --- FR-102: resolución de reportes independiente de plataforma -----------


def test_referencia_uri_posix_conserva_todos_los_segmentos():
    ruta = _ruta_desde_referencia("file:///home/u/proj/target/site/jacoco/jacoco.xml")

    assert ruta == Path("/home/u/proj/target/site/jacoco/jacoco.xml")


def test_referencia_uri_windows_con_barra_espuria():
    assert _ruta_desde_referencia("file:///C:/proj/jacoco.xml") == Path(
        "C:/proj/jacoco.xml"
    )


def test_referencia_uri_windows_con_unidad_como_autoridad():
    assert _ruta_desde_referencia("file://C:/proj/jacoco.xml") == Path(
        "C:/proj/jacoco.xml"
    )


def test_referencia_relativa_se_conserva_tal_cual():
    assert _ruta_desde_referencia("target/site/jacoco/jacoco.xml") == Path(
        "target/site/jacoco/jacoco.xml"
    )


def test_referencia_uri_decodifica_porcentajes():
    ruta = _ruta_desde_referencia("file:///home/mi%20proyecto/jacoco.xml")

    assert ruta == Path("/home/mi proyecto/jacoco.xml")


def test_referencia_vacia_devuelve_none():
    assert _ruta_desde_referencia("") is None
    assert _ruta_desde_referencia("   ") is None
