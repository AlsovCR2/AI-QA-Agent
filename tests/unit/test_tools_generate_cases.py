"""Tests de la herramienta `generate_test_cases` (T058, FR-019, IX).

Cubre: genera casos con fuentes de código real; sin código relevante → comunica
falta de evidencia; distintos tipos de caso según cripticidad.
"""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from qa_agent.llm.backend import LLMBackend
from qa_agent.tools.generate_test_cases import GenerateTestCasesHerramienta
from qa_agent.tools.base import EstadoResultado


class BackendCasosConContrato(LLMBackend):
    nombre = "casos_contrato"
    requiere_api_key = False
    proveedor_requerido = False
    soporta_razonamiento = False

    def __init__(
        self,
        *,
        fallar: bool = False,
        texto: str | None = None,
    ) -> None:
        self.fallar = fallar
        self.texto = texto
        self.llamadas = []

    def interpretar(self, solicitud):
        return {}

    def seleccionar_herramienta(self, solicitud, herramientas):
        return {"ninguna": True}

    def generar_respuesta(self, solicitud, resultados):
        self.llamadas.append((solicitud, resultados))
        if self.fallar:
            raise RuntimeError("backend no disponible")
        texto = self.texto
        if texto is None:
            texto = json.dumps(
                [
                    {
                        "descripcion": "Límite de suma",
                        "entrada_esperada": "sumar(0, 0)",
                        "resultado_esperado": "0",
                        "tipo": "edge_case",
                    }
                ]
            )
        return {
            "texto": texto,
            "confianza": "alta",
        }

    def planificar(self, intencion, catalogo, contexto):
        return None

    def razonar(self, estado, pendientes):
        return {"concluir": True}

    def evaluar(self, estado, observaciones):
        return {"satisfecha": True}

    def responder(self, observaciones, intencion=""):
        return {"texto": ""}


