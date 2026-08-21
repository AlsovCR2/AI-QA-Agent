"""Detección determinista del runner de pruebas/cobertura por tipo de proyecto.

Extraído de `agent/loop.py` (I01, ADR-001) como movimiento puro. Desde T225 la
política concreta —qué manifiestos identifican qué ecosistema y qué comando le
corresponde— vive en `tools/runner_registry.py`, que la expresa como datos en
vez de como una cadena de condicionales. Este módulo se conserva como la
fachada que el bucle ya consumía, para no cambiar sus puntos de llamada
(FR-122 / ADR-009).

Todos los comandos devueltos están dentro de las allowlists de
`run_tests`/`analyze_coverage` (FR-025 / FR-123); este módulo solo decide CUÁL
comando usar, nunca ejecuta nada.
"""

from __future__ import annotations

from qa_agent.tools.runner_registry import (
    ECOSISTEMA_POR_DEFECTO,
    comando_de_cobertura,
    comando_de_pruebas,
    detectar_ecosistema,
)

__all__ = [
    "_detectar_comando_pruebas",
    "_detectar_comando_cobertura",
    "detectar_ecosistema",
]


def _detectar_comando_pruebas(ruta: str) -> str:
    """Comando de pruebas del ecosistema detectado (T073 / T225)."""
    return comando_de_pruebas(ruta)


def _detectar_comando_cobertura(ruta: str) -> str:
    """Comando de cobertura del ecosistema detectado (T073 / T225).

    El registro puede devolver `None` para un ecosistema sin comando de
    cobertura conocido (Gradle, Rust). El bucle espera siempre una cadena, así
    que aquí se degrada al comando por defecto: la herramienta lo rechazará o
    reportará `reporte_no_encontrado` con causa explícita, que es preferible a
    propagar `None` hasta un punto donde el error sería menos legible (IX).
    """
    return comando_de_cobertura(ruta) or ECOSISTEMA_POR_DEFECTO.cobertura or ""
