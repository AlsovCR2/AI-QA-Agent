"""Tests de honestidad y límites del agente (T045, US7).

Cubre los requisitos FR-017 (falta de información), FR-018 (errores/inválidos
manejados explícitamente, no presentados como válidos), FR-022/023 (ninguna
herramienta adecuada → notificación + sugerencia, sin forzar ejecución) y los
criterios SC-002 / SC-005 / SC-009 (UC-007).

`FakeLLM` por defecto selecciona "ninguna", por lo que las solicitudes no
enrutadas no ejecutan herramienta: aísla el comportamiento de honestidad.
"""

from __future__ import annotations

from qa_agent.agent.loop import Agent
from qa_agent.agent.response import Confianza, EstadoAccion
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.security.redactor import Redactor
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)

_SOLICITUD_SIN_ALCANCE = "¿cuántas líneas tiene el archivo que no existe.md?"
_SOLICITUD_ESTRUCTURA = "explora la estructura del proyecto"

_ESQUEMA_EXPLORE = {
    "type": "object",
    "properties": {
        "ruta": {"type": "string"},
        "existe": {"type": "boolean"},
        "accesible": {"type": "boolean"},
        "elementos": {"type": "array"},
    },
    "required": ["ruta", "existe", "accesible", "elementos"],
}


def _fake_sin_herramienta() -> FakeLLM:
    """FakeLLM que nunca selecciona herramienta ("ninguna" por defecto)."""
    return FakeLLM(
        seleccion={"ninguna": True},
        por_defecto={"texto": "Respuesta determinista del FakeLLM.", "confianza": "alta"},
    )


def _stub_explore(ejecutar: callable) -> Herramienta:
    """Stub `explore` instanciable con implementación de `ejecutar` inyectada.

    `ejecutar` se define dentro del cuerpo de la clase (cierre) para que
    satisfaga el método abstracto de `Herramienta` antes de instanciar.
    """
    esquema_entrada_fijo = {"type": "object", "properties": {"ruta": {"type": "string"}}}

    class StubExplorador(Herramienta):
        id = "explore"
        nombre = "explore"
        descripcion = "Explora la estructura del proyecto."
        esquema_entrada = esquema_entrada_fijo
        esquema_salida = _ESQUEMA_EXPLORE
        requiere_autorizacion = False
        rutas_permitidas: list[str] = []

        def ejecutar(self, parametros: dict) -> ResultadoDeHerramienta:
            return ejecutar(parametros)

    return StubExplorador()


def _resultado_exito() -> ResultadoDeHerramienta:
    return ResultadoDeHerramienta(
        herramienta_id="explore",
        estado=EstadoResultado.EXITO,
        datos={
            "ruta": ".",
            "existe": True,
            "accesible": True,
            "elementos": [],
        },
    )


# -- FR-022/023, SC-009: ninguna herramienta adecuada --------------------------


