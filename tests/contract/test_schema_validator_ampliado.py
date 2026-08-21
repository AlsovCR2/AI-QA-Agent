"""Palabras clave añadidas al validador de esquemas (T212 / FR-127).

ADR-002 decidió conservar el validador propio en vez de adoptar `jsonschema`,
tras verificar con 92 casos que cubría los esquemas reales. Esta ampliación
mantiene esa decisión y cierra el hueco que el informe señalaba:
`additionalProperties`, `pattern`, `oneOf`/`anyOf` y los límites de longitud.

La invariante que protege el trabajo anterior es
`test_ningun_esquema_real_declara_las_palabras_nuevas`: mientras eso se cumpla,
la ampliación no puede cambiar el veredicto de ningún contrato existente.
"""

from __future__ import annotations

import pytest

from qa_agent.tools import (
    AnalyzeCoverageHerramienta,
    AnalyzeTestResultsHerramienta,
    CrearArchivoHerramienta,
    EditarArchivoHerramienta,
    EliminarArchivoHerramienta,
    ExploreHerramienta,
    GenerateTestCasesHerramienta,
    LeerArchivoHerramienta,
    LocateHerramienta,
    RunTestsHerramienta,
    SearchHerramienta,
)
from qa_agent.tools.base import explicar_incumplimiento, validar_resultado_esquema

_PALABRAS_NUEVAS = (
    "additionalProperties",
    "pattern",
    "oneOf",
    "anyOf",
    "allOf",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
)


# Las 11 herramientas registradas, igual que la suite de compatibilidad de
# ADR-002. Se listan explícitamente para que añadir una herramienta obligue a
# revisar esta invariante en vez de ampliarla en silencio.
TODAS_LAS_HERRAMIENTAS = (
    ExploreHerramienta,
    LocateHerramienta,
    SearchHerramienta,
    RunTestsHerramienta,
    AnalyzeTestResultsHerramienta,
    GenerateTestCasesHerramienta,
    AnalyzeCoverageHerramienta,
    LeerArchivoHerramienta,
    CrearArchivoHerramienta,
    EditarArchivoHerramienta,
    EliminarArchivoHerramienta,
)


def _palabras_en(esquema, encontradas=None):
    encontradas = encontradas if encontradas is not None else set()
    if isinstance(esquema, dict):
        for clave, valor in esquema.items():
            if clave in _PALABRAS_NUEVAS:
                encontradas.add(clave)
            _palabras_en(valor, encontradas)
    elif isinstance(esquema, list):
        for elemento in esquema:
            _palabras_en(elemento, encontradas)
    return encontradas


# --- Invariante de no regresión -------------------------------------------


def test_ningun_esquema_real_declara_las_palabras_nuevas():
    """Si esto falla, la ampliación SÍ puede haber cambiado un veredicto."""
    for clase in TODAS_LAS_HERRAMIENTAS:
        for esquema in (clase.esquema_entrada, clase.esquema_salida):
            assert _palabras_en(esquema) == set(), clase.id


# --- additionalProperties --------------------------------------------------


def test_additional_properties_false_rechaza_extras():
    esquema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "additionalProperties": False,
    }

    assert validar_resultado_esquema({"a": "x"}, esquema) is True
    assert validar_resultado_esquema({"a": "x", "b": 1}, esquema) is False


def test_additional_properties_como_esquema_valida_los_extras():
    esquema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "additionalProperties": {"type": "integer"},
    }

    assert validar_resultado_esquema({"a": "x", "b": 1}, esquema) is True
    assert validar_resultado_esquema({"a": "x", "b": "no"}, esquema) is False


def test_sin_additional_properties_los_extras_se_admiten():
    """Comportamiento previo: los campos aditivos no invalidan (FR-109)."""
    esquema = {"type": "object", "properties": {"a": {"type": "string"}}}

    assert validar_resultado_esquema({"a": "x", "b": 1}, esquema) is True


# --- pattern ---------------------------------------------------------------


