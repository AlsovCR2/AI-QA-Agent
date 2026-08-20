"""`Redactor`: detección y redacción de secretos (FR-021 / XI / SC-008).

Aplica de forma transversal a respuestas, historial visible y logs. Sustituye
secretos detectados por un valor de redacción (`***`) en strings y recursivamente
dentro de diccionarios y listas. Es idempotente: no altera texto sin secretos.
"""

from __future__ import annotations

import re
from dataclasses import fields, is_dataclass, replace
from typing import Any

_VALOR = "***"

_PATRONES: list[re.Pattern[str]] = [
    # Tokens OpenAI/DeepSeek: sk-...
    re.compile(r"\bsk-[A-Za-z0-9_\-\.]{8,}\b"),
    # Bearer tokens (JWT o arbitrarios)
    re.compile(r"\bBearer\s+[A-Za-z0-9\-_\.]{8,}\b", re.IGNORECASE),
    # api_key=..., api-key=..., apikey=...
    re.compile(r"\bapi[_-]?key\s*=\s*['\"]?[^\s'\"&]+['\"]?", re.IGNORECASE),
    # Claves tipo ASS de Anthropic y genéricas "ass?:[a-z0-9]{8,}"
    re.compile(r"\bass?:[a-z0-9]{8,}\b", re.IGNORECASE),
]


class Redactor:
    """Redacta secretos detectados en strings, dicts y listas."""

    def __init__(self, patrones: list[re.Pattern[str]] | None = None) -> None:
        self._patrones = list(patrones) if patrones is not None else _PATRONES

    @property
    def patrones(self) -> list[re.Pattern[str]]:
        """Patrones de detección (visibles para tests)."""
        return self._patrones

    def _redactar_str(self, texto: str) -> str:
        # Orden: primero sustituir la clave de API, luego el valor puede
        # colisionar. Aplicamos cada patrón siendo idempotente sobre "***".
        resultado = texto
        for patron in self._patrones:
            resultado = patron.sub(_VALOR, resultado)
        return resultado

    def redactar(self, entrada: Any) -> Any:
        """Redacta secretos de forma recursiva manteniendo el tipo de dato."""
        if isinstance(entrada, str):
            return self._redactar_str(entrada)
        if is_dataclass(entrada) and not isinstance(entrada, type):
            valores = {
                campo.name: self.redactar(getattr(entrada, campo.name))
                for campo in fields(entrada)
            }
            return replace(entrada, **valores)
        if isinstance(entrada, dict):
            return {k: self.redactar(v) for k, v in entrada.items()}
        if isinstance(entrada, list):
            return [self.redactar(v) for v in entrada]
        if isinstance(entrada, tuple):
            return tuple(self.redactar(v) for v in entrada)
        return entrada
