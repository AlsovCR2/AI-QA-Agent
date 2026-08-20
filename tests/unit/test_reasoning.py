"""Tests del bucle de razonamiento-acción (Phase 12 / T076).

Modelos del agente: `Intencion`, `PasoDePlan`, `Plan`, `Observacion`,
`EstadoDelAgente` (data-model §Entidades de razonamiento-acción). Ver
`agent-reasoning-loop.md`.
"""

from __future__ import annotations

import pytest

from qa_agent.agent.loop import Agent
from qa_agent.agent.reasoning import (
    EstadoDelAgente,
    Intencion,
    Observacion,
    PasoDePlan,
    Plan,
    # Phase 13 / T085
    EstadoTarea,
    TareaAgente,
    Turno,
    Memoria,
    Conversacion,
)
from qa_agent.agent.response import Confianza
from qa_agent.llm.backend import LLMBackend
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.security.redactor import Redactor
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import Herramienta


def test_intencion_campos():
    intencion = Intencion(
        texto="¿cuáles clases son las más importantes de probar?",
        objetivo="priorizar pruebas",
        entidad="clases",
        contexto={"ruta_base": "."},
    )
    assert intencion.objetivo == "priorizar pruebas"
    assert intencion.entidad == "clases"
    assert intencion.contexto == {"ruta_base": "."}


def test_paso_de_plan_campos():
    paso = PasoDePlan(
        orden=1,
        razon="conocer la estructura y capas",
        herramienta="explore",
        parametros={"ruta": ".", "profundidad_max": 3},
        criterio_salida="lista de directorios y archivos reales",
    )
    assert paso.orden == 1
    assert paso.herramienta == "explore"
    assert paso.parametros["profundidad_max"] == 3
    assert paso.criterio_salida


def test_plan_campos_y_pendientes():
    paso1 = PasoDePlan(
        orden=1,
        razon="explorar estructura",
        herramienta="explore",
        parametros={"ruta": "."},
        criterio_salida="estructura",
    )
    paso2 = PasoDePlan(
        orden=2,
        razon="obtener definiciones de clase",
        herramienta="search",
        parametros={"ruta": ".", "patron_regex": r"class\s+\w+"},
        criterio_salida="clases reales",
    )
    plan = Plan(
        objetivo="priorizar clases a probar",
        criterio_exito="listar clases reales por capa",
        pasos=[paso1, paso2],
        pendientes=[paso1, paso2],
    )
    assert plan.pasos == [paso1, paso2]
    assert plan.pendientes == [paso1, paso2]
    assert plan.criterio_exito.startswith("listar")


def test_observacion_campos():
    paso = PasoDePlan(
        orden=1,
        razon="explorar",
        herramienta="explore",
        parametros={"ruta": "."},
        criterio_salida="estructura",
    )
    observacion = Observacion(
        paso=paso,
        resultado=None,
        evaluacion="la estructura confirma las capas BLL/DAL",
    )
    assert observacion.paso is paso
    assert observacion.evaluacion


def test_estado_inicial():
    intencion = Intencion(texto="x", objetivo="y", entidad="z")
    estado = EstadoDelAgente(intencion=intencion, pasos_max=5)
    assert estado.pasos_ejecutados == 0
    assert estado.observaciones == []
    assert estado.plan is None


def test_estado_pasos_max_por_defecto():
    intencion = Intencion(texto="x", objetivo="y", entidad="z")
    estado = EstadoDelAgente(intencion=intencion)
    assert estado.pasos_max == 12


def test_estado_respeta_pasos_max():
    intencion = Intencion(texto="x", objetivo="y", entidad="z")
    estado = EstadoDelAgente(intencion=intencion, pasos_max=2)
    assert not estado.excedio_pasos_max()
    estado.pasos_ejecutados = 1
    assert not estado.excedio_pasos_max()
    estado.pasos_ejecutados = 2
    assert estado.excedio_pasos_max()


def test_estado_sin_plan_ni_pasos_max_personalizado():
    intencion = Intencion(texto="x", objetivo="y", entidad="z")
    estado = EstadoDelAgente(intencion=intencion, pasos_max=0)
    assert estado.excedio_pasos_max()


# -- T077: contrato LLM de razonamiento + FakeLLM determinista ---------------


def _catalogo():
    from tests.unit.test_recomendaciones import _StubExplore

    return [_StubExplore(), _StubSearch()]


class _StubSearch(Herramienta):
    """`search` instanciable para el bucle multi-paso."""

    id = "search"
    nombre = "search"
    descripcion = "Busca patrones en el código."
    esquema_entrada = {
        "type": "object",
        "properties": {"ruta": {"type": "string"}, "patron_regex": {"type": "string"}},
    }
    esquema_salida = {
        "type": "object",
        "properties": {"ruta": {"type": "string"}, "coincidencias": {"type": "array"}},
    }
    requiere_autorizacion = False

    def ejecutar(self, parametros: dict):
        from qa_agent.tools.base import EstadoResultado, ResultadoDeHerramienta

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "ruta": parametros.get("ruta", "."),
                "coincidencias": ["BLL/Cliente", "BLL/Reserva"],
            },
        )


def test_fake_llm_planificar_devuelve_plan():
    from qa_agent.llm.fake_llm import FakeLLM

    backend = FakeLLM(
        plan={
            "objetivo": "priorizar pruebas",
            "criterio_exito": "listar clases reales",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "conocer la estructura",
                    "herramienta": "explore",
                    "parametros": {"ruta": ".", "profundidad_max": 3},
                    "criterio_salida": "estructura real",
                }
            ],
        }
    )
    plan = backend.planificar(
        Intencion(texto="¿qué clases probar?"), _catalogo(), {}
    )

    assert isinstance(plan, Plan)
    assert plan.objetivo == "priorizar pruebas"
    assert plan.pasos[0].herramienta == "explore"
    assert plan.pasos[0].parametros["profundidad_max"] == 3
    assert plan.pendientes[0].orden == 1


def test_fake_llm_planificar_usa_solo_herramientas_del_catalogo():
    from qa_agent.llm.fake_llm import FakeLLM

    backend = FakeLLM(
        plan={
            "pasos": [
                {"orden": 1, "razon": "x", "herramienta": "no_existe",
                 "parametros": {}, "criterio_salida": ""}
            ]
        }
    )
    plan = backend.planificar(
        Intencion(texto="x"), _catalogo(), {}
    )

    assert plan.pasos == []


def test_fake_llm_razonar_concluye_o_devuelve_paso():
    from qa_agent.llm.fake_llm import FakeLLM

    backend_concluir = FakeLLM(razonar={"concluir": True})
    assert backend_concluir.razonar(
        EstadoDelAgente(intencion=Intencion(texto="x")), [PasoDePlan(
            orden=1, razon="r", herramienta="explore", parametros={}
        )]
    ) == {"concluir": True}

    backend_paso = FakeLLM(
        razonar={
            "herramienta": "explore",
            "parametros": {"ruta": ".", "profundidad_max": 2},
            "razon": "más profundidad",
        }
    )
    siguiente = backend_paso.razonar(
        EstadoDelAgente(intencion=Intencion(texto="x")), [PasoDePlan(
            orden=1, razon="r", herramienta="explore", parametros={}
        )]
    )
    assert siguiente["herramienta"] == "explore"
    assert siguiente["parametros"]["profundidad_max"] == 2


