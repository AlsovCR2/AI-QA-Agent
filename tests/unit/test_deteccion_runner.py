"""Tests de detección del runner de pruebas según el tipo de proyecto (T073).

Cuando el agente ejecuta `run_tests`/`analyze_coverage`, el comando se elige
determinísticamente según los archivos de marcador del proyecto:
- `.csproj`/`.sln` → `dotnet test` (+ `--collect:"XPlat Code Coverage"`)
- `pom.xml` → `mvn test` (+ `jacoco:report`)
- `build.gradle` → `gradle test`
- defecto → pytest

Sin LLM (VI / SC-010). Mismo proyecto → mismo comando.
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.loop import Agent, _detectar_comando_pruebas
from qa_agent.agent.loop import _detectar_comando_cobertura
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.tools.allowlist import Allowlist


def _crear_proyecto(tmp_path: Path, marcador: str | None) -> Path:
    """Crea un proyecto con el archivo de marcador indicado (o sin él)."""
    if marcador:
        (tmp_path / marcador).write_text("", encoding="utf-8")
    return tmp_path


def _agente(proyecto: Path) -> Agent:
    return Agent(
        backend=FakeLLM(seleccion={"ninguna": True}, por_defecto={}),
        herramientas={},
        allowlist=Allowlist([proyecto]),
    )


def test_deteccion_python_default(tmp_path):
    """Sin marcadores → pytest (defecto)."""
    proyecto = _crear_proyecto(tmp_path, None)
    assert _detectar_comando_pruebas(str(proyecto)) == "python -m pytest"
    assert _detectar_comando_cobertura(str(proyecto)) == (
        "pytest --cov=src --cov-report=term-missing"
    )


def test_deteccion_dotnet_csproj(tmp_path):
    """Proyecto .NET (`*.csproj`) → `dotnet test` y cobertura XPlat."""
    proyecto = _crear_proyecto(tmp_path, "App.csproj")
    assert _detectar_comando_pruebas(str(proyecto)) == "dotnet test"
    assert _detectar_comando_cobertura(str(proyecto)) == (
        'dotnet test --collect:"XPlat Code Coverage"'
    )


def test_deteccion_dotnet_sln(tmp_path):
    """Proyecto .NET (`*.sln`) → `dotnet test`."""
    proyecto = _crear_proyecto(tmp_path, "Solucion.sln")
    assert _detectar_comando_pruebas(str(proyecto)) == "dotnet test"


def test_deteccion_maven_pom(tmp_path):
    """Proyecto Maven (`pom.xml`) → `mvn test` y jacoco."""
    proyecto = _crear_proyecto(tmp_path, "pom.xml")
    assert _detectar_comando_pruebas(str(proyecto)) == "mvn test"
    assert _detectar_comando_cobertura(str(proyecto)) == "mvn test jacoco:report"


def test_deteccion_gradle(tmp_path):
    """Proyecto Gradle (`build.gradle`) → `gradle test`."""
    proyecto = _crear_proyecto(tmp_path, "build.gradle")
    assert _detectar_comando_pruebas(str(proyecto)) == "gradle test"


def test_deteccion_determinista_mismo_proyecto(tmp_path):
    """Mismo proyecto → mismo comando en dos llamadas (VI / SC-010)."""
    proyecto = _crear_proyecto(tmp_path, "App.csproj")
    assert _detectar_comando_pruebas(str(proyecto)) == _detectar_comando_pruebas(
        str(proyecto)
    )


def test_parametros_para_run_tests_usa_comando_detectado(tmp_path):
    """`_parametros_para` de run_tests usa el comando detectado por marcador."""
    proyecto = _crear_proyecto(tmp_path, "pom.xml")
    agente = _agente(proyecto)
    from qa_agent.tools.base import Herramienta, ResultadoDeHerramienta

    class StubRunTests(Herramienta):
        id = "run_tests"
        nombre = "run_tests"
        descripcion = ""
        esquema_entrada = {}
        esquema_salida = {}
        requiere_autorizacion = True

        def ejecutar(self, parametros: dict) -> ResultadoDeHerramienta:
            raise NotImplementedError

    parametros = agente._parametros_para(StubRunTests(), "ejecuta los tests")
    assert parametros["comando_pruebas"] == "mvn test"
    assert parametros["conjunto_autorizado"] is True


def test_parametros_para_analyze_coverage_usa_comando_detectado(tmp_path):
    """`_parametros_para` de analyze_coverage usa el comando detectado."""
    proyecto = _crear_proyecto(tmp_path, "App.csproj")
    agente = _agente(proyecto)
    from qa_agent.tools.base import Herramienta, ResultadoDeHerramienta

    class StubCoverage(Herramienta):
        id = "analyze_coverage"
        nombre = "analyze_coverage"
        descripcion = ""
        esquema_entrada = {}
        esquema_salida = {}
        requiere_autorizacion = False

        def ejecutar(self, parametros: dict) -> ResultadoDeHerramienta:
            raise NotImplementedError

    parametros = agente._parametros_para(StubCoverage(), "analiza la cobertura")
    assert parametros["comando_cobertura"] == (
        'dotnet test --collect:"XPlat Code Coverage"'
    )