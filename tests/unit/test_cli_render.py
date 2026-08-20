"""Tests de acotado y render del CLI (T094/T109, FR-020/035).

El historial de acciones y el razonamiento volcaban la salida completa de
cada herramienta (p. ej. `explore` con cientos de archivos), produciendo
paneles ilegibles. `_acotar_render` limita cada salida a un tamaño legible.
Además, el historial está OCULTO por defecto (T109): la trazabilidad de cada
paso sigue en el panel "Razonamiento" y se muestra la tabla solo con
`--mostrar-historial`.
"""

from __future__ import annotations

import io

from rich.console import Console

from qa_agent.agent.response import (
    EstadoAccion,
    RegistroDeAccion,
    RespuestaDelAgente,
)
from qa_agent.cli.main import _acotar_render, _renderizar_respuesta


def test_acotar_render_recorta_salidas_largas():
    largo = "x" * 5000
    corto = _acotar_render(largo)
    assert len(corto) <= 1000
    assert corto.startswith("x" * 50)
    assert corto.endswith("x" * 50)
    assert "[+" in corto


def test_acotar_render_deja_cortos_intactos():
    assert _acotar_render("salida corta") == "salida corta"


def _respuesta_con_historial() -> RespuestaDelAgente:
    respuesta = RespuestaDelAgente(
        texto="Respuesta de prueba.",
        solicitud_id="s-1",
        recomendaciones=["Revisar el dominio."],
    )
    respuesta.acciones.append(
        RegistroDeAccion(
            orden=1,
            herramienta_id="leer_archivo",
            entrada={"archivo_relativo": "src/app.py"},
            salida={"existe": True},
            estado=EstadoAccion.EXITO,
        )
    )
    return respuesta


def test_render_oculta_el_historial_por_defecto(monkeypatch):
    """T109: sin `--mostrar-historial` no se imprime la tabla del historial."""
    captura = io.StringIO()
    monkeypatch.setattr(
        "qa_agent.cli.main._console", Console(file=captura, force_terminal=True)
    )
    _renderizar_respuesta(_respuesta_con_historial())

    salida = captura.getvalue()
    assert "Respuesta de prueba" in salida
    assert "Recomendaciones" in salida
    assert "Historial de acciones" not in salida
    assert "leer_archivo" not in salida


def test_render_muestra_el_historial_con_flag(monkeypatch):
    """T109: con `mostrar_historial=True` la tabla del historial sí aparece."""
    captura = io.StringIO()
    monkeypatch.setattr(
        "qa_agent.cli.main._console", Console(file=captura, force_terminal=True)
    )
    _renderizar_respuesta(_respuesta_con_historial(), mostrar_historial=True)

    salida = captura.getvalue()
    assert "Historial de acciones" in salida
    assert "leer_archivo" in salida