def test_fake_llm_evaluar_satisfecha():
    from qa_agent.llm.fake_llm import FakeLLM

    backend = FakeLLM(evaluar={"satisfecha": True, "razon": "evidencia suficiente"})
    resultado = backend.evaluar(
        EstadoDelAgente(intencion=Intencion(texto="x")), [PasoDePlan(
            orden=1, razon="r", herramienta="explore", parametros={}
        )]
    )
    assert resultado["satisfecha"] is True
    assert resultado["razon"]


def test_fake_llm_responder_incluye_recomendaciones():
    from qa_agent.llm.fake_llm import FakeLLM

    backend = FakeLLM(
        responder={
            "texto": "Las clases más críticas están en BLL.",
            "confianza": "limitada",
            "recomendaciones": ["Prioriza la capa DAL."],
        }
    )
    resultado = backend.responder([PasoDePlan(
        orden=1, razon="r", herramienta="explore", parametros={}
    )])

    assert resultado["texto"].startswith("Las clases")
    assert resultado["recomendaciones"] == ["Prioriza la capa DAL."]
    assert resultado["confianza"] == "limitada"


def test_openai_backend_planificar_convierte_json():
    """`OpenAICompatibleBackend.planificar` llama al LLM y construye un `Plan`."""
    from unittest.mock import Mock, patch

    from qa_agent.llm.openai_compatible_backend import OpenAICompatibleBackend

    backend = OpenAICompatibleBackend(
        base_url="https://api.example.com/v1",
        model="test-model",
        api_key="sk-test",
    )
    mock_message = Mock()
    mock_message.content = (
        '{"objetivo": "priorizar pruebas", "criterio_exito": "listar clases", '
        '"pasos": [{"orden": 1, "razon": "estructura", "herramienta": "explore", '
        '"parametros": {"ruta": "."}, "criterio_salida": "estructura"}]}'
    )
    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_respuesta = Mock()
    mock_respuesta.choices = [mock_choice]

    with patch.object(backend._client.chat.completions, "create",
                      Mock(return_value=mock_respuesta)):
        plan = backend.planificar(
            Intencion(texto="¿qué clases probar?"), _catalogo(), {}
        )

    assert isinstance(plan, Plan)
    assert plan.pasos[0].herramienta == "explore"
    assert plan.criterio_exito == "listar clases"


# -- T079: validación de parámetros propuestos por el LLM (FR-033/FR-025) ------


def _agente_react_plan(pasos: list[dict], responder: dict | None = None) -> Agent:
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "priorizar pruebas",
            "criterio_exito": "evidencia",
            "pasos": pasos,
        },
        responder=responder
        or {"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    return Agent(
        backend=backend,
        herramientas=_catalogo(),
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )


def test_parametros_fuera_del_esquema_no_se_ejecutan():
    """Parámetros que no cumplen el esquema de entrada se rechazan sin ejecutar."""
    agente = _agente_react_plan(
        [
            {
                "orden": 1,
                "razon": "explorar con profundidad inválida",
                "herramienta": "explore",
                "parametros": {"ruta": ".", "profundidad_max": 999},
                "criterio_salida": "",
            }
        ]
    )
    respuesta = agente.atender("explora")

    acciones_error = [a for a in respuesta.acciones if a.estado.value == "error"]
    assert acciones_error
    assert "profundidad" in str(acciones_error[0].salida) or "invalido" in str(
        acciones_error[0].salida
    )


def test_ruta_fuera_de_allowlist_no_se_ejecuta():
    """Una ruta fuera de la allowlist se rechaza sin ejecutar (FR-025)."""
    from qa_agent.agent.loop import Agent

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "pasos": [
                {"orden": 1, "razon": "fuera de ruta", "herramienta": "explore",
                 "parametros": {"ruta": "../secretos"}, "criterio_salida": ""}
            ]
        },
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=_catalogo(),
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("explora")

    assert not [a for a in respuesta.acciones if a.estado.value == "exito"]
    assert any("ruta_no_autorizada" in str(a.salida) for a in respuesta.acciones)


def test_herramienta_inexistente_en_el_paso_no_se_ejecuta():
    """Un paso que referencia una herramienta inexistente se ignora (FR-032)."""
    agente = _agente_react_plan(
        [
            {
                "orden": 1,
                "razon": "herramienta inventada",
                "herramienta": "no_existe",
                "parametros": {},
                "criterio_salida": "",
            }
        ]
    )
    respuesta = agente.atender("explora")

    assert not respuesta.acciones


def test_ruta_inyectada_cuando_llm_propone_parametro_distinto():
    """Si el LLM propone un parámetro distinto a `ruta`, se inyecta la raíz autorizada (FR-025)."""
    agente = _agente_react_plan(
        [
            {
                "orden": 1,
                "razon": "explorar",
                "herramienta": "explore",
                "parametros": {"ruta_base": "C:\\tmp\\otro"},
                "criterio_salida": "",
            }
        ]
    )
    respuesta = agente.atender("explora")

    exito = [a for a in respuesta.acciones if a.estado.value == "exito"]
    assert exito
    assert exito[0].herramienta_id == "explore"


# -- T081: límite de pasos_max (SC-016) ---------------------------------------


class _RazonadorQueAvanza(LLMBackend):
    """Propone un paso NUEVO en cada llamada a `razonar` (variando los
    parámetros) para ejercitar el límite pasos_max sin colisionar con el dedup
    de pasos idénticos (T112)."""

    nombre = "razonador_avanza"
    requiere_api_key = False
    proveedor_requerido = False
    soporta_razonamiento = True

    def __init__(self, evaluar, responder):
        self._evaluar = evaluar
        self._responder = responder
        self._n = 0

    def interpretar(self, solicitud):
        return {}

    def seleccionar_herramienta(self, solicitud, herramientas):
        return {"ninguna": True}

    def generar_respuesta(self, solicitud, resultados):
        return {}

    def planificar(self, intencion, catalogo, contexto):
        p1 = PasoDePlan(1, "e1", "explore", {"ruta": ".", "profundidad_max": 2})
        return Plan("o", "c", [p1], [p1])

    def razonar(self, estado, pendientes):
        self._n += 1
        return {
            "herramienta": "explore",
            "parametros": {"ruta": ".", "profundidad_max": 2 + self._n},
            "razon": "reintento",
        }

    def evaluar(self, estado, observaciones):
        return dict(self._evaluar)

    def responder(self, observaciones, intencion=""):
        return dict(self._responder)


def test_pasos_max_corta_el_bucle_y_responde_con_confianza_limitada():
    """Con evaluador que nunca satisface, el bucle termina en pasos_max (SC-016)."""
    from qa_agent.agent.loop import Agent

    backend = _RazonadorQueAvanza(
        evaluar={"satisfecha": False, "razon": "nunca suficiente"},
        responder={
            "texto": "no pude completar",
            "confianza": "limitada",
            "recomendaciones": ["revisa manualmente"],
        },
    )
    agente = Agent(
        backend=backend,
        herramientas=_catalogo(),
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
        pasos_max=3,
    )
    respuesta = agente.atender("explora")

    assert len([a for a in respuesta.acciones]) >= 3
    assert respuesta.confianza.value == "limitada"
    assert respuesta.recomendaciones == ["revisa manualmente"]


