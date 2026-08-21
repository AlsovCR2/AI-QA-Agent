"""Herramienta `generate_test_cases`: identifica código real relevante (`fuentes`)
de forma determinista y delega la redacción de casos al `LLMBackend` (VI).

Separación de responsabilidades: la herramienta identifica el código
real relevante (`fuentes`) de forma determinista; la generación de los
casos en lenguaje natural es la única parte que puede delegarse al LLM
vía `LLMBackend` (VI).
Los `casos_propuestos` son sugerencias que deben basarse en el código real
citado (FR-019, IX); el agente nunca inventa código inexistente como fuente.
Respeta la `Allowlist` (FR-025). La generación de casos es una acción no
destructiva (no requiere autorización).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)
from qa_agent.llm.backend import LLMBackend
from qa_agent.security.redactor import Redactor
from qa_agent.tools.exclusion_policy import (
    NOMBRES_DIRECTORIO_EXCLUIDOS as _DIRECTORIOS_IGNORADOS,
)

# Extensiones de código fuente reconocidas, mapeadas a la etiqueta de lenguaje
# usada en los bloques de código del prompt del LLM. `generate_test_cases`
# escanea TODAS estas extensiones (no solo `*.py`, T058) para identificar
# `fuentes` reales en proyectos de cualquier lenguaje (p. ej. C# de
# ReservaHotel, T123): un proyecto `.cs` sin `.py` no debía devolver `fuentes`
# vacías aunque tuviera código relevante.
_EXTENSIONES_CODIGO: dict[str, str] = {
    ".py": "python",
    ".cs": "csharp",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".rb": "ruby",
    ".go": "go",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".kt": "kotlin",
    ".swift": "swift",
}

# Directorios que nunca son código fuente real (VCS, build, dependencias).
# Centralizado en `exclusion_policy.py` (I07); ver ese módulo para el
# inventario de duplicados y las decisiones (rulings) tomadas al unificar.


class GenerateTestCasesHerramienta(Herramienta):
    """Genera casos de prueba sugeridos basados en código real del proyecto."""

    id = "generate_test_cases"
    nombre = "generate_test_cases"
    descripcion = (
        "Identifica código real relevante del proyecto (`fuentes`) para un "
        "objetivo dado, y delega la redacción de casos de prueba en lenguaje "
        "natural al LLMBackend. Los casos propuestos citan las fuentes reales "
        "consultadas. Si no hay código relevante, comunica falta de evidencia "
        "sin inventar. Úsala cuando el usuario pida generar tests para una "
        "función o componente específico."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto"},
            "objetivo": {
                "type": "string",
                "description": "Función, componente o escenario a cubrir con tests",
            },
            "cripticidad": {
                "type": "string",
                "enum": ["happy_path", "edge_cases", "usuarios_no_validos"],
                "description": "Tipo de casos a generar",
            },
        },
        "required": ["ruta", "objetivo", "cripticidad"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "casos_propuestos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "descripcion": {"type": "string"},
                        "entrada_esperada": {"type": "string"},
                        "resultado_esperado": {"type": "string"},
                        "tipo": {
                            "type": "string",
                            "enum": ["happy_path", "edge_case", "negativo"],
                        },
                    },
                    "required": [
                        "descripcion",
                        "entrada_esperada",
                        "resultado_esperado",
                        "tipo",
                    ],
                },
            },
            "fuentes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Código real del proyecto consultado como evidencia",
            },
        },
        "required": ["casos_propuestos", "fuentes"],
    }
    requiere_autorizacion = False

    def __init__(
        self,
        rutas_permitidas: list[str] | None = None,
        llm_backend: LLMBackend | None = None,
        redactor: Redactor | None = None,
    ) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None
        self._llm_backend = llm_backend
        self._redactor = redactor or Redactor()

    def _buscar_codigo_relevante(self, ruta: Path, objetivo: str) -> list[tuple[str, str]]:
        """
        Busca código real relevante para el objetivo.
        Retorna lista de (ruta_relativa, contenido_completo_del_archivo).

        Escanea todas las extensiones de código reconocidas (no solo `*.py`,
        T123) y considera relevante un archivo si su contenido o su nombre
        contiene alguna palabra clave del objetivo.
        """
        fuentes: list[tuple[str, str]] = []
        objetivo_lower = objetivo.lower()

        # Palabras clave del objetivo (nombres de clase/método, componentes o
        # escenarios mencionados por el usuario).
        palabras_clave = [
            palabra
            for palabra in re.findall(r"\w+", objetivo_lower)
            if len(palabra) > 2
        ]
        # Sin palabras clave no hay base determinista para elegir fuentes: se
        # comunica falta de evidencia en vez de inventar (FR-019).
        if not palabras_clave:
            return fuentes

        for archivo in ruta.rglob("*"):
            if not archivo.is_file():
                continue
            extension = archivo.suffix.lower()
            if extension not in _EXTENSIONES_CODIGO:
                continue
            partes = {parte.lower() for parte in archivo.parts}
            if partes & _DIRECTORIOS_IGNORADOS:
                continue
            if self._allowlist is not None and not self._allowlist.contiene(str(archivo)):
                continue

            try:
                contenido = archivo.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue

            contenido_min = contenido.lower()
            relevante = any(
                palabra in contenido_min for palabra in palabras_clave
            ) or any(
                palabra in archivo.stem.lower() for palabra in palabras_clave
            )
            if not relevante:
                continue

            ruta_relativa = str(archivo.relative_to(ruta))
            fuentes.append((ruta_relativa, contenido))

        return fuentes

    def _construir_prompt(self, objetivo: str, cripticidad: str, fuentes: list[tuple[str, str]]) -> str:
        """Construye el prompt para el LLM."""
        tipo_map = {
            "happy_path": "happy_path",
            "edge_cases": "edge_case",
            "usuarios_no_validos": "negativo",
        }
        tipo_descripcion = {
            "happy_path": "happy_path (casos de uso normal/esperado)",
            "edge_cases": "edge_case (casos límite, bordes, valores extremos)",
            "usuarios_no_validos": "negativo (entradas inválidas, errores esperados)",
        }
        tipo_esperado = tipo_map.get(cripticidad, cripticidad)
        tipo_texto = tipo_descripcion.get(cripticidad, tipo_esperado)

        fuentes_texto = "\n\n".join(
            [
                f"### Archivo: {ruta}\n```{_EXTENSIONES_CODIGO.get(Path(ruta).suffix.lower(), '')}\n{contenido}\n```"
                for ruta, contenido in fuentes
            ]
        )

        return f"""Genera casos de prueba para: {objetivo}
