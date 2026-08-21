"""Una corrección no puede empeorar lo que no se pidió tocar (FR-043, IX).

Al pedirle "corrige `mediana`", Gemini devolvió el 2026-08-21 una función
CORRECTA que además renombraba el parámetro, borraba el docstring, quitaba las
anotaciones y duplicaba a mano la validación que hacía `_validar`. Las 21
pruebas del proyecto seguían pasando, así que ninguna suite lo veía.

El caso del docstring es el más grave y el más específico: el bug original
existía como una discrepancia ENTRE el docstring y el código. Borrarlo elimina
la especificación que hacía el defecto detectable — arregla el síntoma
destruyendo el detector.

Se comprueba PÉRDIDA, no igualdad: mejorar el docstring o añadir un tipo que
faltaba es legítimo; quitarlos no.
"""

from __future__ import annotations

import pytest

from qa_agent.tools.validacion_sintaxis import reemplazar_funcion

_MODULO = '''"""Módulo."""

from collections.abc import Sequence

Numero = int | float


def _validar(datos: Sequence[Numero]) -> None:
    if not datos:
        raise ValueError("vacía")


def mediana(datos: Sequence[Numero]) -> float:
    """Valor central de `datos`."""
    _validar(datos)
    ordenados = sorted(datos)
    return ordenados[len(ordenados) // 2]
'''

_BUENA = '''def mediana(datos: Sequence[Numero]) -> float:
    """Valor central de `datos`, promediando los dos centrales si son pares."""
    _validar(datos)
    ordenados = sorted(datos)
    medio = len(ordenados) // 2
    if len(ordenados) % 2 == 0:
        return (ordenados[medio - 1] + ordenados[medio]) / 2
    return ordenados[medio]'''


def _error(codigo: str) -> str:
    return reemplazar_funcion(_MODULO, "mediana", codigo)[1]


def test_una_correccion_que_conserva_todo_se_acepta():
    contenido, error = reemplazar_funcion(_MODULO, "mediana", _BUENA)

    assert error == ""
    assert "def _validar" in contenido, "el resto del módulo sigue intacto"


def test_renombrar_un_parametro_se_rechaza():
    """Rompe a quien llame por nombre y ninguna prueba posicional lo ve."""
    error = _error(
        'def mediana(lista: Sequence[Numero]) -> float:\n'
        '    """Valor central."""\n'
        "    _validar(lista)\n"
        "    return sorted(lista)[len(lista) // 2]"
    )

    assert "firma cambió" in error


def test_borrar_el_docstring_se_rechaza():
    error = _error(
        "def mediana(datos: Sequence[Numero]) -> float:\n"
        "    _validar(datos)\n"
        "    return sorted(datos)[len(datos) // 2]"
    )

    assert "docstring" in error


def test_quitar_las_anotaciones_se_rechaza():
    error = _error(
        "def mediana(datos):\n"
        '    """Valor central."""\n'
        "    _validar(datos)\n"
        "    return sorted(datos)[len(datos) // 2]"
    )

    assert "anotaciones de tipo" in error
    assert "datos" in error and "return" in error


def test_dejar_de_usar_un_ayudante_del_modulo_se_rechaza():
    """El caso real: validación duplicada en línea que luego diverge."""
    error = _error(
        "def mediana(datos: Sequence[Numero]) -> float:\n"
        '    """Valor central."""\n'
        "    if not datos:\n"
        '        raise ValueError("otra cosa")\n'
        "    return sorted(datos)[len(datos) // 2]"
    )

    assert "_validar" in error


def test_mejorar_el_docstring_si_se_permite():
    """Se comprueba pérdida, no igualdad."""
    assert (
        _error(
            "def mediana(datos: Sequence[Numero]) -> float:\n"
            '    """Mucho más detallado que antes, con ejemplos y contexto."""\n'
            "    _validar(datos)\n"
            "    return sorted(datos)[len(datos) // 2]"
        )
        == ""
    )


def test_el_codigo_nuevo_debe_definir_la_funcion_pedida():
    error = _error('def otra_cosa(datos):\n    """X."""\n    return 1')

    assert "exactamente una función 'mediana'" in error


@pytest.mark.parametrize(
    "codigo",
    [
        "def mediana(datos: Sequence[Numero]) -> float:\n    return (",
        "def mediana(:\n    pass",
    ],
)
def test_codigo_nuevo_invalido_se_rechaza_antes_de_comparar(codigo):
    assert "no es Python válido" in _error(codigo)
