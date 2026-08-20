"""Configuración de logging con redacción de secretos (T025).

Garantiza que ningún secreto (tokens, API keys, credenciales) aparezca en los
logs (FR-021 / SC-008 / XI). Los logs estructurados incluyen campos estables y
deterministas (VIII / SC-010).
"""

from __future__ import annotations

import logging

from qa_agent.security.redactor import Redactor

_REDACTOR = Redactor()

_LOGGER = logging.getLogger("qa_agent")

_FIELDS = ("level", "logger", "message")


class RedactorFormatter(logging.Formatter):
    """Formatter que redacta secretos en cada registro."""

    def __init__(self, fmt: str | None = None) -> None:
        # Formato estructurado determinista (campos estables, SC-010).
        fmt = fmt or "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        # Redacta el mensaje ya formateado y evita que `super().format`
        # vuelva a aplicar el `%` de args (T025 / SC-008).
        mensaje = _REDACTOR.redactar(record.getMessage())
        record.msg = mensaje
        record.args = ()
        return super().format(record)


def configurar_logging(
    nivel: int = logging.INFO,
    handler: logging.Handler | None = None,
) -> logging.Logger:
    """Configura el logger de `qa_agent` con redacción de secretos."""
    if handler is None:
        handler = logging.StreamHandler()
    handler.setFormatter(RedactorFormatter())
    _LOGGER.setLevel(nivel)
    _LOGGER.addHandler(handler)
    _LOGGER.propagate = False
    return _LOGGER


def get_logger() -> logging.Logger:
    """Devuelve el logger de `qa_agent` (configurado o por defecto)."""
    if not _LOGGER.handlers:
        configurar_logging()
    return _LOGGER