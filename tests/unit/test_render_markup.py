"""El render no puede alterar la evidencia que muestra (FR-035 / VIII).

Rich interpreta `[...]` como marcado. Como los paneles "Razonamiento",
"Respuesta" y "Recomendaciones" imprimen contenido que viene del modelo y de
las herramientas, cualquier indexación (`ordenados[medio]`), lista por
comprensión (`[k for k in ...]`) o anotación de tipo (`list[int]`) desaparecía
de la pantalla.

Encontrado el 2026-08-21 ejecutando el agente contra un proyecto real: el panel
mostraba `return ordenados` y `modas = ` mientras el archivo en disco tenía
`return ordenados[medio]` y `modas = [k for k, v in conteo.items() ...]`.

Es el peor fallo posible en un agente de QA: no corrompe un resultado, corrompe
la EVIDENCIA con la que el usuario decide si fiarse del resultado. El marcado
propio de la CLI (`[yellow]...[/yellow]`) debe seguir funcionando, así que la
solución es escapar el contenido ajeno, no desactivar el marcado.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from qa_agent.cli import main as cli


def _observacion(orden: int, razon: str, herramienta: str, parametros, datos):
    return SimpleNamespace(
        paso=SimpleNamespace(
            orden=orden, razon=razon, herramienta=herramienta, parametros=parametros
        ),
        resultado=SimpleNamespace(datos=datos),
    )


def _respuesta(razonamiento=None, texto="", recomendaciones=None):
    return SimpleNamespace(
        razonamiento=razonamiento or [],
        texto=texto,
        recomendaciones=recomendaciones or [],
        acciones=[],
    )


#: Fragmentos reales tomados del caso que destapó el fallo.
FRAGMENTOS = [
    "return ordenados[medio]",
    "modas = [k for k, v in conteo.items() if v == max_frecuencia]",
    "def f(datos: list[int]) -> dict[str, int]:",
    "matriz[0][1]",
]


@pytest.mark.parametrize("fragmento", FRAGMENTOS)
def test_el_panel_de_respuesta_no_se_come_los_corchetes(fragmento, capsys):
    cli._renderizar_respuesta(_respuesta(texto=fragmento))

    salida = capsys.readouterr().out
    assert fragmento in _sin_saltos(salida), (
        f"el render perdió contenido: se esperaba {fragmento!r}"
    )


@pytest.mark.parametrize("fragmento", FRAGMENTOS)
def test_el_panel_de_razonamiento_no_se_come_los_corchetes(fragmento, capsys):
    cli._renderizar_respuesta(
        _respuesta(
            razonamiento=[
                _observacion(1, "leer el módulo", "leer_archivo", {}, fragmento)
            ]
        )
    )

    salida = capsys.readouterr().out
    assert fragmento in _sin_saltos(salida)


def test_las_recomendaciones_no_se_comen_los_corchetes(capsys):
    rec = "Corregir `ordenados[medio]` para que promedie los centrales"
    cli._renderizar_respuesta(_respuesta(recomendaciones=[rec]))

    assert rec in _sin_saltos(capsys.readouterr().out)


def test_los_parametros_de_la_herramienta_conservan_los_corchetes(capsys):
    cli._renderizar_respuesta(
        _respuesta(
            razonamiento=[
                _observacion(1, "ejecutar", "run_tests", {"datos": [1, 2, 3]}, "ok")
            ]
        )
    )

    assert "[1, 2, 3]" in _sin_saltos(capsys.readouterr().out)


def test_la_tabla_de_historial_no_se_come_los_corchetes(capsys):
    """`--mostrar-historial` vuelca la salida cruda de la herramienta.

    `Table.add_row` interpreta marcado igual que `Console.print`, así que la
    tabla necesita el mismo escape que los paneles.
    """
    accion = SimpleNamespace(
        orden=1,
        herramienta_id="leer_archivo",
        estado=SimpleNamespace(value="exito"),
        salida="return ordenados[medio]",
    )
    respuesta = _respuesta()
    respuesta.acciones = [accion]

    cli._renderizar_respuesta(respuesta, mostrar_historial=True)

    assert "ordenados[medio]" in _sin_saltos(capsys.readouterr().out)


def test_el_marcado_propio_de_la_cli_sigue_funcionando(capsys):
    """Escapar el contenido ajeno no puede desactivar el marcado de la CLI.

    Si se hubiese resuelto con `Console(markup=False)`, este texto aparecería
    con las etiquetas literales en pantalla.
    """
    cli._console.print("[yellow]No hay tareas.[/yellow]")

    salida = capsys.readouterr().out
    assert "No hay tareas." in salida
    assert "[yellow]" not in salida


def _sin_saltos(salida: str) -> str:
    """Deshace el envoltorio de línea que Rich aplica dentro del panel.

    Rich parte las líneas al ancho del panel e inserta los bordes; comparar el
    fragmento contra el texto ya reunido evita que el test dependa del ancho
    del terminal del runner.
    """
    return "".join(
        linea.strip().strip("│").strip() for linea in salida.splitlines()
    )
