"""Tests del historial visible de `Sesion` (T020, FR-020 / SC-007 / SC-008).

Tras registrar 2+ acciones, el historial mantiene el orden por `orden`, y los
secretos se redactan antes de exponerse en entrada/salida.
"""

from __future__ import annotations

from qa_agent.agent.response import EstadoAccion
from qa_agent.agent.session import Sesion


def _accion_con_secreto(denominacion: str) -> dict[str, object]:
    return {"token": f"sk-{denominacion}1234567890", "clave": "valor"}


def test_historial_mantiene_orden_tras_dos_acciones(redactor):
    sesion = Sesion(redactor)
    sesion.agregar_accion(
        "search", {"patron": "config()"}, {"ocurrencias": []}, EstadoAccion.EXITO
    )
    sesion.agregar_accion(
        "locate", {"patron": "main"}, {"coincidencias": []}, EstadoAccion.EXITO
    )
    assert [a.orden for a in sesion.acciones] == [1, 2]
    assert sesion.acciones[0].herramienta_id == "search"
    assert sesion.acciones[1].herramienta_id == "locate"


def test_historial_redacta_secretos_antes_de_exponerse(redactor):
    sesion = Sesion(redactor)
    sesion.agregar_accion(
        "run_tests",
        {"conjunto_autorizado": True},
        _accion_con_secreto("salida"),
        EstadoAccion.EXITO,
    )
    registro = sesion.acciones[0]
    # El secreto en `salida` queda redactado como ***
    assert registro.salida["token"] == "***"
    assert "sk-" not in str(registro.salida)


def test_historial_redacta_secretos_en_entrada(redactor):
    sesion = Sesion(redactor)
    entrada_secreta = {"api_key": "api_key=ass:abcdef12345678"}
    sesion.agregar_accion(
        "search",
        entrada_secreta,
        {"occurrencias": []},
        EstadoAccion.EXITO,
    )
    registro = sesion.acciones[0]
    assert "ass:abcdef12345678" not in str(registro.entrada)


def test_orden_sigue_incrementando_con_cada_accion(redactor):
    sesion = Sesion(redactor)
    for _ in range(3):
        sesion.agregar_accion(
            "search", {"p": "x"}, {"o": []}, EstadoAccion.EXITO
        )
    assert [a.orden for a in sesion.acciones] == [1, 2, 3]