# -- T080: re-planificación ante autorización denegada (FR-036) ---------------


class _RunTestsSensible(Herramienta):
    """`run_tests` sensible: requiere autorización (SC-004)."""

    id = "run_tests"
    nombre = "run_tests"
    descripcion = "Ejecuta las pruebas del proyecto."
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "comando_pruebas": {"type": "string"},
        },
    }
    esquema_salida = {"type": "object", "properties": {"resumen": {"type": "object"}}}
    requiere_autorizacion = True

    def ejecutar(self, parametros: dict):
        from qa_agent.tools.base import EstadoResultado, ResultadoDeHerramienta

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={"resumen": {"pasadas": 1, "falladas": 0}},
        )


def test_denegacion_no_aborta_y_replanifica_con_paso_no_sensible():
    """Un paso sensible denegado no aborta: continúa con el paso no sensible."""
    from qa_agent.agent.loop import Agent

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "analizar",
            "criterio_exito": "evidencia",
            "pasos": [
                {"orden": 1, "razon": "ejecutar tests", "herramienta": "run_tests",
                 "parametros": {"ruta": "."}, "criterio_salida": ""},
                {"orden": 2, "razon": "explorar estructura",
                 "herramienta": "explore", "parametros": {"ruta": "."},
                 "criterio_salida": ""},
            ],
        },
        responder={"texto": "continué con explore", "confianza": "limitada",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_RunTestsSensible()] + _catalogo(),
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("analiza", autorizacion=False)

    denegada = [a for a in respuesta.acciones if a.estado.value == "error"]
    assert denegada
    assert "denegada" in str(denegada[0].salida)
    exito = [a for a in respuesta.acciones if a.estado.value == "exito"]
    assert any(a.herramienta_id == "explore" for a in exito)
    assert respuesta.texto == "continué con explore"


def test_sin_alternativa_responde_con_lo_obtenido_y_confianza_limitada():
    """Sin paso alternativo no sensible, responde con lo obtenido (FR-036)."""
    from qa_agent.agent.loop import Agent

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "pasos": [
                {"orden": 1, "razon": "ejecutar tests", "herramienta": "run_tests",
                 "parametros": {"ruta": "."}, "criterio_salida": ""},
            ]
        },
        responder={"texto": "no pude ejecutar los tests",
                   "confianza": "limitada", "recomendaciones": ["autoriza el paso"]},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_RunTestsSensible()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("ejecuta tests", autorizacion=False)

    assert respuesta.confianza.value == "limitada"
    assert respuesta.recomendaciones == ["autoriza el paso"]
    assert any("denegada" in str(a.salida) for a in respuesta.acciones)


# -- T082: visibilidad del razonamiento (FR-035 / SC-015) ---------------------


def test_historial_incluye_la_razon_de_cada_paso():
    """Cada acción del historial expone la razón por la que se ejecutó (FR-035)."""
    agente = _agente_react(
        pasos=[
            {"orden": 1, "razon": "conocer la estructura",
             "herramienta": "explore", "parametros": {"ruta": "."},
             "criterio_salida": ""},
        ],
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    respuesta = agente.atender("explora")

    registro = respuesta.acciones[-1]
    assert "conocer la estructura" in str(registro.entrada)


def test_respuesta_expone_el_razonamiento_completo():
    """`RespuestaDelAgente.razonamiento` lista las observaciones por pasos."""
    agente = _agente_react(
        pasos=[
            {"orden": 1, "razon": "estructura", "herramienta": "explore",
             "parametros": {"ruta": "."}, "criterio_salida": ""},
        ],
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    respuesta = agente.atender("explora")

    assert len(respuesta.razonamiento) == 1
    assert respuesta.razonamiento[0].paso.razon == "estructura"
    assert respuesta.razonamiento[0].resultado is not None


def test_razonamiento_pasa_por_el_redactor():
    """La razón de cada paso se redacta antes de exponerse (SC-008)."""
    agente = _agente_react(
        pasos=[
            {"orden": 1, "razon": "usar la API key sk-secreto123",
             "herramienta": "explore", "parametros": {"ruta": "."},
             "criterio_salida": ""},
        ],
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    respuesta = agente.atender("explora")

    razon_mostrada = respuesta.razonamiento[0].paso.razon
    assert "sk-secreto123" not in razon_mostrada
    assert "***" in razon_mostrada


# -- T083: honestidad del razonamiento (SC-017 / FR-019) ----------------------


def test_responder_que_inventa_no_produce_afirmaciones_sin_observacion():
    """La respuesta final no puede fabricar datos: sin observaciones → sin evidencia."""
    from qa_agent.agent.loop import Agent

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "pasos": [
                {"orden": 1, "razon": "x", "herramienta": "explore",
                 "parametros": {"ruta": "."}, "criterio_salida": ""},
            ]
        },
        responder={"texto": "Hay 100 clases en BLL.", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=_catalogo(),
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("¿cuántas clases hay?")

    # La observación real de explore no contiene "100 clases" → el agente debe
    # degradar o anclar, nunca afirmar lo no observado.
    assert "100 clases" not in respuesta.texto or respuesta.confianza != Confianza.ALTA


def test_evidencia_real_produce_afirmacion_anclada():
    """Una afirmación anclada en una observación real se mantiene (SC-017)."""
    agente = _agente_react(
        pasos=[
            {"orden": 1, "razon": "buscar clases", "herramienta": "search",
             "parametros": {"ruta": ".", "patron_regex": r"class\s+\w+"},
             "criterio_salida": ""},
        ],
        responder={"texto": "Encontré BLL/Cliente y BLL/Reserva.",
                   "confianza": "alta", "recomendaciones": []},
    )
    respuesta = agente.atender("¿qué clases hay?")

    assert "BLL/Cliente" in respuesta.texto
    assert respuesta.confianza == Confianza.ALTA


def test_respuesta_profunda_con_palabras_al_inicio_de_frase_no_se_degrada():
    """SC-017: las palabras en mayúscula al inicio de frase NO son afirmaciones
    de datos; una respuesta profunda y anclada mantiene confianza ALTA (T107)."""
    agente = _agente_react(
        pasos=[
            {"orden": 1, "razon": "leer tests de dominio", "herramienta": "search",
             "parametros": {"ruta": ".", "patron_regex": r"class\s+\w+"},
             "criterio_salida": ""},
        ],
        responder={"texto": "Cliente y Reserva están en BLL. Aplicación los usa.",
                   "confianza": "alta", "recomendaciones": []},
    )
    respuesta = agente.atender("¿qué clases hay?")

    assert respuesta.confianza == Confianza.ALTA


def test_pasos_max_corta_el_bucle_y_responde_con_confianza_limitada():
    """Con evaluador que nunca satisface, el bucle termina en pasos_max (SC-016)."""
    from qa_agent.agent.loop import Agent

    backend = _RazonadorQueAvanza(
        evaluar={"satisfecha": False, "razon": "nunca suficiente"},
        responder={
            "texto": "no pude completar",
            "confianza": "limitada",
            "recomendaciones": ["revisa manualmente"],
        },
    )
    agente = Agent(
        backend=backend,
        herramientas=_catalogo(),
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
        pasos_max=3,
    )
    respuesta = agente.atender("explora")

    assert len([a for a in respuesta.acciones]) >= 3
    assert respuesta.confianza.value == "limitada"
    assert respuesta.recomendaciones == ["revisa manualmente"]


def _agente_react(pasos: list[dict], responder: dict) -> Agent:
    """Agente con FakeLLM configurado para razonamiento multi-paso."""
    from qa_agent.agent.loop import Agent
    from qa_agent.security.redactor import Redactor
    from qa_agent.tools.allowlist import Allowlist

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "priorizar pruebas",
            "criterio_exito": "obtener clases reales",
            "pasos": pasos,
        },
        responder=responder,
    )
    return Agent(
        backend=backend,
        herramientas=_catalogo(),
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )


def test_react_ejecuta_plan_multi_paso_y_responde():
    """El agente ejecuta varios pasos y la respuesta se basa en observaciones."""
    agente = _agente_react(
        pasos=[
            {
                "orden": 1,
                "razon": "conocer la estructura",
                "herramienta": "explore",
                "parametros": {"ruta": ".", "profundidad_max": 3},
                "criterio_salida": "estructura",
            },
            {
                "orden": 2,
                "razon": "obtener clases",
                "herramienta": "search",
                "parametros": {"ruta": ".", "patron_regex": r"class\s+\w+"},
                "criterio_salida": "clases",
            },
        ],
        responder={
            "texto": "Las clases más críticas están en BLL.",
            "confianza": "limitada",
            "recomendaciones": ["Prioriza DAL."],
        },
    )
    respuesta = agente.atender("¿cuáles clases probar?")

    assert "BLL" in respuesta.texto
    assert respuesta.basada_en_herramientas
    assert len([a for a in respuesta.acciones if a.estado.value == "exito"]) >= 2
    assert respuesta.recomendaciones == ["Prioriza DAL."]


class _StubLeerArchivo(Herramienta):
    """`leer_archivo` instanciable para el bucle (T104 / FR-048)."""

    id = "leer_archivo"
    nombre = "leer_archivo"
    descripcion = "Lee el contenido completo de un archivo."
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "archivo_relativo": {"type": "string"},
        },
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "archivo": {"type": "string"},
            "existe": {"type": "boolean"},
            "contenido": {"type": "string"},
        },
    }
    requiere_autorizacion = False

    def ejecutar(self, parametros: dict):
        from qa_agent.tools.base import EstadoResultado, ResultadoDeHerramienta

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "archivo": parametros.get("archivo_relativo", ""),
                "existe": True,
                "contenido": "def sumar(a, b):\n    return a + b\n",
            },
        )


