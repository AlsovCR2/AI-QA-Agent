"""Tests de la herramienta `search` (T034, FR-009/010/011, UC-004).

Cubre: ocurrencias reales con contexto, sin alterar el código (SC-002/003/011);
patrón ausente → informa ausencia sin inventar (SC-002).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.search import SearchHerramienta


def _crear_proyecto_search(tmp_path: Path) -> Path:
    """Estructura: archivos con contenido para buscar."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        '"""Modulo principal."""\n\n'
        'def procesar_datos(entrada: str) -> str:\n'
        '    """Procesa la entrada y devuelve resultado."""\n'
        '    resultado = entrada.strip().upper()\n'
        '    return resultado\n\n'
        'def validar_email(email: str) -> bool:\n'
        '    """Valida formato de email."""\n'
        '    import re\n'
        '    patron = r"^[^@]+@[^@]+\\.[^@]+$"\n'
        '    return bool(re.match(patron, email))\n'
    )
    (tmp_path / "README.md").write_text("# Proyecto\nEjemplos varios.\n")
    return tmp_path


def test_search_ocurrencias_reales_con_contexto(tmp_path):
    """T034: patrón presente → muestra ocurrencias reales con contexto (SC-003)."""
    proyecto = _crear_proyecto_search(tmp_path)
    herramienta = SearchHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron_regex": "def\\s+\\w+", "ruta": str(proyecto), "contexto_lineas": 1}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert len(resultado.datos["ocurrencias"]) >= 2
    # Verifica que el contexto incluye código real
    for occ in resultado.datos["ocurrencias"]:
        assert "ruta_relativa" in occ
        assert "linea" in occ
        assert "contexto" in occ
        assert len(occ["contexto"]) > 0


def test_search_contenido_coincide_codigo_real(tmp_path):
    """T034: el contenido citado coincide con el código real (SC-002/011)."""
    proyecto = _crear_proyecto_search(tmp_path)
    herramienta = SearchHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron_regex": "procesar_datos", "ruta": str(proyecto), "contexto_lineas": 2}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert len(resultado.datos["ocurrencias"]) >= 1
    # El contexto debe contener la función real
    occ = resultado.datos["ocurrencias"][0]
    assert "procesar_datos" in occ["contexto"]
    assert "entrada: str" in occ["contexto"] or "resultado" in occ["contexto"]


def test_search_patron_ausente_informa_ausencia(tmp_path):
    """T034: patrón ausente → informa ausencia sin inventar (SC-002)."""
    proyecto = _crear_proyecto_search(tmp_path)
    herramienta = SearchHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron_regex": "patron_inexistente_xyz", "ruta": str(proyecto), "contexto_lineas": 1}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["ocurrencias"] == []


def test_search_regex_invalido_estado_error(tmp_path):
    """T037: patrón regex mal formado → estado error, no presenta como válido (SC-005)."""
    proyecto = _crear_proyecto_search(tmp_path)
    herramienta = SearchHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron_regex": "[invalid(", "ruta": str(proyecto), "contexto_lineas": 1}
    )

    assert resultado.estado in {EstadoResultado.ERROR, EstadoResultado.INVALIDO}
    assert resultado.datos.get("ocurrencias", []) == []


def test_search_ruta_fuera_allowlist_no_accede(tmp_path):
    """Search respeta Allowlist: ruta fuera → error (FR-025)."""
    proyecto = _crear_proyecto_search(tmp_path)
    outside = tmp_path.parent / "perimetro_vecino"
    if not outside.exists():
        outside.mkdir()
    herramienta = SearchHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron_regex": "test", "ruta": str(outside), "contexto_lineas": 1}
    )

    assert resultado.estado in {EstadoResultado.ERROR, EstadoResultado.INVALIDO}
    assert resultado.datos == {}


def test_search_ignora_directorios_de_ruido(tmp_path):
    """No busca en `.git`/`bin`/`obj`/`packages` (T094).

    Sin la exclusión, `search` recorría `SemanticSymbols.db` y XML de
    `bin\\Debug`, generando resultados gigantes de ruido que saturaban la
    observación del LLM.
    """
    proyecto = _crear_proyecto_search(tmp_path)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "Debug").mkdir()
    (tmp_path / "bin" / "Debug" / "falso.py").write_text("def procesar_datos():\n    pass\n")
    (tmp_path / "obj").mkdir()
    (tmp_path / "obj" / "falso.py").write_text("def procesar_datos():\n    pass\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "falso.py").write_text("def procesar_datos():\n    pass\n")

    herramienta = SearchHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron_regex": "procesar_datos", "ruta": str(proyecto), "contexto_lineas": 1}
    )

    assert resultado.estado == EstadoResultado.EXITO
    rutas = {o["ruta_relativa"] for o in resultado.datos["ocurrencias"]}
    assert "src\\app.py" in rutas or "src/app.py" in rutas
    assert not any(p.startswith(("bin", "obj", ".git")) for p in rutas)


def test_search_max_ocurrencias_trunca_y_avisa(tmp_path):
    """T108: `max_ocurrencias` limita el volcado y lo avisa (FR-019, honestidad)."""
    proyecto = _crear_proyecto_search(tmp_path)
    # Un archivo con muchas coincidencias para forzar el límite
    (proyecto / "src" / "muchas.py").write_text(
        "\n".join(f"def fn{i}():  # marca_de_busqueda" for i in range(50)),
        encoding="utf-8",
    )
    herramienta = SearchHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "patron_regex": "marca_de_busqueda",
            "ruta": str(proyecto),
            "contexto_lineas": 0,
            "max_ocurrencias": 5,
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert len(resultado.datos["ocurrencias"]) == 5
    assert "nota" in resultado.datos
    assert "Se limitó la búsqueda" in resultado.datos["nota"]
    # Por defecto (sin parametro) no se trunca en proyectos pequeños
    resultado_sin_limite = herramienta.ejecutar(
        {
            "patron_regex": "marca_de_busqueda",
            "ruta": str(proyecto),
            "contexto_lineas": 0,
        }
    )
    assert len(resultado_sin_limite.datos["ocurrencias"]) == 50
    assert "nota" not in resultado_sin_limite.datos