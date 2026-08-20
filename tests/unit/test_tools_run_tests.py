"""Tests de la herramienta `run_tests` (T038, FR-012/013/014, UC-005).

Cubre: conjunto autorizado → reporta pasadas/falladas/errores reales;
prueba fallida → reporta fallo explícito; no autorizado → no ejecuta.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.run_tests import RunTestsHerramienta


def _crear_proyecto_tests(tmp_path: Path) -> Path:
    """Estructura: proyecto con tests que pasan y tests que fallan."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculadora.py").write_text(
        '"""Calculadora simple."""\n\n'
        'def sumar(a: int, b: int) -> int:\n'
        '    return a + b\n\n'
        'def dividir(a: int, b: int) -> float:\n'
        '    if b == 0:\n'
        '        raise ValueError("No se puede dividir por cero")\n'
        '    return a / b\n'
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calculadora.py").write_text(
        'import pytest\n'
        'from src.calculadora import sumar, dividir\n\n'
        'def test_sumar():\n'
        '    assert sumar(2, 3) == 5\n\n'
        'def test_sumar_negativos():\n'
        '    assert sumar(-1, -1) == -2\n\n'
        'def test_dividir():\n'
        '    assert dividir(10, 2) == 5.0\n\n'
        'def test_dividir_por_cero():\n'
        '    with pytest.raises(ValueError):\n'
        '        dividir(10, 0)\n\n'
        '# Test que falla intencionalmente\n'
        'def test_falla_intencional():\n'
        '    assert sumar(2, 2) == 5  # Debe ser 4\n'
    )
    return tmp_path


def test_run_tests_conjunto_autorizado_reporta_estado_real(tmp_path):
    """T038: conjunto autorizado → reporta pasadas/falladas/errores reales (SC-002/011)."""
    proyecto = _crear_proyecto_tests(tmp_path)
    herramienta = RunTestsHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "conjunto_autorizado": True,
            "comando_pruebas": "pytest -v",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    datos = resultado.datos
    assert "pasadas" in datos
    assert "falladas" in datos
    assert "errores" in datos
    assert "total" in datos
    assert "estado_global" in datos
    assert "detalle_fallos" in datos
    # Debe haber al menos 1 fallo (el test intencional)
    assert datos["falladas"] >= 1
    assert datos["total"] >= 5
    assert datos["estado_global"] in {"exito", "fallo"}


def test_run_tests_prueba_fallida_reporta_error_real(tmp_path):
    """T038: prueba fallida → reporta el fallo explícitamente con error real (FR-014, SC-005)."""
    proyecto = _crear_proyecto_tests(tmp_path)
    herramienta = RunTestsHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "conjunto_autorizado": True,
            "comando_pruebas": "pytest -v",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    detalle = resultado.datos["detalle_fallos"]
    assert len(detalle) >= 1
    # Verifica que el fallo tiene info real
    fallo = detalle[0]
    assert "nombre" in fallo
    assert "mensaje_error" in fallo
    assert "ruta_relativa" in fallo
    assert len(fallo["mensaje_error"]) > 0


def test_run_tests_no_autorizado_no_ejecuta(tmp_path):
    """T038: conjunto no autorizado → no ejecuta (SC-011)."""
    proyecto = _crear_proyecto_tests(tmp_path)
    herramienta = RunTestsHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "conjunto_autorizado": False,
            "comando_pruebas": "pytest -v",
        }
    )

    assert resultado.estado in {EstadoResultado.ERROR, EstadoResultado.INVALIDO}
    assert resultado.datos.get("estado_global") == "no_ejecutado"
    assert "no autorizado" in (resultado.error or "").lower() or \
           "no_ejecutado" in str(resultado.datos)


def test_run_tests_comando_fuera_allowlist_rechazado(tmp_path):
    """T041: comando fuera de allowlist → rechazado (SC-011)."""
    proyecto = _crear_proyecto_tests(tmp_path)
    herramienta = RunTestsHerramienta([str(proyecto)])
    # Comando peligroso no en allowlist
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "conjunto_autorizado": True,
            "comando_pruebas": "rm -rf /",
        }
    )

    assert resultado.estado in {EstadoResultado.ERROR, EstadoResultado.INVALIDO}
    assert resultado.datos == {}


