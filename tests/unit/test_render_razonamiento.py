"""El panel de razonamiento debe ser legible, no un volcado de `repr` (FR-035).

Antes, cada observación se imprimía como `str(dict)`: una línea gigantesca con
`\\n` escapados dentro de comillas. El contenido estaba, pero leerlo exigía
descifrar un `repr` de Python envuelto por el ancho del panel — y con `stdout`
de pytest dentro, era ilegible en la práctica.

Peor: no había NINGUNA señal visual de que un paso hubiese fallado. El caso que
motivó esto tenía `run_tests` devolviendo ERROR entre dos pasos correctos, y en
pantalla los tres se veían idénticos.
"""

from __future__ import annotations

from types import SimpleNamespace

from qa_agent.cli import main as cli
from qa_agent.tools.base import EstadoResultado


def _observacion(herramienta: str, datos, estado=EstadoResultado.EXITO, razon="razón"):
    return SimpleNamespace(
        paso=SimpleNamespace(
            orden=1, razon=razon, herramienta=herramienta, parametros={}
        ),
        resultado=SimpleNamespace(estado=estado, datos=datos),
    )


def _respuesta(razonamiento):
    return SimpleNamespace(
        razonamiento=razonamiento, texto="", recomendaciones=[], acciones=[]
    )


def _render(razonamiento, capsys) -> str:
    cli._renderizar_respuesta(_respuesta(razonamiento))
    return capsys.readouterr().out


# --- Señal de estado -------------------------------------------------------


def test_un_paso_fallido_se_distingue_de_uno_correcto(capsys):
    salida = _render(
        [
            _observacion("leer_archivo", {"existe": True}),
            _observacion(
                "run_tests",
                {"causa_no_ejecutado": "fallo_de_coleccion"},
                estado=EstadoResultado.ERROR,
            ),
        ],
        capsys,
    )

    assert cli._MARCA_FALLO in salida, "un paso fallido necesita señal visual"
    assert cli._MARCA_EXITO in salida


def test_un_paso_invalido_tambien_se_marca_como_fallo(capsys):
    salida = _render(
        [_observacion("run_tests", {}, estado=EstadoResultado.INVALIDO)], capsys
    )

    assert cli._MARCA_FALLO in salida


# --- Legibilidad del contenido ---------------------------------------------


def test_los_campos_del_resultado_se_ven_como_campos_no_como_repr(capsys):
    salida = _render(
        [_observacion("run_tests", {"pasadas": 21, "falladas": 0, "total": 21})],
        capsys,
    )

    assert "pasadas: 21" in _plano(salida)
    assert "{'pasadas'" not in salida, "no debe volcarse el repr del diccionario"


def test_el_texto_multilinea_se_imprime_con_saltos_reales(capsys):
    stdout = "línea uno\nlínea dos\nlínea tres"
    salida = _render([_observacion("run_tests", {"stdout_tail": stdout})], capsys)

    assert "\\n" not in salida, "los saltos escapados hacen el panel ilegible"
    assert "línea uno" in _plano(salida)
    assert "línea tres" in _plano(salida)


def test_el_contenido_de_un_archivo_conserva_su_forma(capsys):
    codigo = "def suma(a, b):\n    return a + b\n"
    salida = _render(
        [_observacion("leer_archivo", {"archivo": "calc.py", "contenido": codigo})],
        capsys,
    )

    plano = _plano(salida)
    assert "def suma(a, b):" in plano
    assert "return a + b" in plano


def test_la_herramienta_y_la_razon_siguen_visibles(capsys):
    salida = _plano(
        _render(
            [_observacion("leer_archivo", {"existe": True}, razon="leer el módulo")],
            capsys,
        )
    )

    assert "leer_archivo" in salida
    assert "leer el módulo" in salida


def test_una_salida_que_no_es_diccionario_no_rompe_el_render(capsys):
    salida = _render([_observacion("locate", "sin coincidencias")], capsys)

    assert "sin coincidencias" in _plano(salida)


def test_una_salida_enorme_sigue_acotandose(capsys):
    salida = _render([_observacion("search", {"todo": "x" * 20000})], capsys)

    assert len(salida) < 20000, "el panel no puede volcar una salida sin límite"


def _plano(salida: str) -> str:
    """Quita bordes del panel y reúne el envoltorio de línea de Rich."""
    return " ".join(
        linea.strip().strip("│").strip() for linea in salida.splitlines()
    )
