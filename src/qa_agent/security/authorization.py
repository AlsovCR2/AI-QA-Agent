"""Autorización human-in-the-loop (UC-006 / FR-015/016 / principio V).

Define `AccionSensible` con las transiciones de estado del data-model (#6) y
un gestor que garantiza que solo las acciones `autorizada` se ejecuten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EstadoAutorizacion(str, Enum):
    """Estados de autorización de una `AccionSensible` (data-model #6)."""

    PENDIENTE = "pendiente"
    AUTORIZADA = "autorizada"
    DENEGADA = "denegada"
    EJECUTADA = "ejecutada"
    NO_EJECUTADA = "no_ejecutada"


@dataclass
class AccionSensible:
    """Operación que requiere autorización explícita antes de ejecutarse."""

    id: str
    descripcion: str
    herramienta_id: str
    estado: EstadoAutorizacion = EstadoAutorizacion.PENDIENTE

    @property
    def puede_ejecutarse(self) -> bool:
        """Solo una acción `autorizada` puede ejecutarse (FR-016, V)."""
        return self.estado == EstadoAutorizacion.AUTORIZADA


class GestorDeAutorizacion:
    """Gestiona acciones sensibles y sus transiciones de estado."""

    def __init__(self) -> None:
        self._acciones: dict[str, AccionSensible] = {}

    def crear(
        self, id: str, descripcion: str, herramienta_id: str
    ) -> AccionSensible:
        """Crea una acción sensible en estado `pendiente` (SC-004)."""
        accion = AccionSensible(
            id=id,
            descripcion=descripcion,
            herramienta_id=herramienta_id,
            estado=EstadoAutorizacion.PENDIENTE,
        )
        self._acciones[id] = accion
        return accion

    def obtener(self, id: str) -> AccionSensible:
        """Devuelve la acción por id."""
        return self._acciones[id]

    def autorizar(self, id: str) -> None:
        """Transición `pendiente -> autorizada` (solo desde `pendiente`)."""
        accion = self._acciones[id]
        if accion.estado != EstadoAutorizacion.PENDIENTE:
            raise RuntimeError(
                f"No se puede autorizar: estado actual '{accion.estado.value}'."
            )
        accion.estado = EstadoAutorizacion.AUTORIZADA

    def denegar(self, id: str) -> None:
        """Transición `pendiente -> denegada` (solo desde `pendiente`)."""
        accion = self._acciones[id]
        if accion.estado != EstadoAutorizacion.PENDIENTE:
            raise RuntimeError(
                f"No se puede denegar: estado actual '{accion.estado.value}'."
            )
        accion.estado = EstadoAutorizacion.DENEGADA

    def marcar_ejecutada(self, id: str) -> None:
        """Transición `autorizada -> ejecutada`."""
        accion = self._acciones[id]
        if not accion.puede_ejecutarse:
            raise RuntimeError(
                "No se puede marcar como ejecutada una acción no autorizada "
                "(FR-016)."
            )
        accion.estado = EstadoAutorizacion.EJECUTADA

    def marcar_no_ejecutada(self, id: str) -> None:
        """Transición `denegada -> no_ejecutada` (solo desde `denegada`)."""
        accion = self._acciones[id]
        if accion.estado != EstadoAutorizacion.DENEGADA:
            raise RuntimeError(
                f"No se puede marcar no_ejecutada: estado actual "
                f"'{accion.estado.value}'."
            )
        accion.estado = EstadoAutorizacion.NO_EJECUTADA

    def puede_ejecutarse(self, id: str) -> bool:
        """True si la acción está `autorizada` (FR-016, SC-004)."""
        return self._acciones[id].puede_ejecutarse