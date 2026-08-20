"""Herramientas del agente: capacidades ejecutables con contrato de entrada/salida.

Registro y selección de herramientas. Cada herramienta es un componente
independiente (principio II) que no contiene lógica de agente (principio I).
"""

from __future__ import annotations

from qa_agent.tools.analyze_coverage import AnalyzeCoverageHerramienta
from qa_agent.tools.analyze_test_results import AnalyzeTestResultsHerramienta
from qa_agent.tools.crear_archivo import CrearArchivoHerramienta
from qa_agent.tools.editar_archivo import EditarArchivoHerramienta
from qa_agent.tools.eliminar_archivo import EliminarArchivoHerramienta
from qa_agent.tools.explore import ExploreHerramienta
from qa_agent.tools.generate_test_cases import GenerateTestCasesHerramienta
from qa_agent.tools.leer_archivo import LeerArchivoHerramienta
from qa_agent.tools.locate import LocateHerramienta
from qa_agent.tools.run_tests import RunTestsHerramienta
from qa_agent.tools.search import SearchHerramienta

__all__: list[str] = [
    "AnalyzeCoverageHerramienta",
    "AnalyzeTestResultsHerramienta",
    "CrearArchivoHerramienta",
    "EditarArchivoHerramienta",
    "EliminarArchivoHerramienta",
    "ExploreHerramienta",
    "GenerateTestCasesHerramienta",
    "LeerArchivoHerramienta",
    "LocateHerramienta",
    "RunTestsHerramienta",
    "SearchHerramienta",
]

_HERRAMIENTAS_REGISTRO: dict[str, type] = {
    "analyze_coverage": AnalyzeCoverageHerramienta,
    "analyze_test_results": AnalyzeTestResultsHerramienta,
    "crear_archivo": CrearArchivoHerramienta,
    "editar_archivo": EditarArchivoHerramienta,
    "eliminar_archivo": EliminarArchivoHerramienta,
    "explore": ExploreHerramienta,
    "generate_test_cases": GenerateTestCasesHerramienta,
    "leer_archivo": LeerArchivoHerramienta,
    "locate": LocateHerramienta,
    "run_tests": RunTestsHerramienta,
    "search": SearchHerramienta,
}


def obtener_herramienta(nombre: str, rutas_permitidas: list[str] | None = None):
    """Obtiene una instancia de herramienta registrada."""
    if nombre not in _HERRAMIENTAS_REGISTRO:
        raise ValueError(f"Herramienta no registrada: {nombre}")
    return _HERRAMIENTAS_REGISTRO[nombre](rutas_permitidas)


def listar_herramientas() -> list[str]:
    """Lista los IDs de herramientas disponibles."""
    return list(_HERRAMIENTAS_REGISTRO.keys())