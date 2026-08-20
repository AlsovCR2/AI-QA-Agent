"""Herramienta `editar_archivo`: modifica el contenido de un archivo existente.

Acción destructiva (Phase 14, US-13 / FR-043): requiere autorización explícita
(FR-046 / SC-004 / UC-006), opera SOLO dentro de la `Allowlist` (FR-025 /
SC-022), respalda el estado previo en `.qa-backup/` antes de modificar
(FR-045 / SC-023) y rechaza editar un archivo inexistente o fuera del perímetro
SIN modificar nada (FR-043 / SC-024). Determinística (VI / SC-010).
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


class EditarArchivoHerramienta(Herramienta):
    """Modifica el contenido de un archivo existente dentro del perímetro."""

    id = "editar_archivo"
    nombre = "editar_archivo"
    descripcion = (
        "Modifica el contenido de un archivo existente del proyecto con el "
        "contenido nuevo indicado. Requiere autorización explícita y respalda "
        "el estado previo en .qa-backup/ antes de modificar. Úsala cuando el "
        "usuario pida editar o modificar un archivo (p. ej. 'edita "
        "src/ajustes.py con contenido ...'). Rechaza sin modificar nada si el "
        "archivo no existe o queda fuera de las rutas autorizadas."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto"},
            "archivo_relativo": {
                "type": "string",
                "description": "Ruta del archivo a editar, relativa a `ruta`",
            },
            "contenido": {
                "type": "string",
                "description": "Contenido nuevo a escribir en el archivo",
            },
        },
        "required": ["ruta", "archivo_relativo", "contenido"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "archivo": {"type": "string"},
            "editado": {"type": "boolean"},
            "existia": {"type": "boolean"},
            "backup": {"type": "string"},
        },
        "required": ["archivo", "editado", "existia", "backup"],
    }
    requiere_autorizacion = True

    def __init__(self, rutas_permitidas: list[str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        ruta_raw = parametros.get("ruta", ".")
        archivo_relativo = (parametros.get("archivo_relativo") or "").strip()
        contenido = parametros.get("contenido")

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

        if not isinstance(contenido, str):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={},
                error="No se especificó el contenido nuevo.",
            )

        if not archivo.exists() or archivo.is_dir():
            # Rechaza editar un archivo inexistente sin modificar nada (FR-043).
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={},
                error=(
                    "El archivo no existe; no se editó nada. "
                    "Usa crear_archivo para crearlo (FR-043)."
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
            archivo.write_text(contenido, encoding="utf-8")
        except OSError as error_caught:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=(
                    f"No se pudo modificar el archivo: {error_caught}. "
                    "El respaldo previo queda disponible en .qa-backup/."
                ),
            )

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "archivo": archivo_relativo,
                "editado": True,
                "existia": True,
                "backup": str(backup),
            },
        )