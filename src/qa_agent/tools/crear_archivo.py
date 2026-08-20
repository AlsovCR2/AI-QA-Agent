"""Herramienta `crear_archivo`: crea un archivo nuevo dentro del perímetro.

Acción destructiva (Phase 14, US-13 / FR-042): requiere autorización explícita
(FR-046 / SC-004 / UC-006), opera SOLO dentro de la `Allowlist` (FR-025 /
SC-022) y rechaza crear un archivo que ya existe o una ruta fuera del perímetro
SIN modificar nada (FR-042 / SC-024). Determinística (VI / SC-010).
"""

from __future__ import annotations

from typing import Any

from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
    resolver_archivo_en_perimetro,
)


class CrearArchivoHerramienta(Herramienta):
    """Crea un archivo nuevo dentro del perímetro autorizado."""

    id = "crear_archivo"
    nombre = "crear_archivo"
    descripcion = (
        "Crea un archivo nuevo dentro del proyecto con el contenido indicado. "
        "Requiere autorización explícita. Úsala cuando el usuario pida crear "
        "un archivo nuevo (p. ej. 'crea src/ajustes.py con contenido ...'). "
        "Rechaza sin modificar nada si el archivo ya existe o queda fuera de "
        "las rutas autorizadas."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto"},
            "archivo_relativo": {
                "type": "string",
                "description": "Ruta del archivo a crear, relativa a `ruta`",
            },
            "contenido": {
                "type": "string",
                "description": "Contenido a escribir en el archivo",
            },
        },
        "required": ["ruta", "archivo_relativo", "contenido"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "archivo": {"type": "string"},
            "creado": {"type": "boolean"},
            "existia": {"type": "boolean"},
        },
        "required": ["archivo", "creado", "existia"],
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
                error="No se especificó el contenido a escribir.",
            )

        if archivo.exists():
            # Rechaza crear un archivo existente sin modificar nada (FR-042).
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={
                    "archivo": archivo_relativo,
                    "creado": False,
                    "existia": True,
                },
                error=(
                    "El archivo ya existe; no se creó nada. "
                    "Usa editar_archivo para modificarlo (FR-042)."
                ),
            )

        try:
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(contenido, encoding="utf-8")
        except OSError as error_caught:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=f"No se pudo crear el archivo: {error_caught}",
            )

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "archivo": archivo_relativo,
                "creado": True,
                "existia": False,
            },
        )