"""Tests de la herramienta `leer_archivo` (T104, FR-048 / FR-011 / FR-025).

Cubre: lectura de contenido real tal como existe (FR-011 / SC-002/003);
archivo inexistente → informa ausencia sin inventar (FR-008 / SC-002);
archivo fuera de la allowlist → rechaza sin leer (FR-025 / SC-011);
truncado por `max_lineas` con aviso explícito (honestidad, FR-019).
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.leer_archivo import LeerArchivoHerramienta


def _crear_proyecto_lectura(tmp_path: Path) -> Path:
    """Estructura: un archivo de código y un archivo de tests."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def config():\n"
        "    return {'clave': 'valor'}\n"
        "\n"
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_app.py").write_text(
        "from app import sumar\n"
        "\n"
        "def test_suma():\n"
        "    assert sumar(2, 2) == 4\n",
        encoding="utf-8",
    )
    return tmp_path


def test_leer_archivo_devuelve_contenido_real_tal_cual(tmp_path):
    """T104: lee el contenido real, sin alterarlo (FR-011 / SC-003)."""
    proyecto = _crear_proyecto_lectura(tmp_path)
    herramienta = LeerArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "src/app.py"}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["existe"] is True
    assert resultado.datos["archivo"] == "src/app.py"
    assert resultado.datos["contenido"].startswith("def config():")
    assert "return a + b" in resultado.datos["contenido"]
    assert resultado.datos["truncado"] is False
    # El contenido coincide exactamente con el archivo real (FR-011)
    assert resultado.datos["contenido"] == (proyecto / "src" / "app.py").read_text(
        encoding="utf-8"
    )


def test_leer_archivo_lee_archivos_de_test(tmp_path):
    """T104: puede leer archivos de test (base del análisis por capa)."""
    proyecto = _crear_proyecto_lectura(tmp_path)
    herramienta = LeerArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "tests/test_app.py"}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["existe"] is True
    assert "def test_suma()" in resultado.datos["contenido"]


def test_leer_archivo_inexistente_informa_ausencia_sin_inventar(tmp_path):
    """T104: archivo inexistente → existe=False, no fabrica contenido (SC-002)."""
    proyecto = _crear_proyecto_lectura(tmp_path)
    herramienta = LeerArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "src/no_existe.py"}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["existe"] is False
    assert resultado.datos["contenido"] == ""


def test_leer_archivo_sin_archivo_error_explicito(tmp_path):
    """T104: sin `archivo_relativo` → error explícito (FR-018)."""
    proyecto = _crear_proyecto_lectura(tmp_path)
    herramienta = LeerArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar({"ruta": str(proyecto)})

    assert resultado.estado == EstadoResultado.INVALIDO
    assert "No se especificó el archivo" in (resultado.error or "")


def test_leer_archivo_ruta_fuera_de_allowlist_rechaza(tmp_path):
    """T104: ruta fuera del perímetro → error, no accede (FR-025 / SC-011)."""
    proyecto = _crear_proyecto_lectura(tmp_path)
    outside = tmp_path.parent / "perimetro_vecino"
    outside.mkdir(exist_ok=True)
    herramienta = LeerArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(outside), "archivo_relativo": "secretos.txt"}
    )

    assert resultado.estado == EstadoResultado.ERROR
    assert "fuera de las rutas autorizadas" in (resultado.error or "")


def test_leer_archivo_escape_archivo_relativo_rechaza(tmp_path):
    """T104: `archivo_relativo` con `..` no escapa del perímetro (FR-025)."""
    proyecto = _crear_proyecto_lectura(tmp_path)
    fuera = tmp_path.parent / "secreto.txt"
    fuera.write_text("secreto", encoding="utf-8")
    herramienta = LeerArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "../secreto.txt"}
    )

    assert resultado.estado == EstadoResultado.ERROR
    assert resultado.datos == {}


def test_leer_archivo_trunca_con_aviso_explicito(tmp_path):
    """T104: `max_lineas` trunca y lo avisa (honestidad, FR-019)."""
    proyecto = _crear_proyecto_lectura(tmp_path)
    (proyecto / "src" / "grande.py").write_text(
        "\n".join(f"linea_{i}" for i in range(100)), encoding="utf-8"
    )
    herramienta = LeerArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "src/grande.py", "max_lineas": 10}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["truncado"] is True
    assert resultado.datos["total_lineas"] == 100
    assert "líneas más" in resultado.datos["contenido"]
    # No se inventa contenido: solo las primeras `max_lineas` reales
    assert "linea_0" in resultado.datos["contenido"]
    assert "linea_99" not in resultado.datos["contenido"]