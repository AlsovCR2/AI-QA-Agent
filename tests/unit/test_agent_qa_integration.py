"""Tests de integración de las herramientas QA/Testing en el flujo del agente
(T064, FR-003/004, FR-021).

Verifica que el enrutador determinitico (no LLM) dispara la herramienta QA
correcta, que el bucle la ejecuta, valida su resultado real contra el esquema,
y que las salidas pasan por el `Redactor` en respuesta e historial (SC-008).

`FakeLLM` por defecto selecciona "ninguna", así que la herramienta ejecutada
solo puede venir del enrutador → aísla el comportamiento a probar.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from qa_agent.agent.loop import Agent
from qa_agent.agent.response import Confianza, EstadoAccion
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.security.redactor import Redactor
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.analyze_coverage import AnalyzeCoverageHerramienta
from qa_agent.tools.analyze_test_results import AnalyzeTestResultsHerramienta
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)
from qa_agent.tools.generate_test_cases import GenerateTestCasesHerramienta
from qa_agent.tools.run_tests import RunTestsHerramienta

_SECRETO = "sk-abcdefghij123456"


def _fake_sin_seleccion(texto: str = "Respuesta determinista del FakeLLM.") -> FakeLLM:
    """FakeLLM cuyo fallback no selecciona herramienta (deja actuar al enrutador)."""
    return FakeLLM(
        seleccion={"ninguna": True},
        por_defecto={"texto": texto, "confianza": "alta"},
    )


def _stub_qa(herramienta_id: str, datos: dict, esquema_salida: dict) -> Herramienta:
    """Stub determinista con el `id` de una herramienta QA y su esquema de salida."""
    datos_fijos = datos
    # Nombres auxiliares: el cuerpo de la clase no ve el parámetro si su nombre
    # coincide con un atributo que define la propia clase (NameError de scope).
    esquema_fijo = esquema_salida
    esquema_entrada_fijo = {"type": "object", "properties": {}}

    class StubQA(Herramienta):
        id = herramienta_id
        nombre = herramienta_id
        descripcion = f"Stub de {herramienta_id} para integración (T064)."
        esquema_entrada = esquema_entrada_fijo
        esquema_salida = esquema_fijo
        requiere_autorizacion = False
        rutas_permitidas: list[str] = []

        def ejecutar(self, parametros: dict):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos=datos_fijos,
            )

    return StubQA()


_ESQUEMA_RESULTADOS = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string"},
        "fallos_agrupados": {"type": "array"},
    },
    "required": ["resumen", "fallos_agrupados"],
}

_ESQUEMA_CASOS = {
    "type": "object",
    "properties": {
        "casos_propuestos": {"type": "array"},
        "fuentes": {"type": "array"},
    },
    "required": ["casos_propuestos", "fuentes"],
}

_ESQUEMA_COBERTURA = {
    "type": "object",
    "properties": {
        "cobertura_global": {"type": "number"},
        "por_archivo": {"type": "array"},
        "estado": {"type": "string"},
    },
    "required": ["cobertura_global", "por_archivo", "estado"],
}


def test_agente_enruta_y_ejecuta_analyze_test_results(redactor):
    """'analiza estos resultados de prueba' ejecuta analyze_test_results (T064)."""
    datos = {
        "resumen": "Resumen: 1 fallada de 3 total. Estado global: fallo.",
        "fallos_agrupados": [
            {
                "ruta_relativa": "tests/test_app.py",
                "error_comun": f"assert 2 == 5 (token: {_SECRETO})",
                "posible_causa": "sin evidencia suficiente",
            }
        ],
    }
    agente = Agent(
        backend=_fake_sin_seleccion(),
        herramientas=[_stub_qa("analyze_test_results", datos, _ESQUEMA_RESULTADOS)],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("analiza estos resultados de prueba")
    assert respuesta.basada_en_herramientas
    accion = [
        a for a in respuesta.acciones if a.herramienta_id == "analyze_test_results"
    ][0]
    assert accion.estado == EstadoAccion.EXITO
    # FR-003/004: la respuesta usa el resultado real validado (redactado)
    assert accion.salida["resumen"] == datos["resumen"]
    assert accion.salida["fallos_agrupados"][0]["ruta_relativa"] == "tests/test_app.py"
    assert (
        accion.salida["fallos_agrupados"][0]["posible_causa"]
        == "sin evidencia suficiente"
    )
    # FR-021 / SC-008: el secreto de la salida no aparece en historial ni respuesta
    assert _SECRETO not in str(accion.salida)
    assert "token: ***" in str(accion.salida)
    assert _SECRETO not in respuesta.texto


def test_agente_enruta_y_ejecuta_generate_test_cases(redactor):
    """'genera casos de prueba para X' ejecuta generate_test_cases (T064)."""
    datos = {
        "casos_propuestos": [
            {
                "descripcion": "Caso básico para sumar",
                "entrada_esperada": "sumar(2, 2)",
                "resultado_esperado": "4",
                "tipo": "happy_path",
            }
        ],
        "fuentes": ["src/app.py"],
    }
    agente = Agent(
        backend=_fake_sin_seleccion(),
        herramientas=[_stub_qa("generate_test_cases", datos, _ESQUEMA_CASOS)],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("genera casos de prueba para la función sumar")
    assert respuesta.basada_en_herramientas
    accion = [
        a for a in respuesta.acciones if a.herramienta_id == "generate_test_cases"
    ][0]
    assert accion.estado == EstadoAccion.EXITO
    assert accion.salida["casos_propuestos"] == datos["casos_propuestos"]
    assert accion.salida["fuentes"] == ["src/app.py"]


def test_agente_enruta_y_ejecuta_analyze_coverage(redactor):
    """'analiza la cobertura' ejecuta analyze_coverage (T064)."""
    datos = {
        "cobertura_global": 75.0,
        "por_archivo": [
            {"ruta_relativa": "src/app.py", "cobertura": 75.0, "lineas_faltantes": []}
        ],
        "estado": "exito",
    }
    agente = Agent(
        backend=_fake_sin_seleccion("Cobertura real del 75%."),
        herramientas=[
            _stub_qa("analyze_coverage", datos, _ESQUEMA_COBERTURA)
        ],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("analiza la cobertura")
    assert respuesta.basada_en_herramientas
    accion = [
        a for a in respuesta.acciones if a.herramienta_id == "analyze_coverage"
    ][0]
    assert accion.estado == EstadoAccion.EXITO
    assert accion.salida["cobertura_global"] == 75.0
    assert accion.salida["estado"] == "exito"


def test_agente_analyze_coverage_real_con_resultado_real(tmp_path):
    """End-to-end: analyze_coverage REAL ejecutada por el loop usa resultado real.

    Se mockea solo `subprocess.run` (la salida de pytest-cov); el resto del
    flujo es real: enrutado → ejecución → validación contra el esquema →
    registro en historial.
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout=(
                "Name                 Stmts   Miss  Cover\n"
                "---------------------------------------\n"
                "src/calculadora.py       4      1    75%\n"
                "---------------------------------------\n"
                "TOTAL                    4      1    75%\n"
            ),
            stderr="",
            returncode=0,
        )
        agente = Agent(
            backend=_fake_sin_seleccion("Cobertura real del 75%."),
            herramientas=[AnalyzeCoverageHerramienta()],
            allowlist=None,
            redactor=Redactor(),
        )
        respuesta = agente.atender("analiza la cobertura", autorizacion=True)

    assert respuesta.basada_en_herramientas
    accion = [
        a for a in respuesta.acciones if a.herramienta_id == "analyze_coverage"
    ][0]
    assert accion.estado == EstadoAccion.EXITO
    assert accion.salida["cobertura_global"] == 75.0
    assert accion.salida["estado"] == "exito"


