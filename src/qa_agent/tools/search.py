"""Herramienta `search`: busca patrones regex en el código dentro de la `Allowlist`
y devuelve fragmentos reales en contexto (FR-009/010/011).

Presenta el contenido de código tal como existe, sin alterarlo (FR-011).
Determinística (VI / SC-010) y respeta la `Allowlist` (FR-025).
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


class SearchHerramienta(Herramienta):
    """Busca patrones regex en el código y devuelve ocurrencias con contexto."""

    id = "search"
    nombre = "search"
    descripcion = (
        "Busca un patrón de expresión regular en el contenido de los archivos "
        "del proyecto y devuelve las ocurrencias con su contexto (líneas "
        "antes/después). Úsala cuando el usuario quiera encontrar código "
        "específico o patrones en el código fuente."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "patron_regex": {"type": "string", "description": "Expresión regular a buscar"},
            "ruta": {"type": "string", "description": "Raíz del proyecto a buscar"},
            "contexto_lineas": {"type": "integer", "minimum": 0, "maximum": 20, "default": 3},
            "max_ocurrencias": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10000,
                "default": 200,
                "description": "Límite de ocurrencias devueltas (evita volcados gigantes que saturan la observación del LLM)",
            },
        },
        "required": ["patron_regex", "ruta"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "ocurrencias": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ruta_relativa": {"type": "string"},
                        "linea": {"type": "integer"},
                        "contexto": {"type": "string"},
                    },
                    "required": ["ruta_relativa", "linea", "contexto"],
                },
            },
            "nota": {"type": "string", "description": "Aviso de truncado cuando se alcanza max_ocurrencias"},
        },
        "required": ["ocurrencias"],
    }
    requiere_autorizacion = False

    def __init__(self, rutas_permitidas: list[str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def _leer_archivo(self, path: Path) -> list[str]:
        """Lee el archivo y devuelve líneas (vacío si error)."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.readlines()
        except (OSError, UnicodeDecodeError):
            return []

    def _obtener_contexto(
        self, lineas: list[str], indice: int, contexto_lineas: int
    ) -> str:
        """Obtiene el contexto alrededor de una línea."""
        inicio = max(0, indice - contexto_lineas)
        fin = min(len(lineas), indice + contexto_lineas + 1)
        return "".join(lineas[inicio:fin])

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        patron_regex = parametros.get("patron_regex", "")
        ruta_raw = parametros.get("ruta", ".")
        contexto_lineas = int(parametros.get("contexto_lineas", 3))
        contexto_lineas = max(0, min(contexto_lineas, 20))
        try:
            max_ocurrencias = int(parametros.get("max_ocurrencias", 200))
        except (TypeError, ValueError):
            max_ocurrencias = 200
        max_ocurrencias = max(1, min(max_ocurrencias, 10000))

        # Sin patrón → no buscar un regex vacío (coincidiría con todo y
        # falsificaría resultados: FR-019, SC-002). Error explícito (FR-018).
        if not patron_regex or not patron_regex.strip():
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={"ocurrencias": []},
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

        # Validar regex antes de buscar
        try:
            regex_compilado = re.compile(patron_regex)
        except re.error as e:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={"ocurrencias": []},
                error=f"Patrón regex inválido: {e}",
            )

        ruta = Path(ruta_raw).expanduser().resolve()
        if not ruta.exists():
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={"ocurrencias": []},
            )

        ocurrencias: list[dict[str, Any]] = []
        truncado = False

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

            lineas = self._leer_archivo(archivo)
            if not lineas:
                continue

            for i, linea in enumerate(lineas):
                if not regex_compilado.search(linea):
                    continue
                contexto = self._obtener_contexto(lineas, i, contexto_lineas)
                ocurrencias.append(
                    {
                        "ruta_relativa": str(archivo.relative_to(ruta)),
                        "linea": i + 1,
                        "contexto": contexto.rstrip("\n"),
                    }
                )
                # Límite de ocurrencias: evita volcados gigantes que saturan
                # la observación del LLM (T108 / FR-019, honestidad: se avisa
                # del truncado, nunca se presenta como resultado completo).
                if len(ocurrencias) >= max_ocurrencias:
                    truncado = True
                    break
            if truncado:
                break

        datos: dict[str, Any] = {"ocurrencias": ocurrencias}
        if truncado:
            datos["nota"] = (
                f"Se limitó la búsqueda a {max_ocurrencias} ocurrencias. "
                "Refina el patrón o acota la búsqueda para ver el resto."
            )

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos=datos,
        )