def test_react_ejecuta_paso_leer_archivo_con_archivo_relativo(tmp_path):
    """T104: un paso `leer_archivo` se ejecuta y el loop inyecta la ruta base
    autorizada y el `archivo_relativo` extraído de la solicitud (FR-025/FR-048)."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "explicar qué hace cada capa",
            "criterio_exito": "contenido de los archivos leído",
            "pasos": [
                {"orden": 1, "razon": "leer el test de la capa aplicación",
                 "herramienta": "leer_archivo",
                 "parametros": {"ruta": ".", "archivo_relativo": "tests/test_app.py"},
                 "criterio_salida": "contenido real del archivo"},
            ],
        },
        responder={"texto": "El test valida la suma (sumar(2,2)==4).",
                   "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_StubLeerArchivo()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("explica qué hace tests/test_app.py")

    exito = [a for a in respuesta.acciones if a.estado.value == "exito"]
    assert len(exito) == 1
    assert exito[0].herramienta_id == "leer_archivo"
    assert "tests/test_app.py" in str(exito[0].entrada)
    assert respuesta.basada_en_herramientas


def test_react_observacion_guarda_parametros_realmente_ejecutados():
    """T114: cuando el plan se agota y `razonar` propone un archivo distinto al
    del paso del plan, la observación registra los parámetros REALMENTE
    ejecutados (y su razón), no los del paso del plan ya completado (FR-035)."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "explicar las capas",
            "criterio_exito": "contenido leído",
            "pasos": [
                {"orden": 1, "razon": "leer la aplicación",
                 "herramienta": "leer_archivo",
                 "parametros": {"ruta": ".", "archivo_relativo": "tests/test_app.py"},
                 "criterio_salida": "contenido real"},
            ],
        },
        razonar={
            "herramienta": "leer_archivo",
            "parametros": {"archivo_relativo": "src/ventana_principal.py"},
            "razon": "leer la presentación",
        },
        evaluar={"satisfecha": False, "razon": "falta más evidencia"},
        responder={"texto": "análisis por capas", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_StubLeerArchivo()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
        pasos_max=6,
    )
    respuesta = agente.atender("explica la estructura del proyecto")

    observaciones = list(respuesta.razonamiento)
    assert len(observaciones) >= 2
    # 1ª: paso del plan; 2ª: paso nuevo del razonamiento con sus parámetros reales.
    plan_obs = observaciones[0]
    assert plan_obs.paso.parametros["archivo_relativo"] == "tests/test_app.py"
    razonar_obs = observaciones[1]
    assert razonar_obs.paso.parametros["archivo_relativo"] == "src/ventana_principal.py"
    assert razonar_obs.paso.razon == "leer la presentación"


