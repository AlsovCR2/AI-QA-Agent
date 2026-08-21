"""Herramienta `explore`: explora la estructura del proyecto (UC-002).

Recorre el árbol de directorios con `profundidad_max`, respetando la
`Allowlist` (FR-025) y reportando únicamente información real existente
(FR-008 / SC-003). Determinística, sin LLM (VI / SC-010).
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
from qa_agent.tools.exclusion_policy import (
    NOMBRES_DIRECTORIO_EXCLUIDOS as DIRECTORIOS_IGNORADOS,
)

# Ruido que no aporta información de estructura: artefactos de build,
# dependencias y control de versiones. Suelen dominar el árbol y saturan la
# observación del LLM (UC-002). Se excluyen en cualquier nivel del árbol.
# Centralizado en `exclusion_policy.py` (I07); `DIRECTORIOS_IGNORADOS` se
# re-exporta aquí por compatibilidad (lo reutilizan `locate.py`/`search.py`).


class ExploreHerramienta(Herramienta):
    """Explora la estructura real de un proyecto."""

    id = "explore"
    nombre = "explore"
    descripcion = (
        "Explora la estructura del proyecto (directorios y archivos). Úsala "
        "cuando el usuario pida ver la estructura general, organización o "
        "contenido del proyecto."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto a explorar"},
            "profundidad_max": {"type": "integer", "minimum": 1, "maximum": 8},
        },
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "existe": {"type": "boolean"},
            "accesible": {"type": "boolean"},
            "elementos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string"},
                        "tipo": {"type": "string", "enum": ["archivo", "directorio"]},
                        "ruta_relativa": {"type": "string"},
                    },
                },
            },
        },
        "required": ["ruta", "existe", "accesible", "elementos"],
    }
    requiere_autorizacion = False

    def __init__(self, rutas_permitidas: list[Path | str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self.rutas_permitidas = [str(p) for p in rutas_permitidas]
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def _elemento(
        self, entrada: Path, raiz: Path, profundidad: int
    ) -> dict[str, Any]:
        return {
            "nombre": entrada.name,
            "tipo": "directorio" if entrada.is_dir() else "archivo",
            "ruta_relativa": str(entrada.relative_to(raiz)),
            "profundidad": profundidad,
        }

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        ruta_raw = parametros.get("ruta", ".")
        profundidad_max = int(parametros.get("profundidad_max", 1))
        profundidad_max = max(1, min(profundidad_max, 8))

        # Mínimo privilegio: rechaza rutas fuera del perímetro (FR-025 / SC-011).
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
        if not ruta.exists():
            # No inventa estructura: reporta ausencia (FR-008 / UC-002).
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={
                    "ruta": str(ruta),
                    "existe": False,
                    "accesible": False,
                    "elementos": [],
                },
            )

        elementos: list[dict[str, Any]] = []
        try:
            # Profundidad 1: hijos directos. Profundidad n: hasta n niveles.
            for hijo in ruta.iterdir():
                if hijo.name in DIRECTORIOS_IGNORADOS:
                    continue
                elementos.append(self._elemento(hijo, ruta, 1))
                if profundidad_max > 1 and hijo.is_dir():
                    self._recorrer(hijo, ruta, 2, profundidad_max, elementos)
        except OSError as error:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=f"No se pudo acceder a la ruta: {error}",
            )

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "ruta": str(ruta),
                "existe": True,
                "accesible": True,
                "elementos": elementos,
            },
        )

    def _recorrer(
        self,
        directorio: Path,
        raiz: Path,
        profundidad: int,
        profundidad_max: int,
        elementos: list[dict[str, Any]],
    ) -> None:
        """Recorre subdirectorios hasta `profundidad_max`."""
        for hijo in directorio.iterdir():
            if hijo.name in DIRECTORIOS_IGNORADOS:
                continue
            elementos.append(self._elemento(hijo, raiz, profundidad))
            if profundidad < profundidad_max and hijo.is_dir():
                self._recorrer(
                    hijo, raiz, profundidad + 1, profundidad_max, elementos
                )