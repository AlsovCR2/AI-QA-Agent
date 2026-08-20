"""Modelos del bucle de razonamiento-acción (Phase 12 / T076).

Definen `Intencion`, `PasoDePlan`, `Plan`, `Observacion` y `EstadoDelAgente`
(data-model §Entidades de razonamiento-acción). Sustentan la transición del
flujo de una sola pasada a un agente que percibe, planifica, actúa, observa,
reflexiona y decide (ver `agent-reasoning-loop.md`).

Estos modelos son datos puros: no usan LLM (III / SC-006) y no ejecutan nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intencion:
    """Percepción: qué pide el usuario y sobre qué objeto real del proyecto."""

    texto: str
    objetivo: str = ""
    entidad: str = ""
    contexto: dict[str, Any] = field(default_factory=dict)


@dataclass
class PasoDePlan:
    """Un paso pensado: por qué, qué herramienta y con qué argumentos."""

    orden: int
    razon: str
    herramienta: str
    parametros: dict[str, Any] = field(default_factory=dict)
    criterio_salida: str = ""


@dataclass
class Plan:
    """Plan multi-paso explícito con criterio de éxito."""

    objetivo: str = ""
    criterio_exito: str = ""
    pasos: list[PasoDePlan] = field(default_factory=list)
    pendientes: list[PasoDePlan] = field(default_factory=list)

    def siguiente_paso(self) -> PasoDePlan | None:
        """Devuelve el siguiente paso pendiente (o `None` si no hay)."""
        if not self.pendientes:
            return None
        return self.pendientes[0]

    def marcar_completado(self, paso: PasoDePlan) -> None:
        """Mueve un paso de pendientes a ejecutados (determinista)."""
        if paso in self.pendientes:
            self.pendientes.remove(paso)


@dataclass
class Observacion:
    """Resultado REAL de un paso ejecutado más la reflexión sobre su aporte."""

    paso: PasoDePlan
    resultado: Any = None
    evaluacion: str = ""


@dataclass
class EstadoDelAgente:
    """Estado del ciclo: evidencia acumulada y límites de parada.

    - `pasos_max` (default 12) evita bucles infinitos (SC-016).
    - `presupuesto_tokens` es opcional y lo gestiona el backend.
    """

    intencion: Intencion
    plan: Plan | None = None
    observaciones: list[Observacion] = field(default_factory=list)
    pasos_ejecutados: int = 0
    pasos_max: int = 12
    presupuesto_tokens: int | None = None

    def excedio_pasos_max(self) -> bool:
        """True si se alcanzó o superó el límite de pasos (SC-016)."""
        return self.pasos_ejecutados >= self.pasos_max

    def registrar_observacion(self, observacion: Observacion) -> None:
        """Acumula una observación real en el estado."""
        self.observaciones.append(observacion)
        self.pasos_ejecutados += 1


# --- Entidades conversacionales (Phase 13 / US-12) --------------------------

from enum import Enum
from datetime import datetime
from uuid import uuid4


class EstadoTarea(str, Enum):
    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADA = "completada"
    BLOQUEADA = "bloqueada"


@dataclass
class TareaAgente:
    """Tarea asignable al agente o creada por él, con seguimiento de estado."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    titulo: str = ""
    descripcion: str = ""
    estado: EstadoTarea = EstadoTarea.PENDIENTE
    prioridad: int = 0  # mayor = más urgente
    etiquetas: list[str] = field(default_factory=list)
    dependencias: list[str] = field(default_factory=list)  # ids de tareas
    asignado_a: str = ""  # nombre/rol del agente
    resultado: str = ""  # resumen de la ejecución (evidencia real)
    creada_en: datetime = field(default_factory=datetime.now)
    actualizada_en: datetime = field(default_factory=datetime.now)

    def actualizar_estado(self, nuevo_estado: EstadoTarea) -> None:
        self.estado = nuevo_estado
        self.actualizada_en = datetime.now()


@dataclass
class Turno:
    """Un intercambio usuario↔agente con evidencia del razonamiento usado."""
    numero: int
    usuario: str
    agente: str
    timestamp: datetime = field(default_factory=datetime.now)
    herramientas_usadas: list[str] = field(default_factory=list)
    razonamiento_ref: list = field(default_factory=list)  # Observacion


@dataclass
class Memoria:
    """Memoria a largo plazo persistente entre sesiones."""
    hechos: dict[str, Any] = field(default_factory=dict)
    preferencias: dict[str, Any] = field(default_factory=dict)
    proyectos_conocidos: list[str] = field(default_factory=list)

    def recordar_hecho(self, clave: str, valor: Any) -> None:
        self.hechos[clave] = valor

    def olvidar_hecho(self, clave: str) -> None:
        self.hechos.pop(clave, None)


@dataclass
class Conversacion:
    """Sesión completa de chat: historial, resumen evolutivo y hechos aprendidos."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    turnos: list[Turno] = field(default_factory=list)
    resumen: str = ""
    hechos: dict[str, Any] = field(default_factory=dict)
    tareas: list[TareaAgente] = field(default_factory=list)
    creada_en: datetime = field(default_factory=datetime.now)
    actualizada_en: datetime = field(default_factory=datetime.now)

    def agregar_turno(self, turno: Turno) -> None:
        self.turnos.append(turno)
        self.actualizada_en = datetime.now()

    def agregar_tarea(self, tarea: TareaAgente) -> None:
        self.tareas.append(tarea)
        self.actualizada_en = datetime.now()

    def obtener_tareas_pendientes(self) -> list[TareaAgente]:
        return [t for t in self.tareas if t.estado != EstadoTarea.COMPLETADA]

    def obtener_ultimos_turnos(self, n: int = 5) -> list[Turno]:
        return self.turnos[-n:]