def test_sin_herramienta_adecuada_notifica_y_sugiere_sin_ejecutar(redactor):
    """Solicitud no enrutable + LLM 'ninguna' → notificación + sugerencia.

    No se ejecuta herramienta alguna y se sugiere ajustar la solicitud
    (FR-022/023, SC-009).
    """
    agente = Agent(
        backend=_fake_sin_herramienta(),
        herramientas=[_stub_explore(lambda parametros: _resultado_exito())],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender(_SOLICITUD_SIN_ALCANCE)

    assert respuesta.confianza == Confianza.SIN_INFORMACION
    assert not respuesta.basada_en_herramientas
    assert "no dispongo" in respuesta.texto.lower()
    # Sugiere ajustes a la solicitud (FR-022)
    assert "prueba" in respuesta.texto.lower()
    # No se ejecuta ni se registra ninguna acción (FR-023)
    assert respuesta.acciones == []


def test_no_se_ejecuta_herramienta_inexistente_seleccionada_por_llm(redactor):
    """El LLM fuerza una herramienta inexistente → se abstiene de ejecutar.

    FR-023: cuando ninguna herramienta es adecuada (o la elegida no existe),
    el agente no fuerza una ejecución y notifica.
    """
    llm = FakeLLM(
        seleccion={"herramienta": "herramienta_inexistente"},
        por_defecto={"texto": "Respuesta determinista del FakeLLM.", "confianza": "alta"},
    )
    agente = Agent(
        backend=llm,
        herramientas=[_stub_explore(lambda parametros: _resultado_exito())],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("responde a esto por favor")

    assert respuesta.confianza == Confianza.SIN_INFORMACION
    assert not respuesta.basada_en_herramientas
    assert respuesta.acciones == []
    assert "no dispongo" in respuesta.texto.lower()


# -- FR-017, SC-002: sin información → no inventar -----------------------------


def test_resultado_real_vacio_no_inventa_contenido(redactor):
    """Herramienta devuelve estructura real sin elementos → no se inventa nada.

    La respuesta se basa en la herramienta (FR-003/004) pero el contenido real
    vacío se preserva sin fabricar datos (FR-019, SC-002).
    """
    llm = FakeLLM(
        seleccion={"ninguna": True},
        por_defecto={"texto": "Estructura real sin elementos.", "confianza": "alta"},
    )
    agente = Agent(
        backend=llm,
        herramientas=[_stub_explore(lambda parametros: _resultado_exito())],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender(_SOLICITUD_ESTRUCTURA)

    assert respuesta.basada_en_herramientas
    accion = [a for a in respuesta.acciones if a.herramienta_id == "explore"][0]
    assert accion.estado == EstadoAccion.EXITO
    # El resultado real (vacío) se preserva: no se inventan elementos
    assert accion.salida["elementos"] == []
    assert accion.salida["existe"] is True


def test_confianza_sin_informacion_se_propaga(redactor):
    """Backend comunica falta de información → la respuesta lo refleja.

    FR-017 / SC-002: el agente no inventa contenido y transmite la confianza
    limitada del backend.
    """
    llm = FakeLLM(
        seleccion={"ninguna": True},
        por_defecto={
            "texto": "No tengo suficiente información para responder con confianza.",
            "confianza": "sin_informacion",
        },
    )
    agente = Agent(
        backend=llm,
        herramientas=[_stub_explore(lambda parametros: _resultado_exito())],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("¿por qué falla este test?")

    assert respuesta.confianza == Confianza.SIN_INFORMACION
    assert not respuesta.basada_en_herramientas


# -- FR-018, SC-005: resultados inválidos / errores explícitos -----------------


def test_resultado_invalido_no_se_presenta_como_valido(redactor):
    """Resultado EXITO pero que no cumple el esquema → explícito, no válido.

    SC-005: el resultado inválido se maneja explícitamente y no se presenta
    como válido; no se registra ninguna acción EXITO.
    """

    def ejecutar_invalido(parametros: dict) -> ResultadoDeHerramienta:
        return ResultadoDeHerramienta(
            herramienta_id="explore",
            estado=EstadoResultado.EXITO,
            datos={"ruta": "."},  # faltan existe/accesible/elementos
        )

    agente = Agent(
        backend=_fake_sin_herramienta(),
        herramientas=[_stub_explore(ejecutar_invalido)],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender(_SOLICITUD_ESTRUCTURA)

    assert respuesta.confianza == Confianza.LIMITADA
    assert not respuesta.basada_en_herramientas
    assert "no cumpl" in respuesta.texto or "inválido" in respuesta.texto.lower()
    assert not any(a.estado == EstadoAccion.EXITO for a in respuesta.acciones)
    assert any(a.estado == EstadoAccion.INVALIDO for a in respuesta.acciones)


def test_resultado_estado_error_no_se_presenta_como_valido(redactor):
    """Herramienta devuelve estado ERROR → explícito, no se usa como verdad.

    SC-005 / FR-018: un resultado `error` no se convierte en fuente de verdad
    y se comunica de forma explícita.
    """

    def ejecutar_error(parametros: dict) -> ResultadoDeHerramienta:
        return ResultadoDeHerramienta(
            herramienta_id="explore",
            estado=EstadoResultado.ERROR,
            datos={"error": "no se pudo acceder a la ruta"},
        )

    agente = Agent(
        backend=_fake_sin_herramienta(),
        herramientas=[_stub_explore(ejecutar_error)],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender(_SOLICITUD_ESTRUCTURA)

    assert respuesta.confianza == Confianza.LIMITADA
    assert not respuesta.basada_en_herramientas
    assert not any(a.estado == EstadoAccion.EXITO for a in respuesta.acciones)
    assert any(a.estado == EstadoAccion.ERROR for a in respuesta.acciones)


def test_excepcion_de_herramienta_se_comunica_explicitamente(redactor):
    """La herramienta lanza una excepción → el error se comunica.

    FR-018: el fallo de ejecución se maneja explícitamente (acción ERROR) y
    no se presenta ningún resultado como válido.
    """

    def ejecutar_que_falla(parametros: dict) -> ResultadoDeHerramienta:
        raise RuntimeError("permiso denegado")

    agente = Agent(
        backend=_fake_sin_herramienta(),
        herramientas=[_stub_explore(ejecutar_que_falla)],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender(_SOLICITUD_ESTRUCTURA)

    assert respuesta.confianza == Confianza.LIMITADA
    assert not respuesta.basada_en_herramientas
    assert "falló" in respuesta.texto or "fallo" in respuesta.texto
    assert "permiso denegado" in respuesta.texto
    assert not any(a.estado == EstadoAccion.EXITO for a in respuesta.acciones)
    assert any(a.estado == EstadoAccion.ERROR for a in respuesta.acciones)


# -- T049, FR-019 / SC-002: no-invención transversal (smoke con catálogo real) --


def test_humo_pregunta_fuera_de_alcance_no_inventa_datos(proyecto_ejemplo):
    """Smoke T049: catálogo real + pregunta fuera de alcance → sin inventar.

    Con las herramientas reales construidas por `construir_herramientas`, una
    pregunta sin herramienta adecuada no ejecuta nada ni fabrica datos
    (FR-019/022/023, SC-002).
    """
    from qa_agent.config import construir_herramientas
    from qa_agent.tools.allowlist import Allowlist

    agente = Agent(
        backend=FakeLLM(),  # seleccion {"ninguna": True} por defecto
        herramientas=construir_herramientas(proyecto_ejemplo),
        allowlist=Allowlist([proyecto_ejemplo]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("¿cuál es el sentido de la vida?")

    assert respuesta.confianza == Confianza.SIN_INFORMACION
    assert not respuesta.basada_en_herramientas
    assert respuesta.acciones == []
    assert "no dispongo" in respuesta.texto.lower()


def test_humo_busqueda_sin_coincidencias_no_inventa(proyecto_ejemplo):
    """Smoke T049: búsqueda sin coincidencias → ausencia real, no inventada.

    Con el catálogo real, una búsqueda que no encuentra coincidencias reporta
    la ausencia real (`ocurrencias == []`) sin fabricar resultados (FR-008/019).
    """
    from qa_agent.config import construir_herramientas
    from qa_agent.tools.allowlist import Allowlist

    agente = Agent(
        backend=FakeLLM(
            por_defecto={
                "texto": "No encontré coincidencias para ese patrón.",
                "confianza": "alta",
            }
        ),
        herramientas=construir_herramientas(proyecto_ejemplo),
        allowlist=Allowlist([proyecto_ejemplo]),
        redactor=Redactor(),
    )
    respuesta = agente.atender(
        "busca el patrón zzzPatronQueNoExisteNada en el código"
    )

    assert respuesta.basada_en_herramientas
    accion = [a for a in respuesta.acciones if a.herramienta_id == "search"][0]
    assert accion.estado == EstadoAccion.EXITO
    assert accion.salida["ocurrencias"] == []