"""Una herramienta que falla no puede desaparecer de la respuesta (FR-018/019).

El control de anclaje existente (`_afirmaciones_no_ancladas`) comprueba
PRESENCIA de tokens: que lo afirmado aparezca en la evidencia. Construye esa
evidencia filtrando solo las observaciones con estado EXITO, así que una
observación fallida no contradice nada — simplemente se descarta.

Con una sola herramienta eso no se nota, porque sin observaciones exitosas no
hay nada que anclar y la confianza cae sola. El hueco aparece al MEZCLAR: si
dos herramientas funcionan y una falla, las exitosas anclan el texto y el fallo
se evapora.

Reproducido contra Gemini el 2026-08-21 sobre un proyecto real: `leer_archivo`
y `editar_archivo` correctos, `run_tests` devolviendo `EstadoResultado.ERROR`
con `causa_no_ejecutado='fallo_de_coleccion'` y un `SyntaxError` en la salida —
y la respuesta final afirmando "se ha editado correctamente" y "se han
conservado ... tal como estaban". Las tres afirmaciones eran falsas y la prueba
estaba en la propia traza del agente.

La regla que fijan estos tests es estructural, no de análisis del texto: si una
herramienta falló durante la solicitud, la confianza no puede ser ALTA y el
fallo tiene que aparecer en la respuesta.
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.grounding import (
    nota_de_fallos,
    observaciones_con_fallo_reportado,
    observaciones_fallidas,
    texto_declara_el_fallo,
)
from qa_agent.agent.loop import Agent
from qa_agent.agent.response import Confianza
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.security.redactor import Redactor
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)


def _proyecto(tmp_path: Path) -> Path:
    raiz = tmp_path / "proyecto"
    (raiz / "src").mkdir(parents=True)
    (raiz / "src" / "app.py").write_text("def hola():\n    return 1\n", encoding="utf-8")
    return raiz


def _stub(identificador: str, resultado: ResultadoDeHerramienta) -> Herramienta:
    """Herramienta mínima que siempre devuelve `resultado`."""

    class StubHerramienta(Herramienta):
        id = identificador
        nombre = identificador
        descripcion = f"Stub de {identificador}."
        esquema_entrada = {"type": "object", "properties": {}}
        esquema_salida = {"type": "object", "properties": {}}
        requiere_autorizacion = False
        rutas_permitidas: list[str] = []

        def ejecutar(self, parametros: dict) -> ResultadoDeHerramienta:
            return resultado

    return StubHerramienta()


def _exito(identificador: str, datos: dict) -> ResultadoDeHerramienta:
    return ResultadoDeHerramienta(
        herramienta_id=identificador, estado=EstadoResultado.EXITO, datos=datos
    )


def _fallo(identificador: str, causa: str = "") -> ResultadoDeHerramienta:
    return ResultadoDeHerramienta(
        herramienta_id=identificador,
        estado=EstadoResultado.ERROR,
        error="la herramienta falló",
        datos={"causa_no_ejecutado": causa} if causa else {},
    )


def _plan(*pasos: tuple[int, str]) -> dict:
    return {
        "objetivo": "reproducir el caso mixto",
        "pasos": [
            {
                "orden": orden,
                "razon": f"paso {orden}",
                "herramienta": herramienta,
                "parametros": {},
                "criterio_salida": "",
            }
            for orden, herramienta in pasos
        ],
    }


def _agente(tmp_path: Path, herramientas, plan, responder) -> Agent:
    return Agent(
        backend=FakeLLM(soporta_razonamiento=True, plan=plan, responder=responder),
        herramientas=herramientas,
        allowlist=Allowlist([str(tmp_path)]),
        redactor=Redactor(),
    )


# --- Nivel puro: la función determinista -----------------------------------


def test_observaciones_fallidas_distingue_exito_de_fallo():
    from types import SimpleNamespace

    obs = [
        SimpleNamespace(resultado=_exito("leer_archivo", {"contenido": "x"})),
        SimpleNamespace(resultado=_fallo("run_tests", "fallo_de_coleccion")),
        SimpleNamespace(resultado=_exito("editar_archivo", {"editado": True})),
    ]

    fallidas = observaciones_fallidas(obs)

    assert [o.resultado.herramienta_id for o in fallidas] == ["run_tests"]


def test_la_nota_nombra_la_herramienta_y_su_causa():
    from types import SimpleNamespace

    obs = [SimpleNamespace(resultado=_fallo("run_tests", "fallo_de_coleccion"))]

    nota = nota_de_fallos(observaciones_fallidas(obs))

    assert "run_tests" in nota
    assert "fallo_de_coleccion" in nota


def test_sin_fallos_no_hay_nota():
    from types import SimpleNamespace

    obs = [SimpleNamespace(resultado=_exito("explore", {"elementos": []}))]

    assert nota_de_fallos(observaciones_fallidas(obs)) == ""


# --- Nivel agente: el caso mixto real --------------------------------------


def test_un_fallo_entre_exitos_impide_la_confianza_alta(tmp_path):
    """El caso exacto reproducido contra Gemini."""
    raiz = _proyecto(tmp_path)
    agente = _agente(
        raiz,
        herramientas=[
            _stub("leer_archivo", _exito("leer_archivo", {"contenido": "def f(): ..."})),
            _stub("run_tests", _fallo("run_tests", "fallo_de_coleccion")),
        ],
        plan=_plan((1, "leer_archivo"), (2, "run_tests")),
        responder={
            "texto": "Se ha editado correctamente el archivo y todo funciona.",
            "confianza": "alta",
            "recomendaciones": [],
        },
    )

    respuesta = agente.atender("edita el modulo y ejecuta las pruebas", None)

    assert respuesta.confianza != Confianza.ALTA, (
        "una herramienta falló: la respuesta no puede reportar confianza alta"
    )


def test_un_fallo_entre_exitos_se_declara_en_la_respuesta(tmp_path):
    """No basta con bajar la confianza: el fallo tiene que ser legible."""
    raiz = _proyecto(tmp_path)
    agente = _agente(
        raiz,
        herramientas=[
            _stub("leer_archivo", _exito("leer_archivo", {"contenido": "def f(): ..."})),
            _stub("run_tests", _fallo("run_tests", "fallo_de_coleccion")),
        ],
        plan=_plan((1, "leer_archivo"), (2, "run_tests")),
        responder={
            "texto": "Se ha editado correctamente el archivo y todo funciona.",
            "confianza": "alta",
            "recomendaciones": [],
        },
    )

    respuesta = agente.atender("edita el modulo y ejecuta las pruebas", None)

    assert "run_tests" in respuesta.texto, (
        "el usuario debe poder ver QUÉ falló sin abrir el panel de razonamiento"
    )


def test_todo_exitoso_conserva_la_confianza_alta(tmp_path):
    """El arreglo no puede degradar las respuestas legítimamente correctas."""
    raiz = _proyecto(tmp_path)
    agente = _agente(
        raiz,
        herramientas=[
            _stub("leer_archivo", _exito("leer_archivo", {"contenido": "def f(): ..."})),
            _stub("run_tests", _exito("run_tests", {"pasadas": 3, "falladas": 0})),
        ],
        plan=_plan((1, "leer_archivo"), (2, "run_tests")),
        responder={
            "texto": "leer_archivo y run_tests: 3 pasadas, 0 falladas.",
            "confianza": "alta",
            "recomendaciones": [],
        },
    )

    respuesta = agente.atender("lee el modulo y ejecuta las pruebas", None)

    assert respuesta.confianza == Confianza.ALTA
    assert "Aviso" not in respuesta.texto


def test_la_nota_no_se_duplica_si_el_texto_ya_menciona_el_fallo(tmp_path):
    """Un backend honesto no debe ser penalizado con una nota redundante."""
    raiz = _proyecto(tmp_path)
    agente = _agente(
        raiz,
        herramientas=[
            _stub("leer_archivo", _exito("leer_archivo", {"contenido": "def f(): ..."})),
            _stub("run_tests", _fallo("run_tests", "fallo_de_coleccion")),
        ],
        plan=_plan((1, "leer_archivo"), (2, "run_tests")),
        responder={
            "texto": "La herramienta run_tests falló con fallo_de_coleccion.",
            "confianza": "alta",
            "recomendaciones": [],
        },
    )

    respuesta = agente.atender("edita el modulo y ejecuta las pruebas", None)

    assert respuesta.texto.count("run_tests") == 1


# --- Segundo caso: la herramienta funciona, lo observado sale mal ----------
#
# ADR-006: `run_tests` que corre bien y encuentra pruebas rotas devuelve
# EstadoResultado.EXITO con `estado_global='fallo'`. La regla de arriba no
# dispara —y no debe—, porque la observación SÍ es evidencia válida.
#
# Reproducido contra Gemini el 2026-08-21: tras una edición que cambió el
# contrato de `moda`, `run_tests` devolvió EXITO con 2 falladas y la respuesta
# afirmó "se conservaron las funciones _validar, media, moda y rango en su
# estado original".


def _exito_con_fallo(identificador: str = "run_tests") -> ResultadoDeHerramienta:
    return _exito(
        identificador,
        {"estado_global": "fallo", "pasadas": 19, "falladas": 2, "errores": 0},
    )


def test_un_resultado_malo_se_detecta_aunque_la_herramienta_tenga_exito():
    from types import SimpleNamespace

    obs = [SimpleNamespace(resultado=_exito_con_fallo())]

    assert observaciones_con_fallo_reportado(obs)


def test_una_suite_verde_no_se_marca_como_fallo():
    from types import SimpleNamespace

    obs = [
        SimpleNamespace(
            resultado=_exito(
                "run_tests",
                {"estado_global": "exito", "pasadas": 21, "falladas": 0, "errores": 0},
            )
        )
    ]

    assert observaciones_con_fallo_reportado(obs) == []


def test_informar_del_fallo_cuenta_como_declararlo():
    from types import SimpleNamespace

    obs = [SimpleNamespace(resultado=_exito_con_fallo())]

    assert texto_declara_el_fallo("2 pruebas fallaron en el módulo.", obs)
    assert not texto_declara_el_fallo("Todo se conservó en su estado original.", obs)


def test_omitir_pruebas_rotas_degrada_la_confianza(tmp_path):
    """El caso exacto reproducido contra Gemini."""
    raiz = _proyecto(tmp_path)
    agente = _agente(
        raiz,
        herramientas=[
            _stub("editar_archivo", _exito("editar_archivo", {"editado": True})),
            _stub("run_tests", _exito_con_fallo()),
        ],
        plan=_plan((1, "editar_archivo"), (2, "run_tests")),
        responder={
            "texto": "Se conservaron las funciones en su estado original.",
            "confianza": "alta",
            "recomendaciones": [],
        },
    )

    respuesta = agente.atender("edita el modulo y ejecuta las pruebas", None)

    assert respuesta.confianza != Confianza.ALTA
    assert "run_tests" in respuesta.texto


def test_informar_correctamente_de_pruebas_rotas_no_se_penaliza(tmp_path):
    """Una respuesta honesta sobre una suite en rojo conserva su confianza.

    Sin esto, el arreglo castigaría justo el comportamiento que se quiere.
    """
    raiz = _proyecto(tmp_path)
    agente = _agente(
        raiz,
        herramientas=[
            _stub("editar_archivo", _exito("editar_archivo", {"editado": True})),
            _stub("run_tests", _exito_con_fallo()),
        ],
        plan=_plan((1, "editar_archivo"), (2, "run_tests")),
        responder={
            "texto": "Edité el módulo, pero 2 pruebas fallaron tras el cambio.",
            "confianza": "alta",
            "recomendaciones": [],
        },
    )

    respuesta = agente.atender("edita el modulo y ejecuta las pruebas", None)

    assert respuesta.confianza == Confianza.ALTA
    assert "Aviso" not in respuesta.texto