def test_react_leer_archivo_placeholder_se_deriva_de_la_solicitud():
    """T111: un `archivo_relativo` tipo placeholder ('{{...}}') se sustituye por
    el archivo real extraído de la solicitud en vez de ejecutarse tal cual."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "explicar qué pruebas hace la capa",
            "criterio_exito": "contenido leído",
            "pasos": [
                {"orden": 1, "razon": "leer el test de la capa",
                 "herramienta": "leer_archivo",
                 "parametros": {"ruta": ".", "archivo_relativo": "{{ruta_relativa_archivo_prueba}}"},
                 "criterio_salida": "contenido real"},
            ],
        },
        responder={"texto": "El test valida la suma.", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_StubLeerArchivo()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("explica qué hace tests/test_app.py")

    exito = [a for a in respuesta.acciones if a.estado.value == "exito"]
    assert len(exito) == 1
    assert exito[0].herramienta_id == "leer_archivo"
    assert "tests/test_app.py" in str(exito[0].entrada)
    assert "{{" not in str(exito[0].entrada)


def test_react_leer_archivo_placeholder_sin_archivo_se_rechaza():
    """T111: si el placeholder no puede resolverse desde la solicitud (sin
    archivo.ext), el paso se rechaza sin ejecutar (estado archivo_no_identificado)
    y el bucle no ejecuta una lectura sin sentido."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "detectar pruebas",
            "criterio_exito": "evidencia",
            "pasos": [
                {"orden": 1, "razon": "leer un archivo de prueba",
                 "herramienta": "leer_archivo",
                 "parametros": {"ruta": ".", "archivo_relativo": "{{ruta_relativa_archivo_prueba}}"},
                 "criterio_salida": ""},
            ],
        },
        responder={"texto": "sin evidencia", "confianza": "limitada",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_StubLeerArchivo()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("¿se están efectuando pruebas en este proyecto?")

    assert not [a for a in respuesta.acciones if a.estado.value == "exito"]
    errores = [a for a in respuesta.acciones if a.estado.value == "error"]
    assert any("archivo_no_identificado" in str(a.salida) for a in errores)
    assert "{{" not in respuesta.texto


def test_react_no_repite_pasos_identicos_ya_ejecutados():
    """T112: un paso idéntico (misma herramienta y mismos parámetros) ya
    ejecutado se omite registrando `paso_repetido`, sin volver a llamar a la
    herramienta (regresión: `locate` repetido 4 veces en una sesión real)."""
    llamadas = {"search": 0}

    class _RepiteSearch(Herramienta):
        id = "search"
        nombre = "search"
        descripcion = "buscar coincidencias (stub determinista)"
        esquema_entrada = {
            "type": "object",
            "properties": {
                "ruta": {"type": "string"},
                "patron_regex": {"type": "string"},
            },
            "required": ["patron_regex"],
        }
        esquema_salida = {
            "type": "object",
            "properties": {"coincidencias": {"type": "array", "items": {"type": "object"}}},
            "required": ["coincidencias"],
        }
        requiere_autorizacion = False

        def ejecutar(self, parametros):
            llamadas["search"] += 1
            from qa_agent.tools.base import EstadoResultado, ResultadoDeHerramienta

            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={"coincidencias": []},
            )

    class _Repite(LLMBackend):
        nombre = "repite"
        requiere_api_key = False
        proveedor_requerido = False
        soporta_razonamiento = True

        def interpretar(self, solicitud):
            return {}

        def seleccionar_herramienta(self, solicitud, herramientas):
            return {"ninguna": True}

        def generar_respuesta(self, solicitud, resultados):
            return {}

        def planificar(self, intencion, catalogo, contexto):
            p1 = PasoDePlan(
                1, "e1", "search", {"ruta": ".", "patron_regex": "BLL"}
            )
            return Plan("o", "c", [p1], [p1])

        def razonar(self, estado, pendientes):
            return {
                "herramienta": "search",
                "parametros": {"ruta": ".", "patron_regex": "BLL"},
                "razon": "repetir",
            }

        def evaluar(self, estado, observaciones):
            return {"satisfecha": False, "razon": "sigue"}

        def responder(self, observaciones, intencion=""):
            return {
                "texto": "sin más evidencia",
                "confianza": "limitada",
                "recomendaciones": [],
            }

    agente = Agent(
        backend=_Repite(),
        herramientas=[_RepiteSearch()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
        pasos_max=6,
    )
    respuesta = agente.atender("identifica dónde aparece BLL")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    assert len(exitos) == 1
    assert llamadas["search"] == 1
    repetidos = [a for a in respuesta.acciones if "paso_repetido" in str(a.salida)]
    assert repetidos


def test_react_registra_observaciones_reales():
    """Cada paso produce una observación real registrada en el historial."""
    agente = _agente_react(
        pasos=[
            {
                "orden": 1,
                "razon": "explorar",
                "herramienta": "explore",
                "parametros": {"ruta": "."},
                "criterio_salida": "estructura",
            }
        ],
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    respuesta = agente.atender("explora el proyecto")

    registros = respuesta.acciones
    assert len(registros) >= 1
    assert registros[-1].herramienta_id == "explore"
    assert registros[-1].estado.value == "exito"


def test_react_errores_de_herramienta_no_fabrican_evidencia():
    """Un paso fallido no produce afirmaciones (FR-018, SC-005)."""
    from qa_agent.agent.loop import Agent
    from qa_agent.security.redactor import Redactor
    from qa_agent.tools.allowlist import Allowlist
    from qa_agent.tools.base import EstadoResultado, ResultadoDeHerramienta

    class _Explota(Herramienta):
        id = "explore"
        nombre = "explore"
        descripcion = "explora"
        esquema_entrada = {"type": "object", "properties": {}}
        esquema_salida = {"type": "object", "properties": {}}
        requiere_autorizacion = False

        def ejecutar(self, parametros):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error="boom",
            )

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "pasos": [
                {"orden": 1, "razon": "r", "herramienta": "explore",
                 "parametros": {}, "criterio_salida": ""}
            ]
        },
        responder={"texto": "no hay evidencia", "confianza": "sin_informacion",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_Explota()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("explora")

    assert respuesta.acciones[-1].estado.value == "error"
    assert respuesta.confianza.value == "sin_informacion"


def test_react_ejecuta_pendientes_sin_razonar_por_paso():
    """Con plan multi-paso, el bucle ejecuta los pendientes sin llamar a
    `razonar` en cada paso (optimización de llamadas LLM); `razonar` solo
    re-planifica cuando el plan se agota."""
    llamadas = {"planificar": 0, "razonar": 0, "evaluar": 0, "responder": 0}

    class _Contador(LLMBackend):
        nombre = "contador"
        requiere_api_key = False
        proveedor_requerido = False
        soporta_razonamiento = True

        def interpretar(self, solicitud):
            return {}

        def seleccionar_herramienta(self, solicitud, herramientas):
            return {"ninguna": True}

        def generar_respuesta(self, solicitud, resultados):
            return {}

        def planificar(self, intencion, catalogo, contexto):
            llamadas["planificar"] += 1
            p1 = PasoDePlan(1, "e1", "explore", {"ruta": "."})
            p2 = PasoDePlan(2, "e2", "explore", {"ruta": ".", "profundidad_max": 2})
            return Plan("o", "c", [p1, p2], [p1, p2])

        def razonar(self, estado, pendientes):
            llamadas["razonar"] += 1
            return {"concluir": True}

        def evaluar(self, estado, observaciones):
            llamadas["evaluar"] += 1
            return {"satisfecha": True, "razon": ""}

        def responder(self, observaciones, intencion=""):
            llamadas["responder"] += 1
            return {"texto": "ok", "confianza": "alta", "recomendaciones": []}

    from qa_agent.agent.loop import Agent
    from qa_agent.security.redactor import Redactor
    from qa_agent.tools.allowlist import Allowlist

    agente = Agent(
        backend=_Contador(),
        herramientas=_catalogo(),
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
        pasos_max=3,
    )
    respuesta = agente.atender("explora")

    # Los dos pasos del plan se ejecutan directamente (sin razonar por paso);
    # razonar se invoca solo al agotarse el plan para decidir concluir.
    assert llamadas["planificar"] == 1
    assert llamadas["evaluar"] == 1
    assert llamadas["responder"] == 1
    assert len([a for a in respuesta.acciones if a.estado.value == "exito"]) >= 2


# -- T085: Modelos conversacionales (Phase 13) ----------------------------------


def test_tarea_agente_campos_y_estado():
    """TareaAgente se crea con estado pendiente y permite actualizar."""
    tarea = TareaAgente(titulo="Explorar proyecto", descripcion="...", prioridad=1)
    assert tarea.estado == EstadoTarea.PENDIENTE
    assert tarea.prioridad == 1
    assert tarea.creada_en <= tarea.actualizada_en

    tarea.actualizar_estado(EstadoTarea.EN_PROGRESO)
    assert tarea.estado == EstadoTarea.EN_PROGRESO
    assert tarea.actualizada_en >= tarea.creada_en


def test_tarea_agente_dependencias_y_etiquetas():
    """TareaAgente soporta dependencias y etiquetas."""
    t1 = TareaAgente(titulo="Paso 1")
    t2 = TareaAgente(titulo="Paso 2", dependencias=[t1.id], etiquetas=["qa"])
    assert t1.id in t2.dependencias
    assert "qa" in t2.etiquetas


def test_turno_campos():
    """Turno registra un intercambio con timestamp y herramientas."""
    turno = Turno(numero=1, usuario="¿qué clases probar?", agente="Respuesta...")
    assert turno.numero == 1
    assert turno.usuario.startswith("¿qué")
    assert turno.timestamp is not None


def test_memoria_hechos_y_preferencias():
    """Memoria almacena hechos, preferencias y proyectos conocidos."""
    m = Memoria()
    m.recordar_hecho("proyecto_actual", "ReservaHotel")
    m.preferencias["idioma"] = "es"
    m.proyectos_conocidos.append("ReservaHotel")
    assert m.hechos["proyecto_actual"] == "ReservaHotel"
    assert m.preferencias["idioma"] == "es"
    assert "ReservaHotel" in m.proyectos_conocidos
    m.olvidar_hecho("proyecto_actual")
    assert "proyecto_actual" not in m.hechos


def test_conversacion_turnos_y_tareas():
    """Conversacion mantiene historial, resumen, hechos y tareas."""
    conv = Conversacion()
    t1 = Turno(numero=1, usuario="hola", agente="hola")
    t2 = Turno(numero=2, usuario="¿clases?", agente="BLL...")
    conv.agregar_turno(t1)
    conv.agregar_turno(t2)
    assert len(conv.turnos) == 2
    assert conv.obtener_ultimos_turnos(1)[0].usuario == "¿clases?"

    tarea = TareaAgente(titulo="Explorar", descripcion="...")
    conv.agregar_tarea(tarea)
    pendientes = conv.obtener_tareas_pendientes()
    assert len(pendientes) == 1
    assert pendientes[0].estado == EstadoTarea.PENDIENTE


def test_conversacion_hechos_y_resumen():
    """Conversacion almacena hechos aprendidos y resumen."""
    conv = Conversacion()
    conv.hechos["framework"] = ".NET"
    conv.resumen = "Proyecto ReservaHotel analizado"
    assert conv.hechos["framework"] == ".NET"
    assert "ReservaHotel" in conv.resumen


# -- T086: SesionManager (persistencia) --------------------------------------


def test_sesion_manager_guardar_y_cargar_json(tmp_path):
    """SesionManager guarda y carga conversaciones en JSON."""
    from qa_agent.agent.session_manager import SesionManager

    mgr = SesionManager(base_dir=tmp_path, usar_sqlite=False)
    conv = Conversacion()
    conv.agregar_turno(Turno(1, "hola", "hola"))
    conv.agregar_tarea(TareaAgente(titulo="Tarea 1"))
    conv.hechos["clave"] = "valor"
    conv.resumen = "resumen prueba"

    mgr.guardar(conv)
    conv2 = mgr.cargar(conv.id)

    assert conv2 is not None
    assert conv2.id == conv.id
    assert len(conv2.turnos) == 1
    assert conv2.turnos[0].usuario == "hola"
    assert len(conv2.tareas) == 1
    assert conv2.tareas[0].titulo == "Tarea 1"
    assert conv2.hechos["clave"] == "valor"
    assert conv2.resumen == "resumen prueba"


def test_sesion_manager_listar_y_borrar(tmp_path):
    """SesionManager lista y borra sesiones."""
    from qa_agent.agent.session_manager import SesionManager

    mgr = SesionManager(base_dir=tmp_path, usar_sqlite=False)
    conv1 = Conversacion()
    conv1.agregar_turno(Turno(1, "a", "b"))
    mgr.guardar(conv1)
    conv2 = Conversacion()
    conv2.agregar_turno(Turno(1, "c", "d"))
    mgr.guardar(conv2)

    lista = mgr.listar()
    assert len(lista) == 2
    assert lista[0]["id"] in {conv1.id, conv2.id}

    borrado = mgr.borrar(conv1.id)
    assert borrado is True
    assert mgr.cargar(conv1.id) is None
    lista2 = mgr.listar()
    assert len(lista2) == 1


# -- T087: GestorTareas (CRUD) ------------------------------------------------


def test_gestor_tareas_crud():
    """GestorTareas crea, lista, actualiza estado y borra tareas."""
    from qa_agent.agent.gestor_tareas import GestorTareas

    g = GestorTareas()
    t = g.crear("Revisar cobertura", descripcion="...", prioridad=2, etiquetas=["cobertura"])
    assert t.id in g.tareas
    assert g.obtener(t.id).prioridad == 2
    assert len(g.listar()) == 1

    g.cambiar_estado(t.id, EstadoTarea.EN_PROGRESO)
    assert g.obtener(t.id).estado == EstadoTarea.EN_PROGRESO

    g.actualizar(t.id, prioridad=5)
    assert g.obtener(t.id).prioridad == 5

    assert g.borrar(t.id) is True
    assert g.obtener(t.id) is None


def test_gestor_tareas_filtros_y_dependencias():
    """GestorTareas filtra por estado/etiqueta y detecta bloqueos."""
    from qa_agent.agent.gestor_tareas import GestorTareas

    g = GestorTareas()
    base = g.crear("Preparar entorno", prioridad=1, asignado_a="agente")
    dep = g.crear(
        "Ejecutar pruebas",
        prioridad=3,
        dependencias=[base.id],
        asignado_a="agente",
        etiquetas=["tests"],
    )

    assert len(g.pendientes_para("agente")) == 2
    prox = g.proximas_acciones("agente")
    assert prox == [base]
    assert len(g.bloqueadas_por(base.id)) == 1

    g.cambiar_estado(base.id, EstadoTarea.COMPLETADA)
    prox2 = g.proximas_acciones("agente")
    assert dep in prox2


def test_gestor_tareas_serializacion():
    """GestorTareas se puede serializar/deserializar."""
    from qa_agent.agent.gestor_tareas import GestorTareas

    g = GestorTareas()
    g.crear("Tarea A", prioridad=1, etiquetas=["x"])
    data = g.a_dict()
    g2 = GestorTareas.desde_dict(data)
    assert len(g2.tareas) == 1
    assert g2.listar()[0].titulo == "Tarea A"


def test_conversacion_hechos_y_resumen():
    """Conversacion almacena hechos aprendidos y resumen."""
    conv = Conversacion()
    conv.hechos["framework"] = ".NET"
    conv.resumen = "Proyecto ReservaHotel analizado"
    assert conv.hechos["framework"] == ".NET"
    assert "ReservaHotel" in conv.resumen


def test_react_usa_la_pregunta_como_intencion():
    """La intención percibida llega al backend (contexto de razonamiento)."""
    plan_guardado = {}

    class _Captura(LLMBackend):
        nombre = "captura"
        requiere_api_key = False
        proveedor_requerido = False
        soporta_razonamiento = True

        def interpretar(self, solicitud): return {}
        def seleccionar_herramienta(self, solicitud, herramientas):
            return {"ninguna": True}
        def generar_respuesta(self, solicitud, resultados): return {}

        def planificar(self, intencion, catalogo, contexto):
            plan_guardado["texto"] = intencion.texto
            plan_guardado["objetivo"] = intencion.objetivo
            return Plan(pendientes=[])

        def razonar(self, estado, pendientes): return {"concluir": True}
        def evaluar(self, estado, observaciones):
            return {"satisfecha": True, "razon": ""}
        def responder(self, observaciones, intencion=""):
            return {"texto": "ok", "confianza": "alta", "recomendaciones": []}

    from qa_agent.agent.loop import Agent
    from qa_agent.security.redactor import Redactor
    from qa_agent.tools.allowlist import Allowlist

    agente = Agent(
        backend=_Captura(),
        herramientas=_catalogo(),
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    agente.atender("¿cuáles clases son críticas para probar?")

    assert plan_guardado["texto"] == "¿cuáles clases son críticas para probar?"


# -- T088/T090: AgentConversacional (chat + tareas + memoria) -----------------


def _catalogo_para_chat():
    """Catálogo de herramientas para AgentConversacional (reutiliza helper)."""
    from qa_agent.tools.allowlist import Allowlist
    from qa_agent.security.redactor import Redactor

    allowlist = Allowlist(["."])
    return _catalogo(), allowlist, Redactor()


def _crear_conversacional(backend, tmp_path, **kwargs):
    from qa_agent.agent.conversational import AgentConversacional

    catalogo, allowlist, redactor = _catalogo_para_chat()
    return AgentConversacional(
        backend=backend,
        herramientas=catalogo,
        allowlist=allowlist,
        redactor=redactor,
        base_dir=str(tmp_path),
        **kwargs,
    )


def test_agent_conversacional_delega_qa_a_react(tmp_path):
    """Intención QA (análisis) se delega al bucle ReAct interno."""
    from qa_agent.agent.conversational import AgentConversacional

    backend = FakeLLM(
        seleccion={"herramienta": "search"},
        soporta_razonamiento=True,
        plan={"pasos": [{"orden": 1, "herramienta": "search",
                         "razon": "buscar clases en el código"}]},
    )
    conversacional = _crear_conversacional(backend, tmp_path)
    respuesta = conversacional.atender("¿qué clases de negocio hay en el código?")

    assert respuesta.basada_en_herramientas or respuesta.texto
    assert len(conversacional.conversacion.turnos) == 1
    turno = conversacional.conversacion.turnos[0]
    assert "search" in turno.herramientas_usadas


def test_agent_conversacional_responde_directo_sin_qa(tmp_path):
    """Conversación general (saludo) no delega al ReAct: sin herramientas."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        responder={"texto": "¡Hola! ¿En qué te ayudo?", "confianza": "alta"},
    )
    conversacional = _crear_conversacional(backend, tmp_path)
    respuesta = conversacional.atender("hola, ¿cómo estás?")

    assert "¡Hola" in respuesta.texto
    assert respuesta.basada_en_herramientas is False
    turno = conversacional.conversacion.turnos[0]
    assert turno.herramientas_usadas == []


def test_agent_conversacional_directo_recibe_pregunta_y_respuesta_previa():
    """T113: la respuesta directa del chat recibe en la intención la pregunta
    actual Y la respuesta anterior del asistente, para que el LLM pueda evitar
    repetirla (regresión: el BOT repetía la misma respuesta plantilla)."""
    intenciones = []
    respuestas = [
        "Soy un asistente de QA. Puedo explorar la estructura, localizar "
        "archivos y clases, buscar patrones, leer archivos, ejecutar y "
        "analizar pruebas, analizar cobertura y generar casos de prueba "
        "sugeridos.",
        "No he analizado el proyecto aún: dime qué quieres que explore y lo "
        "haré con la herramienta adecuada.",
    ]

    class _Captura(LLMBackend):
        nombre = "captura"
        requiere_api_key = False
        proveedor_requerido = False
        soporta_razonamiento = True

        def interpretar(self, solicitud):
            return {}

        def seleccionar_herramienta(self, solicitud, herramientas):
            return {"ninguna": True}

        def generar_respuesta(self, solicitud, resultados):
            return {}

        def planificar(self, intencion, catalogo, contexto):
            return None

        def razonar(self, estado, pendientes):
            return {"concluir": True}

        def evaluar(self, estado, observaciones):
            return {"satisfecha": True}

        def responder(self, observaciones, intencion=""):
            intenciones.append(intencion)
            return {
                "texto": respuestas[len(intenciones) - 1],
                "confianza": "alta",
                "recomendaciones": [],
            }

    conversacional = _crear_conversacional(_Captura(), tmp_path=".", usar_sqlite=False)
    primera = conversacional.atender("¿qué puedes hacer?")
    segunda = conversacional.atender("no te pregunto eso, dime qué capas tiene el proyecto")

    assert len(intenciones) == 2
    assert "¿qué puedes hacer?" in intenciones[0]
    # el turno previo (incluida la respuesta anterior) está en la intención del 2º turno
    assert "no te pregunto eso" in intenciones[1]
    assert "Soy un asistente de QA" in intenciones[1]
    assert primera.texto != segunda.texto


def test_agent_conversacional_tareas_y_persistencia(tmp_path):
    """Crea tarea, cambia estado, guarda y carga la sesión completa."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        responder={"texto": "Entendido", "confianza": "alta"},
    )
    conversacional = _crear_conversacional(backend, tmp_path)

    tid = conversacional.crear_tarea(
        "Revisar cobertura de ReservacionBL",
        descripcion="Priorizar pruebas BLL",
        prioridad=2,
        etiquetas=["cobertura", "bll"],
    )
    assert tid is not None
    assert len(conversacional.listar_tareas()) == 1
    assert conversacional.cambiar_estado_tarea(tid, "en_progreso") is True

    conversacional.atender("hola")
    sesion_id = conversacional.guardar()
    assert sesion_id

    # nueva instancia → cargar
    catalogo, allowlist, redactor = _catalogo_para_chat()
    from qa_agent.agent.conversational import AgentConversacional

    conv2 = AgentConversacional(
        backend=backend,
        herramientas=catalogo,
        allowlist=allowlist,
        redactor=redactor,
        base_dir=str(tmp_path),
    )
    assert conv2.cargar(sesion_id) is True
    assert len(conv2.conversacion.turnos) == 1
    assert len(conv2.listar_tareas()) == 1
    assert conv2.listar_tareas()[0].estado == EstadoTarea.EN_PROGRESO


def test_agent_conversacional_inyecta_contexto_historial(tmp_path):
    """El contexto conversacional llega al planificar (historial + tareas)."""
    from qa_agent.agent.loop import Agent
    from qa_agent.agent.reasoning import Plan
    from qa_agent.llm.backend import LLMBackend

    plan_guardado = {}

    class _Captura(LLMBackend):
        nombre = "captura_chat"
        requiere_api_key = False
        proveedor_requerido = False
        soporta_razonamiento = True

        def interpretar(self, solicitud): return {}
        def seleccionar_herramienta(self, solicitud, herramientas):
            return {"ninguna": True}
        def generar_respuesta(self, solicitud, resultados): return {}

        def planificar(self, intencion, catalogo, contexto):
            plan_guardado["contexto"] = contexto
            return Plan(pendientes=[])

        def razonar(self, estado, pendientes): return {"concluir": True}
        def evaluar(self, estado, observaciones):
            return {"satisfecha": True, "razon": ""}
        def responder(self, observaciones, intencion=""):
            return {"texto": "ok", "confianza": "alta", "recomendaciones": []}

    conversacional = _crear_conversacional(_Captura(), tmp_path)
    # Primera consulta QA registra un turno
    conversacional.atender("¿cuál es la estructura del proyecto?")
    # Segunda consulta QA debe inyectar el historial previo en el contexto
    conversacional.atender("ahora localiza el servicio principal")

    ctx = plan_guardado.get("contexto", {})
    assert "historial" in ctx
    assert len(ctx["historial"]) == 1
    assert ctx["historial"][0]["usuario"] == "¿cuál es la estructura del proyecto?"
    assert "tareas_pendientes" in ctx
    assert "resumen" in ctx


# -- T089: comandos CLI del chat ----------------------------------------------


def test_cli_chat_crea_lista_y_actualiza_tareas(tmp_path):
    """Comandos /tarea del chat: add, list, done."""
    from qa_agent.agent.conversational import AgentConversacional
    from qa_agent.cli.main import _comando_tarea

    backend = FakeLLM(soporta_razonamiento=True)
    conversacional = _crear_conversacional(backend, tmp_path)

    _comando_tarea(
        conversacional,
        ["add", "Revisar cobertura BLL", "--desc=priorizar", "--prioridad=3"],
    )
    _comando_tarea(conversacional, ["list"])
    _comando_tarea(conversacional, ["done", conversacional.listar_tareas()[0].id])

    tarea = conversacional.listar_tareas()[0]
    assert tarea.titulo == "Revisar cobertura BLL"
    assert tarea.prioridad == 3
    assert tarea.estado == EstadoTarea.COMPLETADA


def test_cli_chat_tarea_run_ejecuta_y_guarda_resultado(tmp_path):
    """Comando /tarea run del chat ejecuta la tarea con el ReAct."""
    from qa_agent.agent.conversational import AgentConversacional
    from qa_agent.cli.main import _comando_tarea

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={"pasos": [{"orden": 1, "herramienta": "search",
                         "razon": "buscar"}]},
        responder={"texto": "Clases BLL: PagoBL, ReservacionBL.",
                   "confianza": "limitada", "recomendaciones": []},
    )
    conversacional = _crear_conversacional(backend, tmp_path)

    _comando_tarea(conversacional, ["add", "Priorizar BLL"])
    tid = conversacional.listar_tareas()[0].id
    _comando_tarea(conversacional, ["run", tid])

    tarea = conversacional.tareas.obtener(tid)
    assert tarea.estado == EstadoTarea.COMPLETADA
    assert "ReservacionBL" in tarea.resultado


