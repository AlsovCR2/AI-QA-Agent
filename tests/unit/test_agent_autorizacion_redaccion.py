"""Tests del rail de autorización y redacción integrado en el loop (T022/T023).

- T022: una herramienta con `requiere_autorizacion=True` suspende la ejecución
  y solicita autorización (FR-015/016, SC-004).
- T023: ningún secreto aparece en respuesta/historial (SC-008).

Nota: la autorización se resuelve en el rail de la US-6 completa; en US-1 solo
se comprueba que el loop la integra (suspende y no ejecuta hasta abitarse).
"""

from __future__ import annotations

from qa_agent.agent.response import EstadoAccion
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.security.redactor import Redactor
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)


class HerramientaSensible(Herramienta):
    """Herramienta que modifica/borra info del proyecto (UC-006)."""

    id = "run_tests"
    nombre = "run_tests"
    descripcion = "Ejecuta cambios en el proyecto."
    esquema_entrada = {"type": "object"}
    esquema_salida = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    requiere_autorizacion = True
    rutas_permitidas: list[str] = []

    def ejecutar(self, parametros: dict):
        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={"ok": True},
        )


def _fake_sensible():
    return FakeLLM(
        respuestas_por_solicitud={
            "ejecuta el cambio": {
                "seleccion": {"herramienta": "run_tests"},
                "texto": "Hecho.",
                "confianza": "alta",
            }
        }
    )


def test_accion_sensible_se_suspende_sin_ejecutar(redactor):
    from qa_agent.agent.loop import Agent

    agente = Agent(
        backend=_fake_sensible(),
        herramientas=[HerramientaSensible()],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("ejecuta el cambio")
    # Se suspende y solicita autorización (SC-004 / FR-015)
    assert "autorización" in respuesta.texto
    assert not respuesta.basada_en_herramientas
    # Registra estado pendiente_autorizacion en el historial
    assert any(
        a.estado == EstadoAccion.PENDIENTE_AUTORIZACION
        for a in respuesta.acciones
    )


def test_secretos_redactados_en_respuesta_anteloop(redactor):
    from qa_agent.agent.loop import Agent

    secreto = "sk-abcdefgh12345678"
    llm_quieto = FakeLLM(
        respuestas_por_solicitud={
            "hola": {
                "seleccion": {"ninguna": True},
                "texto": f"No herramienta. Token: {secreto}",
                "confianza": "alta",
            }
        }
    )
    agente = Agent(
        backend=llm_quieto,
        herramientas=[],
        allowlist=None,
        redactor=Redactor(),
    )
    respuesta = agente.atender("hola")
    assert secreto not in respuesta.texto
    assert "sk-" not in respuesta.texto


def test_salida_con_secreto_se_redacta_en_historial(redactor):
    from qa_agent.agent.loop import Agent

    # Herramienta que devuelve un secreto en la salida (no real, prueba)
    class HerramientaConSecreto(HerramientaSensible):
        id = "search"
        descripcion = "Busca patrones."
        requiere_autorizacion = False

        def ejecutar(self, parametros):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={"occurrencias": [{"token": "api_key=abc12345678"}]},
            )

    llm = FakeLLM(
        respuestas_por_solicitud={
            "busca": {
                "seleccion": {"herramienta": "search"},
                "texto": "Encontré una ocurrencia.",
                "confianza": "alta",
            }
        }
    )
    agente = Agent(
        backend=llm,
        herramientas=[HerramientaConSecreto()],
        allowlist=None,
        redactor=Redactor(),
    )
    respuesta = agente.atender("busca")
    # Ningún secreto en el historial ni la respuesta (SC-008)
    for accion in respuesta.acciones:
        assert "abc12345678" not in str(accion.salida)
    assert "abc12345678" not in respuesta.texto


# -- US6 plena: decisión del usuario (T043/T044) ------------------------------


def test_accion_autorizada_ejecuta_y_marca_ejecutada(redactor):
    """T043: autorización en True → se ejecuta y queda `ejecutada` (SC-004)."""
    from qa_agent.agent.loop import Agent
    from qa_agent.security.authorization import EstadoAutorizacion

    agente = Agent(
        backend=_fake_sensible(),
        herramientas=[HerramientaSensible()],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("ejecuta el cambio", autorizacion=True)

    assert respuesta.basada_en_herramientas
    assert any(
        a.estado == EstadoAccion.EXITO and a.herramienta_id == "run_tests"
        for a in respuesta.acciones
    )
    accion = agente._autorizaciones.obtener("a1")  # noqa: SLF001 - en test
    assert accion.estado == EstadoAutorizacion.EJECUTADA


def test_accion_denegada_no_ejecuta_y_notifica(redactor):
    """T043: autorización en False → no se ejecuta y notifica (FR-016)."""
    from qa_agent.agent.loop import Agent
    from qa_agent.security.authorization import EstadoAutorizacion

    agente = Agent(
        backend=_fake_sensible(),
        herramientas=[HerramientaSensible()],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("ejecuta el cambio", autorizacion=False)

    assert "denegada" in respuesta.texto.lower()
    assert not respuesta.basada_en_herramientas
    assert not any(
        a.estado == EstadoAccion.EXITO for a in respuesta.acciones
    )
    accion = agente._autorizaciones.obtener("a1")  # noqa: SLF001 - en test
    assert accion.estado == EstadoAutorizacion.NO_EJECUTADA


def test_cli_si_autoriza_y_ejecuta(monkeypatch, redactor):
    """T044: la CLI captura 'sí' y la acción se ejecuta."""
    from qa_agent.agent.loop import Agent
    from qa_agent.cli import main as cli

    agente = Agent(
        backend=_fake_sensible(),
        herramientas=[HerramientaSensible()],
        allowlist=None,
        redactor=redactor,
    )
    monkeypatch.setattr(cli._console, "input", lambda prompt: "sí")
    respuesta = cli._procesar_solicitud(agente, "ejecuta el cambio")
    assert respuesta.basada_en_herramientas
    assert any(
        a.estado == EstadoAccion.EXITO and a.herramienta_id == "run_tests"
        for a in respuesta.acciones
    )


def test_cli_no_deniega_y_no_ejecuta(monkeypatch, redactor):
    """T044: la CLI captura 'no' → no ejecuta y notifica (FR-016)."""
    from qa_agent.agent.loop import Agent
    from qa_agent.cli import main as cli

    agente = Agent(
        backend=_fake_sensible(),
        herramientas=[HerramientaSensible()],
        allowlist=None,
        redactor=redactor,
    )
    monkeypatch.setattr(cli._console, "input", lambda prompt: "no")
    respuesta = cli._procesar_solicitud(agente, "ejecuta el cambio")
    assert "denegada" in respuesta.texto.lower()
    assert not respuesta.basada_en_herramientas
    assert not any(a.estado == EstadoAccion.EXITO for a in respuesta.acciones)


def test_cli_sin_entrada_deniega_por_defecto_seguro(monkeypatch, redactor):
    """T044: sin confirmación positiva (EOF) → no ejecuta (SC-004)."""
    from qa_agent.agent.loop import Agent
    from qa_agent.cli import main as cli

    agente = Agent(
        backend=_fake_sensible(),
        herramientas=[HerramientaSensible()],
        allowlist=None,
        redactor=redactor,
    )

    def _eof(mensaje):
        raise EOFError("entrada no disponible")

    monkeypatch.setattr(cli._console, "input", _eof)
    respuesta = cli._procesar_solicitud(agente, "ejecuta el cambio")
    assert "denegada" in respuesta.texto.lower()
    assert not any(a.estado == EstadoAccion.EXITO for a in respuesta.acciones)