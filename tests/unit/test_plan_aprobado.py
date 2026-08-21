"""Al autorizar se ejecuta EL PLAN QUE EL USUARIO VIO (FR-015/046, principio V).

El flujo interactivo llama a `atender()` dos veces: una sin decisión —que deja
la acción sensible suspendida y se la muestra al usuario— y otra con la
decisión. La segunda replanificaba desde cero.

Dos consecuencias, una de integridad y otra de fiabilidad:

- El permiso concedido para una acción concreta podía acabar ejecutando otra
  distinta, porque el segundo plan no tiene por qué parecerse al primero.
- El resultado dependía de una segunda tirada del modelo. Medido contra Gemini
  el 2026-08-21: la misma corrección salía 5/5 concediendo la autorización por
  API y 4-6/10 por CLI, solo por esta replanificación.
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.loop import Agent
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.explore import ExploreHerramienta
from qa_agent.tools.run_tests import RunTestsHerramienta


class _BackendQueCuenta(FakeLLM):
    """FakeLLM que cuenta cuántas veces se le pide un plan."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.planificaciones = 0

    def planificar(self, intencion, catalogo, contexto=None):
        self.planificaciones += 1
        return super().planificar(intencion, catalogo, contexto)


def _proyecto(tmp_path: Path) -> Path:
    raiz = tmp_path / "proyecto"
    (raiz / "src").mkdir(parents=True)
    (raiz / "src" / "app.py").write_text("def hola():\n    return 1\n", encoding="utf-8")
    return raiz


def _agente(raiz: Path, backend) -> Agent:
    return Agent(
        backend=backend,
        herramientas=[
            ExploreHerramienta([str(raiz)]),
            RunTestsHerramienta([str(raiz)]),
        ],
        allowlist=Allowlist([str(raiz)]),
    )


def _backend(raiz: Path) -> _BackendQueCuenta:
    return _BackendQueCuenta(
        soporta_razonamiento=True,
        plan={
            "objetivo": "ejecutar las pruebas",
            "criterio_exito": "",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "ejecutar las pruebas del proyecto",
                    "herramienta": "run_tests",
                    "parametros": {"ruta": str(raiz), "comando_pruebas": "pytest"},
                    "criterio_salida": "",
                }
            ],
        },
        responder={"texto": "Hecho.", "confianza": "alta", "recomendaciones": []},
    )


def test_autorizar_no_replanifica(tmp_path):
    """La segunda pasada reutiliza el plan; no vuelve a preguntar al modelo."""
    raiz = _proyecto(tmp_path)
    backend = _backend(raiz)
    agente = _agente(raiz, backend)
    pregunta = f"ejecuta las pruebas de {raiz}"

    agente.atender(pregunta, None)
    assert backend.planificaciones == 1

    agente.atender(pregunta, autorizacion=True)

    assert backend.planificaciones == 1, (
        "al autorizar debe ejecutarse el plan ya mostrado, no uno nuevo"
    )


def test_denegar_tampoco_replanifica(tmp_path):
    """Denegar es una decisión sobre el MISMO plan."""
    raiz = _proyecto(tmp_path)
    backend = _backend(raiz)
    agente = _agente(raiz, backend)
    pregunta = f"ejecuta las pruebas de {raiz}"

    agente.atender(pregunta, None)
    agente.atender(pregunta, autorizacion=False)

    assert backend.planificaciones == 1


def test_una_solicitud_distinta_si_replanifica(tmp_path):
    """El plan guardado es de UNA solicitud, no del agente."""
    raiz = _proyecto(tmp_path)
    backend = _backend(raiz)
    agente = _agente(raiz, backend)

    agente.atender(f"ejecuta las pruebas de {raiz}", None)
    agente.atender(f"explora la estructura de {raiz}", autorizacion=True)

    assert backend.planificaciones == 2


def test_el_plan_aprobado_se_consume_una_sola_vez(tmp_path):
    """Autorizar dos veces no puede reejecutar un plan viejo en silencio."""
    raiz = _proyecto(tmp_path)
    backend = _backend(raiz)
    agente = _agente(raiz, backend)
    pregunta = f"ejecuta las pruebas de {raiz}"

    agente.atender(pregunta, None)
    agente.atender(pregunta, autorizacion=True)
    agente.atender(pregunta, autorizacion=True)

    assert backend.planificaciones == 2


def test_sin_pasada_previa_se_planifica_normalmente(tmp_path):
    """Conceder autorización de entrada (uso por API) sigue funcionando."""
    raiz = _proyecto(tmp_path)
    backend = _backend(raiz)

    _agente(raiz, backend).atender(f"ejecuta las pruebas de {raiz}", True)

    assert backend.planificaciones == 1
