"""Tests del cableado de herramientas en la configuración y CLI (T064).

Verifica que el agente construido por la CLI carga el catálogo completo de
herramientas (incluidas las QA/Testing) con la ruta autorizada, de modo que
las nuevas solicitudes puedan disparar las herramientas reales (FR-003/004).
"""

from __future__ import annotations

from qa_agent.cli.main import _construir_agente
from qa_agent.config import construir_backend, construir_herramientas


def test_cli_construye_agente_con_catalogo_completo(tmp_path):
    """El agente de la CLI tiene las 11 herramientas registradas (T064)."""
    agente = _construir_agente(str(tmp_path), demo=True)
    ids = sorted(agente._herramientas.keys())  # noqa: SLF001 - acceso en test
    assert ids == [
        "analyze_coverage",
        "analyze_test_results",
        "crear_archivo",
        "editar_archivo",
        "eliminar_archivo",
        "explore",
        "generate_test_cases",
        "leer_archivo",
        "locate",
        "run_tests",
        "search",
    ]


def test_construir_herramientas_respeta_allowlist_ruta(tmp_path):
    """Todas las herramientas comparten la ruta objetivo autorizada (FR-025)."""
    herramientas = construir_herramientas(str(tmp_path))
    for herramienta in herramientas:
        assert isinstance(herramienta._allowlist.perimetros, list)  # noqa: SLF001
        assert str(tmp_path) in {
            str(p) for p in herramienta._allowlist.perimetros  # noqa: SLF001
        }


def test_generate_test_cases_recibe_backend_para_redactar_casos(tmp_path):
    """generate_test_cases recibe el LLMBackend para delegar redacción (VI)."""
    backend = construir_backend(demo=True)
    herramientas = construir_herramientas(str(tmp_path), backend=backend)
    gtc = [h for h in herramientas if h.id == "generate_test_cases"][0]
    assert gtc._llm_backend is backend  # noqa: SLF001