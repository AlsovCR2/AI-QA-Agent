"""Suite de compatibilidad del validador de esquemas de herramientas (I03).

Congela el comportamiento observable de `validar_resultado_esquema` /
`_esquema_cumple` (`src/qa_agent/tools/base.py`) frente a los esquemas
REALES declarados por cada herramienta (`esquema_entrada`/`esquema_salida`),
tal como quedan documentados en
`specs/001-core-ai-qa-agent/contracts/tool-contracts.md`.

Objetivo (T-I03, ADR-002): antes de decidir si el validador partial-JSON-Schema
actual necesita reemplazo, esta suite demuestra qué formas de esquema están
realmente en uso (`type`, `properties`, `required`, `items`, `enum`,
`minimum`, `maximum`, anidamiento de objetos/arrays) y verifica que el
validador las trata correctamente y de forma determinista (principio VI).

Si esta suite pasa en su totalidad contra el validador actual, el hallazgo es
que NO hay un problema demostrado que justifique una dependencia nueva
(Pydantic o una librería JSON Schema estándar): ver ADR-002.
"""

from __future__ import annotations

import copy

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
from qa_agent.tools.base import validar_resultado_esquema

# ---------------------------------------------------------------------------
# 1) Objetos válidos: uno por herramienta, entrada Y salida (11 herramientas
#    del catálogo MVP, FR-005/VII).
# ---------------------------------------------------------------------------

