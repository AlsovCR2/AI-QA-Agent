"""Tests de validación de contratos de herramientas (T019, FR-005).

Cubre `validar_resultado` (T006): resultado válido → True, resultado inválido
(estructura/tipo erróneo) → False sin excepciones no controladas.
"""

from __future__ import annotations

from qa_agent.tools.base import (
    EstadoResultado,
    ResultadoDeHerramienta,
    validar_resultado,
)


class _Herramienta:
    """Herramienta mínima de prueba con esquema de salida conocido."""

    id = "test"
    nombre = "test"
    descripcion = "herramienta de prueba"
    esquema_salida = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "existe": {"type": "boolean"},
        },
        "required": ["ruta", "existe"],
    }


HER = _Herramienta()


def test_resultado_valido_devuelve_true():
    resultado = ResultadoDeHerramienta(
        herramienta_id="test",
        estado=EstadoResultado.EXITO,
        datos={"ruta": "src/app.py", "existe": True},
    )
    assert validar_resultado(HER, resultado) is True


def test_resultado_con_tipo_incorrecto_devuelve_false():
    """`existe` con tipo esperable boolean a string → inválido (SC-005)."""
    resultado = ResultadoDeHerramienta(
        herramienta_id="test",
        estado=EstadoResultado.EXITO,
        datos={"ruta": "src/app.py", "existe": "NO_ES_BOOLEANO"},
    )
    assert validar_resultado(HER, resultado) is False


def test_resultado_faltante_campo_required_devuelve_false():
    resultado = ResultadoDeHerramienta(
        herramienta_id="test",
        estado=EstadoResultado.EXITO,
        datos={"ruta": "src/app.py"},
    )
    assert validar_resultado(HER, resultado) is False


def test_resultado_estructura_no_dict_devuelve_false():
    resultado = ResultadoDeHerramienta(
        herramienta_id="test",
        estado=EstadoResultado.EXITO,
        datos=[1, 2, 3],  # object esperado
    )
    assert validar_resultado(HER, resultado) is False


def test_resultado_en_estado_error_devuelve_false():
    """El agente NO presenta como válido un resultado en estado error."""
    resultado = ResultadoDeHerramienta(
        herramienta_id="test",
        estado=EstadoResultado.ERROR,
        datos={"ruta": "src/app.py", "existe": True},
        error="boom",
    )
    assert validar_resultado(HER, resultado) is False