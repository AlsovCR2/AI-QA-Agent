"""Caracterización de las reglas de intención/capa antes de su extracción (I02).

Congela el comportamiento observable de las tablas de frases y expresiones
regulares que hoy viven embebidas en `agent/loop.py`
(`_FRASES_ANALISIS_GLOBAL`, `_FRASES_INTENCION_PRUEBAS`, verbos/conectores de
capa y los detectores `_es_analisis_global`, `_es_intencion_pruebas`,
`_es_analisis_exhaustivo`, `_es_analisis_capa`, `_extraer_capa_solicitada`,
`_resolver_capa_real`) ANTES de moverlas a módulos enfocados
(`agent/intent_policy.py`, `agent/layer_policy.py`).

Estas funciones ya cuentan con suites propias (`test_profundidad_analisis.py`,
`test_profundidad_capa.py`, `test_intencion_pruebas.py`); este archivo añade
una superficie compacta y estable pensada para ejecutarse igual antes y
después del movimiento (I02 es un movimiento puro: mismos nombres, mismo
comportamiento, solo cambia el módulo de origen). No se añaden frases nuevas
ni se cambia la semántica de ningún regex (Constitution VI / X / XII).
"""

from __future__ import annotations

from qa_agent.agent import intent_policy, layer_policy
from qa_agent.agent.loop import (
    _es_analisis_capa,
    _es_analisis_exhaustivo,
    _es_analisis_global,
    _es_intencion_pruebas,
    _extraer_capa_solicitada,
    _resolver_capa_real,
)


# -- _es_analisis_global: positivos/negativos representativos ----------------


def test_analisis_global_positivos():
    for frase in (
        "analiza el proyecto",
        "analiza la estructura del proyecto",
        "explora la estructura",
        "qué capas hay",
        "cómo está organizado el proyecto",
        "arquitectura del proyecto",
        "  ANALIZA   EL   PROYECTO  ",  # normalización de espacios/mayúsculas
    ):
        assert _es_analisis_global(frase), frase


def test_analisis_global_negativos():
    for frase in (
        "",
        "explora",
        "analiza estos resultados de prueba",
        "ejecuta los tests",
        "lee el archivo config.py",
    ):
        assert not _es_analisis_global(frase), frase


# -- _es_intencion_pruebas -----------------------------------------------------


def test_intencion_pruebas_positivos():
    for frase in (
        "qué tipo de pruebas podemos hacer",
        "qué pruebas recomiendas",
        "estrategia de pruebas",
        "pruebas unitarias",
        "porcentaje de cobertura",
        "define las pruebas unitarias del proyecto",
    ):
        assert _es_intencion_pruebas(frase), frase


def test_intencion_pruebas_negativos():
    for frase in (
        "",
        "ejecuta las pruebas del proyecto",
        "por qué falla el test de reservas",
        "explícame qué pruebas hace tests/test_app.py",
    ):
        assert not _es_intencion_pruebas(frase), frase


# -- _es_analisis_exhaustivo: combinador OR determinista -----------------------


def test_analisis_exhaustivo_es_or_de_global_y_pruebas():
    assert _es_analisis_exhaustivo("analiza el proyecto")
    assert _es_analisis_exhaustivo("qué pruebas podemos aplicar")
    assert not _es_analisis_exhaustivo("identifica dónde aparece BLL")
    assert not _es_analisis_exhaustivo("")


# -- _es_analisis_capa / _extraer_capa_solicitada -------------------------------


def test_analisis_capa_positivos():
    for frase in (
        "Explora completamente todas las clases de la capa DAL",
        "Revisa si existen mas clases en la capa DAL",
        "explora el directorio src",
        "definir las pruebas unitarias de la capa BLL",
    ):
        assert _es_analisis_capa(frase), frase


def test_analisis_capa_negativos():
    for frase in ("analiza el proyecto", "explora la estructura del proyecto", "", "explora"):
        assert not _es_analisis_capa(frase), frase


def test_extraer_capa_solicitada_casos():
    assert _extraer_capa_solicitada("las clases de la capa DAL") == "dal"
    assert _extraer_capa_solicitada("los archivos de la carpeta BLL") == "bll"
    assert _extraer_capa_solicitada("explora el directorio src") == "src"
    assert _extraer_capa_solicitada("la capa de DAL") == "dal"  # T124: salta conectores
    assert _extraer_capa_solicitada("analiza el proyecto") == ""
    assert _extraer_capa_solicitada("") == ""


# -- _resolver_capa_real: resolución determinista contra el filesystem --------


def test_resolver_capa_real_case_insensitive_y_ausente(tmp_path):
    (tmp_path / "DAL").mkdir()
    assert _resolver_capa_real(str(tmp_path), "dal") == "DAL"
    assert _resolver_capa_real(str(tmp_path), "DAL") == "DAL"
    assert _resolver_capa_real(str(tmp_path), "xyz") is None
    assert _resolver_capa_real(str(tmp_path / "no_existe"), "dal") is None


# -- Identidad tras el movimiento: mismas funciones, no reimplementaciones ----
# `loop.py` importa (no reimplementa) estos detectores desde los módulos
# enfocados de I02: `is` prueba que son el mismo objeto función, no una copia
# que pudiera divergir con el tiempo (movimiento puro, Constitution X / XII).


def test_loop_reexporta_los_mismos_objetos_de_intent_policy():
    assert _es_analisis_global is intent_policy._es_analisis_global
    assert _es_intencion_pruebas is intent_policy._es_intencion_pruebas
    assert _es_analisis_exhaustivo is intent_policy._es_analisis_exhaustivo


def test_loop_reexporta_los_mismos_objetos_de_layer_policy():
    assert _es_analisis_capa is layer_policy._es_analisis_capa
    assert _extraer_capa_solicitada is layer_policy._extraer_capa_solicitada
    assert _resolver_capa_real is layer_policy._resolver_capa_real
