"""Harness de evaluación del agente (T217 / FR-114/116/117).

Ejecuta un conjunto declarado de tareas contra proyectos de referencia
versionados en el repositorio y puntúa el comportamiento observable del agente.

Decisiones que conviene tener presentes al leerlo:

- **Los datos van aparte del motor.** El motor (este módulo) es código
  instalable y con pruebas; el conjunto de tareas y los proyectos de referencia
  viven en `evals/`, fuera del paquete, porque son datos de verificación y no
  deben viajar en la distribución ni ampliar la superficie de importación.
- **Sin dependencias nuevas.** El conjunto de tareas se declara en JSON y no en
  YAML precisamente para no añadir PyYAML (principio XII). El formato no aporta
  nada aquí que justifique una dependencia.
- **Se mide el comportamiento, no el texto.** Las métricas salen de la traza
  estructurada (T213), que es evidencia de lo que el agente hizo, no de lo que
  dijo que hizo.
- **Determinista con `FakeLLM`** (FR-116 / SC-105): dos corridas producen
  métricas idénticas salvo la latencia.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qa_agent.agent.loop import Agent
from qa_agent.agent.tracing import Trazador
from qa_agent.config import construir_allowlist, construir_backend, construir_herramientas
from qa_agent.evaluacion.metricas import (
    ResultadoDeTarea,
    acierto_de_herramienta,
    agregar,
    anclaje_en_evidencia,
    cumplimiento_de_seguridad,
    eficiencia_de_pasos,
)
from qa_agent.security.redactor import Redactor

#: Raíz del conjunto de evaluación, relativa a la raíz del repositorio.
DIRECTORIO_EVALS = "evals"
ARCHIVO_TAREAS = "tasks.json"
DIRECTORIO_DATASETS = "datasets"


@dataclass(frozen=True)
class TareaDeEvaluacion:
    """Una tarea declarada del conjunto de evaluación."""

    id: str
    proyecto: str
    solicitud: str
    herramienta_esperada: str = ""
    debe_pedir_autorizacion: bool = False
    evidencia_esperada: list[str] = field(default_factory=list)
    pasos_optimos: int = 1
    ecosistema: str = "python"

    @staticmethod
    def desde_dict(datos: dict[str, Any]) -> TareaDeEvaluacion:
        return TareaDeEvaluacion(
            id=str(datos["id"]),
            proyecto=str(datos["proyecto"]),
            solicitud=str(datos["solicitud"]),
            herramienta_esperada=str(datos.get("herramienta_esperada", "")),
            debe_pedir_autorizacion=bool(datos.get("debe_pedir_autorizacion", False)),
            evidencia_esperada=[str(e) for e in datos.get("evidencia_esperada", [])],
            pasos_optimos=int(datos.get("pasos_optimos", 1)),
            ecosistema=str(datos.get("ecosistema", "python")),
        )


def raiz_de_evals(base: str | Path | None = None) -> Path:
    """Localiza el directorio `evals/`.

    Se busca hacia arriba desde `base` (o desde este módulo) porque el harness
    debe funcionar tanto ejecutado desde la raíz del repositorio como desde un
    subdirectorio o desde una instalación editable.
    """
    inicio = Path(base).resolve() if base else Path(__file__).resolve()
    for candidato in [inicio, *inicio.parents]:
        posible = candidato / DIRECTORIO_EVALS
        if (posible / ARCHIVO_TAREAS).is_file():
            return posible
    raise FileNotFoundError(
        f"No se encontró '{DIRECTORIO_EVALS}/{ARCHIVO_TAREAS}' desde {inicio}"
    )


def cargar_tareas(ruta_evals: Path) -> list[TareaDeEvaluacion]:
    """Lee y valida el conjunto de tareas declarado."""
    datos = json.loads((ruta_evals / ARCHIVO_TAREAS).read_text(encoding="utf-8"))
    tareas = [TareaDeEvaluacion.desde_dict(t) for t in datos.get("tareas", [])]
    ids = [t.id for t in tareas]
    if len(ids) != len(set(ids)):
        raise ValueError("El conjunto de evaluación tiene ids de tarea duplicados")
    return tareas


def _construir_agente_de_evaluacion(ruta_proyecto: Path, demo: bool) -> Agent:
    """Agente aislado por tarea: sin estado compartido entre tareas.

    Cada tarea estrena agente para que el resultado de una no pueda influir en
    la siguiente a través del historial de sesión (VI).
    """
    backend = construir_backend(demo=demo)
    redactor = Redactor()
    return Agent(
        backend=backend,
        herramientas=construir_herramientas(str(ruta_proyecto), backend=backend),
        allowlist=construir_allowlist(str(ruta_proyecto)),
        redactor=redactor,
        trazador=Trazador(redactor=redactor),
    )


def evaluar_tarea(
    tarea: TareaDeEvaluacion, ruta_evals: Path, demo: bool = True
) -> ResultadoDeTarea:
    """Ejecuta una tarea y la puntúa.

    La autorización se deniega SIEMPRE (`autorizacion=False` implícito: nunca se
    concede). Una evaluación no debe ejecutar pruebas ni modificar los proyectos
    de referencia; lo que se mide es si el agente PIDIÓ permiso, no qué pasa
    después de concederlo (principio V).
    """
    proyecto = ruta_evals / DIRECTORIO_DATASETS / tarea.proyecto
    notas: list[str] = []
    if not proyecto.is_dir():
        return ResultadoDeTarea(
            id=tarea.id,
            ecosistema=tarea.ecosistema,
            acierto_herramienta=0.0,
            anclaje_evidencia=0.0,
            seguridad=0.0,
            eficiencia_pasos=0.0,
            latencia_ms=0,
            notas=[f"proyecto de referencia ausente: {proyecto}"],
        )

    agente = _construir_agente_de_evaluacion(proyecto, demo)
    inicio = time.monotonic()
    respuesta = agente.atender(tarea.solicitud)
    latencia_ms = int((time.monotonic() - inicio) * 1000)

    trazador = agente.trazador
    usadas = trazador.herramientas_ejecutadas()
    pidio = trazador.pidio_autorizacion()
    # Evidencia realmente devuelta por las herramientas, ya redactada por
    # `Sesion`. Ver la justificación en `anclaje_en_evidencia`.
    evidencia_recogida = " ".join(
        str(getattr(accion, "salida", "")) for accion in agente.sesion.acciones
    )

    if tarea.debe_pedir_autorizacion and not pidio:
        notas.append("acción sensible ejecutada sin solicitar autorización")
    if pidio and not tarea.debe_pedir_autorizacion:
        notas.append("solicitó autorización para una acción que no la requiere")

    return ResultadoDeTarea(
        id=tarea.id,
        ecosistema=tarea.ecosistema,
        acierto_herramienta=acierto_de_herramienta(usadas, tarea.herramienta_esperada),
        anclaje_evidencia=anclaje_en_evidencia(
            respuesta.texto, tarea.evidencia_esperada, evidencia_recogida
        ),
        seguridad=cumplimiento_de_seguridad(pidio, tarea.debe_pedir_autorizacion),
        eficiencia_pasos=eficiencia_de_pasos(
            trazador.pasos_ejecutados(), tarea.pasos_optimos
        ),
        latencia_ms=latencia_ms,
        herramientas_usadas=usadas,
        razon_parada=trazador.razon_de_parada(),
        notas=notas,
    )


def ejecutar_evaluacion(
    base: str | Path | None = None,
    demo: bool = True,
    incluir_tiempos: bool = True,
) -> dict[str, Any]:
    """Corre el conjunto completo y devuelve el informe.

    `incluir_tiempos=False` produce un informe reproducible byte a byte entre
    corridas: es el modo que usan las pruebas de determinismo (SC-105).
    """
    ruta_evals = raiz_de_evals(base)
    tareas = cargar_tareas(ruta_evals)
    resultados = [evaluar_tarea(t, ruta_evals, demo) for t in tareas]
    return {
        "modo": "demo" if demo else "proveedor",
        "resumen": agregar(resultados),
        "tareas": [r.como_dict(incluir_tiempos) for r in resultados],
    }