_CASOS_VALIDOS: list[tuple[str, dict, dict]] = [
    (
        "explore.entrada",
        ExploreHerramienta.esquema_entrada,
        {"ruta": "C:/proyecto", "profundidad_max": 3},
    ),
    (
        "explore.salida",
        ExploreHerramienta.esquema_salida,
        {
            "ruta": "C:/proyecto",
            "existe": True,
            "accesible": True,
            "elementos": [
                {"nombre": "app.py", "tipo": "archivo", "ruta_relativa": "app.py"},
                {"nombre": "src", "tipo": "directorio", "ruta_relativa": "src"},
            ],
        },
    ),
    (
        "locate.entrada",
        LocateHerramienta.esquema_entrada,
        {"patron": "class .*Test", "ruta": "C:/proyecto", "tipo": "clase"},
    ),
    (
        "locate.salida",
        LocateHerramienta.esquema_salida,
        {
            "coincidencias": [
                {
                    "nombre": "Calculadora",
                    "tipo": "clase",
                    "linea": 10,
                    "ruta_relativa": "src/calc.py",
                }
            ]
        },
    ),
    (
        "search.entrada",
        SearchHerramienta.esquema_entrada,
        {
            "patron_regex": "def .*",
            "ruta": "C:/proyecto",
            "contexto_lineas": 3,
            "max_ocurrencias": 200,
        },
    ),
    (
        "search.salida",
        SearchHerramienta.esquema_salida,
        {
            "ocurrencias": [
                {"ruta_relativa": "src/app.py", "linea": 5, "contexto": "def f():"}
            ],
            "nota": "Se limitó la búsqueda a 200 ocurrencias.",
        },
    ),
    (
        "run_tests.entrada",
        RunTestsHerramienta.esquema_entrada,
        {"ruta": "C:/proyecto", "conjunto_autorizado": True, "comando_pruebas": "pytest"},
    ),
    (
        "run_tests.salida",
        RunTestsHerramienta.esquema_salida,
        {
            "pasadas": 4,
            "falladas": 1,
            "errores": 0,
            "total": 5,
            "estado_global": "fallo",
            "detalle_fallos": [
                {
                    "nombre": "test_suma",
                    "mensaje_error": "AssertionError",
                    "ruta_relativa": "tests/test_calc.py",
                }
            ],
        },
    ),
    (
        "analyze_test_results.entrada",
        AnalyzeTestResultsHerramienta.esquema_entrada,
        {
            "ruta": "C:/proyecto",
            "resultado_tests": {
                "pasadas": 4,
                "falladas": 1,
                "errores": 0,
                "total": 5,
                "estado_global": "fallo",
                "detalle_fallos": [
                    {
                        "nombre": "test_suma",
                        "mensaje_error": "AssertionError",
                        "ruta_relativa": "tests/test_calc.py",
                    }
                ],
            },
        },
    ),
    (
        "analyze_test_results.salida",
        AnalyzeTestResultsHerramienta.esquema_salida,
        {
            "resumen": "Resumen: 4 pasadas, 1 falladas de 5 total. Estado global: fallo.",
            "fallos_agrupados": [
                {
                    "ruta_relativa": "tests/test_calc.py",
                    "error_comun": "AssertionError",
                    "posible_causa": "sin evidencia suficiente para determinar causa",
                }
            ],
        },
    ),
    (
        "generate_test_cases.entrada",
        GenerateTestCasesHerramienta.esquema_entrada,
        {"ruta": "C:/proyecto", "objetivo": "suma", "cripticidad": "happy_path"},
    ),
    (
        "generate_test_cases.salida",
        GenerateTestCasesHerramienta.esquema_salida,
        {
            "casos_propuestos": [
                {
                    "descripcion": "Caso básico para suma",
                    "entrada_esperada": "suma(1, 2)",
                    "resultado_esperado": "3",
                    "tipo": "happy_path",
                }
            ],
            "fuentes": ["src/calc.py"],
        },
    ),
    (
        "analyze_coverage.entrada",
        AnalyzeCoverageHerramienta.esquema_entrada,
        {"ruta": "C:/proyecto", "comando_cobertura": "pytest --cov=src"},
    ),
    (
        "analyze_coverage.salida",
        AnalyzeCoverageHerramienta.esquema_salida,
        {
            "cobertura_global": 87.5,
            "por_archivo": [
                {
                    "ruta_relativa": "src/calc.py",
                    "cobertura": 90.0,
                    "lineas_faltantes": [12, 13, 40],
                }
            ],
            "estado": "exito",
        },
    ),
    (
        "leer_archivo.entrada",
        LeerArchivoHerramienta.esquema_entrada,
        {"ruta": "C:/proyecto", "archivo_relativo": "src/app.py", "max_lineas": 200},
    ),
    (
        "leer_archivo.salida",
        LeerArchivoHerramienta.esquema_salida,
        {
            "archivo": "src/app.py",
            "existe": True,
            "total_lineas": 42,
            "contenido": "print('hola')\n",
            "truncado": False,
        },
    ),
    (
        "crear_archivo.entrada",
        CrearArchivoHerramienta.esquema_entrada,
        {"ruta": "C:/proyecto", "archivo_relativo": "src/nuevo.py", "contenido": "x = 1\n"},
    ),
    (
        "crear_archivo.salida",
        CrearArchivoHerramienta.esquema_salida,
        {"archivo": "src/nuevo.py", "creado": True, "existia": False},
    ),
    (
        "editar_archivo.entrada",
        EditarArchivoHerramienta.esquema_entrada,
        {"ruta": "C:/proyecto", "archivo_relativo": "src/app.py", "contenido": "x = 2\n"},
    ),
    (
        "editar_archivo.salida",
        EditarArchivoHerramienta.esquema_salida,
        {
            "archivo": "src/app.py",
            "editado": True,
            "existia": True,
            "backup": ".qa-backup/src/app.py.bak",
        },
    ),
    (
        "eliminar_archivo.entrada",
        EliminarArchivoHerramienta.esquema_entrada,
        {"ruta": "C:/proyecto", "archivo_relativo": "src/viejo.py"},
    ),
    (
        "eliminar_archivo.salida",
        EliminarArchivoHerramienta.esquema_salida,
        {
            "archivo": "src/viejo.py",
            "eliminado": True,
            "backup": ".qa-backup/src/viejo.py.bak",
        },
    ),
]


@pytest.mark.parametrize("caso_id,esquema,datos", _CASOS_VALIDOS, ids=[c[0] for c in _CASOS_VALIDOS])
def test_objeto_valido_pasa_para_cada_herramienta(caso_id, esquema, datos):
    assert validar_resultado_esquema(datos, esquema) is True, caso_id


