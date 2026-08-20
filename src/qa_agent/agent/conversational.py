"""`AgentConversacional`: agente de chat persistente con memoria y tareas.

Envuelve el `Agent` ReAct (Phase 12) como herramienta analítica interna y añade
(Phase 13 / T088-T090):

- Historial conversacional: `Conversacion` con turnos, resumen y hechos.
- Memoria a largo plazo: `Memoria` persistente entre sesiones.
- Gestión de tareas: `GestorTareas` ligado a la conversación.
- Persistencia: `SesionManager` (guardar/cargar/listar).
- Delegación: intenciones de análisis QA → `Agent` ReAct; conversación general
  → respuesta directa del LLM.

El contexto conversacional (últimos turnos + resumen + tareas pendientes) se
inyecta en `Intencion.contexto` antes de `planificar` (T088).
"""

from __future__ import annotations

from typing import Any

from qa_agent.agent.gestor_tareas import GestorTareas
from qa_agent.agent.loop import Agent
from qa_agent.agent.response import (
    Confianza,
    EstadoAccion,
    RespuestaDelAgente,
)
from qa_agent.agent.reasoning import (
    Conversacion,
    Memoria,
    Turno,
)
from qa_agent.agent.router import enrutar_solicitud
from qa_agent.agent.session_manager import SesionManager
from qa_agent.llm.backend import LLMBackend
from qa_agent.security.redactor import Redactor
from qa_agent.tools.base import Herramienta


# Palabras clave que indican intención de análisis QA (delegación al ReAct).
# Solo sirven como heurística previa: si el enrutador determinista las capta,
# es QA; si no, se pregunta al LLM con una señal adicional (T090).
_PALABRAS_QA = (
    "explor", "estructura", "localiz", "busc", "patrón", "patron", "regex",
    "clase", "clases", "funcion", "función", "método", "metodo", "prueba",
    "pruebas", "test", "tests", "cobertura", "coverage", "anális", "analisis",
    "archivo", "archivos", "componente", "componentes", "servicio", "bug",
    "falla", "error", "refactor", "código", "codigo",
)


def _es_intencion_qa(texto: str) -> bool:
    """Heurística: si el enrutador la capta o contiene vocabulario QA → análisis."""
    if enrutar_solicitud(texto):
        return True
    norm = texto.lower()
    return any(p in norm for p in _PALABRAS_QA)


