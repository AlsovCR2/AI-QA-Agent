"""`GestorTareas`: CRUD de tareas del agente (Phase 13 / T087)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from qa_agent.agent.reasoning import EstadoTarea, TareaAgente


@dataclass
class GestorTareas:
    """Gestiona el ciclo de vida de las tareas del agente."""

    tareas: dict[str, TareaAgente] = field(default_factory=dict)

    # -- CRUD -----------------------------------------------------------------

    def crear(
        self,
        titulo: str,
        descripcion: str = "",
        prioridad: int = 0,
        etiquetas: list[str] | None = None,
        dependencias: list[str] | None = None,
        asignado_a: str = "",
    ) -> TareaAgente:
        """Crea una nueva tarea y la registra."""
        tarea = TareaAgente(
            titulo=titulo,
            descripcion=descripcion,
            prioridad=prioridad,
            etiquetas=etiquetas or [],
            dependencias=dependencias or [],
            asignado_a=asignado_a,
        )
        self.tareas[tarea.id] = tarea
        return tarea

    def obtener(self, tarea_id: str) -> TareaAgente | None:
        return self.tareas.get(tarea_id)

    def listar(
        self,
        estado: "EstadoTarea | None" = None,
        etiqueta: str | None = None,
        asignado_a: str | None = None,
    ) -> list:
        """Lista tareas con filtros opcionales."""
        from qa_agent.agent.reasoning import EstadoTarea

        res = list(self.tareas.values())
        if estado is not None:
            res = [t for t in res if t.estado == estado]
        if etiqueta is not None:
            res = [t for t in res if etiqueta in t.etiquetas]
        if asignado_a is not None:
            res = [t for t in res if t.asignado_a == asignado_a]
        return sorted(res, key=lambda t: (-t.prioridad, t.creada_en))

    def actualizar(
        self,
        tarea_id: str,
        *,
        titulo: str | None = None,
        descripcion: str | None = None,
        prioridad: int | None = None,
        etiquetas: list[str] | None = None,
        dependencias: list[str] | None = None,
        asignado_a: str | None = None,
    ) -> TareaAgente | None:
        """Actualiza campos de una tarea."""
        tarea = self.tareas.get(tarea_id)
        if tarea is None:
            return None
        if titulo is not None:
            tarea.titulo = titulo
        if descripcion is not None:
            tarea.descripcion = descripcion
        if prioridad is not None:
            tarea.prioridad = prioridad
        if etiquetas is not None:
            tarea.etiquetas = etiquetas
        if dependencias is not None:
            tarea.dependencias = dependencias
        if asignado_a is not None:
            tarea.asignado_a = asignado_a
        tarea.actualizada_en = datetime.now()
        return tarea

    def cambiar_estado(self, tarea_id: str, nuevo_estado: "EstadoTarea") -> TareaAgente | None:
        """Cambia el estado de una tarea (pendiente/en_progreso/completada/bloqueada)."""
        from qa_agent.agent.reasoning import EstadoTarea

        tarea = self.tareas.get(tarea_id)
        if tarea is None:
            return None
        if not isinstance(nuevo_estado, EstadoTarea):
            nuevo_estado = EstadoTarea(nuevo_estado)
        tarea.actualizar_estado(nuevo_estado)
        return tarea

    def borrar(self, tarea_id: str) -> bool:
        """Elimina una tarea."""
        if tarea_id in self.tareas:
            del self.tareas[tarea_id]
            return True
        return False

    # -- utilidades -----------------------------------------------------------

    def pendientes_para(self, agente: str) -> list:
        """Tareas pendientes asignadas a un agente."""
        return self.listar(estado="pendiente", asignado_a=agente)

    def bloqueadas_por(self, tarea_id: str) -> list:
        """Tareas que dependen de la tarea dada."""
        return [t for t in self.tareas.values() if tarea_id in t.dependencias]

    def proximas_acciones(self, agente: str, max_items: int = 5) -> list:
        """Próximas tareas accionables para un agente (pendientes, sin bloqueos, prioridad alta)."""
        from qa_agent.agent.reasoning import EstadoTarea

        pendientes = self.listar(estado=EstadoTarea.PENDIENTE, asignado_a=agente)
        accionables = []
        for t in pendientes:
            bloqueada = any(
                self.tareas.get(dep_id, TareaAgente()).estado != EstadoTarea.COMPLETADA
                for dep_id in t.dependencias
            )
            if not bloqueada:
                accionables.append(t)
        accionables.sort(key=lambda t: (-t.prioridad, t.creada_en))
        return accionables[:max_items]

    # -- serialización ligera -------------------------------------------------

    def a_dict(self) -> dict[str, Any]:
        return {tid: self._tarea_a_dict(t) for tid, t in self.tareas.items()}

    @classmethod
    def desde_dict(cls, data: dict[str, Any]) -> "GestorTareas":
        from qa_agent.agent.reasoning import EstadoTarea

        g = cls()
        for tid, td in data.items():
            t = TareaAgente(
                id=td["id"],
                titulo=td["titulo"],
                descripcion=td.get("descripcion", ""),
                estado=EstadoTarea(td["estado"]),
                prioridad=td.get("prioridad", 0),
                etiquetas=td.get("etiquetas", []),
                dependencias=td.get("dependencias", []),
                asignado_a=td.get("asignado_a", ""),
                resultado=td.get("resultado", ""),
                creada_en=datetime.fromisoformat(td["creada_en"]),
                actualizada_en=datetime.fromisoformat(td["actualizada_en"]),
            )
            g.tareas[tid] = t
        return g

    @staticmethod
    def _tarea_a_dict(t) -> dict:
        return {
            "id": t.id,
            "titulo": t.titulo,
            "descripcion": t.descripcion,
            "estado": t.estado.value,
            "prioridad": t.prioridad,
            "etiquetas": t.etiquetas,
            "dependencias": t.dependencias,
            "asignado_a": t.asignado_a,
            "resultado": t.resultado,
            "creada_en": t.creada_en.isoformat(),
            "actualizada_en": t.actualizada_en.isoformat(),
        }