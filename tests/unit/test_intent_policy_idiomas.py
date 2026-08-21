"""Detección de intención en inglés y no-regresión en español (T226 / FR-128).

El informe señalaba que las tablas de intención eran listas de frases en
español compiladas en el código, y que una pregunta en inglés no se enrutaba.
El fallo era silencioso: el agente respondía igual, solo que sin ampliar el
presupuesto de pasos ni enriquecer el plan por capa, así que la respuesta salía
más pobre sin ninguna señal de por qué.

Estas pruebas están parametrizadas a propósito: añadir una frase debe ser
añadir una fila, no escribir un test nuevo.
"""

from __future__ import annotations

import pytest

from qa_agent.agent.intent_policy import (
    _es_analisis_global,
    _es_intencion_pruebas,
)

_ANALISIS_GLOBAL_ES = (
    "analiza el proyecto",
    "analiza la estructura del proyecto",
    "¿cuál es la estructura del proyecto?",
    "explica la arquitectura",
)

_ANALISIS_GLOBAL_EN = (
    "analyze the project",
    "analyze the codebase",
    "explain the architecture",
    "how is the project organized?",
    "give me an overview of the project",
    "walk me through the project",
)

_PRUEBAS_ES = (
    "¿qué tipo de pruebas podemos aplicar?",
    "qué casos de prueba sugieres",
    "estrategia de pruebas",
)

_PRUEBAS_EN = (
    "what kind of tests should we write?",
    "suggest tests for this module",
    "what is the testing strategy?",
    "test cases for the login flow",
)

_NO_SON_ANALISIS_GLOBAL = (
    "lee el archivo config.py",
    "read the file config.py",
    "borra el archivo temporal",
    "hola, ¿qué tal?",
)

_NO_SON_PRUEBAS = (
    "explora la estructura",
    "read the readme",
    "elimina el directorio build",
)


# --- No regresión: el español sigue funcionando exactamente igual ---------


@pytest.mark.parametrize("texto", _ANALISIS_GLOBAL_ES)
def test_analisis_global_en_espanol(texto):
    assert _es_analisis_global(texto) is True


@pytest.mark.parametrize("texto", _PRUEBAS_ES)
def test_intencion_de_pruebas_en_espanol(texto):
    assert _es_intencion_pruebas(texto) is True


# --- Cobertura nueva: inglés ----------------------------------------------


@pytest.mark.parametrize("texto", _ANALISIS_GLOBAL_EN)
def test_analisis_global_en_ingles(texto):
    assert _es_analisis_global(texto) is True


@pytest.mark.parametrize("texto", _PRUEBAS_EN)
def test_intencion_de_pruebas_en_ingles(texto):
    assert _es_intencion_pruebas(texto) is True


# --- Falsos positivos ------------------------------------------------------


@pytest.mark.parametrize("texto", _NO_SON_ANALISIS_GLOBAL)
def test_no_confunde_otras_intenciones_con_analisis_global(texto):
    assert _es_analisis_global(texto) is False


@pytest.mark.parametrize("texto", _NO_SON_PRUEBAS)
def test_no_confunde_otras_intenciones_con_pruebas(texto):
    assert _es_intencion_pruebas(texto) is False


# --- Propiedades del detector ---------------------------------------------


@pytest.mark.parametrize("texto", _ANALISIS_GLOBAL_ES + _ANALISIS_GLOBAL_EN)
def test_la_deteccion_es_insensible_a_mayusculas(texto):
    assert _es_analisis_global(texto.upper()) is _es_analisis_global(texto)


def test_texto_vacio_no_dispara_nada():
    assert _es_analisis_global("") is False
    assert _es_intencion_pruebas("") is False


@pytest.mark.parametrize("texto", _ANALISIS_GLOBAL_EN)
def test_la_deteccion_es_determinista(texto):
    """VI: la misma entrada siempre da el mismo veredicto."""
    assert len({_es_analisis_global(texto) for _ in range(5)}) == 1
