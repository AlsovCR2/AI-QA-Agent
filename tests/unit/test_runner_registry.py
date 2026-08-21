"""Registro de ecosistemas y detección por manifiesto (T223–T225, FR-122/123/124).

La prueba que más importa aquí es `test_todo_comando_esta_en_allowlist`: el
registro elige comandos, pero quien los ejecuta son `run_tests` y
`analyze_coverage`, que solo aceptan lo que está en su allowlist. Un comando
nuevo en el registro que no esté allí sería un ecosistema que el agente cree
soportar y que fallaría en tiempo de ejecución.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qa_agent.agent.runner_detection import (
    _detectar_comando_cobertura,
    _detectar_comando_pruebas,
)
from qa_agent.tools.analyze_coverage import _COMANDOS_COBERTURA_PERMITIDOS
from qa_agent.tools.run_tests import _COMANDOS_PERMITIDOS
from qa_agent.tools.runner_registry import (
    ECOSISTEMA_POR_DEFECTO,
    ECOSISTEMAS,
    comando_de_cobertura,
    comando_de_pruebas,
    detectar_ecosistema,
)

# manifiesto → id de ecosistema esperado
_MANIFIESTOS = [
    ("pom.xml", "maven"),
    ("build.gradle", "gradle"),
    ("build.gradle.kts", "gradle"),
    ("Cargo.toml", "rust"),
    ("go.mod", "go"),
    ("package.json", "node"),
    ("pyproject.toml", "python"),
    ("Aplicacion.csproj", "dotnet"),
    ("Solucion.sln", "dotnet"),
]


def _proyecto(base: Path, *manifiestos: str) -> Path:
    raiz = base / "proyecto"
    raiz.mkdir(parents=True, exist_ok=True)
    for nombre in manifiestos:
        (raiz / nombre).write_text("{}\n", encoding="utf-8")
    return raiz


# --- Invariante de seguridad (FR-123) --------------------------------------


def test_todo_comando_esta_en_allowlist():
    """Principio IV: el registro no puede proponer nada no ejecutable."""
    for ecosistema in ECOSISTEMAS:
        assert ecosistema.pruebas in _COMANDOS_PERMITIDOS, ecosistema.id
        if ecosistema.cobertura is not None:
            assert (
                ecosistema.cobertura in _COMANDOS_COBERTURA_PERMITIDOS
            ), ecosistema.id


def test_los_ids_de_ecosistema_son_unicos():
    ids = [e.id for e in ECOSISTEMAS]

    assert len(ids) == len(set(ids))


# --- Detección por manifiesto (FR-124) -------------------------------------


@pytest.mark.parametrize(
    "manifiesto,esperado", _MANIFIESTOS, ids=[m[0] for m in _MANIFIESTOS]
)
def test_detecta_ecosistema_por_manifiesto(tmp_path, manifiesto, esperado):
    raiz = _proyecto(tmp_path, manifiesto)

    assert detectar_ecosistema(str(raiz)).id == esperado


def test_no_detecta_por_extension_de_archivo(tmp_path):
    """FR-124: un `.go` suelto no convierte el proyecto en un proyecto Go."""
    raiz = _proyecto(tmp_path)
    (raiz / "utilidad.go").write_text("package main\n", encoding="utf-8")
    (raiz / "script.rs").write_text("fn main() {}\n", encoding="utf-8")

    assert detectar_ecosistema(str(raiz)).id == ECOSISTEMA_POR_DEFECTO.id


def test_manifiesto_dentro_de_directorio_excluido_se_ignora(tmp_path):
    """Un `package.json` en `node_modules` no define el ecosistema."""
    raiz = _proyecto(tmp_path, "pyproject.toml")
    dependencias = raiz / "node_modules" / "alguna-lib"
    dependencias.mkdir(parents=True)
    (dependencias / "package.json").write_text("{}\n", encoding="utf-8")

    assert detectar_ecosistema(str(raiz)).id == "python"


def test_proyecto_poliglota_resuelve_por_prioridad(tmp_path):
    """Java con scripts Python de apoyo sigue siendo un proyecto Java."""
    raiz = _proyecto(tmp_path, "pom.xml", "pyproject.toml")

    assert detectar_ecosistema(str(raiz)).id == "maven"


def test_ruta_inexistente_devuelve_el_ecosistema_por_defecto(tmp_path):
    assert detectar_ecosistema(str(tmp_path / "no-existe")).id == (
        ECOSISTEMA_POR_DEFECTO.id
    )


def test_deteccion_es_determinista(tmp_path):
    """VI: la misma entrada produce el mismo resultado siempre."""
    raiz = _proyecto(tmp_path, "go.mod")

    assert len({detectar_ecosistema(str(raiz)).id for _ in range(5)}) == 1


# --- Comandos resultantes --------------------------------------------------


def test_comandos_de_los_ecosistemas_nuevos(tmp_path):
    assert comando_de_pruebas(str(_proyecto(tmp_path / "a", "go.mod"))) == (
        "go test ./..."
    )
    assert comando_de_pruebas(str(_proyecto(tmp_path / "b", "Cargo.toml"))) == (
        "cargo test"
    )
    assert comando_de_pruebas(str(_proyecto(tmp_path / "c", "package.json"))) == (
        "npm test"
    )


def test_ecosistema_sin_cobertura_conocida_devuelve_none(tmp_path):
    """FR-019: no se inventa un comando de otro lenguaje."""
    assert comando_de_cobertura(str(_proyecto(tmp_path / "a", "Cargo.toml"))) is None
    assert (
        comando_de_cobertura(str(_proyecto(tmp_path / "b", "build.gradle"))) is None
    )


def test_go_tiene_cobertura_integrada(tmp_path):
    assert comando_de_cobertura(str(_proyecto(tmp_path, "go.mod"))) == (
        "go test ./... -cover"
    )


# --- Fachada consumida por el bucle (T225) ---------------------------------


def test_la_fachada_del_agente_sigue_devolviendo_cadenas(tmp_path):
    """El bucle espera `str`; un `None` del registro no puede escaparse."""
    raiz = _proyecto(tmp_path, "Cargo.toml")

    assert isinstance(_detectar_comando_pruebas(str(raiz)), str)
    cobertura = _detectar_comando_cobertura(str(raiz))
    assert isinstance(cobertura, str)
    assert cobertura != ""


def test_la_fachada_conserva_el_comportamiento_previo_de_python(tmp_path):
    """Regresión: los ecosistemas que ya existían no cambian de comando."""
    raiz = _proyecto(tmp_path, "pyproject.toml")

    assert _detectar_comando_pruebas(str(raiz)) == "python -m pytest"
    assert _detectar_comando_cobertura(str(raiz)) == (
        "pytest --cov=src --cov-report=term-missing"
    )


def test_la_fachada_conserva_dotnet_y_maven(tmp_path):
    dotnet = _proyecto(tmp_path / "a", "App.csproj")
    maven = _proyecto(tmp_path / "b", "pom.xml")

    assert _detectar_comando_pruebas(str(dotnet)) == "dotnet test"
    assert _detectar_comando_cobertura(str(dotnet)) == (
        'dotnet test --collect:"XPlat Code Coverage"'
    )
    assert _detectar_comando_pruebas(str(maven)) == "mvn test"
    assert _detectar_comando_cobertura(str(maven)) == "mvn test jacoco:report"
