"""Herramienta `leer_archivo`: lee el contenido real de un archivo del proyecto.

Permite al agente acceder al contenido completo de archivos concretos (código,
tests, documentación) dentro de la `Allowlist` (FR-025), presentándolo tal como
existe (FR-011). Es la base para respuestas profundas que expliquen qué hace
cada capa o qué pruebas cubre cada archivo, evitando respuestas superficiales
basadas solo en nombres de archivos.

Determinística (VI / SC-010) y sin LLM (III / SC-006). El contenido se
presenta tal cual (FR-011) y nunca se inventa (FR-019 / SC-002).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)


class LeerArchivoHerramienta(Herramienta):
    """Lee el contenido real de un archivo dentro del perímetro autorizado."""

    id = "leer_archivo"
    nombre = "leer_archivo"
    descripcion = (
        "Lee el contenido completo de un archivo concreto del proyecto "
        "(código, tests o documentación) y lo devuelve tal como existe. Úsala "
        "cuando el usuario pida entender qué hace una capa, qué pruebas cubre "
        "un archivo concreto o ver el código de un archivo específico."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto"},
            "archivo_relativo": {
                "type": "string",
                "description": "Ruta del archivo a leer, relativa a `ruta`",
            },
            "max_lineas": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "default": 200,
            },
        },
        "required": ["ruta", "archivo_relativo"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "archivo": {"type": "string"},
            "existe": {"type": "boolean"},
            "total_lineas": {"type": "integer"},
            "contenido": {"type": "string"},
            "truncado": {"type": "boolean"},
        },
        "required": ["archivo", "existe", "contenido"],
    }
    requiere_autorizacion = False

    def __init__(self, rutas_permitidas: list[str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        ruta_raw = parametros.get("ruta", ".")
        archivo_relativo = (parametros.get("archivo_relativo") or "").strip()
        try:
            max_lineas = int(parametros.get("max_lineas", 200))
        except (TypeError, ValueError):
            max_lineas = 200
        max_lineas = max(1, min(max_lineas, 1000))

        # Sin archivo → error explícito (FR-018), nunca leer un directorio
        # ni buscar un patrón vacío (FR-019, SC-002).
        if not archivo_relativo:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={},
                error="No se especificó el archivo a leer.",
            )

        # Mínimo privilegio: raíz dentro de la allowlist (FR-025 / SC-011).
        if self._allowlist is not None and not self._allowlist.contiene(ruta_raw):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=(
                    "La ruta solicitada queda fuera de las rutas autorizadas "
                    "(FR-025)."
                ),
            )

        ruta = Path(ruta_raw).expanduser().resolve()
        archivo = (ruta / archivo_relativo).resolve()
        # El archivo resuelto debe quedar dentro del perímetro autorizado
        # (defensa ante `..`/symlinks en `archivo_relativo`, FR-025).
        if self._allowlist is not None and not self._allowlist.contiene(str(archivo)):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=(
                    "El archivo queda fuera de las rutas autorizadas "
                    "(FR-025)."
                ),
            )

        if not archivo.exists() or archivo.is_dir():
            # No inventa contenido: reporta ausencia (FR-008/019).
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={
                    "archivo": archivo_relativo,
                    "existe": False,
                    "contenido": "",
                    "total_lineas": 0,
                    "truncado": False,
                },
            )

        try:
            with open(archivo, "r", encoding="utf-8", errors="replace") as f:
                lineas = f.readlines()
        except OSError as error:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=f"No se pudo leer el archivo: {error}",
            )

        total = len(lineas)
        truncado = total > max_lineas
        contenido = "".join(lineas[:max_lineas])
        if truncado:
            contenido += f"\n… [{total - max_lineas} líneas más] …\n"

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "archivo": archivo_relativo,
                "existe": True,
                "contenido": contenido,
                "total_lineas": total,
                "truncado": truncado,
            },
        )