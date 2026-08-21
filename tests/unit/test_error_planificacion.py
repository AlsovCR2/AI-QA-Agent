"""Un fallo del proveedor no puede parecer "tu pregunta no aplica" (IX/FR-019).

`planificar` degradaba a `plan = None` capturando la excepción y tirándola. El
usuario veía "No tengo una respuesta basada en evidencia para eso", que es lo
mismo que dice el agente ante una solicitud fuera de alcance.

Encontrado el 2026-08-21 de la peor forma: midiendo la fiabilidad del agente,
la cuota diaria de Gemini se agotó y devolvió 429 en todas las llamadas. El
agente respondía como si no hubiera nada que hacer, y la medición marcó 0/10
atribuyéndolo a un cambio de código. Degradar sin decir por qué convierte un
problema de infraestructura en un diagnóstico equivocado.
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.loop import Agent
from qa_agent.agent.response import Confianza
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.explore import ExploreHerramienta


class _ErrorDeCuota(Exception):
    pass


class _BackendQueFalla(FakeLLM):
    """Simula un proveedor caído durante la planificación."""

    def planificar(self, intencion, catalogo, contexto=None):
        raise _ErrorDeCuota("429 quota exceeded para el modelo")


def _proyecto(tmp_path: Path) -> Path:
    raiz = tmp_path / "proyecto"
    (raiz / "src").mkdir(parents=True)
    (raiz / "src" / "app.py").write_text("def hola():\n    return 1\n", encoding="utf-8")
    return raiz


def _agente(raiz: Path) -> Agent:
    return Agent(
        backend=_BackendQueFalla(
            soporta_razonamiento=True,
            responder={"texto": "", "confianza": "alta"},
        ),
        herramientas=[ExploreHerramienta([str(raiz)])],
        allowlist=Allowlist([str(raiz)]),
    )


def test_el_fallo_del_proveedor_se_nombra_en_la_respuesta(tmp_path):
    raiz = _proyecto(tmp_path)

    respuesta = _agente(raiz).atender(f"explora la estructura de {raiz}", None)

    assert "proveedor LLM" in respuesta.texto
    assert "_ErrorDeCuota" in respuesta.texto or "429" in respuesta.texto


def test_no_se_confunde_con_una_solicitud_fuera_de_alcance(tmp_path):
    """El mensaje de "sin evidencia" significa otra cosa y no debe aparecer."""
    raiz = _proyecto(tmp_path)

    respuesta = _agente(raiz).atender(f"explora la estructura de {raiz}", None)

    assert "No tengo una respuesta basada en evidencia" not in respuesta.texto


def test_el_agente_no_se_rompe(tmp_path):
    """Degradar sigue siendo degradar: se responde, no se lanza."""
    raiz = _proyecto(tmp_path)

    respuesta = _agente(raiz).atender(f"explora la estructura de {raiz}", None)

    assert respuesta.confianza == Confianza.SIN_INFORMACION
    assert respuesta.solicitud_id
