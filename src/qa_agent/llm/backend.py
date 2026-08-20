"""Interfaz `LLMBackend` (Strategy).

Aísla al proveedor del modelo de lenguaje del núcleo del agente, garantizando
la independencia del proveedor (constitución) y la testabilidad sin LLM real
(principio III / FR-003 / SC-006). Ver `contracts/llm-backend-contract.md`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# Tipos de datos que atraviesan la interfaz. Se definen de forma ligera para
# no acoplar esta capa a implementaciones concretas aún no existentes
# (Solicitud, Intencion, Seleccion, RespuestaDelAgente).


class LLMBackend(ABC):
    """Contrato del backend de lenguaje (contrato llm-backend-contract.md)."""

    nombre: str
    requiere_api_key: bool
    proveedor_requerido: bool
    soporta_razonamiento: bool = False

    @abstractmethod
    def interpretar(self, solicitud: dict[str, Any]) -> dict[str, Any]:
        """Interpreta una solicitud del usuario en una acción de agente."""

    @abstractmethod
    def seleccionar_herramienta(
        self, solicitud: dict[str, Any], herramientas: list[Any]
    ) -> dict[str, Any]:
        """Selecciona la herramienta adecuada entre las disponibles.

        Devuelve el `id` de una herramienta existente o una señal de "ninguna
        herramienta adecuada" (FR-022/023, SC-009).
        """

    @abstractmethod
    def generar_respuesta(
        self, solicitud: dict[str, Any], resultados: list[Any]
    ) -> dict[str, Any]:
        """Genera la respuesta final basada en resultados reales validados."""

    # -- contrato de razonamiento (Phase 12 / T077) ----------------------

    @abstractmethod
    def planificar(
        self, intencion: Any, catalogo: list[Any], contexto: dict[str, Any]
    ) -> Any:
        """Genera un plan multi-paso (Plan) con criterio de éxito.

        El plan solo usa herramientas reales del catálogo y rutas permitidas
        (FR-032 / FR-033). Determinista ante la misma entrada (SC-010).
        """

    @abstractmethod
    def razonar(self, estado: Any, pendientes: list[Any]) -> dict[str, Any]:
        """Elige el siguiente paso (`PasoDePlan` o `{"concluir": true}`).

        Basado en las observaciones reales acumuladas en `estado`. Nunca
        inventa resultados (FR-019).
        """

    @abstractmethod
    def evaluar(self, estado: Any, observaciones: list[Any]) -> dict[str, Any]:
        """Evalúa si la evidencia satisface la intención.

        Devuelve `{"satisfecha": bool, "razon": str}`. Si duda, `satisfecha`
        debe ser `False` (no se da por satisfecha evidencia incompleta).
        """

    @abstractmethod
    def responder(self, observaciones: list[Any], intencion: str = "") -> dict[str, Any]:
        """Genera la respuesta final anclada en las observaciones reales.

        `intencion` (opcional) es la pregunta del usuario, para que la
        respuesta la atienda directamente. Devuelve
        `{"texto": ..., "confianza": ..., "recomendaciones": [...]}`.
        Toda afirmación se ancla en una observación (SC-017 / FR-019).
        """