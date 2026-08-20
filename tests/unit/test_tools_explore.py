"""Tests de la herramienta `explore` (T026, FR-006/007/008, UC-002).

Cubre: estructura real → elementos reales (SC-003); ruta inexistente →
`existe=False`; ruta fuera de la `Allowlist` → no accede (SC-002).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.explore import ExploreHerramienta


def _crear_proyecto(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def config(): return {}\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_x(): pass\n")
    return tmp_path


def test_explore_devuelve_elementos_reales(tmp_path):
    proyecto = _crear_proyecto(tmp_path)
    herramienta = ExploreHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar({"ruta": str(proyecto)})

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["existe"] is True
    assert resultado.datos["accesible"] is True
    nombres = [e["nombre"] for e in resultado.datos["elementos"]]
    tipos = [e["tipo"] for e in resultado.datos["elementos"]]
    # Elementos reales existentes (SC-003 / FR-008)
    assert "src" in nombres and "tests" in nombres
    assert any(t == "directorio" for t in tipos)


def test_explore_ruta_inexistente_marca_existe_false(tmp_path):
    # tmp_path base (ruta inexistente dentro)
    inexistente = tmp_path / "no_existe"
    herramienta = ExploreHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar({"ruta": str(inexistente)})

    assert resultado.estado == EstadoResultado.EXITO  # la herramienta no falla
    assert resultado.datos["existe"] is False
    assert resultado.datos["accesible"] is False
    assert resultado.datos["elementos"] == []  # no inventa estructura (UC-002)


def test_explore_ruta_fuera_de_allowlist_no_accede(tmp_path):
    proyecto = _crear_proyecto(tmp_path)
    outside = tmp_path.parent / "perimetro_vecino"
    if not outside.exists():
        outside.mkdir()
    herramienta = ExploreHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar({"ruta": str(outside)})

    # No inventa contenido fuera del perímetro (SC-002 / FR-025)
    assert resultado.estado in {EstadoResultado.ERROR, EstadoResultado.INVALIDO}
    assert resultado.datos == {}


def _nombres_de(resultado) -> list[str]:
    return [e["nombre"] for e in resultado.datos["elementos"]]


def test_explore_respeta_profundidad_max(tmp_path):
    proyecto = _crear_proyecto(tmp_path)
    (tmp_path / "nivel1").mkdir()
    (tmp_path / "nivel1" / "nivel2").mkdir()
    (tmp_path / "nivel1" / "nivel2" / "nivel3").mkdir()
    herramienta = ExploreHerramienta([str(tmp_path)])

    # profundidad 1: solo primeros niveles, no profundiza a nivel2/nivel3
    resultado = herramienta.ejecutar(
        {"ruta": str(tmp_path), "profundidad_max": 1}
    )
    nombres = _nombres_de(resultado)
    assert "nivel1" in nombres
    profundidades = {
        e.get("profundidad", 0) for e in resultado.datos["elementos"]
        if e["nombre"].startswith("nivel")
    }
    assert profundidades == {1}

    # profundidad 2: incluye nivel2
    resultado2 = herramienta.ejecutar(
        {"ruta": str(tmp_path), "profundidad_max": 2}
    )
    nombres2 = _nombres_de(resultado2)
    assert "nivel2" in nombres2


def test_explore_ignora_directorios_de_ruido(tmp_path):
    """Excluye artefactos de build/dependencias/VCS en cualquier nivel (T094).

    `.git`, `.vs`, `bin`, `obj`, `packages` y `node_modules` son ruido que
    satura la observación y confunde al LLM (UC-002); la estructura real del
    código debe seguir apareciendo.
    """
    proyecto = _crear_proyecto(tmp_path)
    for ruido in (".git", ".vs", "bin", "obj", "packages", "node_modules"):
        (tmp_path / ruido).mkdir()
        (tmp_path / ruido / "contenido.txt").write_text("x")
    # Ruido también anidado dentro de un directorio de código real.
    (tmp_path / "src" / "bin").mkdir()

    herramienta = ExploreHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "profundidad_max": 2}
    )
    nombres = _nombres_de(resultado)
    for ruido in (".git", ".vs", "bin", "obj", "packages", "node_modules"):
        assert ruido not in nombres
    # La estructura real sigue visible.
    assert "src" in nombres and "tests" in nombres
    assert "test_app.py" in nombres


def test_explore_no_excluye_directorios_legitimos(tmp_path):
    """Un directorio con nombre parecido a 'bin' pero distinto no se excluye."""
    proyecto = _crear_proyecto(tmp_path)
    (tmp_path / "src" / "binario").mkdir()
    herramienta = ExploreHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "profundidad_max": 2}
    )
    nombres = _nombres_de(resultado)
    assert "binario" in nombres