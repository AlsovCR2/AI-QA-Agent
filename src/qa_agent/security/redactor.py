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
    # Tokens de GitHub: ghp_/gho_/ghs_ (clásicos) y github_pat_ (fine-grained)
    re.compile(r"\b(?:ghp|gho|ghs)_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    # Claves de acceso AWS: AKIA + 16 alfanuméricos en mayúscula
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # JWT: tres segmentos base64url separados por puntos; el header JSON
    # ("{...") codificado en base64 siempre empieza por "eyJ".
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    # Bloques de clave PRIVADA en formato PEM (RSA/EC/DSA/OpenSSH/genérica).
    # Las claves PÚBLICAS ("PUBLIC KEY") no son secretas y no coinciden.
    re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----"
        r"[\s\S]+?"
        r"-----END (?:RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----"
    ),
    # Claves de API de Google (Maps, Cloud, Firebase): AIza + 35 caracteres.
    # Longitud fija: no coincide con identificadores que empiecen por "AIza".
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    # Secretos de cliente OAuth de Google (formato moderno).
    re.compile(r"\bGOCSPX-[A-Za-z0-9_\-]{20,}\b"),
    # Secretos de cliente de Entra ID (Azure AD). El formato documentado lleva
    # "8Q~" como marca fija tras los primeros caracteres; anclarse a ella evita
    # que cualquier cadena con "~" se redacte por error.
    re.compile(r"\b[A-Za-z0-9_~.\-]{2,4}8Q~[A-Za-z0-9_~.\-]{30,}\b"),
    # Claves de cuenta de Azure Storage embebidas en cadenas de conexión.
    re.compile(r"\bAccountKey\s*=\s*[A-Za-z0-9+/=]{40,}", re.IGNORECASE),
    # Firma de un SAS de Azure: el parámetro `sig=` es el secreto del token.
    re.compile(r"\bsig=[A-Za-z0-9%+/=]{20,}", re.IGNORECASE),
    # Tokens npm/registro: npm_ + 36 alfanuméricos
    re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    # Credenciales embebidas en cadenas de conexión: esquema://usuario:contraseña@
    # Solo se sustituye "usuario:contraseña" (lookbehind "://", lookahead "@";
    # el propio "@" no forma parte de la coincidencia y se conserva).
    re.compile(r"(?<=://)[^\s:@/]{1,100}:[^\s@/]{1,200}(?=@)"),
    # Asignaciones genéricas password=/secret=/token= (clave exacta, no
    # identificadores compuestos como "reset_token"). El lookahead negativo
    # evita volver a consumir un valor ya redactado por un patrón anterior
    # (idempotencia dentro de la misma pasada, p. ej. "token=***").
    re.compile(
        r"\b(?:password|secret|token)\s*=\s*(?!\*\*\*(?:[\s'\"]|$))"
        r"['\"]?[^\s'\"&]+['\"]?",
        re.IGNORECASE,
    ),
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
