"""Tests de `BackupManager` (Phase 14, T099 / FR-045 / SC-023).

Cubre: respaldo del contenido original en `.qa-backup/` preservando la ruta
relativa bajo una marca de tiempo; restauración del contenido original;
rechazo de restaurar backups inexistentes o ajenos al proyecto (sin modificar
nada). Determinístico (VI / SC-010).
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.backup import BackupManager


def test_respaldar_guarda_bajo_directorio_con_marca(tmp_path):
    """T099: el backup preserva la ruta relativa bajo `.qa-backup/`."""
    proyecto = tmp_path
    (proyecto / "src").mkdir()
    gestor = BackupManager(proyecto)
    backup = gestor.respaldar("src/app.py", "ORIGINAL\n")

    assert backup.is_file()
    assert (proyecto / ".qa-backup").is_dir()
    relativo = backup.relative_to(proyecto / ".qa-backup")
    assert relativo.parts[1:] == ("src", "app.py")
    assert backup.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_restaurar_recupera_el_original(tmp_path):
    """T099: `restaurar` vuelve a escribir el contenido original."""
    proyecto = tmp_path
    (proyecto / "src").mkdir()
    gestor = BackupManager(proyecto)
    backup = gestor.respaldar("src/app.py", "ORIGINAL\n")

    assert gestor.restaurar(backup) is True
    assert (proyecto / "src" / "app.py").read_text(encoding="utf-8") == "ORIGINAL\n"


def test_restaurar_backup_inexistente_devuelve_false(tmp_path):
    """T099: backup inexistente → False sin modificar nada."""
    gestor = BackupManager(tmp_path)
    assert gestor.restaurar(tmp_path / "no_existe.bak") is False


def test_restaurar_backup_ajeno_al_proyecto_devuelve_false(tmp_path):
    """T099: backup fuera del directorio del proyecto → False (mínimo privilegio)."""
    proyecto = tmp_path
    ajeno = tmp_path.parent / "ajeno.bak"
    ajeno.write_text("x", encoding="utf-8")
    gestor = BackupManager(proyecto)
    assert gestor.restaurar(ajeno) is False


def test_directorio_queda_dentro_del_proyecto(tmp_path):
    """T099: `.qa-backup/` vive dentro del proyecto (FR-045)."""
    gestor = BackupManager(tmp_path)
    assert str(gestor.directorio).startswith(str(tmp_path))
    assert gestor.directorio.name == ".qa-backup"