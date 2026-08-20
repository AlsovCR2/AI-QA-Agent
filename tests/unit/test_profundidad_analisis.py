"""Tests de profundidad/exhaustividad del análisis global (T116..T118).

Cubre la mejora de profundidad aprobada para el modelo actual:
- Presupuesto de pasos dinámico para intenciones de análisis global (SC-016).
- Enriquecimiento determinista del plan por capa (`_enriquecer_plan_analisis_global`):
  `explore` por capa + `leer_archivo` de archivos de código reales (FR-024/FR-049).
- Nota de cobertura en la respuesta cuando el presupuesto se agota (IX / FR-019).
"""

from __future__ import annotations

from qa_agent.agent.loop import Agent, _es_analisis_global
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


class _StubExploreConCapas(_StubExplore):
    """`explore` con una capa real `src` en la raíz y vacía dentro."""

    def ejecutar(self, parametros: dict) -> ResultadoDeHerramienta:
        ruta = parametros.get("ruta", ".")
        elementos = []
        if ruta == ".":
            elementos = [
                {"nombre": "src", "tipo": "directorio", "ruta_relativa": "src"}
            ]
        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={"ruta": ruta, "existe": True, "elementos": elementos},
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
        "objetivo": "análisis",
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
        responder={"texto": "análisis", "confianza": "alta", "recomendaciones": []},
        **kwargs,
    )
    return Agent(
        backend=backend,
        herramientas=[_StubExplore()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
        pasos_max=pasos_max,
    )


# -- T116: presupuesto de pasos dinámico (SC-016) -----------------------------


def test_es_analisis_global_determinista():
    """La detección de análisis global es determinista, sin LLM (VI/SC-010)."""
    assert _es_analisis_global("analiza el proyecto")
    assert _es_analisis_global("Analiza   todo el proyecto")
    assert _es_analisis_global("explora la estructura del proyecto")
    assert _es_analisis_global("dime la estructura")
    assert _es_analisis_global("revisa el proyecto completo")
    # T120: variantes que antes NO disparaban el análisis global (regresión real).
    assert _es_analisis_global("analiza la estructura del proyecto")
    assert _es_analisis_global("analiza la estructura")
    assert _es_analisis_global("analiza la arquitectura del proyecto")
    assert _es_analisis_global("explica la estructura del proyecto")
    assert _es_analisis_global("describe la estructura")
    assert _es_analisis_global("qué capas hay")
    assert _es_analisis_global("cuáles son las capas del proyecto")
    assert _es_analisis_global("cómo está organizado el proyecto")
    assert _es_analisis_global("organización del proyecto")
    assert _es_analisis_global("distribución por capas")
    # Negativos: consultas puntuales o frases sueltas no se tratan como globales.
    assert not _es_analisis_global("explora")
    assert not _es_analisis_global("analiza estos resultados de prueba")
    assert not _es_analisis_global("explica qué hace tests/test_app.py")
    assert not _es_analisis_global("¿cuáles clases probar?")
    assert not _es_analisis_global("")


def test_presupuesto_global_amplia_pasos_max():
    """Intención global amplía el presupuesto: el plan completo se ejecuta."""
    agente = _agente(pasos_max=5, plan=_plan_de(7))
    respuesta = agente.atender("analiza el proyecto")

    assert len([a for a in respuesta.acciones]) == 7


def test_sin_intencion_global_respeta_pasos_max():
    """Intención puntual respeta `pasos_max`: el bucle corta en el límite."""
    agente = _agente(pasos_max=5, plan=_plan_de(7))
    respuesta = agente.atender("identifica dónde aparece BLL")

    assert len([a for a in respuesta.acciones]) == 5


# -- T117: enriquecimiento determinista del plan por capa (FR-024/FR-049) -----


def test_enriquecimiento_anade_explore_y_lectura_por_capa(tmp_path):
    """El análisis global recorre CADA capa real y lee su código principal."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def sumar(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "def test_suma():\n    assert True\n", encoding="utf-8"
    )

    from qa_agent.tools.explore import ExploreHerramienta
    from qa_agent.tools.leer_archivo import LeerArchivoHerramienta

    rutas = [str(tmp_path)]
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "análisis global",
            "criterio_exito": "cubrir todo",
            "pasos": [
                {"orden": 1, "razon": "ver la raíz", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path), "profundidad_max": 1},
                 "criterio_salida": ""}
            ],
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "análisis por capas", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[ExploreHerramienta(rutas), LeerArchivoHerramienta(rutas)],
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
    )
    respuesta = agente.atender("analiza el proyecto")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    exploradas = {
        a.entrada.get("ruta") for a in exitos if a.herramienta_id == "explore"
    }
    assert str(tmp_path / "src") in exploradas
    assert str(tmp_path / "tests") in exploradas
    leidos = {
        a.entrada.get("archivo_relativo")
        for a in exitos
        if a.herramienta_id == "leer_archivo"
    }
    assert {"src/app.py", "tests/test_app.py"} <= leidos


def test_analiza_la_estructura_dispara_enriquecimiento(tmp_path):
    """T120: la frase que produjo la respuesta superficial en ReservaHotel
    ("analiza la estructura del proyecto") ahora dispara el enriquecimiento
    por capa y la lectura del código principal."""
    for capa in ("BLL", "DAL", "UIL"):
        (tmp_path / capa).mkdir()
        (tmp_path / capa / "Clase.cs").write_text(
            "class Clase{}\n", encoding="utf-8"
        )
    (tmp_path / "WebPortal").mkdir()
    (tmp_path / "WebPortal" / "WebPortal.csproj").write_text(
        "<Project></Project>\n", encoding="utf-8"
    )

    from qa_agent.tools.explore import ExploreHerramienta
    from qa_agent.tools.leer_archivo import LeerArchivoHerramienta

    rutas = [str(tmp_path)]
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "análisis",
            "criterio_exito": "cubrir todo",
            "pasos": [
                {"orden": 1, "razon": "ver la raíz", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path), "profundidad_max": 1},
                 "criterio_salida": ""}
            ],
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "análisis por capas", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[ExploreHerramienta(rutas), LeerArchivoHerramienta(rutas)],
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
    )
    respuesta = agente.atender("analiza la estructura del proyecto")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    exploradas = {
        a.entrada.get("ruta") for a in exitos if a.herramienta_id == "explore"
    }
    assert str(tmp_path / "BLL") in exploradas
    assert str(tmp_path / "DAL") in exploradas
    assert str(tmp_path / "UIL") in exploradas
    leidos = {
        a.entrada.get("archivo_relativo")
        for a in exitos
        if a.herramienta_id == "leer_archivo"
    }
    assert "BLL/Clase.cs" in leidos


def test_enriquecimiento_no_duplica_capas_ya_previstas(tmp_path):
    """Si el plan ya cubre una capa o archivo, el enriquecimiento no duplica."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    from qa_agent.tools.explore import ExploreHerramienta
    from qa_agent.tools.leer_archivo import LeerArchivoHerramienta

    rutas = [str(tmp_path)]
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "análisis",
            "criterio_exito": "todo",
            "pasos": [
                {"orden": 1, "razon": "raíz", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path), "profundidad_max": 1},
                 "criterio_salida": ""},
                {"orden": 2, "razon": "capa src", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path / "src"),
                                "profundidad_max": 3},
                 "criterio_salida": ""},
                {"orden": 3, "razon": "leer app", "herramienta": "leer_archivo",
                 "parametros": {"ruta": str(tmp_path),
                                "archivo_relativo": "src/app.py"},
                 "criterio_salida": ""},
            ],
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[ExploreHerramienta(rutas), LeerArchivoHerramienta(rutas)],
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
    )
    respuesta = agente.atender("analiza el proyecto")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    explores_src = [
        a for a in exitos
        if a.herramienta_id == "explore"
        and a.entrada.get("ruta") == str(tmp_path / "src")
    ]
    assert len(explores_src) == 1
    lecturas_app = [
        a for a in exitos
        if a.herramienta_id == "leer_archivo"
        and a.entrada.get("archivo_relativo") == "src/app.py"
    ]
    assert len(lecturas_app) == 1


