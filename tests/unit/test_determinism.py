"""Tests de determinismo de operaciones sin LLM (T051, FR-024 / SC-010 / VI).

Verifica que las operaciones que no requieren inteligencia artificial
(explore, locate, search, run_tests y análisis de resultados) producen
resultados idénticos ante la misma entrada y estado, y que no dependen del
modelo de lenguaje (ninguna herramienta recibe ni usa un backend LLM).
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from qa_agent.tools.analyze_coverage import AnalyzeCoverageHerramienta
from qa_agent.tools.analyze_test_results import AnalyzeTestResultsHerramienta
from qa_agent.tools.explore import ExploreHerramienta
from qa_agent.tools.locate import LocateHerramienta
from qa_agent.tools.run_tests import RunTestsHerramienta
from qa_agent.tools.search import SearchHerramienta

_SALIDA_PYTEST = (
    "============================= test session starts =============================\n"
    "tests/test_main.py::test_config_return_value PASSED\n"
    "tests/test_main.py::test_sumar_suma_correctamente PASSED\n"
    "tests/test_main.py::test_falla_intencionadamente FAILED\n"
    "FAILED tests/test_main.py::test_falla_intencionadamente - assert 4 == 5\n"
    "========================= 2 passed, 1 failed in 0.10s =========================\n"
)


def test_explore_determinista(proyecto_ejemplo):
    herramienta = ExploreHerramienta([str(proyecto_ejemplo)])
    parametros = {"ruta": str(proyecto_ejemplo)}
    r1 = herramienta.ejecutar(parametros)
    r2 = herramienta.ejecutar(parametros)
    assert r1.datos == r2.datos
    assert [e["nombre"] for e in r1.datos["elementos"]] == [
        e["nombre"] for e in r2.datos["elementos"]
    ]


def test_locate_determinista(proyecto_ejemplo):
    herramienta = LocateHerramienta([str(proyecto_ejemplo)])
    parametros = {"ruta": str(proyecto_ejemplo), "patron": "sumar"}
    r1 = herramienta.ejecutar(parametros)
    r2 = herramienta.ejecutar(parametros)
    assert r1.datos == r2.datos
    assert r1.datos["coincidencias"] == r2.datos["coincidencias"]


def test_search_determinista(proyecto_ejemplo):
    herramienta = SearchHerramienta([str(proyecto_ejemplo)])
    parametros = {"ruta": str(proyecto_ejemplo), "patron_regex": r"def \w+"}
    r1 = herramienta.ejecutar(parametros)
    r2 = herramienta.ejecutar(parametros)
    assert r1.datos == r2.datos


def test_run_tests_determinista_con_misma_salida(proyecto_ejemplo):
    """run_tests con la misma salida de subprocess → resultados idénticos."""
    herramienta = RunTestsHerramienta([str(proyecto_ejemplo)])
    parametros = {
        "ruta": str(proyecto_ejemplo),
        "conjunto_autorizado": True,
        "comando_pruebas": "python -m pytest",
    }
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout=_SALIDA_PYTEST, stderr="", returncode=1)
        r1 = herramienta.ejecutar(parametros)
        r2 = herramienta.ejecutar(parametros)
    assert r1.datos == r2.datos
    assert r1.datos["estado_global"] == "fallo"
    assert r1.datos["pasadas"] == 2 and r1.datos["falladas"] == 1


def test_analyze_test_results_determinista():
    """El análisis de resultados es determinista ante el mismo input."""
    herramienta = AnalyzeTestResultsHerramienta()
    resultado_tests = {
        "pasadas": 2,
        "falladas": 1,
        "errores": 0,
        "total": 3,
        "estado_global": "fallo",
        "detalle_fallos": [
            {
                "nombre": "test_falla_intencionadamente",
                "mensaje_error": "assert 4 == 5",
                "ruta_relativa": "test_main.py",
            }
        ],
    }
    parametros = {"ruta": ".", "resultado_tests": resultado_tests}
    r1 = herramienta.ejecutar(parametros)
    r2 = herramienta.ejecutar(parametros)
    assert r1.datos == r2.datos


def test_herramientas_no_dependen_de_llm():
    """Ninguna herramienta recibe ni invoca un backend LLM (VI / SC-010).

    Las operaciones deterministas no tienen atributos de backend: el LLM no
    interviene en su resultado.
    """
    herramientas = [
        ExploreHerramienta(),
        LocateHerramienta(),
        SearchHerramienta(),
        RunTestsHerramienta(),
        AnalyzeTestResultsHerramienta(),
        AnalyzeCoverageHerramienta(),
    ]
    for herramienta in herramientas:
        assert not hasattr(herramienta, "_backend")
        assert not hasattr(herramienta, "_llm_backend")