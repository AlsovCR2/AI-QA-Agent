"""Harness de evaluación del agente (T217/T218 — ver ADR-008)."""

from qa_agent.evaluacion.harness import (
    TareaDeEvaluacion,
    cargar_tareas,
    ejecutar_evaluacion,
    evaluar_tarea,
    raiz_de_evals,
)
from qa_agent.evaluacion.metricas import ResultadoDeTarea, agregar

__all__ = [
    "TareaDeEvaluacion",
    "ResultadoDeTarea",
    "agregar",
    "cargar_tareas",
    "ejecutar_evaluacion",
    "evaluar_tarea",
    "raiz_de_evals",
]
