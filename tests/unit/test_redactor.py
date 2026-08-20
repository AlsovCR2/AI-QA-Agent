"""Tests del `Redactor` de secretos (T046, US7: FR-021 / SC-008 / XI).

Verifica que los secretos (tokens, API keys, credenciales) se detectan y
sustituyen por `***` en strings y estructuras anidadas, que no se altera el
texto legítimo sin secretos (sin falsos positivos) y que ningún secreto
aparece en respuesta, historial visible ni logs (SC-008).
"""

from __future__ import annotations

import logging
import re

import pytest

from qa_agent.agent.loop import Agent
from qa_agent.agent.response import EstadoAccion
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.logging_config import RedactorFormatter, get_logger
from qa_agent.security.redactor import Redactor
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)

_SECRETO_SK = "sk-abcdefghij123456"
_SECRETO_BEARER = "Bearer eyJhbGciOiJIUzI1NiJ9.ejemplo.abc12345"
_SECRETO_API_KEY = "api_key=clave_secreta_123"
_SECRETO_ASS = "ass:abcdef12345678"


# -- Strings --------------------------------------------------------------


def test_redacta_token_sk_en_string():
    redactor = Redactor()
    assert redactor.redactar(f"usa {_SECRETO_SK} aquí") == "usa *** aquí"


def test_redacta_bearer_token():
    redactor = Redactor()
    assert _SECRETO_BEARER not in redactor.redactar(f"Authorization: {_SECRETO_BEARER}")


def test_redacta_api_key_con_igual():
    redactor = Redactor()
    assert redactor.redactar(f"config: {_SECRETO_API_KEY}") == "config: ***"


def test_redacta_api_key_con_guiones():
    redactor = Redactor()
    assert redactor.redactar("apikey=abc1234567890") == "***"


def test_redacta_clave_tipo_ass():
    redactor = Redactor()
    assert redactor.redactar(f"clave: {_SECRETO_ASS}") == "clave: ***"


def test_no_altera_texto_sin_secretos():
    """Código normal sin secretos no se modifica (sin falsos positivos)."""
    redactor = Redactor()
    texto = (
        "def config():\n"
        "    return {'clave': 'valor', 'modo': 'passthrough'}\n"
        "\n"
        "class Configuracion:\n"
        "    pass\n"
    )
    assert redactor.redactar(texto) == texto


def test_no_altera_palabras_comunes():
    """'class', 'pass', 'as', 'ass', 'ask' no son secretos."""
    redactor = Redactor()
    texto = "class As: as=1; pass  # password y ask no son secretos"
    assert redactor.redactar(texto) == texto


def test_es_idempotente():
    redactor = Redactor()
    assert redactor.redactar("***") == "***"


# -- Estructuras anidadas -------------------------------------------------


def test_redacta_en_dict_y_listas_anidadas():
    redactor = Redactor()
    entrada = {
        "token": _SECRETO_SK,
        "lista": [_SECRETO_ASS, "valor_limpio"],
        "anidado": {"api": {"llave": f"apikey={_SECRETO_ASS}"}},
    }
    salida = redactor.redactar(entrada)
    assert salida["token"] == "***"
    assert salida["lista"][0] == "***"
    assert salida["lista"][1] == "valor_limpio"
    assert salida["anidado"]["api"]["llave"] == "***"


def test_redacta_en_tuple_manteniendo_tipo():
    redactor = Redactor()
    salida = redactor.redactar((_SECRETO_SK, "limpio"))
    assert isinstance(salida, tuple)
    assert salida == ("***", "limpio")


# -- SC-008: secretos ausentes en respuesta, historial y logs --------------


class _HerramientaConSecreto(Herramienta):
    id = "explore"
    nombre = "explore"
    descripcion = "Explora la estructura del proyecto."
    esquema_entrada = {"type": "object", "properties": {}}
    esquema_salida = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "existe": {"type": "boolean"},
            "accesible": {"type": "boolean"},
            "elementos": {"type": "array"},
        },
        "required": ["ruta", "existe", "accesible", "elementos"],
    }
    requiere_autorizacion = False
    rutas_permitidas: list[str] = []

    def ejecutar(self, parametros: dict) -> ResultadoDeHerramienta:
        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "ruta": ".",
                "existe": True,
                "accesible": True,
                "elementos": [
                    {"nombre": "config.json", "contenido": f"token={_SECRETO_SK}"}
                ],
            },
        )


def test_secretos_no_aparecen_en_respuesta_ni_historial(redactor):
    """El secreto en la salida de una herramienta no aparece en respuesta/historial.

    SC-008: el bucle redacta antes de exponer respuesta e historial visible.
    """
    llm = FakeLLM(
        seleccion={"ninguna": True},
        por_defecto={
            "texto": f"Encontré el archivo con token {_SECRETO_SK}.",
            "confianza": "alta",
        },
    )
    agente = Agent(
        backend=llm,
        herramientas=[_HerramientaConSecreto()],
        allowlist=None,
        redactor=redactor,
    )
    respuesta = agente.atender("explora la estructura del proyecto")

    assert _SECRETO_SK not in respuesta.texto
    assert _SECRETO_SK not in str(respuesta.acciones)
    accion = [a for a in respuesta.acciones if a.herramienta_id == "explore"][0]
    assert accion.estado == EstadoAccion.EXITO
    assert "token=***" in str(accion.salida)


def test_secretos_no_aparecen_en_logs():
    """El formatter de logging redacta secretos (SC-008, T025)."""
    logger = logging.getLogger(f"qa_agent.test_redactor_{id(object())}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(RedactorFormatter())
    logger.addHandler(handler)

    registro: list[str] = []
    original_emit = handler.emit

    def emit_redirigido(record: logging.LogRecord) -> None:
        registro.append(handler.format(record))
        original_emit(record)

    handler.emit = emit_redirigido

    try:
        logger.info("token=%s detectado", _SECRETO_SK)
        logger.info("clave api_key=%s", _SECRETO_ASS)
    finally:
        logger.removeHandler(handler)

    assert registro, "debería haberse registrado al menos un mensaje"
    # Ningún secreto aparece en ningún log (SC-008)
    for mensaje in registro:
        assert _SECRETO_SK not in mensaje
        assert _SECRETO_ASS not in mensaje
    # Cada mensaje fue redactado con ***
    assert "token=***" in registro[0]
    assert "clave ***" in registro[1]