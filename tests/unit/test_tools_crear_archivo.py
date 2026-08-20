"""Tests de la herramienta `crear_archivo` (Phase 14, T096 / FR-042).

Cubre: creación real del archivo con su contenido (FR-042); rechazo sin
modificar nada si el archivo ya existe (FR-042 / SC-024); rechazo de rutas
fuera de la allowlist incl. `..`/path traversal (FR-025 / SC-022); rechazo de
archivo vacío o sin contenido (FR-019 / SC-002); requiere autorización
(FR-046 / SC-004). Determinística (VI / SC-010).
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.crear_archivo import CrearArchivoHerramienta


def test_crear_archivo_crea_con_contenido_real(tmp_path):
    """T096: crea el archivo con el contenido indicado (FR-042)."""
    proyecto = tmp_path
    herramienta = CrearArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "archivo_relativo": "src/config/ajustes.py",
            "contenido": "DEBUG = True\n",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["creado"] is True
    assert resultado.datos["existia"] is False
    archivo = proyecto / "src" / "config" / "ajustes.py"
    assert archivo.exists()
    assert archivo.read_text(encoding="utf-8") == "DEBUG = True\n"


def test_crear_archivo_existente_rechaza_sin_modificar(tmp_path):
    """T096: crear un archivo existente se rechaza SIN modificar nada (FR-042)."""
    proyecto = tmp_path
    archivo = proyecto / "app.py"
    archivo.write_text("ORIGINAL\n", encoding="utf-8")
    herramienta = CrearArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "archivo_relativo": "app.py",
            "contenido": "NUEVO\n",
        }
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert resultado.datos["creado"] is False
    assert resultado.datos["existia"] is True
    assert archivo.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_crear_archivo_fuera_de_allowlist_se_rechaza(tmp_path):
    """T096: archivo fuera del perímetro → rechazo sin crear nada (FR-025)."""
    proyecto = tmp_path
    (proyecto / "src").mkdir()
    # Perímetro restringido a `src/`: crear en la raíz queda fuera (FR-025).
    herramienta = CrearArchivoHerramienta([str(proyecto / "src")])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "archivo_relativo": "fuera.py",
            "contenido": "x",
        }
    )

    assert resultado.estado == EstadoResultado.ERROR
    assert not (proyecto / "fuera.py").exists()


def test_crear_archivo_traversal_se_rechaza_sin_crear_nada(tmp_path):
    """T096: `..` para escapar del perímetro se rechaza (FR-025 / SC-022)."""
    proyecto = tmp_path
    exterior = tmp_path.parent / "fuera_raiz.py"
    herramienta = CrearArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "archivo_relativo": "../fuera_raiz.py",
            "contenido": "x",
        }
    )

    assert resultado.estado == EstadoResultado.ERROR
    assert not exterior.exists()


def test_crear_archivo_sin_archivo_ni_contenido_rechaza(tmp_path):
    """T096: sin archivo o sin contenido → error explícito sin ejecutar (FR-019)."""
    proyecto = tmp_path
    herramienta = CrearArchivoHerramienta([str(proyecto)])
    sin_archivo = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "", "contenido": "x"}
    )
    assert sin_archivo.estado == EstadoResultado.ERROR

    sin_contenido = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "app.py"}
    )
    assert sin_contenido.estado == EstadoResultado.INVALIDO


def test_crear_archivo_requiere_autorizacion():
    """T096: acción destructiva → requiere autorización (FR-046 / SC-004)."""
    assert CrearArchivoHerramienta([]).requiere_autorizacion is True


def test_crear_archivo_raiz_fuera_de_allowlist(tmp_path):
    """T096: raíz no autorizada → rechazo explícito (FR-025)."""
    herramienta = CrearArchivoHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {"ruta": str(tmp_path.parent), "archivo_relativo": "x.py", "contenido": "x"}
    )
    assert resultado.estado == EstadoResultado.ERROR