def test_run_tests_ruta_fuera_allowlist_no_accede(tmp_path):
    """RunTests respeta Allowlist: ruta fuera → error (FR-025)."""
    proyecto = _crear_proyecto_tests(tmp_path)
    outside = tmp_path.parent / "perimetro_vecino"
    if not outside.exists():
        outside.mkdir()
    herramienta = RunTestsHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(outside),
            "conjunto_autorizado": True,
            "comando_pruebas": "pytest -v",
        }
    )

    assert resultado.estado in {EstadoResultado.ERROR, EstadoResultado.INVALIDO}
    assert resultado.datos == {}


# -- Ampliación multi-lenguaje: dotnet test / mvn test / gradle test ----------

_SALIDA_DOTNET_OK = (
    "  Determining projects to restore...\n"
    "  Calculadora -> bin/Debug/net8.0/Calculadora.dll\n"
    "Passed!  - Failed: 0, Passed: 4, Skipped: 0, Total: 4, Duration: 1 s\n"
)

_SALIDA_DOTNET_FALLO = (
    "  Determinar proyectos para restaurar...\n"
    "Failed!  - Failed: 1, Passed: 3, Skipped: 0, Total: 4, Duration: 1 s\n"
    "  Failed TestSuma [2 ms]\n"
    "  Error Message:\n"
    "   Expected: 5\n"
    "   But was: 4\n"
    "  Stack Trace:\n"
    "   en Calculadora.Sumar(...) en Calculadora.cs:línea 10\n"
)

_SALIDA_MAVEN_OK = (
    "-------------------------------------------------------\n"
    " T E S T S\n"
    "-------------------------------------------------------\n"
    "Running com.example.CalculadoraTest\n"
    "Tests run: 4, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.3 s\n"
    "[INFO] BUILD SUCCESS\n"
)

_SALIDA_MAVEN_FALLO = (
    "-------------------------------------------------------\n"
    " T E S T S\n"
    "-------------------------------------------------------\n"
    "Running com.example.CalculadoraTest\n"
    "Tests run: 4, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 0.4 s\n"
    "\n"
    "Results:\n"
    "\n"
    "Tests run: 4, Failures: 1, Errors: 0, Skipped: 0\n"
    "[ERROR] Failures:\n"
    "[ERROR]   CalculadoraTest.testSuma:10 expected:<5> but was:<4>\n"
    "[ERROR] Tests run: 4, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 0.4 s\n"
    "[INFO] BUILD FAILURE\n"
)

_SALIDA_GRADLE_OK = (
    "> Task :test\n"
    "CalculadoraTest > testSuma PASSED\n"
    "CalculadoraTest > testResta PASSED\n"
    "\n"
    "BUILD SUCCESSFUL in 1s\n"
    "4 tests completed\n"
)

_SALIDA_GRADLE_FALLO = (
    "> Task :test FAILED\n"
    "CalculadoraTest > testSuma FAILED\n"
    "    org.opentest4j.AssertionFailedError at CalculadoraTest.java:10\n"
    "\n"
    "BUILD FAILED in 2s\n"
    "4 tests completed, 1 failed\n"
)


def _mock_subprocess(salida: str):
    mock = Mock()
    mock.stdout = salida
    mock.stderr = ""
    mock.returncode = 0
    return mock


def test_run_tests_dotnet_allowlist_y_parseo_ok(tmp_path):
    """dotnet test está en allowlist y reporta métricas reales (FR-013, SC-002)."""
    proyecto = tmp_path
    with patch("subprocess.run", return_value=_mock_subprocess(_SALIDA_DOTNET_OK)):
        herramienta = RunTestsHerramienta([str(proyecto)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(proyecto),
                "conjunto_autorizado": True,
                "comando_pruebas": "dotnet test",
            }
        )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["pasadas"] == 4
    assert resultado.datos["falladas"] == 0
    assert resultado.datos["total"] == 4
    assert resultado.datos["estado_global"] == "exito"


