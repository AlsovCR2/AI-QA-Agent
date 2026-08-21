"""Metadatos de ejecución y taxonomía de causas (T206–T209, FR-105/106/107/108).

El agente distinguía "no se ejecutó" de nada más: `estado_global` era
`no_ejecutado` tanto si el proyecto no tenía pruebas, como si el runner no
estaba instalado, como si la colección había fallado. Estas pruebas fijan la
diferencia entre esos casos, que es lo que hace accionable la respuesta.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from qa_agent.tools.analyze_coverage import AnalyzeCoverageHerramienta
from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.ejecucion import (
    EJECUTADO,
    ERROR_DE_EJECUCION,
    FALLO_DE_COLECCION,
    REPORTE_NO_ENCONTRADO,
    RUNNER_NO_DISPONIBLE,
    SIN_EJECUTAR,
    SIN_PRUEBAS,
    TIMEOUT,
    MetadatosDeEjecucion,
    clasificar_salida,
    cola_redactada,
    detectar_runner_de_comando,
    ejecutar_comando,
    metadatos_sin_ejecutar,
)
from qa_agent.tools.run_tests import RunTestsHerramienta

_CAMPOS = (
    "exit_code",
    "runner_detectado",
    "duracion_ms",
    "stdout_tail",
    "stderr_tail",
    "causa_no_ejecutado",
)


def _proyecto_con_prueba(tmp_path: Path, cuerpo: str = "assert True") -> Path:
    (tmp_path / "test_muestra.py").write_text(
        f"def test_muestra():\n    {cuerpo}\n", encoding="utf-8"
    )
    return tmp_path


# --- Detección de runner ---------------------------------------------------


@pytest.mark.parametrize(
    "comando,esperado",
    [
        ("pytest", "pytest"),
        ("pytest -v", "pytest"),
        ("python -m pytest --tb=short", "pytest"),
        ("coverage run -m pytest", "coverage"),
        ("dotnet test", "dotnet"),
        ("mvn test jacoco:report", "maven"),
        ("gradle test", "gradle"),
        ("npm test", "npm"),
        ("go test ./...", "go"),
        ("cargo test", "cargo"),
        ("herramienta-inventada --x", "desconocido"),
        ("", "desconocido"),
    ],
)
def test_detecta_el_runner_desde_el_comando(comando, esperado):
    assert detectar_runner_de_comando(comando) == esperado


def test_prefijo_mas_especifico_gana():
    """'python -m pytest' es pytest, no un runner genérico de python."""
    assert detectar_runner_de_comando("python -m pytest") == "pytest"
    assert detectar_runner_de_comando("python -m coverage run") == "coverage"


# --- Clasificación de salida ----------------------------------------------


def test_sin_pruebas_se_distingue_de_ejecucion_normal():
    assert clasificar_salida("collected 0 items\n") == SIN_PRUEBAS
    assert clasificar_salida("no tests ran in 0.01s") == SIN_PRUEBAS
    assert clasificar_salida("2 passed in 0.10s") == EJECUTADO


def test_fallo_de_coleccion_gana_sobre_sin_pruebas():
    """Si la colección falló, la causa accionable es esa, no 'no hay pruebas'."""
    salida = "ERROR collecting test_x.py\nModuleNotFoundError: no module named 'x'\ncollected 0 items"

    assert clasificar_salida(salida) == FALLO_DE_COLECCION


# --- Redacción de las colas (FR-108) --------------------------------------


def test_la_cola_redacta_secretos_antes_de_salir_del_modulo():
    cola = cola_redactada("conectando con api_key=sk-abcdefgh12345678 ok")

    assert "sk-abcdefgh12345678" not in cola
    assert "***" in cola


def test_la_cola_conserva_solo_el_final():
    cola = cola_redactada("A" * 100 + "FINAL", maximo=10)

    assert cola == "AAAAAFINAL"
    assert len(cola) == 10


def test_cola_vacia_es_cadena_vacia():
    assert cola_redactada("") == ""


# --- Ejecución real --------------------------------------------------------


def test_runner_ausente_se_reporta_como_causa_propia(tmp_path):
    """El caso que rompía en macOS: binario inexistente ≠ error genérico."""
    proceso, metadatos = ejecutar_comando(
        ["binario-que-no-existe-en-ninguna-parte"],
        cwd=str(tmp_path),
        comando_original="pytest",
    )

    assert proceso is None
    assert metadatos.causa_no_ejecutado == RUNNER_NO_DISPONIBLE
    assert metadatos.exit_code == SIN_EJECUTAR
    assert metadatos.runner_detectado == "pytest"


def test_timeout_se_reporta_como_causa_propia(tmp_path):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 1)):
        proceso, metadatos = ejecutar_comando(
            ["cualquiera"], cwd=str(tmp_path), comando_original="pytest"
        )

    assert proceso is None
    assert metadatos.causa_no_ejecutado == TIMEOUT


def test_error_de_sistema_se_distingue_de_runner_ausente(tmp_path):
    with patch("subprocess.run", side_effect=OSError("disco lleno")):
        proceso, metadatos = ejecutar_comando(
            ["cualquiera"], cwd=str(tmp_path), comando_original="pytest"
        )

    assert proceso is None
    assert metadatos.causa_no_ejecutado == ERROR_DE_EJECUCION
    assert "disco lleno" in metadatos.stderr_tail


def test_ejecucion_correcta_devuelve_exit_code_y_duracion(tmp_path):
    import sys

    proceso, metadatos = ejecutar_comando(
        [sys.executable, "-c", "print('hola')"],
        cwd=str(tmp_path),
        comando_original="pytest",
    )

    assert proceso is not None
    assert metadatos.exit_code == 0
    assert metadatos.causa_no_ejecutado == EJECUTADO
    assert "hola" in metadatos.stdout_tail
    assert metadatos.duracion_ms >= 0


def test_ejecucion_usa_shell_false_siempre(tmp_path):
    """Principio IV: nunca se delega la tokenización al shell."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)
        ejecutar_comando(["echo", "hola"], cwd=str(tmp_path))

    assert mock_run.call_args.kwargs["shell"] is False