def test_pattern_acepta_y_rechaza():
    esquema = {"type": "string", "pattern": r"^v\d+\.\d+$"}

    assert validar_resultado_esquema("v1.0", esquema) is True
    assert validar_resultado_esquema("versión uno", esquema) is False


def test_pattern_mal_formado_rechaza_en_vez_de_aceptar_por_descarte():
    """Un esquema roto nunca debe traducirse en 'todo vale'."""
    esquema = {"type": "string", "pattern": "["}

    assert validar_resultado_esquema("cualquier cosa", esquema) is False


# --- Longitudes y cardinalidades ------------------------------------------


@pytest.mark.parametrize(
    "valor,esperado", [("ab", False), ("abc", True), ("abcde", True), ("abcdef", False)]
)
def test_min_y_max_length(valor, esperado):
    esquema = {"type": "string", "minLength": 3, "maxLength": 5}

    assert validar_resultado_esquema(valor, esquema) is esperado


@pytest.mark.parametrize(
    "valor,esperado", [([], False), ([1], True), ([1, 2], True), ([1, 2, 3], False)]
)
def test_min_y_max_items(valor, esperado):
    esquema = {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 2}

    assert validar_resultado_esquema(valor, esquema) is esperado


# --- Combinadores ----------------------------------------------------------


def test_any_of_basta_con_una_rama():
    esquema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}

    assert validar_resultado_esquema("x", esquema) is True
    assert validar_resultado_esquema(3, esquema) is True
    assert validar_resultado_esquema([], esquema) is False


def test_one_of_exige_exactamente_una_rama():
    # Un entero cumple `integer` Y `number`: dos ramas → oneOf falla.
    ambigua = {"oneOf": [{"type": "integer"}, {"type": "number"}]}
    exclusiva = {"oneOf": [{"type": "string"}, {"type": "integer"}]}

    assert validar_resultado_esquema(3, ambigua) is False
    assert validar_resultado_esquema(3, exclusiva) is True
    assert validar_resultado_esquema([], exclusiva) is False


def test_all_of_exige_todas_las_ramas():
    esquema = {
        "allOf": [
            {"type": "object", "required": ["a"]},
            {"type": "object", "required": ["b"]},
        ]
    }

    assert validar_resultado_esquema({"a": 1, "b": 2}, esquema) is True
    assert validar_resultado_esquema({"a": 1}, esquema) is False


# --- Motivos de rechazo (FR-127) ------------------------------------------


def test_un_objeto_valido_no_produce_motivos():
    assert explicar_incumplimiento({"a": "x"}, {"type": "object", "required": ["a"]}) == []


def test_el_motivo_nombra_la_propiedad_que_falta():
    motivos = explicar_incumplimiento({}, {"type": "object", "required": ["ruta"]})

    assert motivos
    assert "ruta" in motivos[0]


def test_el_motivo_localiza_el_campo_anidado():
    esquema = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {"type": "object", "required": ["id"]}}
        },
    }

    motivos = explicar_incumplimiento({"items": [{"id": 1}, {}]}, esquema)

    assert any("items[1]" in m for m in motivos)


def test_explicar_nunca_lanza_ante_entradas_absurdas():
    assert explicar_incumplimiento(None, None) != []
    assert explicar_incumplimiento(object(), {"type": "object"}) != []


def test_explicar_y_validar_coinciden_siempre():
    """Dos caminos, un solo veredicto: no pueden divergir."""
    casos = [
        ({"a": "x"}, {"type": "object", "required": ["a"]}),
        ({}, {"type": "object", "required": ["a"]}),
        ("v1.0", {"type": "string", "pattern": r"^v\d+\.\d+$"}),
        ("nope", {"type": "string", "pattern": r"^v\d+\.\d+$"}),
        (3, {"oneOf": [{"type": "string"}, {"type": "integer"}]}),
    ]

    for datos, esquema in casos:
        assert validar_resultado_esquema(datos, esquema) == (
            explicar_incumplimiento(datos, esquema) == []
        )
