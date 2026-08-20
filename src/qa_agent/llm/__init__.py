"""Capa de modelos de lenguaje: interfaz `LLMBackend` y backends concretos.

El núcleo del agente depende solo de la interfaz, nunca de un proveedor
específico (independencia del proveedor). Se incluyen `OpenAICompatibleBackend`
(producción) y `FakeLLM` (pruebas / modo --demo).
"""

from __future__ import annotations

__all__: list[str] = []