# --- run_tests: los metadatos llegan al resultado -------------------------


def test_run_tests_siempre_emite_los_metadatos(tmp_path):
    """FR-105: los campos no están en `required` del esquema, así que el
    contrato real de "siempre presentes" se fija aquí."""
    resultado = RunTestsHerramienta([str(tmp_path)]).ejecutar(
        {
            "ruta": str(_proyecto_con_prueba(tmp_path)),
            "conjunto_autorizado": True,
            "comando_pruebas": "pytest -v",
        }
    )

    for campo in _CAMPOS:
        assert campo in resultado.datos, campo
    assert resultado.datos["runner_detectado"] == "pytest"
    assert resultado.datos["exit_code"] == 0
    assert resultado.datos["causa_no_ejecutado"] == EJECUTADO


def test_run_tests_sin_pruebas_reporta_la_causa(tmp_path):
    """Proyecto vacío: se ejecutó, pero no había nada que ejecutar."""
    resultado = RunTestsHerramienta([str(tmp_path)]).ejecutar(
        {
            "ruta": str(tmp_path),
            "conjunto_autorizado": True,
            "comando_pruebas": "pytest -v",
        }
    )

    assert resultado.datos["causa_no_ejecutado"] == SIN_PRUEBAS
    assert resultado.datos["estado_global"] == "no_ejecutado"
    # Se ejecutó de verdad: hay un exit code real, no el centinela.
    assert resultado.datos["exit_code"] != SIN_EJECUTAR


def test_run_tests_fallo_de_coleccion_no_se_confunde_con_sin_pruebas(tmp_path):
    (tmp_path / "test_roto.py").write_text(
        "import modulo_que_no_existe\n\ndef test_x():\n    assert True\n",
        encoding="utf-8",
    )

    resultado = RunTestsHerramienta([str(tmp_path)]).ejecutar(
        {
            "ruta": str(tmp_path),
            "conjunto_autorizado": True,
            "comando_pruebas": "pytest -v",
        }
    )

    assert resultado.datos["causa_no_ejecutado"] == FALLO_DE_COLECCION
    assert resultado.datos["causa_no_ejecutado"] != SIN_PRUEBAS