def test_cli_chat_guardar_listar_y_cargar_sesion(tmp_path):
    """Comandos /sesion: save, list, load."""
    from qa_agent.agent.conversational import AgentConversacional
    from qa_agent.cli.main import _comando_sesion

    backend = FakeLLM(soporta_razonamiento=True)
    conversacional = _crear_conversacional(backend, tmp_path)
    conversacional.atender("hola")

    sid = conversacional.guardar()
    assert sid

    # nueva instancia en el mismo directorio
    catalogo, allowlist, redactor = _catalogo_para_chat()
    conv2 = AgentConversacional(
        backend=backend,
        herramientas=catalogo,
        allowlist=allowlist,
        redactor=redactor,
        base_dir=str(tmp_path),
    )
    _comando_sesion(conv2, ["load", sid])
    assert len(conv2.conversacion.turnos) == 1
    assert conv2.conversacion.turnos[0].usuario == "hola"


def test_cli_chat_memoria_y_ayuda(tmp_path):
    """Comandos /memoria y /ayuda no rompen el chat."""
    from qa_agent.agent.conversational import AgentConversacional
    from qa_agent.cli.main import _mostrar_memoria

    backend = FakeLLM(soporta_razonamiento=True)
    conversacional = _crear_conversacional(backend, tmp_path)
    conversacional.atender("hola")
    _mostrar_memoria(conversacional)
    assert conversacional.conversacion.turnos[0].agente


