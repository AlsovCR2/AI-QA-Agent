"""Tests de robustez del `responder` (T119): evidencia acotada y honestidad.

Cubre el fix de la respuesta genérica "No tengo una respuesta basada en
evidencia para eso" cuando el análisis acumula mucha evidencia:

- `OpenAICompatibleBackend.responder` acota cada observación para no exceder el
  contexto del modelo y, ante un fallo de la API, reintenta UNA vez con
  evidencia compacta (observaciones más recientes, más acotadas).
- El bucle (`loop._respuesta_react`) expone el error real del proveedor LLM en
  la respuesta final en vez del fallback genérico (honestidad, IX / FR-019).

Sin red: se mockea `_completar_json` (III / SC-006).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from qa_agent.agent.loop import Agent
from qa_agent.agent.reasoning import Observacion, PasoDePlan
from qa_agent.agent.response import Confianza
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.llm.openai_compatible_backend import (
    OpenAICompatibleBackend,
)
from qa_agent.security.redactor import Redactor
from qa_agent.tools.allowlist import Allowlist

from tests.unit.test_profundidad_analisis import _StubExplore


def _backend():
    return OpenAICompatibleBackend(
        base_url="https://api.example.com/v1",
        model="test-model",
        api_key="sk-test",
    )


def _observaciones(n: int = 10, tam_resultado: int = 2000) -> list[Observacion]:
    return [
        Observacion(
            paso=PasoDePlan(
                i, f"razon {i}", "explore",
                {"ruta": ".", "profundidad_max": 1},
            ),
            resultado={"datos": "x" * tam_resultado},
        )
        for i in range(1, n + 1)
    ]


def test_responder_acota_cada_observacion():
    """La evidencia se acota por observación (cabe en el contexto del modelo)."""
    backend = _backend()
    usuarios: list[str] = []

    def _falso_completar(sistema, usuario):
        usuarios.append(usuario)
        return {"texto": "ok", "confianza": "alta", "recomendaciones": []}

    with patch.object(backend, "_completar_json", side_effect=_falso_completar):
        resultado = backend.responder(_observaciones(), "explora el proyecto")

    assert resultado["texto"] == "ok"
    assert len(usuarios) == 1
    # Truncado presente y total mucho menor que la evidencia cruda (10×2000).
    assert "[+" in usuarios[0]
    assert len(usuarios[0]) < 10 * 2000
    # Todas las observaciones siguen visibles (anclaje completo, FR-019).
    assert usuarios[0].count("paso ") == 10


def test_responder_reintenta_con_evidencia_compacta():
    """Ante un fallo de la API, `responder` reintenta con evidencia menor."""
    backend = _backend()
    usuarios: list[str] = []

    def _falso_completar(sistema, usuario):
        usuarios.append(usuario)
        if len(usuarios) == 1:
            raise RuntimeError("context_length_exceeded")
        return {"texto": "resumen", "confianza": "alta", "recomendaciones": []}

    with patch.object(backend, "_completar_json", side_effect=_falso_completar):
        resultado = backend.responder(_observaciones(n=10), "explora el proyecto")

    assert resultado["texto"] == "resumen"
    assert len(usuarios) == 2
    primero, segundo = usuarios
    assert len(segundo) < len(primero)
    # El reintento conserva solo las observaciones más recientes (6 de 10).
    assert segundo.count("paso ") == 6
    assert "paso 5" in segundo
    assert "paso 10" in segundo
    assert "paso 4" not in segundo


def test_responder_propaga_error_si_reintento_tambien_falla():
    """Si el reintento compacto también falla, el error se propaga (no se oculta)."""
    backend = _backend()
    with patch.object(
        backend, "_completar_json", side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError, match="boom"):
            backend.responder(_observaciones(n=3), "explora el proyecto")


def test_responder_sin_observaciones_no_reintenta():
    """Rama conversacional (sin observaciones): el error se propaga tal cual."""
    backend = _backend()
    with patch.object(
        backend, "_completar_json", side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError, match="boom"):
            backend.responder([], "hola")


class _ResponderQueFalla(FakeLLM):
    """Backend cuyo `responder` siempre falla (simula error del proveedor)."""

    def responder(self, observaciones, intencion: str = ""):
        raise RuntimeError("fallo_llm_simulado")


def test_respuesta_expone_error_real_del_backend():
    """El bucle muestra el error real del proveedor, no el fallback genérico."""
    backend = _ResponderQueFalla(
        soporta_razonamiento=True,
        plan={
            "pasos": [
                {"orden": 1, "razon": "explorar", "herramienta": "explore",
                 "parametros": {"ruta": "."}, "criterio_salida": ""}
            ]
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "", "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_StubExplore()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("explora")

    assert respuesta.confianza == Confianza.SIN_INFORMACION
    assert "fallo_llm_simulado" in respuesta.texto
    assert "No tengo una respuesta" not in respuesta.texto


def test_respuesta_sin_error_mantiene_fallback_original():
    """Sin error del backend (respuesta vacía), se conserva el fallback original."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "pasos": [
                {"orden": 1, "razon": "explorar", "herramienta": "explore",
                 "parametros": {"ruta": "."}, "criterio_salida": ""}
            ]
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "", "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_StubExplore()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("explora")

    assert respuesta.confianza == Confianza.SIN_INFORMACION
    assert respuesta.texto == "No tengo una respuesta basada en evidencia para eso."