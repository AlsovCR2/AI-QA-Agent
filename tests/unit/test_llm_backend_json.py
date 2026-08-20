"""Tests de robustez del backend OpenAI-compatible ante respuestas no-JSON.

Un LLM real (p. ej. NVIDIA NIM / nemotron) no siempre devuelve JSON puro:
puede añadir prosa, delimitadores, o negarse a responder. `_completar_json`
debe extraer el objeto JSON cuando exista y devolver `{}` en lugar de lanzar
`JSONDecodeError` (que rompería todo el agente, FR-017/018).

Sin red: se mockea `client.chat.completions.create` (III / SC-006).
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from qa_agent.llm.openai_compatible_backend import OpenAICompatibleBackend


def _backend():
    return OpenAICompatibleBackend(
        base_url="https://api.example.com/v1",
        model="test-model",
        api_key="sk-test",
    )


def _mock_completions(contenido: str):
    mock_message = Mock()
    mock_message.content = contenido
    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_respuesta = Mock()
    mock_respuesta.choices = [mock_choice]
    return Mock(return_value=mock_respuesta)


def test_json_valido_directo():
    """JSON puro se parsea sin cambios."""
    backend = _backend()
    with patch.object(backend._client.chat.completions, "create",
                      _mock_completions('{"accion": "ejecutar_pruebas"}')):
        assert backend._completar_json("sistema", "usuario") == {
            "accion": "ejecutar_pruebas"
        }


def test_json_con_texto_alrededor():
    """Prosa antes/después del JSON no rompe el parseo."""
    backend = _backend()
    contenido = (
        'Aquí tienes el resumen:\n\n'
        '{"texto": "Los tests pasan", "confianza": "alta"}\n'
        'Espero que te sea útil.'
    )
    with patch.object(backend._client.chat.completions, "create",
                      _mock_completions(contenido)):
        resultado = backend._completar_json("sistema", "usuario")
    assert resultado == {"texto": "Los tests pasan", "confianza": "alta"}


def test_json_en_bloque_markdown():
    """JSON envuelto en ```json ... ``` se extrae."""
    backend = _backend()
    contenido = '```json\n{"herramienta": "explore"}\n```'
    with patch.object(backend._client.chat.completions, "create",
                      _mock_completions(contenido)):
        assert backend._completar_json("sistema", "usuario") == {
            "herramienta": "explore"
        }


def test_respuesta_solo_prosa_devuelve_vacio():
    """El modelo responde prosa sin JSON → `{}` en vez de excepción (FR-018)."""
    backend = _backend()
    with patch.object(backend._client.chat.completions, "create",
                      _mock_completions("Lo siento, no puedo generar JSON.")):
        assert backend._completar_json("sistema", "usuario") == {}


def test_respuesta_vacia_devuelve_vacio():
    """Contenido vacío → `{}`."""
    backend = _backend()
    with patch.object(backend._client.chat.completions, "create",
                      _mock_completions("")):
        assert backend._completar_json("sistema", "usuario") == {}


def test_json_invalido_devuelve_vacio():
    """Texto con llaves pero no JSON válido → `{}` sin excepción."""
    backend = _backend()
    with patch.object(backend._client.chat.completions, "create",
                      _mock_completions("Esto no es { json válido")):
        assert backend._completar_json("sistema", "usuario") == {}


def test_acotar_conserva_inicio_y_final():
    """`_acotar` recorta manteniendo cabecera y cola (T094).

    Truncar solo desde el inicio hacía que el LLM viera únicamente `.git`
    (primero alfabéticamente) y respondiera sin anclaje. Conservar el final
    mantiene la estructura real visible en la evidencia.
    """
    backend = _backend()
    largo = "a" * 5000
    resultado = backend._acotar(largo, max_chars=1500)
    assert len(resultado) <= 1500
    assert resultado.startswith("a" * 200)
    assert resultado.endswith("a" * 200)
    assert "[+" in resultado  # marca el contenido omitido

    corto = "evidencia breve"
    assert backend._acotar(corto) == corto