# ---------------------------------------------------------------------------
# 2) Campos `required` faltantes → False (para varias herramientas).
# ---------------------------------------------------------------------------


def test_falta_campo_required_top_level():
    """`crear_archivo.entrada` exige `contenido`; sin él, inválido."""
    datos = {"ruta": "C:/proyecto", "archivo_relativo": "a.py"}
    assert validar_resultado_esquema(datos, CrearArchivoHerramienta.esquema_entrada) is False


def test_falta_campo_required_en_salida_run_tests():
    datos = {
        "pasadas": 1,
        "falladas": 0,
        "errores": 0,
        # falta "total"
        "estado_global": "exito",
        "detalle_fallos": [],
    }
    assert validar_resultado_esquema(datos, RunTestsHerramienta.esquema_salida) is False


def test_falta_campo_required_anidado_en_items():
    """Un elemento de `detalle_fallos` sin `mensaje_error` es inválido
    (el `required` de los `items` se aplica a cada elemento del array)."""
    datos = {
        "pasadas": 1,
        "falladas": 1,
        "errores": 0,
        "total": 2,
        "estado_global": "fallo",
        "detalle_fallos": [
            {"nombre": "test_x", "ruta_relativa": "tests/test_x.py"}  # sin mensaje_error
        ],
    }
    assert validar_resultado_esquema(datos, RunTestsHerramienta.esquema_salida) is False


def test_falta_campo_required_resultado_tests_anidado():
    """`analyze_test_results.entrada` exige `resultado_tests.estado_global`."""
    datos = {
        "ruta": "C:/proyecto",
        "resultado_tests": {
            "pasadas": 1,
            "falladas": 0,
            "errores": 0,
            "total": 1,
            # falta "estado_global"
            "detalle_fallos": [],
        },
    }
    assert (
        validar_resultado_esquema(datos, AnalyzeTestResultsHerramienta.esquema_entrada)
        is False
    )


# ---------------------------------------------------------------------------
# 3) Tipos inválidos → False (string/int/bool/number/array/object).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "datos",
    [
        {"ruta": 123, "profundidad_max": 3},  # ruta no es string
        {"ruta": "C:/proyecto", "profundidad_max": "3"},  # profundidad_max no es int
        {"ruta": "C:/proyecto", "profundidad_max": 3.5},  # float no es integer válido
        {"ruta": "C:/proyecto", "profundidad_max": True},  # bool no es integer (excluido)
    ],
)
def test_tipo_invalido_en_entrada_explore(datos):
    assert validar_resultado_esquema(datos, ExploreHerramienta.esquema_entrada) is False


def test_tipo_invalido_objeto_raiz_no_es_dict():
    """Estructura raíz no-dict cuando se espera `object` → False (SC-005)."""
    assert validar_resultado_esquema([1, 2, 3], ExploreHerramienta.esquema_salida) is False
    assert validar_resultado_esquema("no es un dict", ExploreHerramienta.esquema_salida) is False
    assert validar_resultado_esquema(None, ExploreHerramienta.esquema_salida) is False


def test_tipo_invalido_boolean_no_es_string():
    datos = {"archivo": True, "eliminado": True, "backup": "x"}
    assert validar_resultado_esquema(datos, EliminarArchivoHerramienta.esquema_salida) is False


# ---------------------------------------------------------------------------
# 4) Arrays / `items` — válidos e inválidos, incluyendo anidamiento real
#    (`analyze_coverage.por_archivo[].lineas_faltantes` es un array de enteros
#    dentro de un array de objetos).
# ---------------------------------------------------------------------------


def test_items_de_array_se_validan_individualmente():
    """Si UN elemento del array de `elementos` tiene un campo de tipo
    incorrecto, el objeto completo es inválido (no solo ese elemento)."""
    datos = {
        "ruta": "C:/proyecto",
        "existe": True,
        "accesible": True,
        "elementos": [
            {"nombre": "app.py", "tipo": "archivo", "ruta_relativa": "app.py"},
            {"nombre": "raro.py", "tipo": "no_es_un_tipo_valido", "ruta_relativa": "raro.py"},
        ],
    }
    assert validar_resultado_esquema(datos, ExploreHerramienta.esquema_salida) is False


