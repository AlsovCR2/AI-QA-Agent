"""Herramienta `locate`: busca archivos/clases/funciones por patrón dentro de la `Allowlist` (FR-007/008).

Utiliza expresiones regulares para encontrar coincidencias en el contenido de los archivos.
Devuelve solo coincidencias reales (FR-008) y lista vacía si no hay coincidencias (sin fabricar).
Determinística, sin LLM (VI / SC-010).
"""

from __future__ import annotations

import re
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


# Mapeo de extensiones a tipos heurísticos (no exhaustivo, solo para guiar)
_EXTENSION_TIPO = {
    ".py": "funcion",
    ".pyw": "funcion",
    ".md": "documento",
    ".txt": "documento",
    ".json": "documento",
    ".yaml": "documento",
    ".yml": "documento",
    ".css": "estilo",
    ".js": "funcion",
    ".html": "documento",
}


class LocateHerramienta(Herramienta):
    """Busca patrones en el contenido de archivos de un proyecto."""

    id = "locate"
    nombre = "locate"
    descripcion = (
        "Busca un patrón en el contenido de los archivos de un proyecto, "
        "devuelve coincidencias con el nombre, tipo, línea y ruta relativa."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "patron": {"type": "string", "description": "Expresión regular a buscar"},
            "ruta": {"type": "string", "description": "Raíz del proyecto a buscar"},
            "tipo": {"type": "string", "enum": ["archivo", "clase", "funcion", "componente", "cualquiera"]},
        },
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "coincidencias": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string"},
                        "tipo": {"type": "string", "enum": ["archivo", "clase", "funcion", "componente", "cualquiera"]},
                        "linea": {"type": "integer"},
                        "ruta_relativa": {"type": "string"},
                    },
                },
            },
        },
        "required": ["coincidencias"],
    }
    requiere_autorizacion = False

    def __init__(self, rutas_permitidas: list[str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def _tipo_archivo(self, path: Path) -> str:
        """Heurística simple: tipo por extensión."""
        ext = path.suffix.lower()
        return _EXTENSION_TIPO.get(ext, "cualquiera")

    def _buscar_en_archivo(
        self, path: Path, raiz: Path, patron: str
    ) -> list[dict[str, Any]]:
        """Busca `patron` en el archivo y devuelve coincidencias con número de línea.

        `ruta_relativa` se calcula contra la raíz de la búsqueda (no contra el
        directorio padre del archivo): así el resultado indica la carpeta real
        (`BLL\\ClienteBL.cs` y no `ClienteBL.cs`), permitiendo que el agente
        localice y lea cada coincidencia (T114 / FR-008).
        """
        coincidencias = []
        if not patron:
            return coincidencias
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for numero_linea, linea in enumerate(f, start=1):
                    if re.search(patron, linea):
                        coincidencias.append(
                            {
                                "nombre": path.name,
                                "tipo": self._tipo_archivo(path),
                                "linea": numero_linea,
                                "ruta_relativa": str(path.relative_to(raiz)),
                            }
                        )
        except (OSError, UnicodeDecodeError):
            return []
        return coincidencias

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        patron = parametros.get("patron", "")
        ruta_raw = parametros.get("ruta", ".")
        tipo_busqueda = parametros.get("tipo", "cualquiera")

        # Sin patrón → no buscar un regex vacío (coincidiría con todo y
        # falsificaría resultados: FR-019, SC-002). Error explícito (FR-018).
        if not patron or not patron.strip():
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={"coincidencias": []},
                error="No se especificó un patrón de búsqueda.",
            )

        # Mínimo privilegio: allowlist (FR-025 / SC-011)
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
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={"coincidencias": []},
            )

        tipo_busqueda_normalizado = tipo_busqueda.lower().strip() if tipo_busqueda else "cualquiera"
        resultados: list[dict[str, Any]] = []

        for archivo in ruta.rglob("*"):
            if not archivo.is_file():
                continue
            # Saltar artefactos de build/dependencias/VCS (T094): no son código
            # fuente y saturan el resultado (UC-002).
            try:
                partes = archivo.relative_to(ruta).parts
            except ValueError:
                partes = ()
            if any(p in DIRECTORIOS_IGNORADOS for p in partes):
                continue
            # Filtrar por allowlist interna si existe
            if self._allowlist is not None and not self._allowlist.contiene(str(archivo)):
                continue
            # Filtrar por tipo si se especifica
            if tipo_busqueda_normalizado != "cualquiera":
                heuristico = self._tipo_archivo(archivo)
                # Aceptar si el heurístico coincide o es "cualquiera"
                if heuristico not in (tipo_busqueda_normalizado, "cualquiera"):
                    continue
            # Buscar patrón en el archivo (la ruta relativa se calcula contra la
            # raíz de la búsqueda, no contra el directorio padre del archivo).
            coincidencias = self._buscar_en_archivo(archivo, ruta, patron)
            resultados.extend(coincidencias)

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={"coincidencias": resultados},
        )