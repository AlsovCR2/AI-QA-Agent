"""Tests de intenciones de sugerencia de pruebas (T121).

"¿Qué pruebas podemos aplicar al proyecto?" ahora se trata como análisis
exhaustivo: amplía el presupuesto de pasos, garantiza la cobertura por capa
(FR-049) y añade de forma determinista `locate` de clases reales +
`generate_test_cases`, para que la respuesta no dependa solo de un plan
superficial del LLM (FR-024 / VI).
"""

from __future__ import annotations

import os

from qa_agent.agent.loop import Agent, _es_analisis_exhaustivo, _es_intencion_pruebas
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.security.redactor import Redactor
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)


class _StubExplore(Herramienta):
    """`explore` determinista mínimo: estructura vacía."""

    id = "explore"
    nombre = "explore"
    descripcion = "Explora la estructura del proyecto."
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "profundidad_max": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "existe": {"type": "boolean"},
            "elementos": {"type": "array"},
        },
    }
    requiere_autorizacion = False

    def ejecutar(self, parametros: dict) -> ResultadoDeHerramienta:
        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "ruta": parametros.get("ruta", "."),
                "existe": True,
                "elementos": [],
            },
        )


class _CapturaResponder(FakeLLM):
    """FakeLLM que registra la intención recibida por `responder`."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.ultima_intencion: str | None = None

    def responder(self, observaciones, intencion: str = ""):
        self.ultima_intencion = intencion
        return super().responder(observaciones, intencion)


def _plan_de(n: int) -> dict:
    """Plan con `n` pasos `explore` distintos (sin colisionar con el dedup)."""
    return {
        "objetivo": "sugerir pruebas",
        "criterio_exito": "cubrir todo",
        "pasos": [
            {
                "orden": i,
                "razon": f"explorar paso {i}",
                "herramienta": "explore",
                "parametros": {"ruta": ".", "profundidad_max": i},
                "criterio_salida": "",
            }
            for i in range(1, n + 1)
        ],
    }


def _agente(pasos_max: int, plan: dict, backend=FakeLLM, **kwargs) -> Agent:
    backend = backend(
        soporta_razonamiento=True,
        plan=plan,
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "pruebas sugeridas", "confianza": "alta",
                   "recomendaciones": []},
        **kwargs,
    )
    return Agent(
        backend=backend,
        herramientas=[_StubExplore()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
        pasos_max=pasos_max,
    )


# -- T121: detector determinista ----------------------------------------------


def test_es_intencion_pruebas_determinista():
    """La detección de sugerencia de pruebas es determinista, sin LLM (VI)."""
    assert _es_intencion_pruebas("¿qué pruebas podemos aplicar al proyecto?")
    assert _es_intencion_pruebas("qué tipo de pruebas podemos hacer")
    assert _es_intencion_pruebas("¿Qué estrategia de pruebas recomiendas?")
    assert _es_intencion_pruebas("qué casos de prueba cubriría")
    assert _es_intencion_pruebas("cómo probar el proyecto")
    assert _es_intencion_pruebas("genera casos de prueba para la función sumar")
    # Definición/redacción de pruebas y cobertura (T123): sin estos términos,
    # la intención de escribir pruebas no disparaba el enriquecimiento y el
    # LLM planificaba rutas inventadas ("Datos"/"Negocio").
    assert _es_intencion_pruebas(
        "Procede a definir las pruebas unitarias y cobertura que se van a "
        "realizar a la capa DAL"
    )
    assert _es_intencion_pruebas(
        "definas en UnitTest.md las pruebas unitarias y cobertura de la capa "
        "de datos"
    )
    assert _es_intencion_pruebas("define las pruebas unitarias del proyecto")
    assert _es_intencion_pruebas(
        "cuál es el porcentaje de cobertura de las pruebas"
    )
    # No se confunde con ejecutar pruebas ni con explicar archivos concretos.
    assert not _es_intencion_pruebas("ejecuta las pruebas del proyecto")
    assert not _es_intencion_pruebas("por qué falla el test de reservas")
    assert not _es_intencion_pruebas("explícame qué pruebas hace tests/test_app.py")
    assert not _es_intencion_pruebas("")
    assert not _es_intencion_pruebas("explora")


def test_es_analisis_exhaustivo_combina_global_y_pruebas():
    """El análisis exhaustivo cubre análisis global y sugerencia de pruebas."""
    assert _es_analisis_exhaustivo("analiza el proyecto")
    assert _es_analisis_exhaustivo("qué pruebas podemos aplicar")
    assert not _es_analisis_exhaustivo("identifica dónde aparece BLL")


# -- T121: presupuesto de pasos (SC-016) ---------------------------------------


def test_presupuesto_intencion_pruebas_amplia_pasos_max():
    """Intención de pruebas amplía el presupuesto: el plan completo se ejecuta."""
    agente = _agente(pasos_max=5, plan=_plan_de(7))
    respuesta = agente.atender("qué pruebas podemos aplicar al proyecto")

    assert len([a for a in respuesta.acciones]) == 7


def test_sin_intencion_pruebas_respeta_pasos_max():
    """Consulta puntual sobre pruebas respeta `pasos_max`."""
    agente = _agente(pasos_max=5, plan=_plan_de(7))
    respuesta = agente.atender("explícame qué pruebas hace tests/test_app.py")

    assert len([a for a in respuesta.acciones]) == 5


# -- T121: enriquecimiento determinista del plan (FR-024/FR-049) ---------------


def test_enriquecimiento_pruebas_anade_cobertura_locate_y_casos(tmp_path):
    """"¿Qué pruebas podemos aplicar?" recorre capas, localiza clases y genera
    casos de prueba sugeridos."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        '"""Proyecto de prueba."""\n\ndef sumar(a, b):\n    return a + b\n',
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "def test_suma():\n    assert True\n", encoding="utf-8"
    )

    from qa_agent.tools.explore import ExploreHerramienta
    from qa_agent.tools.generate_test_cases import GenerateTestCasesHerramienta
    from qa_agent.tools.leer_archivo import LeerArchivoHerramienta
    from qa_agent.tools.locate import LocateHerramienta

    rutas = [str(tmp_path)]
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "sugerir pruebas",
            "criterio_exito": "cubrir todo",
            "pasos": [
                {"orden": 1, "razon": "ver la raíz", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path), "profundidad_max": 1},
                 "criterio_salida": ""}
            ],
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "pruebas sugeridas", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[
            ExploreHerramienta(rutas),
            LeerArchivoHerramienta(rutas),
            LocateHerramienta(rutas),
            GenerateTestCasesHerramienta(rutas),
        ],
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
    )
    respuesta = agente.atender("qué pruebas podemos aplicar al proyecto")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    exploradas = {
        a.entrada.get("ruta") for a in exitos if a.herramienta_id == "explore"
    }
    assert str(tmp_path / "src") in exploradas
    assert str(tmp_path / "tests") in exploradas
    localizadas = [
        a for a in exitos if a.herramienta_id == "locate"
    ]
    assert len(localizadas) == 1
    casos = [
        a for a in exitos if a.herramienta_id == "generate_test_cases"
    ]
    assert len(casos) == 1
    assert casos[0].salida.get("casos_propuestos")
    assert casos[0].salida.get("fuentes") == [os.path.join("src", "app.py")]


def test_enriquecimiento_pruebas_no_duplica_steps_ya_previstos(tmp_path):
    """Si el plan ya prevé `locate`/`generate_test_cases`, no se duplican."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")

    from qa_agent.tools.explore import ExploreHerramienta
    from qa_agent.tools.generate_test_cases import GenerateTestCasesHerramienta
    from qa_agent.tools.leer_archivo import LeerArchivoHerramienta
    from qa_agent.tools.locate import LocateHerramienta

    rutas = [str(tmp_path)]
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "pruebas",
            "criterio_exito": "todo",
            "pasos": [
                {"orden": 1, "razon": "raíz", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path), "profundidad_max": 1},
                 "criterio_salida": ""},
                {"orden": 2, "razon": "clases", "herramienta": "locate",
                 "parametros": {"ruta": str(tmp_path), "patron": "class",
                                "tipo": "clase"},
                 "criterio_salida": ""},
                {"orden": 3, "razon": "casos", "herramienta": "generate_test_cases",
                 "parametros": {"ruta": str(tmp_path), "objetivo": "sumar",
                                "cripticidad": "happy_path"},
                 "criterio_salida": ""},
            ],
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[
            ExploreHerramienta(rutas),
            LeerArchivoHerramienta(rutas),
            LocateHerramienta(rutas),
            GenerateTestCasesHerramienta(rutas),
        ],
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
    )
    respuesta = agente.atender("qué pruebas podemos aplicar al proyecto")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    assert len([a for a in exitos if a.herramienta_id == "locate"]) == 1
    assert (
        len([a for a in exitos if a.herramienta_id == "generate_test_cases"])
        == 1
    )


# -- T121: nota de cobertura al agotar el presupuesto (IX / FR-019) ------------


def test_respuesta_incluye_nota_de_cobertura_en_intencion_pruebas():
    """Intención de pruebas que agota el presupuesto añade la nota de cobertura."""
    agente = _agente(
        pasos_max=3,
        plan=_plan_de(20),
        backend=_CapturaResponder,
    )
    respuesta = agente.atender("qué pruebas podemos aplicar al proyecto")

    assert len([a for a in respuesta.acciones]) == 18
    assert "NOTA DE COBERTURA" in agente._backend.ultima_intencion
    assert respuesta.texto