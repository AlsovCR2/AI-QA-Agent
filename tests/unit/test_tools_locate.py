"""Tests de la herramienta `locate` (T030/T031, FR-007/008, UC-003).

Cubre: coincidencias reales (SC-003); sin coincidencias → ausencia sin fabricar (FR-008, UC-003).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.locate import LocateHerramienta


def _crear_proyecto_locate(tmp_path: Path) -> Path:
    """Estructura: 1 archivo Python con docstring y 1 archivo de texto."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        '"""Modulo de ejemplos."""\n\ndef hola() -> str:\n    return "hola"\n'
    )
    (tmp_path / "README.md").write_text("# Proyecto\nEjemplos varios.\n")
    return tmp_path


def _nombres_de(resultado) -> list[str]:
    return [c["nombre"] for c in resultado.datos["coincidencias"]]


def test_locate_coincidencias_reales(tmp_path):
    """T030: encontrar coincidencias reales devuelve elementos (SC-003)."""
    proyecto = _crear_proyecto_locate(tmp_path)
    herramienta = LocateHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {"patron": "hola", "ruta": str(tmp_path), "tipo": "funcion"}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert len(resultado.datos["coincidencias"]) >= 1
    assert "app.py" in _nombres_de(resultado)


def test_locate_ruta_relativa_incluye_el_directorio(tmp_path):
    """T114: `ruta_relativa` es relativa a la raíz de la búsqueda (`src/app.py`),
    no solo el nombre del archivo (`app.py`) — permite localizar y leer cada
    coincidencia sin ambigüedad (FR-008)."""
    _crear_proyecto_locate(tmp_path)
    herramienta = LocateHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {"patron": "hola", "ruta": str(tmp_path), "tipo": "funcion"}
    )

    assert resultado.estado == EstadoResultado.EXITO
    coincidencias = resultado.datos["coincidencias"]
    assert coincidencias
    for coincidencia in coincidencias:
        assert coincidencia["ruta_relativa"].endswith("app.py")
        assert coincidencia["ruta_relativa"] != "app.py"
        assert "src" in coincidencia["ruta_relativa"]


def test_locate_sin_coincidencias_no_fabricar(tmp_path):
    """T030: sin coincidencias → ausencia sin fabricar (FR-008, UC-003)."""
    proyecto = _crear_proyecto_locate(tmp_path)
    herramienta = LocateHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {"patron": "patrón_inexistente_al_100%", "ruta": str(tmp_path), "tipo": "cualquiera"}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["coincidencias"] == []


def test_locate_ruta_vacia_no_fabricar(tmp_path):
    """T030: ruta vacía o sin coincidencias no inventa contenido."""
    proyecto = _crear_proyecto_locate(tmp_path)
    herramienta = LocateHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {"patron": "", "ruta": str(tmp_path), "tipo": "cualquiera"}
    )

    # No debe devolver coincidencias falsas
    assert resultado.datos["coincidencias"] == []


def test_locate_ignora_directorios_de_ruido(tmp_path):
    """No busca en `.git`/`bin`/`obj`/`packages` (T094)."""
    proyecto = _crear_proyecto_locate(tmp_path)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "falso.py").write_text('"""Módulo falso."""\ndef hola() -> str:\n    return "x"\n')
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "falso.py").write_text('"""Módulo falso."""\ndef hola() -> str:\n    return "x"\n')

    herramienta = LocateHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {"patron": "hola", "ruta": str(tmp_path), "tipo": "funcion"}
    )

    assert resultado.estado == EstadoResultado.EXITO
    nombres = _nombres_de(resultado)
    assert "app.py" in nombres
    assert "falso.py" not in nombres