class AgentConversacional:
    """Agente conversacional persistente (chat + tareas + memoria)."""

    def __init__(
        self,
        backend: LLMBackend,
        herramientas: list[Herramienta],
        allowlist: Any | None = None,
        redactor: Redactor | None = None,
        pasos_max: int = 12,
        base_dir: str | None = None,
        usar_sqlite: bool = False,
        memoria: Memoria | None = None,
    ) -> None:
        self._redactor = redactor or Redactor()
        self._agente_qa = Agent(
            backend=backend,
            herramientas=herramientas,
            allowlist=allowlist,
            redactor=self._redactor,
            pasos_max=pasos_max,
        )
        self._backend = backend
        self._conversacion = Conversacion()
        self._gestor = GestorTareas()
        self._sesiones = SesionManager(base_dir=base_dir, usar_sqlite=usar_sqlite)
        self._memoria = memoria or Memoria()

    # -- estado expuesto ----------------------------------------------------

    @property
    def conversacion(self) -> Conversacion:
        return self._conversacion

    @property
    def tareas(self) -> GestorTareas:
        return self._gestor

    @property
    def memoria(self) -> Memoria:
        return self._memoria

    @property
    def agente_qa(self) -> Agent:
        """Agente ReAct interno (delegación de análisis QA)."""
        return self._agente_qa

    @property
    def sesiones(self) -> SesionManager:
        return self._sesiones

    # -- ciclo conversacional -------------------------------------------------

    def atender(
        self, texto: str, autorizacion: bool | None = None
    ) -> RespuestaDelAgente:
        """Procesa un turno: delega a ReAct si es QA, o responde directo.

        `autorizacion` (Phase 14 / T101) es la decisión del usuario ante una
        acción sensible: `None` sin decisión (se suspende y se informa),
        `True` autorizada o `False` denegada. Si el turno queda pendiente de
        autorización NO se registra en la conversación (el CLI lo re-invoca
        con la decisión para registrar solo la respuesta final, SC-004).
        """
        texto = (texto or "").strip()
        if not texto:
            return RespuestaDelAgente(
                texto="Recibí una solicitud vacía. ¿En qué te ayudo?",
                solicitud_id="",
                confianza=Confianza.SIN_INFORMACION,
            )
        turno = self._crear_turno(texto)
        contexto = self._contexto_conversacional()
        if _es_intencion_qa(texto):
            respuesta = self._agente_qa.atender(
                texto, contexto=contexto, autorizacion=autorizacion
            )
        else:
            respuesta = self._responder_directo(texto)
        pendientes = [
            a
            for a in respuesta.acciones
            if a.estado == EstadoAccion.PENDIENTE_AUTORIZACION
        ]
        if not pendientes:
            self._registrar_turno(turno, respuesta)
            self._aprender(texto, respuesta)
        return respuesta

    def _crear_turno(self, texto: str) -> Turno:
        numero = len(self._conversacion.turnos) + 1
        return Turno(
            numero=numero,
            usuario=self._redactor.redactar(texto),
            agente="",
        )

    def _registrar_turno(self, turno: Turno, respuesta: RespuestaDelAgente) -> None:
        turno.agente = respuesta.texto
        turno.herramientas_usadas = [
            a.herramienta_id for a in respuesta.acciones
        ]
        turno.razonamiento_ref = list(respuesta.razonamiento)
        self._conversacion.agregar_turno(turno)

    def _contexto_conversacional(self) -> dict[str, Any]:
        """Historial reciente + resumen + tareas pendientes para planificar."""
        ultimos = self._conversacion.obtener_ultimos_turnos(5)
        pendientes = self._gestor.pendientes_para("agente")
        return {
            "historial": [
                {"usuario": t.usuario, "agente": t.agente} for t in ultimos
            ],
            "resumen": self._conversacion.resumen,
            "tareas_pendientes": [
                {"titulo": t.titulo, "id": t.id} for t in pendientes
            ],
            "hechos": dict(self._memoria.hechos),
        }

    def _aprender(self, texto: str, respuesta: RespuestaDelAgente) -> None:
        """Actualiza memoria y resumen tras cada turno (T088)."""
        hechos = self._memoria.hechos
        hechos.setdefault("proyectos_conocidos", self._memoria.proyectos_conocidos)
        if respuesta.confianza == Confianza.ALTA and respuesta.texto:
            self._conversacion.resumen = (
                f"Última consulta: {self._redactor.redactar(texto[:120])}"
            )
        self._conversacion.actualizada_en = self._conversacion.creada_en  # marca visita

    def _responder_directo(self, texto: str) -> RespuestaDelAgente:
        """Respuesta de conversación general sin delegar al bucle ReAct."""
        contexto = self._contexto_conversacional()
        intencion = (
            f"Contexto de la conversación:\n"
            f"- Historial reciente: {contexto['historial']}\n"
            f"- Resumen: {contexto['resumen'] or '(vacío)'}\n"
            f"- Tareas pendientes: {contexto['tareas_pendientes'] or '(ninguna)'}\n"
            f"- Hechos: {contexto['hechos'] or '(ninguno)'}\n\n"
            f"Turno del usuario: {texto}"
        )
        try:
            generada = self._backend.responder([], intencion)
        except Exception:  # noqa: BLE001 - degradar sin romper el chat
            generada = {}
        if not isinstance(generada, dict):
            generada = {}
        confianza_raw = generada.get("confianza", Confianza.ALTA.value)
        try:
            confianza = Confianza(confianza_raw)
        except ValueError:
            confianza = Confianza.ALTA
        return RespuestaDelAgente(
            texto=self._redactor.redactar(generada.get("texto", ""))
            or "No tengo una respuesta para eso todavía.",
            solicitud_id="",
            confianza=confianza,
            basada_en_herramientas=False,
            recomendaciones=[
                r for r in generada.get("recomendaciones", [])
                if isinstance(r, str) and r.strip()
            ],
        )

    # -- tareas (delegación a GestorTareas) -----------------------------------

    def crear_tarea(
        self,
        titulo: str,
        descripcion: str = "",
        prioridad: int = 0,
        etiquetas: list[str] | None = None,
    ) -> str:
        """Crea una tarea asignada al agente y devuelve su id."""
        tarea = self._gestor.crear(
            titulo=titulo,
            descripcion=descripcion,
            prioridad=prioridad,
            etiquetas=etiquetas,
            asignado_a="agente",
        )
        self._conversacion.agregar_tarea(tarea)
        return tarea.id

    def listar_tareas(self, filtro_estado: str | None = None) -> list:
        return self._gestor.listar(estado=filtro_estado)

    def cambiar_estado_tarea(self, tarea_id: str, nuevo_estado: str) -> bool:
        """Cambia el estado de una tarea. Devuelve False si no existe."""
        from qa_agent.agent.reasoning import EstadoTarea

        try:
            estado = EstadoTarea(nuevo_estado)
        except ValueError:
            return False
        return self._gestor.cambiar_estado(tarea_id, estado) is not None

    def ejecutar_tarea(self, tarea_id: str) -> bool:
        """Ejecuta una tarea pendiente delegándola al bucle ReAct (QA).

        La tarea se convierte en una `Intencion` QA y se ejecuta con las
        herramientas reales; al terminar se marca `completada` (si hay
        evidencia) o `bloqueada` (si no se pudo obtener evidencia), y se
        guarda el resultado en `TareaAgente.resultado`. Devuelve False si la
        tarea no existe o ya está completada.
        """
        from qa_agent.agent.reasoning import EstadoTarea

        tarea = self._gestor.obtener(tarea_id)
        if tarea is None:
            return False
        if tarea.estado == EstadoTarea.COMPLETADA:
            return False
        if tarea.estado != EstadoTarea.EN_PROGRESO:
            tarea.actualizar_estado(EstadoTarea.EN_PROGRESO)

        texto = f"Tarea: {tarea.titulo}. {tarea.descripcion}".strip()
        contexto = self._contexto_conversacional()
        respuesta = self._agente_qa.atender(texto, contexto=contexto)

        turno = self._crear_turno(texto)
        turno.agente = respuesta.texto
        turno.herramientas_usadas = [a.herramienta_id for a in respuesta.acciones]
        turno.razonamiento_ref = list(respuesta.razonamiento)
        self._conversacion.agregar_turno(turno)

        tarea.resultado = respuesta.texto
        if respuesta.basada_en_herramientas and respuesta.texto:
            tarea.actualizar_estado(EstadoTarea.COMPLETADA)
        else:
            tarea.actualizar_estado(EstadoTarea.BLOQUEADA)
        self._conversacion.actualizada_en = tarea.actualizada_en
        return True

    # -- persistencia (delegación a SesionManager) -----------------------------

    def guardar(self) -> str:
        """Persiste la conversación actual y devuelve su id."""
        self._sesiones.guardar(self._conversacion)
        return self._conversacion.id

    def cargar(self, sesion_id: str) -> bool:
        """Carga una sesión previa. Devuelve False si no existe."""
        conv = self._sesiones.cargar(sesion_id)
        if conv is None:
            return False
        self._conversacion = conv
        self._gestor = GestorTareas()
        for t in conv.tareas:
            self._gestor.tareas[t.id] = t
        return True

    def listar_sesiones(self) -> list[dict[str, Any]]:
        return self._sesiones.listar()