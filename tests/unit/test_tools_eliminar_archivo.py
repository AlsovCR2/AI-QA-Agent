"""Tests de la herramienta `eliminar_archivo` (Phase 14, T098 / FR-044).

Cubre: eliminación real del archivo (FR-044); backup del estado previo en
`.qa-backup/` antes de eliminar y restauración (FR-045 / SC-023); rechazo sin
modificar nada de un archivo inexistente o directorio (FR-044 / SC-024) o
fuera del perímetro (FR-025 / SC-022); requiere autorización (FR-046 / SC-004).
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.backup import BackupManager
from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.eliminar_archivo import EliminarArchivoHerramienta


def test_eliminar_archivo_borra_con_backup_restaurable(tmp_path):
    """T098: elimina el archivo y deja el original restaurable (FR-044/045)."""
    proyecto = tmp_path
    archivo = proyecto / "viejo.py"
    archivo.write_text("ORIGINAL\n", encoding="utf-8")
    herramienta = EliminarArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "viejo.py"}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["eliminado"] is True
    assert not archivo.exists()

    backup_ruta = Path(resultado.datos["backup"])
    assert backup_ruta.is_file()
    assert backup_ruta.read_text(encoding="utf-8") == "ORIGINAL\n"
    assert BackupManager(proyecto).restaurar(backup_ruta) is True
    assert archivo.exists()
    assert archivo.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_eliminar_archivo_inexistente_rechaza_sin_modificar(tmp_path):
    """T098: eliminar un archivo inexistente se rechaza SIN modificar nada (FR-044)."""
    proyecto = tmp_path
    herramienta = EliminarArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "no_existe.py"}
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert not (proyecto / "no_existe.py").exists()


def test_eliminar_archivo_directorio_rechaza(tmp_path):
    """T098: un directorio no se elimina (solo archivos, FR-044)."""
    proyecto = tmp_path
    (proyecto / "carpeta").mkdir()
    herramienta = EliminarArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "carpeta"}
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert (proyecto / "carpeta").is_dir()


def test_eliminar_archivo_fuera_de_allowlist_se_rechaza(tmp_path):
    """T098: fuera del perímetro → rechazo sin eliminar nada (FR-025 / SC-022)."""
    proyecto = tmp_path
    exterior = tmp_path.parent / "exterior.txt"
    exterior.write_text("ORIGINAL\n", encoding="utf-8")
    herramienta = EliminarArchivoHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "archivo_relativo": "../exterior.txt"}
    )

    assert resultado.estado == EstadoResultado.ERROR
    assert exterior.exists()


def test_eliminar_archivo_requiere_autorizacion():
    """T098: acción destructiva → requiere autorización (FR-046 / SC-004)."""
    assert EliminarArchivoHerramienta([]).requiere_autorizacion is True