"""Tests de la herramienta `editar_archivo` (Phase 14, T097 / FR-043).

Cubre: edición real del contenido (FR-043); backup del estado previo en
`.qa-backup/` antes de modificar y restauración (FR-045 / SC-023); rechazo sin
modificar nada de un archivo inexistente (FR-043 / SC-024) o fuera del
perímetro (FR-025 / SC-022); requiere autorización (FR-046 / SC-004).
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.backup import BackupManager
from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.editar_archivo import EditarArchivoHerramienta


def _crear_archivo_editable(tmp_path: Path) -> Path:
    archivo = tmp_path / "app.py"
    archivo.write_text("ORIGINAL\n", encoding="utf-8")
    return archivo


def test_editar_archivo_modifica_contenido_real(tmp_path):
    """T097: edita el archivo con el contenido nuevo (FR-043)."""
    proyecto = tmp_path
    archivo = _crear_archivo_editable(proyecto)
    herramienta = EditarArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "archivo_relativo": "app.py",
            "contenido": "EDITADO\n",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["editado"] is True
    assert resultado.datos["existia"] is True
    assert archivo.read_text(encoding="utf-8") == "EDITADO\n"


def test_editar_archivo_respalda_estado_previo_y_restaura(tmp_path):
    """T097: backup del original en `.qa-backup/` restaurable (FR-045 / SC-023)."""
    proyecto = tmp_path
    _crear_archivo_editable(proyecto)
    herramienta = EditarArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "archivo_relativo": "app.py",
            "contenido": "EDITADO\n",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    backup_ruta = Path(resultado.datos["backup"])
    assert (proyecto / ".qa-backup").exists()
    assert backup_ruta.is_file()
    assert backup_ruta.read_text(encoding="utf-8") == "ORIGINAL\n"

    gestor = BackupManager(proyecto)
    assert gestor.restaurar(backup_ruta) is True
    assert (proyecto / "app.py").read_text(encoding="utf-8") == "ORIGINAL\n"


def test_editar_archivo_inexistente_rechaza_sin_modificar(tmp_path):
    """T097: editar un archivo inexistente se rechaza SIN modificar nada (FR-043)."""
    proyecto = tmp_path
    herramienta = EditarArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "archivo_relativo": "no_existe.py",
            "contenido": "x",
        }
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert not (proyecto / "no_existe.py").exists()


def test_editar_archivo_fuera_de_allowlist_se_rechaza(tmp_path):
    """T097: fuera del perímetro → rechazo sin modificar nada (FR-025 / SC-022)."""
    proyecto = tmp_path
    exterior = tmp_path.parent / "exterior.txt"
    exterior.write_text("ORIGINAL\n", encoding="utf-8")
    herramienta = EditarArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(proyecto),
            "archivo_relativo": "../exterior.txt",
            "contenido": "x",
        }
    )

    assert resultado.estado == EstadoResultado.ERROR
    assert exterior.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_editar_archivo_sin_contenido_rechaza(tmp_path):
    """T097: sin contenido nuevo → error explícito sin ejecutar (FR-019)."""
    proyecto = tmp_path
    archivo = _crear_archivo_editable(proyecto)
    herramienta = EditarArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "app.py"}
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert archivo.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_editar_archivo_requiere_autorizacion():
    """T097: acción destructiva → requiere autorización (FR-046 / SC-004)."""
    assert EditarArchivoHerramienta([]).requiere_autorizacion is True