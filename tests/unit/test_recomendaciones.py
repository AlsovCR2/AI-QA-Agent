"""Tests del modo recomendación (T075).

Cuando la evidencia real de las herramientas no responde directamente a la
pregunta (p. ej. "¿qué estrategia de pruebas recomiendas?"), el agente puede
ofrecer recomendaciones claramente etiquetadas como tales, basadas en lo que
SÍ ve (estructura, framework, ausencia de tests), sin afirmar hechos inventados
(FR-019 / IX). Las recomendaciones son sugerencias, no datos del proyecto.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from qa_agent.agent.loop import Agent
from qa_agent.agent.response import Confianza
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.security.redactor import Redactor
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import EstadoResultado, Herramienta, ResultadoDeHerramienta


class _StubExplore(Herramienta):
    """`explore` instanciable (id, esquemas y `ejecutar` concreto)."""

    id = "explore"
    nombre = "explore"
    descripcion = "Explora la estructura del proyecto."
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "profundidad_max": {"type": "integer", "minimum": 1, "maximum": 8},
        },
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "existe": {"type": "boolean"},
            "elementos": {"type": "array"},
        },
    }
    requiere_autorizacion = False

    def ejecutar(self, parametros: dict) -> ResultadoDeHerramienta:
        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "ruta": parametros.get("ruta", "."),
                "existe": True,
                "elementos": [],
            },
        )


def _agente(por_defecto: dict | None = None) -> Agent:
    return Agent(
        backend=FakeLLM(
            seleccion={"herramienta": "explore"},
            por_defecto={
                "texto": "No hay evidencia directa de una estrategia.",
                "confianza": "limitada",
                **(por_defecto or {}),
            },
        ),
        herramientas=[_StubExplore()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )


def test_respuesta_con_recomendaciones_se_propaga():
    """Las recomendaciones del backend llegan a la respuesta del agente."""
    agente = _agente(
        {
            "recomendaciones": [
                "Empieza con pruebas unitarias sobre BLL.",
                "Añade una suite de integración con la base de datos.",
            ]
        }
    )
    respuesta = agente.atender(
        "¿Qué estrategia de pruebas recomiendas usar para este proyecto?"
    )

    assert respuesta.recomendaciones == [
        "Empieza con pruebas unitarias sobre BLL.",
        "Añade una suite de integración con la base de datos.",
    ]


def test_respuesta_sin_recomendaciones_lista_vacia():
    """Sin recomendaciones del backend → lista vacía (sin cambio de comportamiento)."""
    agente = _agente({"recomendaciones": None})
    respuesta = agente.atender("¿Qué estrategia de pruebas recomiendas?")

    assert respuesta.recomendaciones == []


def test_recomendaciones_se_redactan_antes_de_exponer():
    """Las recomendaciones pasan por el Redactor (secretos ocultos, SC-008)."""
    agente = _agente(
        {
            "recomendaciones": [
                "Usa la API key sk-secreto123 para configurar el runner.",
            ]
        }
    )
    respuesta = agente.atender("recomiéndame cómo configurar la CI")

    assert respuesta.recomendaciones
    assert "sk-secreto123" not in " ".join(respuesta.recomendaciones)
    assert "***" in respuesta.recomendaciones[0]


def test_recomendaciones_no_afectan_confianza():
    """Tener recomendaciones no eleva la confianza (siguen siendo sugerencias)."""
    agente = _agente(
        {
            "recomendaciones": ["Revisa la estructura antes de decidir."],
        }
    )
    respuesta = agente.atender("¿Qué estrategia de pruebas recomiendas?")

    assert respuesta.confianza == Confianza.LIMITADA


def test_backend_generar_respuesta_acepta_recomendaciones():
    """El backend OpenAI-compatible propaga `recomendaciones` del LLM (T075)."""
    from qa_agent.llm.openai_compatible_backend import OpenAICompatibleBackend

    backend = OpenAICompatibleBackend(
        base_url="https://api.example.com/v1",
        model="test-model",
        api_key="sk-test",
    )
    mock_message = Mock()
    mock_message.content = (
        '{"texto": "No hay tests aún.", "confianza": "limitada", '
        '"recomendaciones": ["Empieza con pruebas unitarias."]}'
    )
    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_respuesta = Mock()
    mock_respuesta.choices = [mock_choice]

    with patch.object(backend._client.chat.completions, "create",
                      Mock(return_value=mock_respuesta)):
        resultado = backend.generar_respuesta(
            {"texto": "¿qué estrategia?"}, [Mock()]
        )

    assert resultado["recomendaciones"] == ["Empieza con pruebas unitarias."]


def test_backend_sin_recomendaciones_devuelve_vacio():
    """Sin campo `recomendaciones` en la respuesta del LLM → lista vacía."""
    from qa_agent.llm.openai_compatible_backend import OpenAICompatibleBackend

    backend = OpenAICompatibleBackend(
        base_url="https://api.example.com/v1",
        model="test-model",
        api_key="sk-test",
    )
    mock_message = Mock()
    mock_message.content = '{"texto": "ok", "confianza": "alta"}'
    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_respuesta = Mock()
    mock_respuesta.choices = [mock_choice]

    with patch.object(backend._client.chat.completions, "create",
                      Mock(return_value=mock_respuesta)):
        resultado = backend.generar_respuesta(
            {"texto": "¿qué estrategia?"}, [Mock()]
        )

    assert resultado.get("recomendaciones", []) == []