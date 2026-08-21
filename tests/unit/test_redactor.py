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


# -- I08: cobertura ampliada de secretos (grupo A: GitHub / AWS) -----------


def test_redacta_token_github_ghp():
    redactor = Redactor()
    secreto = "ghp_" + "a" * 36
    assert redactor.redactar(f"usa {secreto} en el header") == "usa *** en el header"


def test_redacta_token_github_gho():
    redactor = Redactor()
    secreto = "gho_" + "B1c2D3e4F5g6H7i8J9k0" + "l" * 16
    assert secreto not in redactor.redactar(f"token: {secreto}")


def test_redacta_token_github_ghs():
    redactor = Redactor()
    secreto = "ghs_" + "0" * 36
    assert secreto not in redactor.redactar(f"token: {secreto}")


def test_redacta_token_github_pat_fine_grained():
    redactor = Redactor()
    secreto = "github_pat_" + "a1B2c3" * 5
    assert secreto not in redactor.redactar(f"token: {secreto}")


def test_no_redacta_hash_git_similar_a_token_github():
    """Un hash de commit git (hex de 40 chars) no empieza con ghp_/gho_/ghs_/github_pat_."""
    redactor = Redactor()
    texto = "commit a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    assert redactor.redactar(texto) == texto


def test_no_redacta_prefijo_github_sin_longitud_suficiente():
    """'ghp_' mencionado en prosa sin los 36+ caracteres no es un token real."""
    redactor = Redactor()
    texto = "los tokens con prefijo ghp_ identifican credenciales clásicas"
    assert redactor.redactar(texto) == texto


def test_redacta_clave_acceso_aws():
    redactor = Redactor()
    secreto = "AKIAIOSFODNN7EXAMPLE"
    assert redactor.redactar(f"clave: {secreto}") == "clave: ***"


def test_no_redacta_id_similar_a_clave_aws():
    """Un identificador de 20 chars mayúsculas que no empieza con AKIA no es una clave AWS."""
    redactor = Redactor()
    texto = "referencia: ORDR20230101ABCDEFGH"
    assert redactor.redactar(texto) == texto


def test_no_redacta_uuid_como_secreto():
    redactor = Redactor()
    texto = "id: 550e8400-e29b-41d4-a716-446655440000"
    assert redactor.redactar(texto) == texto


# -- I08: cobertura ampliada de secretos (grupo B: JWT / PEM) --------------


def test_redacta_jwt_sin_prefijo_bearer():
    """Un JWT que aparece solo (sin 'Bearer ' delante) también debe redactarse."""
    redactor = Redactor()
    secreto = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ"
        ".dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    )
    assert redactor.redactar(f"token JWT: {secreto}") == "token JWT: ***"


def test_no_redacta_version_ni_dominio_similar_a_jwt():
    """Una cadena con puntos (versión semver, dominio) no es un JWT."""
    redactor = Redactor()
    texto = "versión 1.2.3 disponible en app.staging.example.com"
    assert redactor.redactar(texto) == texto


def test_no_redacta_base64_no_jwt():
    """Un blob base64 de un solo segmento (sin dos puntos ni prefijo eyJ) no es un JWT."""
    redactor = Redactor()
    texto = "adjunto: aGVsbG8gbXVuZG8gZXN0byBubyBlcyB1biBzZWNyZXRv"
    assert redactor.redactar(texto) == texto


def test_redacta_bloque_pem_clave_privada():
    redactor = Redactor()
    bloque = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIBOgIBAAJBAK...ejemplo...==\n"
        "-----END RSA PRIVATE KEY-----"
    )
    assert redactor.redactar(f"contenido:\n{bloque}\nfin") == "contenido:\n***\nfin"


def test_redacta_bloque_pem_clave_privada_generica():
    redactor = Redactor()
    bloque = (
        "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...\n-----END PRIVATE KEY-----"
    )
    assert bloque not in redactor.redactar(bloque)


def test_no_redacta_bloque_pem_clave_publica():
    """Una clave PÚBLICA no es un secreto y no debe redactarse."""
    redactor = Redactor()
    bloque = (
        "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAw...\n"
        "-----END PUBLIC KEY-----"
    )
    assert redactor.redactar(bloque) == bloque


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