"""Detección determinista del runner de pruebas/cobertura por tipo de proyecto.

Extraído de `agent/loop.py` (I01, ADR-001) como movimiento puro: mismos
marcadores, mismos comandos, mismo comportamiento observable. El runner se
detecta por archivos de marcador del proyecto destino (sin LLM, VI / SC-010):
.NET → `dotnet test`, Maven → `mvn test`, Gradle → `gradle test`, por defecto
`pytest` (T073). Todos los comandos quedan dentro de las allowlists de
`run_tests`/`analyze_coverage` (FR-025); este módulo solo decide CUÁL comando
usar, nunca ejecuta nada.
"""

from __future__ import annotations

from pathlib import Path

_MARCADORES_DOTNET = ("*.csproj", "*.sln", "*.fsproj", "*.vbproj")
_MARCADORES_MAVEN = ("pom.xml",)
_MARCADORES_GRADLE = ("build.gradle", "settings.gradle", "build.gradle.kts")

_COMANDO_PRUEBAS_PYTEST = "python -m pytest"
_COMANDO_PRUEBAS_DOTNET = "dotnet test"
_COMANDO_PRUEBAS_MAVEN = "mvn test"
_COMANDO_PRUEBAS_GRADLE = "gradle test"

_COMANDO_COBERTURA_PYTEST = "pytest --cov=src --cov-report=term-missing"
_COMANDO_COBERTURA_DOTNET = 'dotnet test --collect:"XPlat Code Coverage"'
_COMANDO_COBERTURA_MAVEN = "mvn test jacoco:report"


def _encontrar_marcador(ruta: str, patrones: tuple[str, ...]) -> bool:
    """True si existe algún archivo de marcador dentro de `ruta` (recursivo)."""
    base = Path(ruta)
    if not base.exists():
        return False
    return any(next(base.rglob(patron), None) is not None for patron in patrones)


def _detectar_comando_pruebas(ruta: str) -> str:
    """Elige el comando de pruebas según el tipo de proyecto (T073)."""
    if _encontrar_marcador(ruta, _MARCADORES_DOTNET):
        return _COMANDO_PRUEBAS_DOTNET
    if _encontrar_marcador(ruta, _MARCADORES_MAVEN):
        return _COMANDO_PRUEBAS_MAVEN
    if _encontrar_marcador(ruta, _MARCADORES_GRADLE):
        return _COMANDO_PRUEBAS_GRADLE
    return _COMANDO_PRUEBAS_PYTEST


def _detectar_comando_cobertura(ruta: str) -> str:
    """Elige el comando de cobertura según el tipo de proyecto (T073)."""
    if _encontrar_marcador(ruta, _MARCADORES_DOTNET):
        return _COMANDO_COBERTURA_DOTNET
    if _encontrar_marcador(ruta, _MARCADORES_MAVEN):
        return _COMANDO_COBERTURA_MAVEN
    return _COMANDO_COBERTURA_PYTEST
