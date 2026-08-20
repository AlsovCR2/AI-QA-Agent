"""AI QA & Software Engineering Agent.

Asistente de análisis, exploración y validación de proyectos de software,
orientado a herramientas, controlado y verificable.
"""

from __future__ import annotations

__version__ = "0.1.0"

# API pública del agente.
from qa_agent.agent.loop import Agent

__all__ = ["Agent", "__version__"]