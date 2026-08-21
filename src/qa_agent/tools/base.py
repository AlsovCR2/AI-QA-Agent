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
import re
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


def _explicar(motivos: list[str] | None, mensaje: str) -> bool:
    """Anota un motivo de rechazo (si se está recogiendo) y devuelve `False`.

    Existe para que el validador pueda decir POR QUÉ rechaza sin duplicar la
    lógica en dos funciones (T212 / FR-127): cuando `motivos` es `None` el coste
    es una comparación, así que la ruta rápida —la que se ejecuta en cada paso
    del bucle— no paga nada por la capacidad de explicar.
    """
    if motivos is not None:
        motivos.append(mensaje)
    return False


def _esquema_cumple(
    valor: Any,
    esquema: dict[str, Any],
    motivos: list[str] | None = None,
    ruta: str = "$",
) -> bool:
    """Valida una instancia contra un (sub)esquema JSON determinísticamente.

    Soporta el subconjunto que usan los contratos del proyecto —`type`,
    `properties`, `required`, `items`, `enum`, `minimum`, `maximum`— ampliado
    en T212 con `additionalProperties`, `pattern`, `minLength`/`maxLength`,
    `minItems`/`maxItems` y los combinadores `oneOf`/`anyOf`/`allOf`
    (FR-127).

    La ampliación es estrictamente conservadora: una palabra clave nueva solo
    puede rechazar algo si el esquema la declara. Ningún esquema existente las
    declara, así que el veredicto sobre los 11 esquemas actuales y los 92 casos
    de la suite de compatibilidad de ADR-002 no cambia — lo verifica
    `tests/contract/test_schema_validator_compat.py`.

    Devuelve `False` ante estructuras inválidas sin lanzar (FR-005, VII, SC-010).
    """
    if not isinstance(esquema, dict):
        return _explicar(motivos, f"{ruta}: el esquema no es un objeto")

    # Combinadores. Se evalúan antes que el resto porque delimitan qué
    # subesquema aplica; sus ramas nunca contaminan la lista de motivos del
    # nivel superior (una rama fallida es información esperada, no un error).
    if "allOf" in esquema:
        for i, sub in enumerate(esquema["allOf"] or []):
            if not _esquema_cumple(valor, sub, motivos, f"{ruta}.allOf[{i}]"):
                return False
    if "anyOf" in esquema:
        ramas = esquema["anyOf"] or []
        if not any(_esquema_cumple(valor, sub, None, ruta) for sub in ramas):
            return _explicar(motivos, f"{ruta}: no cumple ninguna rama de anyOf")
    if "oneOf" in esquema:
        ramas = esquema["oneOf"] or []
        cumplidas = sum(
            1 for sub in ramas if _esquema_cumple(valor, sub, None, ruta)
        )
        if cumplidas != 1:
            return _explicar(
                motivos,
                f"{ruta}: oneOf exige exactamente una rama válida, cumple {cumplidas}",
            )

    tipo = esquema.get("type")
    if tipo is not None and not _tipo_cumple(valor, tipo):
        return _explicar(
            motivos, f"{ruta}: se esperaba tipo '{tipo}' y llegó {type(valor).__name__}"
        )

    if "enum" in esquema and valor not in esquema["enum"]:
        return _explicar(motivos, f"{ruta}: valor fuera del enum declarado")

    if isinstance(valor, str):
        if "minLength" in esquema and len(valor) < esquema["minLength"]:
            return _explicar(motivos, f"{ruta}: más corto que minLength")
        if "maxLength" in esquema and len(valor) > esquema["maxLength"]:
            return _explicar(motivos, f"{ruta}: más largo que maxLength")
        patron = esquema.get("pattern")
        if patron is not None:
            try:
                if re.search(patron, valor) is None:
                    return _explicar(motivos, f"{ruta}: no casa con el patrón")
            except re.error:
                # Un patrón mal formado es un defecto del esquema, no del dato:
                # se rechaza el esquema, nunca se acepta el dato por descarte.
                return _explicar(motivos, f"{ruta}: patrón inválido en el esquema")

    if tipo == "object" and isinstance(valor, dict):
        propiedades = esquema.get("properties", {})
        for prop in esquema.get("required", []):
            if prop not in valor:
                return _explicar(motivos, f"{ruta}: falta la propiedad '{prop}'")
        for prop, subesquema in propiedades.items():
            if prop in valor and not _esquema_cumple(
                valor[prop], subesquema, motivos, f"{ruta}.{prop}"
            ):
                return False
        adicionales = esquema.get("additionalProperties")
        if adicionales is False:
            sobrantes = sorted(set(valor) - set(propiedades))
            if sobrantes:
                return _explicar(
                    motivos, f"{ruta}: propiedades no declaradas: {sobrantes}"
                )
        elif isinstance(adicionales, dict):
            for prop in sorted(set(valor) - set(propiedades)):
                if not _esquema_cumple(
                    valor[prop], adicionales, motivos, f"{ruta}.{prop}"
                ):
                    return False

    if tipo == "array" and isinstance(valor, list):
        if "minItems" in esquema and len(valor) < esquema["minItems"]:
            return _explicar(motivos, f"{ruta}: menos elementos que minItems")
        if "maxItems" in esquema and len(valor) > esquema["maxItems"]:
            return _explicar(motivos, f"{ruta}: más elementos que maxItems")
        items = esquema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(valor):
                if not _esquema_cumple(item, items, motivos, f"{ruta}[{i}]"):
                    return False

    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if "minimum" in esquema and valor < esquema["minimum"]:
            return _explicar(motivos, f"{ruta}: por debajo del mínimo")
        if "maximum" in esquema and valor > esquema["maximum"]:
            return _explicar(motivos, f"{ruta}: por encima del máximo")

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
    except (TypeError, ValueError, KeyError, AttributeError):
        return False


def explicar_incumplimiento(
    datos: Any, esquema: dict[str, Any]
) -> list[str]:
    """Motivos por los que `datos` no cumple `esquema`; vacío si cumple.

    Complementa a `validar_resultado_esquema` (T212 / FR-127): el veredicto
    booleano sigue siendo el camino rápido del bucle, y esta función es la que
    convierte un rechazo en un mensaje accionable para el usuario o para el
    diagnóstico (principio IX). Nunca lanza.
    """
    motivos: list[str] = []
    try:
        if _esquema_cumple(datos, esquema, motivos):
            return []
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        return [f"$: esquema o datos no procesables ({error})"]
    return motivos


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