_SALIDA_PYTEST_CON_FALLO = (
    "============================= test session starts =============================\n"
    "FAILED tests/test_main.py::test_falla_intencionadamente - assert 2 == 5\n"
    "========================= 1 failed, 2 passed in 0.10s =========================\n"
)


def test_agente_analyze_test_results_encadena_run_tests(proyecto_ejemplo):
    """analyze_test_results encadena run_tests real y analiza su resultado.

    La secuencia run_tests → analyze_test_results queda registrada en el
    historial y la respuesta usa el análisis real (FR-003/004, T067).
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            stdout=_SALIDA_PYTEST_CON_FALLO,
            stderr="",
            returncode=1,
        )
        agente = Agent(
            backend=_fake_sin_seleccion("Análisis: 1 fallada de 3 total."),
            herramientas=[
                RunTestsHerramienta([str(proyecto_ejemplo)]),
                AnalyzeTestResultsHerramienta([str(proyecto_ejemplo)]),
            ],
            allowlist=Allowlist([proyecto_ejemplo]),
            redactor=Redactor(),
        )
        respuesta = agente.atender(
            "analiza estos resultados de prueba",
            autorizacion=True,
        )

    assert respuesta.basada_en_herramientas
    accion_atr = [
        a
        for a in respuesta.acciones
        if a.herramienta_id == "analyze_test_results"
    ][0]
    assert accion_atr.estado == EstadoAccion.EXITO
    assert "1 fallada" in accion_atr.salida["resumen"]
    assert accion_atr.salida["fallos_agrupados"]
    # La secuencia run_tests → analyze_test_results queda registrada (honestidad)
    accion_rt = [
        a for a in respuesta.acciones if a.herramienta_id == "run_tests"
    ]
    assert accion_rt and accion_rt[0].estado == EstadoAccion.EXITO


def test_agente_generate_test_cases_con_objetivo_extraido(proyecto_ejemplo):
    """generate_test_cases real usa el objetivo extraído de la solicitud.

    Sin LLM, genera casos deterministas citando el código real del proyecto
    (el objetivo 'sumar' se extrae de la frase) (FR-019, VI).
    """
    gtc = GenerateTestCasesHerramienta(
        [str(proyecto_ejemplo)], llm_backend=None
    )
    agente = Agent(
        backend=_fake_sin_seleccion("Casos sugeridos con fuentes reales."),
        herramientas=[gtc],
        allowlist=Allowlist([proyecto_ejemplo]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("genera casos de prueba para la función sumar")
    assert respuesta.basada_en_herramientas
    accion = [
        a for a in respuesta.acciones if a.herramienta_id == "generate_test_cases"
    ][0]
    assert accion.estado == EstadoAccion.EXITO
    # El objetivo extraído ('sumar') encuentra código real como evidencia
    assert accion.salida["fuentes"] and any(
        fuente.endswith("app.py") for fuente in accion.salida["fuentes"]
    )
    # Sin LLM genera casos básicos deterministas sobre el objetivo real
    assert accion.salida["casos_propuestos"]
    assert any(
        "sumar" in caso["descripcion"] or "sumar" in caso["entrada_esperada"]
        for caso in accion.salida["casos_propuestos"]
    )


def test_enrutador_delega_y_llm_sigue_seleccionando():
    """Sin palabras clave QA, el enrutador delega y el LLM elige igual."""
    from qa_agent.tools.base import EstadoResultado

    datos = {
        "ruta": ".",
        "existe": True,
        "accesible": True,
        "elementos": [{"nombre": "src", "tipo": "directorio"}],
    }

    class HerramientaEstructura(Herramienta):
        id = "explore"
        nombre = "explore"
        descripcion = "Explora la estructura del proyecto."
        esquema_entrada = {"type": "object", "properties": {}}
        esquema_salida = {"type": "object", "properties": {"ruta": {"type": "string"}}}
        requiere_autorizacion = False
        rutas_permitidas: list[str] = []

        def ejecutar(self, parametros: dict):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos=datos,
            )

    llm = FakeLLM(
        seleccion={"herramienta": "explore"},
        respuestas_por_solicitud={
            "¿cuál es la estructura?": {
                "texto": "La estructura contiene 'src'.",
                "confianza": "alta",
            }
        },
    )
    agente = Agent(
        backend=llm,
        herramientas=[HerramientaEstructura()],
        allowlist=None,
        redactor=Redactor(),
    )
    respuesta = agente.atender("¿cuál es la estructura?")
    assert respuesta.basada_en_herramientas
    assert any(a.herramienta_id == "explore" and a.estado == EstadoAccion.EXITO for a in respuesta.acciones)
