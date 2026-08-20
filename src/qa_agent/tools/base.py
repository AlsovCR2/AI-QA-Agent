"""Contrato base de herramienta.

Define `Herramienta` (clase base para todas las capacidades ejecutables) y
`ResultadoDeHerramienta` (salida validable, fuente de verdad para el
razonamiento del agente). Alineado con el data-model (entidades #2 y #3) y el
contrato general de herramienta (`contracts/tool-contracts.md`).

La herramienta NO contiene lógica de agente ni selecciona otras herramientas
(principio I). Es pura, determinística y no depende del LLM (principios III/VI).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from qa_agent.tools.allowlist import Allowlist

# Esquemas de entrada/salida se expresan como JSON Schema (dict).


class EstadoResultado(str, Enum):
    """Estado de una ejecución de herramienta (data-model #3)."""

    EXITO = "exito"
    ERROR = "error"
    INVALIDO = "invalido"


@dataclass
class ResultadoDeHerramienta:
    """Salida validable de una herramienta (data-model, entidad #3)."""

    herramienta_id: str
    estado: EstadoResultado
    datos: dict[str, Any]
    es_valido: bool = False
    error: str | None = None
    momento: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Herramienta(ABC):
    """Contrato base de herramienta (data-model, entidad #2)."""

    id: str
    nombre: str
    descripcion: str
    esquema_entrada: dict[str, Any]
    esquema_salida: dict[str, Any]
    requiere_autorizacion: bool = False
    rutas_permitidas: list[str] = []

    @abstractmethod
    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        """Ejecuta la herramienta de forma determinística.

        Opera únicamente sobre rutas de su `rutas_permitidas` (mínimo
        privilegio, FR-025). El resultado se valida contra `esquema_salida`
        antes de usarse (FR-005, VII).
        """

    def validar_resultado(self, resultado: ResultadoDeHerramienta) -> bool:
        """Valida un resultado contra el esquema de salida (FR-005).

        Delega en la función pura `validar_resultado` (T006).
        """
        return validar_resultado_esquema(resultado.datos, self.esquema_salida)


def _tipo_cumple(valor: Any, tipo: str) -> bool:
    """Comprueba si un valor cumple un tipo JSON Schema (determinístico)."""
    if tipo == "string":
        return isinstance(valor, str)
    if tipo == "integer":
        return isinstance(valor, int) and not isinstance(valor, bool)
    if tipo == "number":
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)
    if tipo == "boolean":
        return isinstance(valor, bool)
    if tipo == "array":
        return isinstance(valor, list)
    if tipo == "object":
        return isinstance(valor, dict)
    return True  # tipo desconocido: no imponer restricción adicional


def _esquema_cumple(valor: Any, esquema: dict[str, Any]) -> bool:
    """Valida una instancia contra un (sub)esquema JSON determinísticamente.

    Soporta la forma usada por los contratos: `type`, `properties`,
    `required`, `items`, `enum`, `minimum`, `maximum`. Devuelve `False` ante
    estructuras inválidas sin lanzar excepciones (FR-005, VII, SC-010).
    """
    if not isinstance(esquema, dict):
        return False

    tipo = esquema.get("type")
    if tipo is not None and not _tipo_cumple(valor, tipo):
        return False

    if "enum" in esquema and valor not in esquema["enum"]:
        return False

    if tipo == "object" and isinstance(valor, dict):
        for prop in esquema.get("required", []):
            if prop not in valor:
                return False
        for prop, subesquema in esquema.get("properties", {}).items():
            if prop in valor and not _esquema_cumple(valor[prop], subesquema):
                return False

    if tipo == "array" and isinstance(valor, list):
        items = esquema.get("items")
        if isinstance(items, dict):
            if not all(_esquema_cumple(item, items) for item in valor):
                return False

    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if "minimum" in esquema and valor < esquema["minimum"]:
            return False
        if "maximum" in esquema and valor > esquema["maximum"]:
            return False

    return True


def validar_resultado_esquema(
    datos: Any, esquema_salida: dict[str, Any]
) -> bool:
    """Valida datos contra el esquema de salida de una herramienta (T006).

    Pura y determinística (no LLM, VI / SC-010). Devuelve `True` solo si el
    resultado cumple el esquema; `False` ante tipo/estructura inválida sin
    lanzar excepción de validación de esquema no controlada (FR-005).
    """
    try:
        return _esquema_cumple(datos, esquema_salida)
    except (TypeError, ValueError, KeyError):
        return False


def validar_resultado(
    herramienta: Herramienta, resultado: ResultadoDeHerramienta
) -> bool:
    """Validación de contrato de un resultado frente a su esquema de salida.

    Conveniencia que combina `ResultadoDeHerramienta.es_valido` (estado exito)
    y la validación estructural del esquema (T006, FR-005, VII).
    """
    if not isinstance(resultado, ResultadoDeHerramienta):
        return False
    if resultado.estado != EstadoResultado.EXITO:
        return False
    return validar_resultado_esquema(resultado.datos, herramienta.esquema_salida)


def resolver_archivo_en_perimetro(
    ruta_raw: str,
    archivo_relativo: str,
    allowlist: Allowlist | None,
) -> tuple[Path | None, str | None]:
    """Resuelve `archivo_relativo` bajo la raíz `ruta_raw` verificando el perímetro.

    Seguridad de las herramientas destructivas (Phase 14, FR-025/SC-022):
    - `archivo_relativo` vacío → error explícito (nunca operar sobre la raíz).
    - Raíz o archivo resuelto fuera de la allowlist (incl. `..`, symlinks o
      path traversal) → error, sin ejecutar nada.
    Devuelve `(archivo_resuelto, None)` o `(None, mensaje_error)`.
    """
    if not archivo_relativo or not archivo_relativo.strip():
        return None, "No se especificó el archivo objetivo."
    if allowlist is not None and not allowlist.contiene(ruta_raw):
        return None, "La ruta solicitada queda fuera de las rutas autorizadas (FR-025)."
    ruta = Path(ruta_raw).expanduser().resolve()
    archivo = (ruta / archivo_relativo).resolve()
    if allowlist is not None and not allowlist.contiene(str(archivo)):
        return (
            None,
            "El archivo objetivo queda fuera de las rutas autorizadas (FR-025).",
        )
    return archivo, None