"""Fixtures compartidas (Phase 1, T004).

- `redactor`: instancia del `Redactor` (FR-021).
- `fake_llm`: backend determinista para pruebas (T012, SC-006).
- `proyecto_ejemplo`: proyecto temporal con código, tests que pasan/fallan y un
  patrón único buscable (`config()`).
"""

from __future__ import annotations

import pytest

from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.security.redactor import Redactor


@pytest.fixture
def redactor() -> Redactor:
    """Instancia del redactor de secretos (FR-021)."""
    return Redactor()


@pytest.fixture
def fake_llm() -> FakeLLM:
    """Backend determinista sin red para pruebas del bucle del agente."""
    return FakeLLM(
        seleccion={"ninguna": True},
        por_defecto={
            "texto": "Respuesta determinista del FakeLLM.",
            "confianza": "alta",
            "basada_en_herramientas": False,
        },
    )


@pytest.fixture
def proyecto_ejemplo(tmp_path):
    """Proyecto temporal determinista con código y pruebas.

    - `src/app.py`: define `config()` (patrón único buscable).
    - `tests/test_main.py`: contiene una prueba que pasa y una que falla.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    (tmp_path / "src" / "app.py").write_text(
        "def config():\n"
        "    return {'clave': 'valor'}\n"
        "\n"
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    (tmp_path / "tests" / "test_main.py").write_text(
        "from app import config, sumar\n"
        "\n"
        "def test_config_return_value():\n"
        "    assert config()['clave'] == 'valor'\n"
        "\n"
        "def test_sumar_suma_correctamente():\n"
        "    assert sumar(2, 2) == 4\n"
        "\n"
        "def test_falla_intencionadamente():\n"
        "    assert sumar(2, 2) == 5\n",
        encoding="utf-8",
    )

    return tmp_path