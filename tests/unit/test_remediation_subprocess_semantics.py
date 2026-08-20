"""Matriz de returncode y salida para T130."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from qa_agent.tools.analyze_coverage import AnalyzeCoverageHerramienta
from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.run_tests import RunTestsHerramienta


def _ejecutar_tests(tmp_path, returncode: int, salida: str):
    proceso = SimpleNamespace(stdout=salida, stderr="", returncode=returncode)
    herramienta = RunTestsHerramienta([str(tmp_path)])
    with patch("subprocess.run", return_value=proceso):
        return herramienta.ejecutar(
            {
                "ruta": str(tmp_path),
                "conjunto_autorizado": True,
                "comando_pruebas": "pytest",
            }
        )


def _ejecutar_cobertura(tmp_path, returncode: int, salida: str):
    proceso = SimpleNamespace(stdout=salida, stderr="", returncode=returncode)
    herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])
    with patch("subprocess.run", return_value=proceso):
        return herramienta.ejecutar(
            {
                "ruta": str(tmp_path),
                "comando_cobertura": "pytest --cov=src --cov-report=term",
            }
        )


@pytest.mark.parametrize(
    ("returncode", "salida", "estado_externo", "estado_global"),
    [
        (0, "1 passed in 0.01s", EstadoResultado.EXITO, "exito"),
        (1, "1 failed in 0.01s", EstadoResultado.EXITO, "fallo"),
        (5, "no tests ran in 0.01s", EstadoResultado.EXITO, "no_ejecutado"),
        (2, "1 passed in 0.01s", EstadoResultado.ERROR, "no_ejecutado"),
        (2, "INTERNALERROR runner roto", EstadoResultado.ERROR, "no_ejecutado"),
        (0, "salida desconocida", EstadoResultado.ERROR, "no_ejecutado"),
    ],
)
def test_t130_run_tests_combina_returncode_y_evidencia(
    tmp_path,
    returncode,
    salida,
    estado_externo,
    estado_global,
):
    resultado = _ejecutar_tests(tmp_path, returncode, salida)

    assert resultado.estado == estado_externo
    assert resultado.datos["estado_global"] == estado_global
    assert bool(resultado.error) is (estado_externo == EstadoResultado.ERROR)


def test_t130_run_tests_distingue_spawn_y_timeout(tmp_path):
    herramienta = RunTestsHerramienta([str(tmp_path)])
    parametros = {
        "ruta": str(tmp_path),
        "conjunto_autorizado": True,
        "comando_pruebas": "pytest",
    }
    for error in (
        OSError("pytest no disponible"),
        subprocess.TimeoutExpired(["pytest"], 120),
    ):
        with patch("subprocess.run", side_effect=error):
            resultado = herramienta.ejecutar(parametros)
        assert resultado.estado == EstadoResultado.ERROR
        assert resultado.datos["estado_global"] == "no_ejecutado"
        assert resultado.error


_COBERTURA_OK = (
    "Name Stmts Miss Cover\n"
    "src/mod.py 10 0 100%\n"
    "TOTAL 10 0 100%\n"
)


@pytest.mark.parametrize(
    ("returncode", "salida", "estado_externo", "estado_cobertura"),
    [
        (0, _COBERTURA_OK, EstadoResultado.EXITO, "exito"),
        (1, _COBERTURA_OK, EstadoResultado.ERROR, "error"),
        (5, "no tests ran in 0.01s", EstadoResultado.EXITO, "no_ejecutado"),
        (2, "", EstadoResultado.ERROR, "error"),
        (2, "salida no soportada", EstadoResultado.ERROR, "error"),
        (0, "salida no soportada", EstadoResultado.ERROR, "error"),
    ],
)
def test_t130_cobertura_combina_returncode_y_evidencia(
    tmp_path,
    returncode,
    salida,
    estado_externo,
    estado_cobertura,
):
    resultado = _ejecutar_cobertura(tmp_path, returncode, salida)

    assert resultado.estado == estado_externo
    assert resultado.datos["estado"] == estado_cobertura
    assert bool(resultado.error) is (estado_externo == EstadoResultado.ERROR)


def test_t130_cobertura_distingue_spawn_y_timeout(tmp_path):
    herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])
    parametros = {
        "ruta": str(tmp_path),
        "comando_cobertura": "pytest --cov=src --cov-report=term",
    }
    for error in (
        OSError("pytest-cov no disponible"),
        subprocess.TimeoutExpired(["pytest"], 180),
    ):
        with patch("subprocess.run", side_effect=error):
            resultado = herramienta.ejecutar(parametros)
        assert resultado.estado == EstadoResultado.ERROR
        assert resultado.datos["estado"] in {"error", "no_ejecutado"}
        assert resultado.error