Tipo de casos: {tipo_texto}

Código real del proyecto (fuentes):
{fuentes_texto}

Genera una lista JSON de casos de prueba. Cada caso debe tener:
- descripcion: descripción breve del caso
- entrada_esperada: código de entrada (ej: "funcion(1, 2)")
- resultado_esperado: resultado esperado (ej: "3")
- tipo: "{tipo_esperado}" (usar exactamente este valor)

Solo genera casos basados en el código real proporcionado. Si no hay código relevante, devuelve [].

Formato de salida (JSON válido):
[
  {{
    "descripcion": "...",
    "entrada_esperada": "...",
    "resultado_esperado": "...",
    "tipo": "{tipo_esperado}"
  }}
]"""

    def _parsear_respuesta_llm(self, respuesta: str, cripticidad: str) -> list[dict[str, Any]]:
        """Parsea la respuesta del LLM y valida estructura."""
        import json

        # Mapear cripticidad a tipo de caso esperado en el schema
        tipo_map = {
            "happy_path": "happy_path",
            "edge_cases": "edge_case",
            "usuarios_no_validos": "negativo",
        }
        tipo_esperado = tipo_map.get(cripticidad, cripticidad)

        # Extraer JSON y fallar explícitamente si el backend no cumple el
        # contrato; una lista JSON vacía sigue siendo una respuesta válida.
        respuesta = respuesta.strip()
        if respuesta.startswith("```json"):
            respuesta = respuesta[7:]
        if respuesta.endswith("```"):
            respuesta = respuesta[:-3]
        respuesta = respuesta.strip()
        try:
            casos = json.loads(respuesta)
        except json.JSONDecodeError as error:
            raise ValueError("respuesta JSON inválida del backend") from error

        if not isinstance(casos, list):
            raise ValueError("la respuesta del backend debe ser una lista JSON")

        casos_validos = []
        campos = ("descripcion", "entrada_esperada", "resultado_esperado", "tipo")
        for caso in casos:
            if not isinstance(caso, dict) or not all(k in caso for k in campos):
                raise ValueError("caso de prueba inválido en respuesta del backend")
            caso_normalizado = dict(caso)
            caso_normalizado["tipo"] = tipo_esperado
            casos_validos.append(caso_normalizado)

        return casos_validos

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        ruta_raw = parametros.get("ruta", ".")
        objetivo = parametros.get("objetivo", "")
        cripticidad = parametros.get("cripticidad", "happy_path")

        if not objetivo:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={"casos_propuestos": [], "fuentes": []},
                error="Objetivo requerido para generar casos de prueba.",
            )

        # Validar ruta
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

        ruta = Path(ruta_raw).expanduser().resolve()
        if not ruta.exists():
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={"casos_propuestos": [], "fuentes": []},
            )

        # 1. Identificar código real relevante (determinista, sin LLM)
        fuentes_encontradas = self._buscar_codigo_relevante(ruta, objetivo)

        if not fuentes_encontradas:
            # Sin código relevante → comunicar falta de evidencia sin inventar
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={"casos_propuestos": [], "fuentes": []},
            )

        # 2. Delegar redacción al LLMBackend (si disponible)
        rutas_fuentes = [ruta for ruta, _ in fuentes_encontradas]
        casos_propuestos: list[dict[str, Any]] = []

        if self._llm_backend is not None:
            prompt = self._construir_prompt(objetivo, cripticidad, fuentes_encontradas)
            try:
                solicitud_llm = self._redactor.redactar({"texto": prompt})
                evidencia = ResultadoDeHerramienta(
                    herramienta_id=self.id,
                    estado=EstadoResultado.EXITO,
                    datos={"fuentes": rutas_fuentes},
                )
                respuesta_llm = self._llm_backend.generar_respuesta(
                    solicitud_llm,
                    self._redactor.redactar([evidencia]),
                )
                if not isinstance(respuesta_llm, dict):
                    raise TypeError("generar_respuesta debe devolver un diccionario")
                texto_respuesta = respuesta_llm.get("texto")
                if not isinstance(texto_respuesta, str):
                    raise TypeError("la respuesta del backend no contiene texto")
                casos_propuestos = self._parsear_respuesta_llm(
                    texto_respuesta,
                    cripticidad,
                )
            except Exception as error:  # noqa: BLE001 - frontera de proveedor
                return ResultadoDeHerramienta(
                    herramienta_id=self.id,
                    estado=EstadoResultado.ERROR,
                    datos={
                        "casos_propuestos": [],
                        "fuentes": rutas_fuentes,
                    },
                    error=(
                        "Error del backend LLM al generar casos: "
                        f"{self._redactor.redactar(str(error))}"
                    ),
                )
        else:
            # Sin LLM disponible: generar casos básicos deterministas basados en el código
            casos_propuestos = self._generar_casos_basicos(fuentes_encontradas, cripticidad)

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "casos_propuestos": casos_propuestos,
                "fuentes": rutas_fuentes,
            },
        )

    def _extraer_metodos(self, contenido: str, extension: str) -> list[tuple[str, str]]:
        """Extrae `(nombre, argumentos_formateados)` de métodos/funciones reales.

        Para Python usa `ast`; para el resto de lenguajes (C#, Java, JS, ...)
        usa un patrón determinista de firmas con modificador de acceso/static:
        `public ... Nombre(args)` (T123). Solo sirve como fallback sin LLM.
        """
        if extension == ".py":
            try:
                arbol = ast.parse(contenido)
            except SyntaxError:
                return []
            return [
                (nodo.name, ", ".join(f"{arg.arg}=..." for arg in nodo.args.args))
                for nodo in ast.walk(arbol)
                if isinstance(nodo, ast.FunctionDef)
            ]

        patron = (
            r"\b(?:public|private|protected|internal|static|virtual|override|"
            r"async)\s+[\w<>\[\]?,\.]+\s+(\w+)\s*\(([^)]*)\)"
        )
        metodos: list[tuple[str, str]] = []
        for coincidencia in re.finditer(patron, contenido):
            nombre = coincidencia.group(1)
            parametros = [
                parametro.split()[-1]
                for parametro in coincidencia.group(2).split(",")
                if parametro.strip()
            ]
            metodos.append((nombre, ", ".join(parametros)))
        return metodos

    def _generar_casos_basicos(
        self, fuentes: list[tuple[str, str]], cripticidad: str
    ) -> list[dict[str, Any]]:
        """Genera casos básicos deterministas sin LLM (fallback)."""
        casos = []

        for ruta, contenido in fuentes:
            extension = Path(ruta).suffix.lower()
            for nombre, args_str in self._extraer_metodos(contenido, extension):
                if cripticidad == "happy_path":
                    casos.append(
                        {
                            "descripcion": f"Caso básico para {nombre}",
                            "entrada_esperada": f"{nombre}({args_str})",
                            "resultado_esperado": "resultado esperado según implementación",
                            "tipo": "happy_path",
                        }
                    )
                elif cripticidad == "edge_cases":
                    casos.append(
                        {
                            "descripcion": f"Caso límite para {nombre}",
                            "entrada_esperada": f"{nombre}({args_str}) con valores borde",
                            "resultado_esperado": "manejo correcto de bordes",
                            "tipo": "edge_case",
                        }
                    )
                elif cripticidad == "usuarios_no_validos":
                    casos.append(
                        {
                            "descripcion": f"Entrada inválida para {nombre}",
                            "entrada_esperada": f"{nombre}(argumentos_inválidos)",
                            "resultado_esperado": "lanza excepción apropiada",
                            "tipo": "negativo",
                        }
                    )

        return casos[:3]  # Máximo 3 casos básicos
