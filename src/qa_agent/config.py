"""Configuración del agente (T017).

Carga los parámetros del proveedor LLM desde variables de entorno (`python-dotenv`,
`.env`), selecciona el backend adecuado (real si hay `LLM_API_KEY`, `FakeLLM` en
`--demo` o sin key) y construye la `Allowlist` con la ruta objetivo (FR-025).

Los secretos nunca se imprimen en configuración ni logs (XI).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from qa_agent.llm.backend import LLMBackend
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.llm.openai_compatible_backend import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    OpenAICompatibleBackend,
)
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.analyze_coverage import AnalyzeCoverageHerramienta
from qa_agent.tools.analyze_test_results import AnalyzeTestResultsHerramienta
from qa_agent.tools.base import Herramienta
from qa_agent.tools.crear_archivo import CrearArchivoHerramienta
from qa_agent.tools.editar_archivo import EditarArchivoHerramienta
from qa_agent.tools.eliminar_archivo import EliminarArchivoHerramienta
from qa_agent.tools.explore import ExploreHerramienta
from qa_agent.tools.generate_test_cases import GenerateTestCasesHerramienta
from qa_agent.tools.leer_archivo import LeerArchivoHerramienta
from qa_agent.tools.locate import LocateHerramienta
from qa_agent.tools.run_tests import RunTestsHerramienta
from qa_agent.tools.search import SearchHerramienta

load_dotenv()  # carga `.env` si existe (sin imprimir secretos)

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)
LLM_MODEL = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
LLM_API_KEY = os.environ.get("LLM_API_KEY", "").strip()


def construir_backend(demo: bool = False) -> LLMBackend:
    """Selecciona el backend LLM conforme a la configuración disponible.

    - `demo=True` (flag `--demo`) → `FakeLLM` sin proveedor.
    - Sin `LLM_API_KEY` → `FakeLLM` (pruebas/validación без red, SC-006).
    - Con `LLM_API_KEY` → `OpenAICompatibleBackend` (DeepSeek por defecto;
      NVIDIA/OpenAI vía `.env`).
    """
    if demo or not LLM_API_KEY:
        return FakeLLM()
    return OpenAICompatibleBackend(
        base_url=LLM_BASE_URL,
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
    )


def construir_allowlist(
    ruta: Path | str | None = None,
) -> Allowlist:
    """Construye la `Allowlist` con la ruta objetivo (mínimo privilegio).

    La raíz del proyecto a analizar es `ruta` o el directorio de trabajo
    actual (`cwd`) por defecto (FR-025).
    """
    ruta_objetivo = Path(ruta).resolve() if ruta is not None else Path.cwd()
    return Allowlist([ruta_objetivo])


def construir_herramientas(
    ruta: Path | str | None = None,
    backend: LLMBackend | None = None,
) -> list[Herramienta]:
    """Construye el catálogo de herramientas con la ruta objetivo autorizada.

    Todas las herramientas comparten la misma raíz autorizada (FR-025).
    `generate_test_cases` recibe el backend LLM para redactar los casos (VI).
    """
    allowlist = construir_allowlist(ruta)
    rutas = allowlist.perimetros
    return [
        ExploreHerramienta(rutas),
        LocateHerramienta(rutas),
        SearchHerramienta(rutas),
        LeerArchivoHerramienta(rutas),
        RunTestsHerramienta(rutas),
        AnalyzeTestResultsHerramienta(rutas),
        GenerateTestCasesHerramienta(rutas, llm_backend=backend),
        AnalyzeCoverageHerramienta(rutas),
        CrearArchivoHerramienta(rutas),
        EditarArchivoHerramienta(rutas),
        EliminarArchivoHerramienta(rutas),
    ]