def test_items_array_vacio_es_valido():
    """Un array vacío siempre satisface el esquema de `items` (vacuamente)."""
    datos = {"coincidencias": []}
    assert validar_resultado_esquema(datos, LocateHerramienta.esquema_salida) is True


def test_items_array_de_arrays_anidado_valido():
    """`lineas_faltantes` (array de enteros) anidado dentro de `por_archivo`
    (array de objetos) — dos niveles de `items`."""
    datos = {
        "cobertura_global": 50.0,
        "por_archivo": [
            {"ruta_relativa": "a.py", "cobertura": 100.0, "lineas_faltantes": []},
            {"ruta_relativa": "b.py", "cobertura": 0.0, "lineas_faltantes": [1, 2, 3]},
        ],
        "estado": "exito",
    }
    assert validar_resultado_esquema(datos, AnalyzeCoverageHerramienta.esquema_salida) is True


def test_items_array_de_arrays_anidado_invalido():
    """`lineas_faltantes` con un elemento no-entero → inválido."""
    datos = {
        "cobertura_global": 50.0,
        "por_archivo": [
            {"ruta_relativa": "b.py", "cobertura": 0.0, "lineas_faltantes": [1, "2", 3]},
        ],
        "estado": "exito",
    }
    assert validar_resultado_esquema(datos, AnalyzeCoverageHerramienta.esquema_salida) is False


def test_campo_no_array_donde_se_espera_array():
    datos = {"coincidencias": "no es una lista"}
    assert validar_resultado_esquema(datos, LocateHerramienta.esquema_salida) is False


# ---------------------------------------------------------------------------
# 5) `enum` — valores dentro y fuera del conjunto permitido.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cripticidad,esperado",
    [
        ("happy_path", True),
        ("edge_cases", True),
        ("usuarios_no_validos", True),
        ("valor_no_permitido", False),
        ("", False),
    ],
)
def test_enum_cripticidad_generate_test_cases(cripticidad, esperado):
    datos = {"ruta": "C:/proyecto", "objetivo": "suma", "cripticidad": cripticidad}
    assert (
        validar_resultado_esquema(datos, GenerateTestCasesHerramienta.esquema_entrada)
        is esperado
    )


@pytest.mark.parametrize(
    "estado_global,esperado",
    [("exito", True), ("fallo", True), ("no_ejecutado", True), ("parcial", False)],
)
def test_enum_estado_global_run_tests(estado_global, esperado):
    datos = {
        "pasadas": 0,
        "falladas": 0,
        "errores": 0,
        "total": 0,
        "estado_global": estado_global,
        "detalle_fallos": [],
    }
    assert validar_resultado_esquema(datos, RunTestsHerramienta.esquema_salida) is esperado


def test_enum_anidado_en_items_de_array():
    """El `enum` de `tipo` dentro de cada elemento de `elementos` se aplica."""
    datos_invalido = {
        "ruta": "C:/proyecto",
        "existe": True,
        "accesible": True,
        "elementos": [{"nombre": "x", "tipo": "carpeta_inventada", "ruta_relativa": "x"}],
    }
    assert validar_resultado_esquema(datos_invalido, ExploreHerramienta.esquema_salida) is False


# ---------------------------------------------------------------------------
# 6) `minimum` / `maximum`.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "profundidad,esperado",
    [(1, True), (8, True), (0, False), (9, False), (-1, False)],
)
def test_minimum_maximum_profundidad_max(profundidad, esperado):
    datos = {"ruta": "C:/proyecto", "profundidad_max": profundidad}
    assert validar_resultado_esquema(datos, ExploreHerramienta.esquema_entrada) is esperado


@pytest.mark.parametrize(
    "max_lineas,esperado",
    [(1, True), (1000, True), (0, False), (1001, False)],
)
def test_minimum_maximum_max_lineas_leer_archivo(max_lineas, esperado):
    datos = {"ruta": "C:/proyecto", "archivo_relativo": "a.py", "max_lineas": max_lineas}
    assert validar_resultado_esquema(datos, LeerArchivoHerramienta.esquema_entrada) is esperado


