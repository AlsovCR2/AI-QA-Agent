"""`Sesion`: estado por conversación en memoria (sin BD).

Mantiene solicitudes, resultados y el historial visible de acciones
`List[RegistroDeAccion]` ordenado por `orden` (FR-020 / SC-007 / VIII).
`agregar_accion` redacta siempre secretos (via `Redactor`) antes de añadir al
historial (SC-008 / FR-021). No persiste a disco (Storage: N/A, XII).
"""

from __future__ import annotations

from typing import Any

from qa_agent.agent.response import (
    EstadoAccion,
    RegistroDeAccion,
    RespuestaDelAgente,
)
from qa_agent.security.redactor import Redactor


class Sesion:
    """Conversación en memoria con historial visible de acciones."""

    def __init__(self, redactor: Redactor) -> None:
        self._redactor = redactor
        self._siguiente_orden = 1
        self._acciones: list[RegistroDeAccion] = []
        self._solicitudes: list[dict[str, Any]] = []
        self._respuestas: list[RespuestaDelAgente] = []

    @property
    def acciones(self) -> list[RegistroDeAccion]:
        """Historial visible ordenado por `orden` (SC-007)."""
        return sorted(self._acciones, key=lambda accion: accion.orden)

    @property
    def siguiente_orden(self) -> int:
        return self._siguiente_orden

    def registrar_solicitud(self, solicitud: dict[str, Any]) -> None:
        """Guarda una solicitud recibida (en memoria)."""
        self._solicitudes.append(solicitud)

    def registrar_respuesta(self, respuesta: RespuestaDelAgente) -> None:
        """Guarda una respuesta generada (en memoria)."""
        self._respuestas.append(respuesta)

    def agregar_accion(
        self,
        herramienta_id: str,
        entrada: dict[str, Any],
        salida: dict[str, Any],
        estado: EstadoAccion,
    ) -> RegistroDeAccion:
        """Añade una acción al historial redactando secretos (SC-008).

        `entrada` y `salida` pasan por el `Redactor` antes de exponerse para
        garantizar que ningún secreto aparezca en el historial (FR-021).
        """
        registro = RegistroDeAccion(
            orden=self._siguiente_orden,
            herramienta_id=herramienta_id,
            entrada=self._redactor.redactar(dict(entrada)),
            salida=self._redactor.redactar(dict(salida)),
            estado=estado,
        )
        self._siguiente_orden += 1
        self._acciones.append(registro)
        return registro