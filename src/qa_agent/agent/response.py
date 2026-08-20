"""Respuesta del agente e historial visible (FR-020 / VIII).

Define `RegistroDeAccion` (entrada del historial visible, data-model #5) y
`RespuestaDelAgente` (respuesta final, data-model #4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qa_agent.agent.reasoning import Observacion


class EstadoAccion(str, Enum):
    """Estado de una acción registrada en el historial (data-model #5)."""

    EXITO = "exito"
    ERROR = "error"
    INVALIDO = "invalido"
    PENDIENTE_AUTORIZACION = "pendiente_autorizacion"


class Confianza(str, Enum):
    """Nivel de confianza de la respuesta (data-model #4 / UC-007)."""

    ALTA = "alta"
    LIMITADA = "limitada"
    SIN_INFORMACION = "sin_informacion"


@dataclass
class RegistroDeAccion:
    """Entrada del historial visible (data-model #5)."""

    orden: int
    herramienta_id: str
    entrada: dict[str, Any]
    salida: dict[str, Any]
    estado: EstadoAccion


@dataclass
class RespuestaDelAgente:
    """Respuesta final hacia el usuario (data-model #4)."""

    texto: str
    solicitud_id: str
    acciones: list[RegistroDeAccion] = field(default_factory=list)
    confianza: Confianza = Confianza.ALTA
    basada_en_herramientas: bool = False
    recomendaciones: list[str] = field(default_factory=list)
    razonamiento: list[Any] = field(default_factory=list)