def test_run_tests_dotnet_fallo_con_detalle(tmp_path):
    """dotnet: fallo se reporta explícito con nombre de test real (FR-014)."""
    proyecto = tmp_path
    with patch("subprocess.run", return_value=_mock_subprocess(_SALIDA_DOTNET_FALLO)):
        herramienta = RunTestsHerramienta([str(proyecto)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(proyecto),
                "conjunto_autorizado": True,
                "comando_pruebas": "dotnet test",
            }
        )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["pasadas"] == 3
    assert resultado.datos["falladas"] >= 1
    assert resultado.datos["estado_global"] == "fallo"
    assert any("TestSuma" in f["nombre"] for f in resultado.datos["detalle_fallos"])


def test_run_tests_maven_allowlist_y_parseo_ok(tmp_path):
    """mvn test está en allowlist y reporta métricas reales."""
    proyecto = tmp_path
    with patch("subprocess.run", return_value=_mock_subprocess(_SALIDA_MAVEN_OK)):
        herramienta = RunTestsHerramienta([str(proyecto)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(proyecto),
                "conjunto_autorizado": True,
                "comando_pruebas": "mvn test",
            }
        )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["total"] == 4
    assert resultado.datos["falladas"] == 0
    assert resultado.datos["estado_global"] == "exito"


def test_run_tests_maven_fallo_con_detalle(tmp_path):
    """mvn: fallo con nombre de test real extraído de la salida Surefire."""
    proyecto = tmp_path
    with patch("subprocess.run", return_value=_mock_subprocess(_SALIDA_MAVEN_FALLO)):
        herramienta = RunTestsHerramienta([str(proyecto)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(proyecto),
                "conjunto_autorizado": True,
                "comando_pruebas": "mvn test",
            }
        )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["falladas"] == 1
    assert resultado.datos["estado_global"] == "fallo"
    assert any("testSuma" in f["nombre"] for f in resultado.datos["detalle_fallos"])


def test_run_tests_gradle_allowlist_y_parseo_ok(tmp_path):
    """gradle test está en allowlist y reporta métricas reales."""
    proyecto = tmp_path
    with patch("subprocess.run", return_value=_mock_subprocess(_SALIDA_GRADLE_OK)):
        herramienta = RunTestsHerramienta([str(proyecto)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(proyecto),
                "conjunto_autorizado": True,
                "comando_pruebas": "gradle test",
            }
        )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["total"] == 4
    assert resultado.datos["falladas"] == 0
    assert resultado.datos["estado_global"] == "exito"


def test_run_tests_gradle_fallo_con_detalle(tmp_path):
    """gradle: fallo se reporta explícito con nombre de test real."""
    proyecto = tmp_path
    with patch("subprocess.run", return_value=_mock_subprocess(_SALIDA_GRADLE_FALLO)):
        herramienta = RunTestsHerramienta([str(proyecto)])
        resultado = herramienta.ejecutar(
            {
                "ruta": str(proyecto),
                "conjunto_autorizado": True,
                "comando_pruebas": "gradle test",
            }
        )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["falladas"] == 1
    assert resultado.datos["estado_global"] == "fallo"
    assert any("testSuma" in f["nombre"] for f in resultado.datos["detalle_fallos"])


def test_run_tests_comando_multi_lenguaje_fuera_allowlist_rechazado(tmp_path):
    """Variantes no permitidas (dotnet test -c Release) se rechazan (SC-011)."""
    proyecto = tmp_path
    herramienta = RunTestsHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "conjunto_autorizado": True,
            "comando_pruebas": "dotnet test -c Release",
        }
    )

    assert resultado.estado in {EstadoResultado.ERROR, EstadoResultado.INVALIDO}
    assert resultado.datos == {}