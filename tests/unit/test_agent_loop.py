"""Tests del bucle del agente con `FakeLLM` (T018, FR-001..005 / SC-001/002/007).

Simula el flujo: recibe solicitud → selecciona herramienta → ejecuta → valida →
responde con historial visible. Usa `FakeLLM` scripted y una herramienta real
mínima (determinista, sin LLM).
"""

from __future__ import annotations

import pytest

from qa_agent.agent.response import Confianza, EstadoAccion
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)


class HerramientaEstructura(Herramienta):
    """Herramienta determinista mínima: devuelve la estructura real fija."""

    id = "explore"
    nombre = "explore"
    descripcion = "Explora la estructura del proyecto."
    esquema_entrada = {"type": "object", "properties": {"ruta": {"type": "string"}}}
    esquema_salida = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "existe": {"type": "boolean"},
            "accesible": {"type": "boolean"},
            "elementos": {"type": "array"},
        },
        "required": ["ruta", "existe", "accesible", "elementos"],
    }
    requiere_autorizacion = False
    rutas_permitidas: list[str] = []

    def ejecutar(self, parametros: dict):
        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "ruta": parametros.get("ruta", "."),
                "existe": True,
                "accesible": True,
                "elementos": [{"nombre": "src", "tipo": "directorio"}],
            },
        )


@pytest.fixture
def explorador():
    return HerramientaEstructura()


def _fake_con_explore():
    return FakeLLM(
        respuestas_por_solicitud={
            "¿cuál es la estructura del proyecto?": {
                "seleccion": {"herramienta": "explore"},
                "texto": "Estructura real: contiene 'src' (directorio).",
                "confianza": "alta",
                "basada_en_herramientas": True,
            }
        },
    )


def test_respuesta_no_vacia_para_solicitud_valida(redactor, explorador):
    from qa_agent.agent.loop import Agent

    agente = Agent(
        backend=_fake_con_explore(),
        herramientas=[explorador],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("¿cuál es la estructura del proyecto?")
    assert respuesta.texto  # SC-001: respuesta no vacía


def test_ejecuta_herramienta_real_y_respuesta_se_basa_en_resultado(
    redactor, explorador
):
    from qa_agent.agent.loop import Agent

    agente = Agent(
        backend=_fake_con_explore(),
        herramientas=[explorador],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("¿cuál es la estructura del proyecto?")
    # FR-003/004: la respuesta se basa en el resultado real de la herramienta
    assert respuesta.basada_en_herramientas
    assert "src" in respuesta.texto
    # Registra en Sesion cada herramienta y su resultado (FR-020 / SC-007)
    assert any(a.herramienta_id == "explore" for a in respuesta.acciones)
    assert all(a.estado == EstadoAccion.EXITO for a in respuesta.acciones)


def test_ninguna_herramienta_responde_notificacion(redactor, explorador):
    from qa_agent.agent.loop import Agent

    ninguno = FakeLLM(
        seleccion={"ninguna": True},
        respuestas_por_solicitud={
            "hola": {"texto": "No tengo herramienta para eso.", "confianza": "sin_informacion"}
        },
    )
    agente = Agent(
        backend=ninguno,
        herramientas=[explorador],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("hola")
    # FR-022/023, SC-009: notificación + sugerencia, sin forzar ejecución
    assert respuesta.texto
    assert respuesta.confianza == Confianza.SIN_INFORMACION
    assert not respuesta.basada_en_herramientas
    assert respuesta.acciones == [] or not any(
        a.estado == EstadoAccion.EXITO for a in respuesta.acciones
    )