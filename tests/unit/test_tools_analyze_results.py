"""Tests de la herramienta `analyze_test_results` (T057, FR-013/014/019, UC-007).

Cubre: resumen cuantitativo determinista; causas limitadas a la evidencia;
no inventa fallos ni causas.
"""

from __future__ import annotations

import pytest

from qa_agent.tools.analyze_test_results import AnalyzeTestResultsHerramienta
from qa_agent.tools.base import EstadoResultado


def test_analyze_test_results_resumen_determinista():
    """T057: resumen cuantitativo determinista (SC-010)."""
    herramienta = AnalyzeTestResultsHerramienta()
    resultado_tests = {
        "pasadas": 10,
        "falladas": 3,
        "errores": 1,
        "total": 14,
        "estado_global": "fallo",
        "detalle_fallos": [
            {
                "nombre": "test_login",
                "mensaje_error": "AssertionError: expected True",
                "ruta_relativa": "tests/test_auth.py",
            },
            {
                "nombre": "test_logout",
                "mensaje_error": "TimeoutError",
                "ruta_relativa": "tests/test_auth.py",
            },
            {
                "nombre": "test_registro",
                "mensaje_error": "ValueError: invalid email",
                "ruta_relativa": "tests/test_usuario.py",
            },
        ],
    }

    resultado = herramienta.ejecutar(
        {"ruta": "/proyecto", "resultado_tests": resultado_tests}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert "resumen" in resultado.datos
    assert "fallos_agrupados" in resultado.datos
    # Verificar que el resumen incluye números correctos
    assert "10" in resultado.datos["resumen"]  # pasadas
    assert "3" in resultado.datos["resumen"]  # falladas
    assert "1" in resultado.datos["resumen"]  # errores


def test_analyze_test_results_agrupa_fallos_por_ruta():
    """T057: agrupa fallos por archivo/ruta."""
    herramienta = AnalyzeTestResultsHerramienta()
    resultado_tests = {
        "pasadas": 5,
        "falladas": 3,
        "errores": 0,
        "total": 8,
        "estado_global": "fallo",
        "detalle_fallos": [
            {
                "nombre": "test_login",
                "mensaje_error": "AssertionError: expected True",
                "ruta_relativa": "tests/test_auth.py",
            },
            {
                "nombre": "test_logout",
                "mensaje_error": "TimeoutError",
                "ruta_relativa": "tests/test_auth.py",
            },
            {
                "nombre": "test_registro",
                "mensaje_error": "ValueError: invalid email",
                "ruta_relativa": "tests/test_usuario.py",
            },
        ],
    }

    resultado = herramienta.ejecutar(
        {"ruta": "/proyecto", "resultado_tests": resultado_tests}
    )

    assert resultado.estado == EstadoResultado.EXITO
    fallos_agrupados = resultado.datos["fallos_agrupados"]
    assert len(fallos_agrupados) == 2  # Dos archivos distintos
    # Verificar agrupación por ruta
    rutas = [f["ruta_relativa"] for f in fallos_agrupados]
    assert "tests/test_auth.py" in rutas
    assert "tests/test_usuario.py" in rutas


def test_analyze_test_results_causas_limitadas_evidencia():
    """T057: posible_causa se limita a la evidencia o 'sin evidencia suficiente' (FR-014)."""
    herramienta = AnalyzeTestResultsHerramienta()
    resultado_tests = {
        "pasadas": 5,
        "falladas": 1,
        "errores": 0,
        "total": 6,
        "estado_global": "fallo",
        "detalle_fallos": [
            {
                "nombre": "test_x",
                "mensaje_error": "AssertionError: 4 != 5",
                "ruta_relativa": "tests/test_calc.py",
            },
        ],
    }

    resultado = herramienta.ejecutar(
        {"ruta": "/proyecto", "resultado_tests": resultado_tests}
    )

    assert resultado.estado == EstadoResultado.EXITO
    fallos_agrupados = resultado.datos["fallos_agrupados"]
    assert len(fallos_agrupados) == 1
    causa = fallos_agrupados[0]["posible_causa"]
    # La causa debe basarse en evidencia o indicar insuficiencia
    assert isinstance(causa, str)
    assert len(causa) > 0
    # No debe inventar causas no respaldadas
    assert "sin evidencia" in causa.lower() or "aserción" in causa.lower() or "inesperado" in causa.lower()


def test_analyze_test_results_sin_fallos():
    """T057: sin fallos → fallos_agrupados vacío."""
    herramienta = AnalyzeTestResultsHerramienta()
    resultado_tests = {
        "pasadas": 10,
        "falladas": 0,
        "errores": 0,
        "total": 10,
        "estado_global": "exito",
        "detalle_fallos": [],
    }

    resultado = herramienta.ejecutar(
        {"ruta": "/proyecto", "resultado_tests": resultado_tests}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["fallos_agrupados"] == []
    assert "10" in resultado.datos["resumen"]


def test_analyze_test_results_no_inventa_fallos():
    """T057: no inventa fallos ni causas (FR-019, SC-002)."""
    herramienta = AnalyzeTestResultsHerramienta()
    resultado_tests = {
        "pasadas": 5,
        "falladas": 0,
        "errores": 0,
        "total": 5,
        "estado_global": "exito",
        "detalle_fallos": [],
    }

    resultado = herramienta.ejecutar(
        {"ruta": "/proyecto", "resultado_tests": resultado_tests}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["fallos_agrupados"] == []
    # No debe reportar fallos que no existan
    assert "falladas" not in str(resultado.datos).lower() or "0" in resultado.datos["resumen"]