# -- T093: ejecución de tareas (opción A: /tarea run) --------------------------


def test_ejecutar_tarea_completada_con_resultado(tmp_path):
    """/tarea run completa la tarea y guarda el resultado basado en evidencia."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={"pasos": [{"orden": 1, "herramienta": "search",
                         "razon": "buscar clases de negocio"}]},
        responder={"texto": "Encontré 5 clases BLL: ClienteBL, PagoBL...",
                   "confianza": "limitada", "recomendaciones": []},
    )
    conversacional = _crear_conversacional(backend, tmp_path)
    tid = conversacional.crear_tarea("Priorizar clases BLL", descripcion="clases a probar")

    assert conversacional.ejecutar_tarea(tid) is True
    tarea = conversacional.tareas.obtener(tid)
    assert tarea.estado == EstadoTarea.COMPLETADA
    assert "ClienteBL" in tarea.resultado
    # quedó registrado como turno en la conversación
    assert len(conversacional.conversacion.turnos) == 1


def test_ejecutar_tarea_bloqueada_sin_evidencia(tmp_path):
    """Sin evidencia real la tarea queda bloqueada con confianza sin información."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        responder={"texto": "No hay información suficiente.",
                   "confianza": "sin_informacion", "recomendaciones": []},
    )
    conversacional = _crear_conversacional(backend, tmp_path)
    tid = conversacional.crear_tarea("Analizar cobertura")

    assert conversacional.ejecutar_tarea(tid) is True
    tarea = conversacional.tareas.obtener(tid)
    assert tarea.estado == EstadoTarea.BLOQUEADA
    assert tarea.resultado