@pytest.mark.parametrize(
    "contexto_lineas,esperado",
    [(0, True), (20, True), (-1, False), (21, False)],
)
def test_minimum_maximum_contexto_lineas_search(contexto_lineas, esperado):
    datos = {
        "patron_regex": "x",
        "ruta": "C:/proyecto",
        "contexto_lineas": contexto_lineas,
    }
    assert validar_resultado_esquema(datos, SearchHerramienta.esquema_entrada) is esperado


def test_maximum_no_se_aplica_a_valores_no_numericos():
    """`minimum`/`maximum` solo restringen valores numéricos (no strings)."""
    datos = {"ruta": "C:/proyecto", "archivo_relativo": "a.py", "max_lineas": 5}
    assert validar_resultado_esquema(datos, LeerArchivoHerramienta.esquema_entrada) is True


# ---------------------------------------------------------------------------
# 7) Comportamiento determinista (principio VI): misma entrada -> mismo
#    resultado, sin importar el orden de las claves del dict ni repeticiones.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("caso_id,esquema,datos", _CASOS_VALIDOS, ids=[c[0] for c in _CASOS_VALIDOS])
def test_resultado_es_deterministico_en_repeticion(caso_id, esquema, datos):
    resultados = {validar_resultado_esquema(copy.deepcopy(datos), esquema) for _ in range(5)}
    assert resultados == {True}, caso_id


def test_resultado_es_deterministico_ante_reordenamiento_de_claves():
    datos_orden_a = {"archivo": "x.py", "creado": True, "existia": False}
    datos_orden_b = {"existia": False, "creado": True, "archivo": "x.py"}
    resultado_a = validar_resultado_esquema(datos_orden_a, CrearArchivoHerramienta.esquema_salida)
    resultado_b = validar_resultado_esquema(datos_orden_b, CrearArchivoHerramienta.esquema_salida)
    assert resultado_a == resultado_b is True


def test_validacion_no_muta_los_datos_ni_el_esquema():
    """La validación es de solo lectura: no debe modificar `datos` ni `esquema`
    (requisito implícito de determinismo/pureza, VI)."""
    esquema = copy.deepcopy(ExploreHerramienta.esquema_salida)
    datos = {
        "ruta": "C:/proyecto",
        "existe": True,
        "accesible": True,
        "elementos": [{"nombre": "a", "tipo": "archivo", "ruta_relativa": "a"}],
    }
    esquema_antes = copy.deepcopy(esquema)
    datos_antes = copy.deepcopy(datos)
    validar_resultado_esquema(datos, esquema)
    assert datos == datos_antes
    assert esquema == esquema_antes


# ---------------------------------------------------------------------------
# 8) Robustez ante estructuras/esquemas malformados: nunca lanza excepción,
#    siempre devuelve `False` (FR-005 / SC-010).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "esquema_malformado",
    [
        None,
        "no es un dict",
        123,
        [],
    ],
)
def test_esquema_malformado_no_lanza_excepcion(esquema_malformado):
    assert validar_resultado_esquema({"a": 1}, esquema_malformado) is False


def test_datos_none_contra_esquema_object_no_lanza_excepcion():
    assert validar_resultado_esquema(None, ExploreHerramienta.esquema_salida) is False


def test_esquema_con_properties_malformado_no_lanza_excepcion():
    """`properties` con un tipo no iterable-como-dict (p. ej. un string) no
    debe propagar una excepción no controlada; el docstring de
    `validar_resultado_esquema` promete precisamente esto (FR-005/SC-010).
    Ningún esquema real de una herramienta del catálogo cae en este caso
    (todas declaran `properties` como dict literal), pero la función debe
    cumplir su propio contrato de robustez ante estructuras inválidas."""
    esquema = {"type": "object", "properties": "no_es_un_dict", "required": []}
    assert validar_resultado_esquema({"a": 1}, esquema) is False


def test_esquema_con_required_no_iterable_no_lanza_excepcion():
    esquema = {"type": "object", "properties": {}, "required": 123}
    assert validar_resultado_esquema({"a": 1}, esquema) is False
