"""Regresiones de seguridad/correctitud para T125-T127."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from qa_agent.agent.loop import Agent
from qa_agent.agent.reasoning import PasoDePlan, Plan
from qa_agent.agent.session_manager import SesionManager
from qa_agent.cli.main import app
from qa_agent.llm.backend import LLMBackend
from qa_agent.security.redactor import Redactor
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.analyze_coverage import AnalyzeCoverageHerramienta
from qa_agent.tools.analyze_test_results import AnalyzeTestResultsHerramienta
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)
from qa_agent.tools.run_tests import RunTestsHerramienta


class _HerramientaConEvidenciaSecreta(Herramienta):
    id = "custom_probe"
    nombre = id
    descripcion = "Devuelve evidencia controlada para probar la frontera LLM."
    esquema_entrada = {"type": "object", "properties": {"ruta": {"type": "string"}}}
    esquema_salida = {
        "type": "object",
        "properties": {"evidencia": {"type": "string"}},
        "required": ["evidencia"],
    }
    requiere_autorizacion = False

    def __init__(self, evidencia: str) -> None:
        self.evidencia = evidencia

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={"evidencia": self.evidencia},
        )


class _BackendGrabador(LLMBackend):
    nombre = "grabador"
    requiere_api_key = False
    proveedor_requerido = False

    def __init__(self, *, react: bool, herramienta: str = "custom_probe") -> None:
        self.soporta_razonamiento = react
        self.herramienta = herramienta
        self.recibido: dict[str, list[str]] = {}

    def _grabar(self, metodo: str, *argumentos: Any) -> None:
        self.recibido.setdefault(metodo, []).append(repr(argumentos))

    def interpretar(self, solicitud: dict[str, Any]) -> dict[str, Any]:
        self._grabar("interpretar", solicitud)
        return {}

    def seleccionar_herramienta(
        self, solicitud: dict[str, Any], herramientas: list[Any]
    ) -> dict[str, Any]:
        self._grabar("seleccionar_herramienta", solicitud, herramientas)
        return {"herramienta": self.herramienta}

    def generar_respuesta(
        self, solicitud: dict[str, Any], resultados: list[Any]
    ) -> dict[str, Any]:
        self._grabar("generar_respuesta", solicitud, resultados)
        return {"texto": "Respuesta segura.", "confianza": "alta"}

    def planificar(
        self, intencion: Any, catalogo: list[Any], contexto: dict[str, Any]
    ) -> Plan:
        self._grabar("planificar", intencion, catalogo, contexto)
        paso = PasoDePlan(
            orden=1,
            razon="Obtener evidencia",
            herramienta=self.herramienta,
            parametros={"ruta": "."},
            criterio_salida="evidencia disponible",
        )
        return Plan(
            pasos=[paso],
            pendientes=[paso],
            criterio_exito="evidencia disponible",
        )

    def razonar(self, estado: Any, pendientes: list[Any]) -> dict[str, Any]:
        self._grabar("razonar", estado, pendientes)
        return {"concluir": True}

    def evaluar(self, estado: Any, observaciones: list[Any]) -> dict[str, Any]:
        self._grabar("evaluar", estado, observaciones)
        return {"satisfecha": False, "razon": "concluir tras revisar"}

    def responder(
        self, observaciones: list[Any], intencion: str = ""
    ) -> dict[str, Any]:
        self._grabar("responder", observaciones, intencion)
        return {"texto": "Respuesta segura.", "confianza": "limitada"}


def _assert_frontera_redactada(
    backend: _BackendGrabador, secretos: tuple[str, ...]
) -> None:
    registrado = repr(backend.recibido)
    for secreto in secretos:
        assert secreto not in registrado
    assert "***" in registrado


def test_t125_una_pasada_redacta_solicitud_y_resultado_antes_del_backend():
    """Falla si selección/respuesta reciben solicitud o evidencia cruda."""
    secreto_usuario = "sk-usuario12345678"
    secreto_herramienta = "api_key=herramienta12345678"
    backend = _BackendGrabador(react=False)
    agente = Agent(
        backend=backend,
        herramientas=[_HerramientaConEvidenciaSecreta(secreto_herramienta)],
        redactor=Redactor(),
    )

    respuesta = agente.atender(f"inspecciona el componente {secreto_usuario}")

    assert respuesta.texto == "Respuesta segura."
    _assert_frontera_redactada(
        backend, (secreto_usuario, secreto_herramienta)
    )


def test_t125_react_redacta_contexto_y_observaciones_en_todas_las_llamadas():
    """Falla si planificar/razonar/evaluar/responder reciben secretos crudos."""
    secreto_usuario = "sk-reactusuario12345678"
    secreto_contexto = "Bearer contexto12345678"
    secreto_herramienta = "api_key=observacion12345678"
    backend = _BackendGrabador(react=True)
    agente = Agent(
        backend=backend,
        herramientas=[_HerramientaConEvidenciaSecreta(secreto_herramienta)],
        redactor=Redactor(),
        pasos_max=3,
    )

    respuesta = agente.atender(
        f"revisa el componente {secreto_usuario}",
        contexto={"nota": secreto_contexto},
    )

    assert respuesta.texto == "Respuesta segura."
    assert {"planificar", "evaluar", "razonar", "responder"} <= set(
        backend.recibido
    )
    _assert_frontera_redactada(
        backend, (secreto_usuario, secreto_contexto, secreto_herramienta)
    )


def _agente_de_ejecucion(tmp_path, herramienta_id: str) -> Agent:
    herramientas = [
        RunTestsHerramienta([str(tmp_path)]),
        AnalyzeTestResultsHerramienta([str(tmp_path)]),
        AnalyzeCoverageHerramienta([str(tmp_path)]),
    ]
    return Agent(
        backend=_BackendGrabador(
            react=False,
            herramienta=herramienta_id,
        ),
        herramientas=herramientas,
        allowlist=Allowlist([str(tmp_path)]),
        redactor=Redactor(),
    )


def _proceso_pytest_exitoso() -> SimpleNamespace:
    return SimpleNamespace(
        stdout="================ 1 passed in 0.01s ================",
        stderr="",
        returncode=0,
    )


def _proceso_cobertura_exitoso() -> SimpleNamespace:
    return SimpleNamespace(
        stdout=(
            "Name Stmts Miss Cover\n"
            "---------------------\n"
            "src/mod.py 10 0 100%\n"
            "TOTAL 10 0 100%\n"
        ),
        stderr="",
        returncode=0,
    )


def test_t126_analisis_indirecto_pendiente_no_ejecuta_subproceso(tmp_path):
    agente = _agente_de_ejecucion(tmp_path, "analyze_test_results")

    with patch("subprocess.run", return_value=_proceso_pytest_exitoso()) as ejecutar:
        respuesta = agente.atender("analiza los resultados de las pruebas")

    ejecutar.assert_not_called()
    assert "pendiente de autorización" in respuesta.texto


def test_t126_analisis_indirecto_denegado_no_ejecuta_subproceso(tmp_path):
    agente = _agente_de_ejecucion(tmp_path, "analyze_test_results")

    with patch("subprocess.run", return_value=_proceso_pytest_exitoso()) as ejecutar:
        respuesta = agente.atender(
            "analiza los resultados de las pruebas",
            autorizacion=False,
        )

    ejecutar.assert_not_called()
    assert "denegada" in respuesta.texto.lower()


def test_t126_analisis_indirecto_aprobado_puede_ejecutar(tmp_path):
    agente = _agente_de_ejecucion(tmp_path, "analyze_test_results")

    with patch("subprocess.run", return_value=_proceso_pytest_exitoso()) as ejecutar:
        respuesta = agente.atender(
            "analiza los resultados de las pruebas",
            autorizacion=True,
        )

    ejecutar.assert_called_once()
    assert respuesta.basada_en_herramientas


def test_t126_cobertura_pendiente_no_ejecuta_subproceso(tmp_path):
    agente = _agente_de_ejecucion(tmp_path, "analyze_coverage")

    with patch("subprocess.run", return_value=_proceso_cobertura_exitoso()) as ejecutar:
        respuesta = agente.atender("analiza la cobertura")

    ejecutar.assert_not_called()
    assert "pendiente de autorización" in respuesta.texto


def test_t126_cobertura_denegada_no_ejecuta_subproceso(tmp_path):
    agente = _agente_de_ejecucion(tmp_path, "analyze_coverage")

    with patch("subprocess.run", return_value=_proceso_cobertura_exitoso()) as ejecutar:
        respuesta = agente.atender("analiza la cobertura", autorizacion=False)

    ejecutar.assert_not_called()
    assert "denegada" in respuesta.texto.lower()


def test_t126_cobertura_aprobada_puede_ejecutar(tmp_path):
    agente = _agente_de_ejecucion(tmp_path, "analyze_coverage")

    with patch("subprocess.run", return_value=_proceso_cobertura_exitoso()) as ejecutar:
        respuesta = agente.atender("analiza la cobertura", autorizacion=True)

    ejecutar.assert_called_once()
    assert respuesta.basada_en_herramientas


def test_t127_construir_gestor_no_crea_directorio_persistente(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    SesionManager()

    assert not (tmp_path / ".qa_sessions").exists()


def test_t127_cli_no_expone_chat_persistente():
    resultado = CliRunner().invoke(app, ["--help"])

    assert resultado.exit_code == 0
    assert "chat" not in resultado.output.lower()


def test_t127_uso_mvp_una_pasada_y_react_no_crea_qa_sessions(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    herramienta = _HerramientaConEvidenciaSecreta("evidencia")

    una_pasada = Agent(
        backend=_BackendGrabador(react=False),
        herramientas=[herramienta],
        redactor=Redactor(),
    )
    una_pasada.atender("revisa el proyecto")

    react = Agent(
        backend=_BackendGrabador(react=True),
        herramientas=[herramienta],
        redactor=Redactor(),
        pasos_max=3,
    )
    react.atender("revisa el proyecto")

    assert not (tmp_path / ".qa_sessions").exists()
