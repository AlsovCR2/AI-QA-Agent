"""`BackupManager`: respaldo del estado previo antes de modificar/eliminar.

Phase 14 / FR-045 / SC-023: antes de `editar_archivo` o `eliminar_archivo` se
copia el contenido original a `.qa-backup/` dentro del proyecto (preservando la
ruta relativa bajo una marca de tiempo) y se expone `restaurar(backup)` para
revertir. Determinístico y sin LLM (VI / SC-010).
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


class BackupManager:
    """Respalda y restaura archivos del proyecto dentro de `.qa-backup/`."""

    def __init__(self, proyecto: Path | str) -> None:
        self._proyecto = Path(proyecto).resolve()
        self._directorio = self._proyecto / ".qa-backup"

    @property
    def proyecto(self) -> Path:
        """Raíz del proyecto que se respalda."""
        return self._proyecto

    @property
    def directorio(self) -> Path:
        """Directorio de backups (`.qa-backup/` bajo el proyecto)."""
        return self._directorio

    def _marca(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")

    def respaldar(self, ruta_relativa: str, contenido: str) -> Path:
        """Copia `contenido` (estado original) a `.qa-backup/` y devuelve el backup.

        El backup preserva la ruta relativa bajo una marca de tiempo:
        `.qa-backup/<marca>/<ruta_relativa>`.
        """
        destino = self._directorio / self._marca() / ruta_relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
        return destino

    def restaurar(self, backup: Path | str) -> bool:
        """Restaura el contenido original de `backup` a su ubicación del proyecto.

        Devuelve `False` (sin modificar nada) si el backup no existe o no
        pertenece al directorio de backups de este proyecto.
        """
        backup_path = Path(backup)
        if not backup_path.is_file():
            return False
        try:
            relativo = backup_path.relative_to(self._directorio)
        except ValueError:
            return False
        partes = relativo.parts
        if len(partes) < 2:
            return False
        ruta_relativa = str(Path(*partes[1:]))
        destino = (self._proyecto / ruta_relativa).resolve()
        try:
            destino.relative_to(self._proyecto)
        except ValueError:
            return False
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, destino)
        return True