def test_ejecutar_tarea_inexistente_o_completada(tmp_path):
    """No ejecuta tareas inexistentes ni ya completadas."""
    backend = FakeLLM(soporta_razonamiento=True)
    conversacional = _crear_conversacional(backend, tmp_path)
    assert conversacional.ejecutar_tarea("no-existe") is False

    tid = conversacional.crear_tarea("Tarea")
    conversacional.cambiar_estado_tarea(tid, "completada")
    assert conversacional.ejecutar_tarea(tid) is False


def test_ejecutar_tarea_persiste_resultado_al_guardar(tmp_path):
    """El resultado de la ejecución sobrevive a guardar/cargar la sesión."""
    from qa_agent.agent.conversational import AgentConversacional

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={"pasos": [{"orden": 1, "herramienta": "search",
                         "razon": "buscar"}]},
        responder={"texto": "Evidencia: clase ReservacionBL encontrada.",
                   "confianza": "limitada", "recomendaciones": []},
    )
    conversacional = _crear_conversacional(backend, tmp_path)
    tid = conversacional.crear_tarea("Localizar ReservacionBL")
    conversacional.ejecutar_tarea(tid)
    sid = conversacional.guardar()

    catalogo, allowlist, redactor = _catalogo_para_chat()
    conv2 = AgentConversacional(
        backend=backend,
        herramientas=catalogo,
        allowlist=allowlist,
        redactor=redactor,
        base_dir=str(tmp_path),
    )
    conv2.cargar(sid)
    tarea = conv2.tareas.obtener(tid)
    assert tarea.estado == EstadoTarea.COMPLETADA
    assert "ReservacionBL" in tarea.resultado