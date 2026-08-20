"""Tests del gestor de autorización (T042, FR-015/016, UC-006).

Cubre todas las transiciones de la state-machine de `AccionSensible`
(data-model.md #6): `pendiente → autorizada → ejecutada` y
`pendiente → denegada → no_ejecutada`, así como las transiciones inválidas
que se rechazan (nunca se ejecuta una acción no autorizada, SC-004).
"""

from __future__ import annotations

import pytest

from qa_agent.security.authorization import (
    EstadoAutorizacion,
    GestorDeAutorizacion,
)


@pytest.fixture
def gestor() -> GestorDeAutorizacion:
    return GestorDeAutorizacion()


def _crear(gestor: GestorDeAutorizacion, id: str = "a1"):
    return gestor.crear(
        id=id,
        descripcion="Ejecutar run_tests sobre el proyecto",
        herramienta_id="run_tests",
    )


def test_nueva_accion_queda_pendiente_y_no_se_ejecuta(gestor):
    """Acción sensible pendiente → no se ejecuta (FR-016, SC-004)."""
    accion = _crear(gestor)
    assert accion.estado == EstadoAutorizacion.PENDIENTE
    assert not accion.puede_ejecutarse
    assert not gestor.puede_ejecutarse(accion.id)


def test_transicion_pendiente_a_autorizada(gestor):
    """pendiente → autorizada: la acción ya puede ejecutarse (SC-004)."""
    accion = _crear(gestor)
    gestor.autorizar(accion.id)
    assert accion.estado == EstadoAutorizacion.AUTORIZADA
    assert accion.puede_ejecutarse
    assert gestor.puede_ejecutarse(accion.id)


def test_transicion_pendiente_a_denegada_y_no_ejecutada(gestor):
    """pendiente → denegada → no_ejecutada (FR-016)."""
    accion = _crear(gestor)
    gestor.denegar(accion.id)
    assert accion.estado == EstadoAutorizacion.DENEGADA
    assert not accion.puede_ejecutarse
    gestor.marcar_no_ejecutada(accion.id)
    assert accion.estado == EstadoAutorizacion.NO_EJECUTADA
    assert not accion.puede_ejecutarse


def test_transicion_autorizada_a_ejecutada(gestor):
    """autorizada → ejecutada: comando autorizado ejecutado."""
    accion = _crear(gestor)
    gestor.autorizar(accion.id)
    gestor.marcar_ejecutada(accion.id)
    assert accion.estado == EstadoAutorizacion.EJECUTADA


def test_denegada_no_puede_marcarse_ejecutada(gestor):
    """Denegada no puede saltar a ejecutada (FR-016)."""
    accion = _crear(gestor)
    gestor.denegar(accion.id)
    with pytest.raises(RuntimeError):
        gestor.marcar_ejecutada(accion.id)


def test_pendiente_no_puede_marcarse_ejecutada(gestor):
    """Solo `autorizada` puede marcar `ejecutada` (data-model)."""
    accion = _crear(gestor)
    with pytest.raises(RuntimeError):
        gestor.marcar_ejecutada(accion.id)


def test_autorizar_desde_autorizada_se_rechaza(gestor):
    """Re-autorizar una acción ya autorizada se rechaza (state-machine)."""
    accion = _crear(gestor)
    gestor.autorizar(accion.id)
    with pytest.raises(RuntimeError):
        gestor.autorizar(accion.id)


def test_denegar_desde_autorizada_se_rechaza(gestor):
    """Denegar una acción ya autorizada se rechaza."""
    accion = _crear(gestor)
    gestor.autorizar(accion.id)
    with pytest.raises(RuntimeError):
        gestor.denegar(accion.id)


def test_no_ejecutada_solo_desde_denegada(gestor):
    """`no_ejecutada` solo se alcanza desde `denegada` (data-model)."""
    accion = _crear(gestor)
    with pytest.raises(RuntimeError):
        gestor.marcar_no_ejecutada(accion.id)
    gestor.autorizar(accion.id)
    with pytest.raises(RuntimeError):
        gestor.marcar_no_ejecutada(accion.id)


def test_denegar_desde_denegada_se_rechaza(gestor):
    """No se puede denegar dos veces."""
    accion = _crear(gestor)
    gestor.denegar(accion.id)
    with pytest.raises(RuntimeError):
        gestor.denegar(accion.id)


def test_obtener_y_puede_ejecutarse_consistentes(gestor):
    """`obtener`/`puede_ejecutarse` reflejan el estado actual."""
    accion = _crear(gestor)
    assert gestor.obtener(accion.id) is accion
    assert gestor.puede_ejecutarse(accion.id) is False
    gestor.autorizar(accion.id)
    assert gestor.puede_ejecutarse(accion.id) is True


def test_acciones_independientes_entre_si(gestor):
    """Dos acciones sensibles no comparten estado."""
    primera = _crear(gestor, id="a1")
    segunda = _crear(gestor, id="a2")
    gestor.autorizar(primera.id)
    assert gestor.puede_ejecutarse(primera.id)
    assert not gestor.puede_ejecutarse(segunda.id)
