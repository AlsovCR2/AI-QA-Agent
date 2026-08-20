"""Herramienta `eliminar_archivo`: elimina un archivo existente del perímetro.

Acción destructiva (Phase 14, US-13 / FR-044): requiere autorización explícita
(FR-046 / SC-004 / UC-006), opera SOLO dentro de la `Allowlist` (FR-025 /
SC-022), respalda el estado previo en `.qa-backup/` antes de eliminar
(FR-045 / SC-023) y rechaza eliminar un archivo inexistente o fuera del
perímetro SIN modificar nada (FR-044 / SC-024). Determinística (VI / SC-010).
"""

from __future__ import annotations

from typing import Any

from qa_agent.agent.backup import BackupManager
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
    resolver_archivo_en_perimetro,
)


class EliminarArchivoHerramienta(Herramienta):
    """Elimina un archivo existente dentro del perímetro autorizado."""

    id = "eliminar_archivo"
    nombre = "eliminar_archivo"
    descripcion = (
        "Elimina un archivo existente del proyecto. Requiere autorización "
        "explícita y respalda el estado previo en .qa-backup/ antes de "
        "eliminar. Úsala cuando el usuario pida eliminar o borrar un archivo "
        "(p. ej. 'elimina src/viejo.py'). Rechaza sin modificar nada si el "
        "archivo no existe o queda fuera de las rutas autorizadas."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto"},
            "archivo_relativo": {
                "type": "string",
                "description": "Ruta del archivo a eliminar, relativa a `ruta`",
            },
        },
        "required": ["ruta", "archivo_relativo"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "archivo": {"type": "string"},
            "eliminado": {"type": "boolean"},
            "backup": {"type": "string"},
        },
        "required": ["archivo", "eliminado", "backup"],
    }
    requiere_autorizacion = True

    def __init__(self, rutas_permitidas: list[str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        ruta_raw = parametros.get("ruta", ".")
        archivo_relativo = (parametros.get("archivo_relativo") or "").strip()

        archivo, error = resolver_archivo_en_perimetro(
            ruta_raw, archivo_relativo, self._allowlist
        )
        if error is not None:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=error,
            )

        if not archivo.exists() or archivo.is_dir():
            # Rechaza eliminar un archivo inexistente sin modificar nada (FR-044).
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={},
                error=(
                    "El archivo no existe (o es un directorio); no se eliminó "
                    "nada (FR-044)."
                ),
            )

        try:
            original = archivo.read_text(encoding="utf-8")
        except OSError as error_caught:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=f"No se pudo leer el archivo: {error_caught}",
            )

        try:
            backup = BackupManager(ruta_raw).respaldar(archivo_relativo, original)
            archivo.unlink()
        except OSError as error_caught:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=(
                    f"No se pudo eliminar el archivo: {error_caught}. "
                    "El respaldo previo queda disponible en .qa-backup/."
                ),
            )

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "archivo": archivo_relativo,
                "eliminado": True,
                "backup": str(backup),
            },
        )