def test_run_tests_runner_ausente_reporta_causa_y_no_inventa(tmp_path):
    _proyecto_con_prueba(tmp_path)
    with patch("subprocess.run", side_effect=FileNotFoundError("python")):
        resultado = RunTestsHerramienta([str(tmp_path)]).ejecutar(
            {
                "ruta": str(tmp_path),
                "conjunto_autorizado": True,
                "comando_pruebas": "pytest -v",
            }
        )

    assert resultado.estado == EstadoResultado.ERROR
    assert resultado.datos["causa_no_ejecutado"] == RUNNER_NO_DISPONIBLE
    # Nunca se inventan resultados (FR-019).
    assert resultado.datos["pasadas"] == 0
    assert resultado.datos["total"] == 0


def test_run_tests_no_filtra_secretos_en_las_colas(tmp_path):
    (tmp_path / "test_secreto.py").write_text(
        "def test_x():\n    print('api_key=sk-abcdefgh12345678')\n    assert True\n",
        encoding="utf-8",
    )

    resultado = RunTestsHerramienta([str(tmp_path)]).ejecutar(
        {
            "ruta": str(tmp_path),
            "conjunto_autorizado": True,
            "comando_pruebas": "pytest -v",
        }
    )

    assert "sk-abcdefgh12345678" not in resultado.datos["stdout_tail"]
    assert "sk-abcdefgh12345678" not in resultado.datos["stderr_tail"]


# --- analyze_coverage ------------------------------------------------------


def test_coverage_distingue_comando_fallido_de_reporte_ausente(tmp_path):
    """FR-107: dos causas distintas que antes colapsaban en 'error'."""
    herramienta = AnalyzeCoverageHerramienta([str(tmp_path)])

    with patch("subprocess.run") as mock_run:
        # El comando terminó bien (returncode 0) pero su salida no contiene
        # ninguna tabla ni referencia a un informe.
        mock_run.return_value = Mock(
            stdout="ejecucion terminada sin informe\n", stderr="", returncode=0
        )
        sin_reporte = herramienta.ejecutar(
            {"ruta": str(tmp_path), "comando_cobertura": "pytest --cov=src"}
        )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout="", stderr="boom\n", returncode=2)
        fallo = herramienta.ejecutar(
            {"ruta": str(tmp_path), "comando_cobertura": "pytest --cov=src"}
        )

    assert sin_reporte.datos["causa_no_ejecutado"] == REPORTE_NO_ENCONTRADO
    assert fallo.datos["causa_no_ejecutado"] != REPORTE_NO_ENCONTRADO
    assert fallo.datos["exit_code"] == 2


def test_coverage_emite_los_metadatos_en_exito(tmp_path):
    salida = (
        "Name                 Stmts   Miss  Cover\n"
        "----------------------------------------\n"
        "src/calculadora.py       4      1    75%\n"
        "----------------------------------------\n"
        "TOTAL                    4      1    75%\n"
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(stdout=salida, stderr="", returncode=0)
        resultado = AnalyzeCoverageHerramienta([str(tmp_path)]).ejecutar(
            {"ruta": str(tmp_path), "comando_cobertura": "pytest --cov=src"}
        )

    assert resultado.estado == EstadoResultado.EXITO
    for campo in _CAMPOS:
        assert campo in resultado.datos, campo
    assert resultado.datos["causa_no_ejecutado"] == EJECUTADO


# --- Determinismo (VI) -----------------------------------------------------


def test_metadatos_son_deterministas_salvo_la_duracion():
    a = MetadatosDeEjecucion(exit_code=0, runner_detectado="pytest", duracion_ms=11)
    b = MetadatosDeEjecucion(exit_code=0, runner_detectado="pytest", duracion_ms=980)

    sin_tiempo = lambda m: {  # noqa: E731 - comparación local y explícita
        k: v for k, v in m.como_dict().items() if k != "duracion_ms"
    }

    assert sin_tiempo(a) == sin_tiempo(b)


def test_con_causa_conserva_el_resto_de_la_evidencia():
    original = metadatos_sin_ejecutar(RUNNER_NO_DISPONIBLE, "pytest")
    derivado = original.con_causa(SIN_PRUEBAS)

    assert derivado.causa_no_ejecutado == SIN_PRUEBAS
    assert derivado.runner_detectado == original.runner_detectado
    assert derivado.exit_code == original.exit_code
