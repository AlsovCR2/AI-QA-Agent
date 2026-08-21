"""El modelo debe poder saber qué comandos puede pedir (FR-025 / SC-011 / IV).

La allowlist de `run_tests` y `analyze_coverage` es un conjunto CERRADO de
cadenas exactas. El esquema de entrada solo daba dos ejemplos, así que el
modelo proponía comandos razonables pero inválidos —`pytest tests/x.py`,
`pytest --cov=calculadora --cov-report=term`— que se rechazaban siempre.

Observado contra Gemini el 2026-08-21: en cada corrida de análisis se perdían
uno o dos pasos del presupuesto en comandos rechazados, y desde que un fallo de
herramienta degrada la confianza (FR-018), esos rechazos dejaban en `limitada`
análisis que por lo demás eran correctos.

Exponer la allowlist como `enum` NO amplía el perímetro: la validación real
sigue estando en `_validar_comando`. Lo que cambia es que el modelo deja de
adivinar. Estos tests fijan que ambas listas no puedan divergir.
"""

from __future__ import annotations

from qa_agent.tools.analyze_coverage import (
    _COMANDOS_COBERTURA_PERMITIDOS,
    AnalyzeCoverageHerramienta,
)
from qa_agent.tools.run_tests import _COMANDOS_PERMITIDOS, RunTestsHerramienta


def _enum_de(herramienta, campo: str) -> list[str]:
    return herramienta.esquema_entrada["properties"][campo]["enum"]


def test_el_enum_de_run_tests_es_exactamente_la_allowlist():
    """Si divergen, el modelo pide comandos que se rechazan (o al revés)."""
    assert set(_enum_de(RunTestsHerramienta([]), "comando_pruebas")) == set(
        _COMANDOS_PERMITIDOS
    )


def test_el_enum_de_analyze_coverage_es_exactamente_la_allowlist():
    assert set(
        _enum_de(AnalyzeCoverageHerramienta([]), "comando_cobertura")
    ) == set(_COMANDOS_COBERTURA_PERMITIDOS)


def test_los_comandos_expuestos_son_realmente_aceptados():
    """Cada comando anunciado tiene que pasar la validación real.

    Anunciar un comando que luego se rechaza sería peor que no anunciarlo.
    """
    herramienta = RunTestsHerramienta([])
    for comando in _enum_de(herramienta, "comando_pruebas"):
        assert herramienta._validar_comando(comando), comando


def test_un_comando_con_argumentos_extra_sigue_rechazandose():
    """El `enum` documenta; no relaja la validación (SC-011 / IV)."""
    herramienta = RunTestsHerramienta([])

    assert not herramienta._validar_comando("pytest tests/test_x.py")
    assert not herramienta._validar_comando("pytest --cov=src")
    assert not herramienta._validar_comando("pytest && rm -rf /")


def test_la_descripcion_avisa_de_que_no_admite_argumentos():
    descripcion = RunTestsHerramienta([]).esquema_entrada["properties"][
        "comando_pruebas"
    ]["description"]

    assert "EXACTO" in descripcion