def test_enriquecimiento_se_omite_sin_leer_archivo():
    """Sin `leer_archivo` en el catálogo solo se añaden los explores de capa."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={"pasos": [
            {"orden": 1, "razon": "raíz", "herramienta": "explore",
             "parametros": {"ruta": "."}, "criterio_salida": ""}
        ]},
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[_StubExploreConCapas()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("analiza el proyecto")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    assert any(a.herramienta_id == "explore" for a in exitos)
    assert not any(a.herramienta_id == "leer_archivo" for a in respuesta.acciones)


# -- T118: nota de cobertura cuando se agota el presupuesto (IX / FR-019) -----


def test_respuesta_incluye_nota_de_cobertura_cuando_agota_presupuesto():
    """Análisis global que agota el presupuesto añade la nota de cobertura."""
    agente = _agente(
        pasos_max=3,
        plan=_plan_de(20),
        backend=_CapturaResponder,
    )
    respuesta = agente.atender("analiza el proyecto")

    # Presupuesto global = max(3, 18) = 18: el bucle corta en 18 y avisa.
    assert len([a for a in respuesta.acciones]) == 18
    assert "NOTA DE COBERTURA" in agente._backend.ultima_intencion
    assert respuesta.texto


def test_respuesta_sin_nota_cuando_presupuesto_agotado_no_es_global():
    """Intención puntual agotada no añade la nota de cobertura."""
    agente = _agente(
        pasos_max=3,
        plan=_plan_de(20),
        backend=_CapturaResponder,
    )
    respuesta = agente.atender("identifica dónde aparece BLL")

    assert len([a for a in respuesta.acciones]) == 3
    assert "NOTA DE COBERTURA" not in agente._backend.ultima_intencion
    assert respuesta.texto