def test_generate_test_cases_con_fuentes_reales(tmp_path):
    """T058: casos propuestos citan al menos una fuente real (FR-019)."""
    # Crear archivo de código real
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calculadora.py").write_text(
        '"""Calculadora."""\n\n'
        'def sumar(a: int, b: int) -> int:\n'
        '    """Suma dos números."""\n'
        '    return a + b\n\n'
        'def dividir(a: int, b: int) -> float:\n'
        '    if b == 0:\n'
        '        raise ValueError("No se puede dividir por cero")\n'
        '    return a / b\n'
    )

    # Mock LLMBackend para evitar llamada real
    mock_llm = Mock()
    mock_llm.generar_respuesta.return_value = {
        "texto": (
        '[\n'
        '  {\n'
        '    "descripcion": "Suma de dos positivos",\n'
        '    "entrada_esperada": "sumar(2, 3)",\n'
        '    "resultado_esperado": "5",\n'
        '    "tipo": "happy_path"\n'
        '  },\n'
        '  {\n'
        '    "descripcion": "Suma con negativos",\n'
        '    "entrada_esperada": "sumar(-1, -1)",\n'
        '    "resultado_esperado": "-2",\n'
        '    "tipo": "edge_case"\n'
        '  }\n'
        ']'
        )
    }

    herramienta = GenerateTestCasesHerramienta([str(tmp_path)], llm_backend=mock_llm)
    resultado = herramienta.ejecutar(
        {
            "ruta": str(tmp_path),
            "objetivo": "función sumar",
            "cripticidad": "happy_path",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert "casos_propuestos" in resultado.datos
    assert "fuentes" in resultado.datos
    assert len(resultado.datos["casos_propuestos"]) >= 1
    assert len(resultado.datos["fuentes"]) >= 1
    # Verificar que cita fuente real
    assert any("calculadora.py" in f for f in resultado.datos["fuentes"])


def test_generate_test_cases_sin_codigo_relevante(tmp_path):
    """T058: objetivo sin código relevante → comunica falta de evidencia (SC-002)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "otro.py").write_text('def foo(): pass\n')

    mock_llm = Mock()
    mock_llm.generar_respuesta.return_value = {"texto": "[]"}

    herramienta = GenerateTestCasesHerramienta([str(tmp_path)], llm_backend=mock_llm)
    resultado = herramienta.ejecutar(
        {
            "ruta": str(tmp_path),
            "objetivo": "función inexistente_xyz",
            "cripticidad": "happy_path",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    # Debe comunicar falta de evidencia
    assert resultado.datos["casos_propuestos"] == []
    assert len(resultado.datos["fuentes"]) == 0


def test_generate_test_cases_distintos_tipos_segun_cripticidad(tmp_path):
    """T058: con cripticidad distinta, produce tipos de caso distintos."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "validador.py").write_text(
        'def validar_email(email: str) -> bool:\n'
        '    return "@" in email and "." in email\n'
    )

    mock_llm = Mock()
    # Para edge_cases
    mock_llm.generar_respuesta.return_value = {
        "texto": (
        '[\n'
        '  {"descripcion": "Email vacío", "entrada_esperada": "validar_email(\\\"\\\")", '
        '"resultado_esperado": "False", "tipo": "edge_case"},\n'
        '  {"descripcion": "Email sin @", "entrada_esperada": "validar_email(\\\"test\\\")", '
        '"resultado_esperado": "False", "tipo": "edge_case"}\n'
        ']'
        )
    }

    herramienta = GenerateTestCasesHerramienta([str(tmp_path)], llm_backend=mock_llm)
    resultado = herramienta.ejecutar(
        {
            "ruta": str(tmp_path),
            "objetivo": "validar_email",
            "cripticidad": "edge_cases",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    casos = resultado.datos["casos_propuestos"]
    assert len(casos) >= 1
    # Todos deben ser edge_case
    for caso in casos:
        assert caso["tipo"] == "edge_case"


def test_generate_test_cases_con_fuentes_csharp(tmp_path):
    """T123: proyectos C# (`.cs`) sin archivos `.py` también producen fuentes
    reales y casos (el escaneo ya no está limitado a `*.py`)."""
    dal = tmp_path / "DAL"
    dal.mkdir()
    (dal / "ClienteDAL.cs").write_text(
        "namespace DAL\n{\n    public class ClienteDAL\n    {\n"
        "        public Cliente BuscarPorCedula(string cedula)\n"
        "        {\n            return null;\n        }\n"
        "        private Cliente MappearFila(System.Data.SqlClient.SqlDataReader dr)\n"
        "        {\n            return new Cliente();\n        }\n"
        "    }\n}\n",
        encoding="utf-8",
    )

    # Sin LLM: fallback determinista (_generar_casos_basicos) sobre C#.
    herramienta = GenerateTestCasesHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(tmp_path),
            "objetivo": "BuscarPorCedula y MappearFila",
            "cripticidad": "happy_path",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert any("ClienteDAL.cs" in f for f in resultado.datos["fuentes"])
    casos = resultado.datos["casos_propuestos"]
    assert len(casos) >= 1
    assert any("BuscarPorCedula" in c["entrada_esperada"] for c in casos)
    assert all(c["tipo"] == "happy_path" for c in casos)


def test_generate_test_cases_ignora_directorios_de_build(tmp_path):
    """T123: archivos en `bin`/`obj`/`.git` no son código fuente real y no se
    usan como evidencia (FR-025/FR-019)."""
    dal = tmp_path / "DAL"
    dal.mkdir()
    (dal / "BitacoraDAL.cs").write_text(
        "public class BitacoraDAL { public void Insertar(string ip) { } }",
        encoding="utf-8",
    )
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "CompiladoDAL.cs").write_text(
        "public class BitacoraDAL { public void Insertar(string ip) { } }",
        encoding="utf-8",
    )
    (tmp_path / "obj").mkdir()
    (tmp_path / "obj" / "ObjetoDAL.cs").write_text(
        "public class BitacoraDAL { public void Insertar(string ip) { } }",
        encoding="utf-8",
    )

    herramienta = GenerateTestCasesHerramienta([str(tmp_path)])
    resultado = herramienta.ejecutar(
        {
            "ruta": str(tmp_path),
            "objetivo": "Insertar de BitacoraDAL",
            "cripticidad": "happy_path",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert any("BitacoraDAL.cs" in f for f in resultado.datos["fuentes"])
    assert not any("bin" in f or "obj" in f for f in resultado.datos["fuentes"])


def test_t128_cumple_contrato_backend_y_mapea_enum_sin_filtrar_secretos(
    tmp_path,
):
    (tmp_path / "sumador.py").write_text(
        "api_key=clave_super_secreta_123456\n"
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    backend = BackendCasosConContrato()
    herramienta = GenerateTestCasesHerramienta(
        [str(tmp_path)],
        llm_backend=backend,
    )

    resultado = herramienta.ejecutar(
        {
            "ruta": str(tmp_path),
            "objetivo": "sumar",
            "cripticidad": "edge_cases",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert resultado.datos["casos_propuestos"][0]["tipo"] == "edge_case"
    assert len(backend.llamadas) == 1
    solicitud, resultados = backend.llamadas[0]
    assert isinstance(solicitud, dict)
    assert isinstance(resultados, list)
    assert '"tipo": "edge_case"' in solicitud["texto"]
    assert "clave_super_secreta_123456" not in repr(backend.llamadas)


def test_t128_error_backend_es_explicito_y_no_lista_vacia_exitosa(tmp_path):
    (tmp_path / "sumador.py").write_text(
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    herramienta = GenerateTestCasesHerramienta(
        [str(tmp_path)],
        llm_backend=BackendCasosConContrato(fallar=True),
    )

    resultado = herramienta.ejecutar(
        {
            "ruta": str(tmp_path),
            "objetivo": "sumar",
            "cripticidad": "happy_path",
        }
    )

    assert resultado.estado == EstadoResultado.ERROR
    assert resultado.error
    assert "backend" in resultado.error.lower()


def test_t128_respuesta_malformada_es_error_explicito(tmp_path):
    (tmp_path / "sumador.py").write_text(
        "def sumar(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    herramienta = GenerateTestCasesHerramienta(
        [str(tmp_path)],
        llm_backend=BackendCasosConContrato(texto="no es json"),
    )

    resultado = herramienta.ejecutar(
        {
            "ruta": str(tmp_path),
            "objetivo": "sumar",
            "cripticidad": "happy_path",
        }
    )

    assert resultado.estado == EstadoResultado.ERROR
    assert resultado.error
