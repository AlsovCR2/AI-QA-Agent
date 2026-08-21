"""Cobertura de redacción para Google y Azure (T210 / FR-125).

El informe de evaluación pedía explícitamente estos dos proveedores y quedaron
fuera de la ampliación de I08. Cada patrón lleva su prueba positiva y su prueba
de falso positivo: un redactor demasiado agresivo destruye evidencia legítima,
que para un agente QA es tan dañino como filtrar un secreto.
"""

from __future__ import annotations

import pytest

from qa_agent.security.redactor import Redactor

REDACTOR = Redactor()

# Valores con la forma real de cada proveedor. Ninguno es una credencial
# válida: son cadenas construidas para las pruebas.
_SECRETOS = [
    # Google API key: AIza + exactamente 35 caracteres.
    ("google_api_key", "AIzaSyD-ejemplo000000000000000000000000"),
    # Secreto de cliente OAuth de Google.
    ("google_oauth", "GOCSPX-ejemplo000000000000000000"),
    # Secreto de cliente de Entra ID (Azure AD).
    ("entra_client_secret", "abc8Q~ejemplo00000000000000000000000000"),
]


@pytest.mark.parametrize("nombre,secreto", _SECRETOS, ids=[s[0] for s in _SECRETOS])
def test_secreto_se_redacta(nombre, secreto):
    salida = REDACTOR.redactar(f"configurando cliente con {secreto} y arrancando")

    assert secreto not in salida
    assert "***" in salida


def test_account_key_de_azure_storage_se_redacta():
    cadena = (
        "DefaultEndpointsProtocol=https;AccountName=micuenta;"
        "AccountKey=YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXowMTIzNDU2Nzg5YWJjZGVmZ2g=;"
        "EndpointSuffix=core.windows.net"
    )

    salida = REDACTOR.redactar(cadena)

    assert "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXowMTIzNDU2Nzg5YWJjZGVmZ2g=" not in salida
    # El resto de la cadena, que no es secreto, se conserva como evidencia útil.
    assert "AccountName=micuenta" in salida


def test_firma_sas_de_azure_se_redacta():
    url = (
        "https://micuenta.blob.core.windows.net/c/b?sv=2021-06-08&"
        "sig=aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789%2Fabc%3D"
    )

    salida = REDACTOR.redactar(url)

    assert "aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789" not in salida
    assert "sv=2021-06-08" in salida


# --- Falsos positivos ------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        # Prefijo correcto pero longitud incorrecta: no es una clave de Google.
        "el identificador AIzaCorto no es una clave",
        # Nombre de variable que empieza igual.
        "AIzaConfiguracion = cargar_config()",
        # Un tilde en texto normal no es un secreto de Entra.
        "el rango va de 8 a 10, aproximadamente ~ 9",
        # Nombre de campo sin valor.
        "revisar el campo AccountKey en la documentación",
        # `sig` como palabra, no como parámetro con valor largo.
        "la firma (sig) es obligatoria",
    ],
)
def test_texto_legitimo_no_se_redacta(texto):
    assert REDACTOR.redactar(texto) == texto


def test_ruta_de_archivo_con_target_no_se_redacta():
    """Regresión: los patrones nuevos no deben tocar rutas ni nombres."""
    texto = "el informe está en target/site/jacoco/jacoco.xml"

    assert REDACTOR.redactar(texto) == texto


# --- Idempotencia (SC-008) -------------------------------------------------


@pytest.mark.parametrize("nombre,secreto", _SECRETOS, ids=[s[0] for s in _SECRETOS])
def test_redactar_dos_veces_no_cambia_el_resultado(nombre, secreto):
    una = REDACTOR.redactar(f"clave: {secreto}")
    dos = REDACTOR.redactar(una)

    assert una == dos
