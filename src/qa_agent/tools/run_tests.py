"""Herramienta `run_tests`: ejecuta el comando de pruebas autorizado (allowlist de
comandos seguros, p. ej. `pytest`) sobre el conjunto autorizado y analiza la
salida (FR-012/013/014).

Solo ejecuta sobre conjuntos autorizados (FR-012, FR-025) y con comandos de
una allowlist de comandos seguros (FR-025, SC-011, IV).
Reporta el estado real de la ejecución (FR-013).
No atribuye causas no respaldadas por la evidencia (FR-014, UC-007).
Si no puede ejecutarse → `estado_global=no_ejecutado` e informa explícitamente (FR-017/018).
Determinístico: ejecutar el comando es determinista; solo el análisis de causa
puede ser asistido por LLM (VI).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)


# Allowlist de comandos de prueba seguros (pytest, dotnet, maven, gradle).
# Multi-lenguaje (T073): se admiten comandos fijos sin argumentos adicionales
# para evitar ejecución arbitraria (SC-011 / IV).
_COMANDOS_PERMITIDOS = {
    # pytest / python -m pytest
    "pytest",
    "pytest -v",
    "pytest -vv",
    "pytest --tb=short",
    "pytest --tb=long",
    "pytest -x",
    "pytest -x -v",
    "pytest --tb=short -v",
    "pytest --tb=long -v",
    "pytest -q",
    "pytest --collect-only",
    "python -m pytest",
    "python -m pytest -v",
    "python -m pytest --tb=short",
    "python -m pytest -x",
    # .NET / C#
    "dotnet test",
    "dotnet test -v minimal",
    "dotnet test --no-restore",
    # Maven / Java
    "mvn test",
    "mvn test -q",
    "mvn test -DskipTests=false",
    # Gradle / Java
    "gradle test",
    "gradle test --console=plain",
    "gradlew test",
    "gradlew test --console=plain",
}


class RunTestsHerramienta(Herramienta):
    """Ejecuta pruebas autorizadas y reporta estado real."""

    id = "run_tests"
    nombre = "run_tests"
    descripcion = (
        "Ejecuta el comando de pruebas autorizado (p. ej. pytest) sobre un "
        "conjunto de pruebas autorizado y reporta el estado real de la "
        "ejecución (pasadas, falladas, errores, total). Solo ejecuta comandos "
        "de una allowlist predefinida de comandos seguros. Úsala cuando el "
        "usuario pida ejecutar tests o verificar el estado de las pruebas."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto donde ejecutar las pruebas"},
            "conjunto_autorizado": {"type": "boolean", "description": "Indica si el conjunto de pruebas está autorizado"},
            "comando_pruebas": {"type": "string", "description": "Comando autorizado y acotado (p. ej. 'pytest', 'pytest -v')"},
        },
        "required": ["ruta", "conjunto_autorizado", "comando_pruebas"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "pasadas": {"type": "integer"},
            "falladas": {"type": "integer"},
            "errores": {"type": "integer"},
            "total": {"type": "integer"},
            "estado_global": {"type": "string", "enum": ["exito", "fallo", "no_ejecutado"]},
            "detalle_fallos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string"},
                        "mensaje_error": {"type": "string"},
                        "ruta_relativa": {"type": "string"},
                    },
                    "required": ["nombre", "mensaje_error", "ruta_relativa"],
                },
            },
        },
        "required": ["pasadas", "falladas", "errores", "total", "estado_global", "detalle_fallos"],
    }
    # Ejecutar pruebas puede afectar el estado del proyecto (crear cachés,
    # ejecutar código) → acción sensible que requiere autorización (UC-006,
    # FR-015, principio V).
    requiere_autorizacion = True

    def __init__(self, rutas_permitidas: list[str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def _validar_comando(self, comando: str) -> bool:
        """Valida que el comando esté en la allowlist."""
        return comando.strip() in _COMANDOS_PERMITIDOS

    def _normalizar_comando(self, comando: str) -> list[str]:
        """Normaliza el comando para ejecución segura (usa python -m pytest si pytest directo falla)."""
        cmd = comando.strip()
        # En Windows, pytest puede no estar en PATH, usar python -m pytest
        if cmd.startswith("pytest "):
            partes = cmd.split()
            return ["python", "-m", "pytest"] + partes[1:]
        elif cmd == "pytest":
            return ["python", "-m", "pytest"]
        elif cmd.startswith("python -m pytest"):
            return cmd.split()
        else:
            return cmd.split()

    def _parsear_salida_pytest(self, salida: str, ruta_proyecto: Path) -> dict[str, Any]:
        """Parsea la salida de pytest para extraer métricas y fallos."""
        pasadas = 0
        falladas = 0
        errores = 0
        detalle_fallos: list[dict[str, str]] = []

        # Buscar resumen final en la última línea: "X passed, Y failed, Z error in 0.07s"
        # Buscar la línea que contiene "passed" o "failed" o "error" cerca del final
        lineas = salida.strip().split('\n')
        resumen_linea = ""
        for linea in reversed(lineas):
            if 'passed' in linea or 'failed' in linea or 'error' in linea:
                if 'in ' in linea and ('passed' in linea or 'failed' in linea):
                    resumen_linea = linea
                    break
                elif linea.strip().startswith('='):
                    continue
                else:
                    resumen_linea = linea
                    break

        if resumen_linea:
            # Extraer números: "1 failed, 2 passed" o "2 passed, 1 failed" etc.
            passed_match = re.search(r'(\d+)\s+passed', resumen_linea)
            failed_match = re.search(r'(\d+)\s+failed', resumen_linea)
            error_match = re.search(r'(\d+)\s+error', resumen_linea)
            
            if passed_match:
                pasadas = int(passed_match.group(1))
            if failed_match:
                falladas = int(failed_match.group(1))
            if error_match:
                errores = int(error_match.group(1))

        # Buscar fallos individuales (formato: FAILED tests/test_file.py::test_name - ...)
        fallo_pattern = re.compile(
            r"FAILED\s+([^\s]+)\s+-\s+(.+?)(?:\n|$)"
        )
        for match in fallo_pattern.finditer(salida):
            nombre_completo = match.group(1).strip()
            mensaje = match.group(2).strip()
            partes = nombre_completo.split("::")
            ruta_relativa = partes[0] if partes else nombre_completo
            nombre_test = partes[-1] if len(partes) > 1 else nombre_completo
            detalle_fallos.append(
                {
                    "nombre": nombre_test,
                    "mensaje_error": mensaje[:500],
                    "ruta_relativa": str(ruta_relativa),
                }
            )

        # Si el resumen no capturó fallos pero hay fallos en detalle, usar esos
        if falladas == 0 and detalle_fallos:
            falladas = len(detalle_fallos)

        total = pasadas + falladas + errores

        if total == 0:
            estado_global = "no_ejecutado"
        elif falladas > 0 or errores > 0:
            estado_global = "fallo"
        else:
            estado_global = "exito"

        return {
            "pasadas": pasadas,
            "falladas": falladas,
            "errores": errores,
            "total": total,
            "estado_global": estado_global,
            "detalle_fallos": detalle_fallos,
        }

    def _parsear_salida(self, salida: str, comando: str) -> dict[str, Any]:
        """Despacha el parser según el runner (pytest/dotnet/mvn/gradle)."""
        cmd = comando.strip().lower()
        if cmd.startswith("dotnet"):
            return self._parsear_salida_dotnet(salida)
        if cmd.startswith("mvn"):
            return self._parsear_salida_maven(salida)
        if cmd.startswith("gradle"):
            return self._parsear_salida_gradle(salida)
        return self._parsear_salida_pytest(salida, Path("."))

    def _parsear_salida_dotnet(self, salida: str) -> dict[str, Any]:
        """Parsea la salida de `dotnet test` (formato VSTest)."""
        pasadas = 0
        falladas = 0
        errores = 0
        detalle_fallos: list[dict[str, str]] = []

        # Resumen final: "Passed!  - Failed: 0, Passed: 4, Skipped: 0, Total: 4, Duration: 1 s"
        resumen = re.search(
            r"(?:Passed|Failed)!\s+-?\s*Failed:\s*(\d+),\s*Passed:\s*(\d+),\s*Skipped:\s*(\d+),\s*Total:\s*(\d+)",
            salida,
        )
        total = 0
        if resumen:
            falladas = int(resumen.group(1))
            pasadas = int(resumen.group(2))
            errores = int(resumen.group(3))
            total = int(resumen.group(4))

        # Fallos individuales: "  Failed TestSuma [2 ms]" + "  Error Message:"
        for match in re.finditer(r"^\s*Failed\s+(\S+)\s*\[", salida, re.MULTILINE):
            nombre = match.group(1)
            # Extraer mensaje de error tras la línea "Error Message:"
            bloque = salida[match.end():]
            m_msg = re.search(r"Error Message:\s*\n(.*?)(?=\n\s*Stack Trace:|$)", bloque, re.DOTALL)
            mensaje = m_msg.group(1).strip() if m_msg else ""
            detalle_fallos.append(
                {
                    "nombre": nombre,
                    "mensaje_error": mensaje[:500],
                    "ruta_relativa": "",
                }
            )

        if total == 0:
            estado_global = "no_ejecutado"
        elif falladas > 0 or errores > 0:
            estado_global = "fallo"
        else:
            estado_global = "exito"

        return {
            "pasadas": pasadas,
            "falladas": falladas,
            "errores": errores,
            "total": total,
            "estado_global": estado_global,
            "detalle_fallos": detalle_fallos,
        }

    def _parsear_salida_maven(self, salida: str) -> dict[str, Any]:
        """Parsea la salida de `mvn test` (Surefire)."""
        pasadas = 0
        falladas = 0
        errores = 0
        detalle_fallos: list[dict[str, str]] = []

        # Resumen: "Tests run: 4, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 0.4 s"
        resumen = re.search(
            r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)",
            salida,
        )
        total = 0
        if resumen:
            total = int(resumen.group(1))
            falladas = int(resumen.group(2))
            errores = int(resumen.group(3))
            pasadas = total - falladas - errores

        # Fallos: "[ERROR]   CalculadoraTest.testSuma:10 expected:<5> but was:<4>"
        for match in re.finditer(r"\[ERROR\]\s+([\w.]+)\.(\w+):\d+\s+(.+?)\s*$", salida, re.MULTILINE):
            clase = match.group(1)
            test = match.group(2)
            mensaje = match.group(3).strip()
            detalle_fallos.append(
                {
                    "nombre": f"{clase}.{test}",
                    "mensaje_error": mensaje[:500],
                    "ruta_relativa": "",
                }
            )

        if total == 0:
            estado_global = "no_ejecutado"
        elif falladas > 0 or errores > 0:
            estado_global = "fallo"
        else:
            estado_global = "exito"

        return {
            "pasadas": pasadas,
            "falladas": falladas,
            "errores": errores,
            "total": total,
            "estado_global": estado_global,
            "detalle_fallos": detalle_fallos,
        }

    def _parsear_salida_gradle(self, salida: str) -> dict[str, Any]:
        """Parsea la salida de `gradle test` (formato Gradle)."""
        pasadas = 0
        falladas = 0
        errores = 0
        detalle_fallos: list[dict[str, str]] = []

        # Fallos: "CalculadoraTest > testSuma FAILED"
        for match in re.finditer(
            r"^\s*([\w.]+)\s*>\s*(\w+)\s+FAILED\s*$", salida, re.MULTILINE
        ):
            detalle_fallos.append(
                {
                    "nombre": f"{match.group(1)}.{match.group(2)}",
                    "mensaje_error": "",
                    "ruta_relativa": "",
                }
            )
            falladas += 1

        # Resumen: "4 tests completed, 1 failed"
        resumen = re.search(r"(\d+)\s+tests completed", salida)
        total = int(resumen.group(1)) if resumen else falladas
        falladas_resumen = 0
        if resumen:
            m_failed = re.search(r"(\d+)\s+tests completed,\s*(\d+)\s+failed", salida)
            falladas_resumen = int(m_failed.group(2)) if m_failed else 0
        falladas = max(falladas, falladas_resumen)
        pasadas = total - falladas - errores
        if pasadas < 0:
            pasadas = 0

        if total == 0:
            estado_global = "no_ejecutado"
        elif falladas > 0 or errores > 0:
            estado_global = "fallo"
        else:
            estado_global = "exito"

        return {
            "pasadas": pasadas,
            "falladas": falladas,
            "errores": errores,
            "total": total,
            "estado_global": estado_global,
            "detalle_fallos": detalle_fallos,
        }

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        ruta_raw = parametros.get("ruta", ".")
        conjunto_autorizado = bool(parametros.get("conjunto_autorizado", False))
        comando_pruebas = parametros.get("comando_pruebas", "pytest")

        # Verificar autorización del conjunto
        if not conjunto_autorizado:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={
                    "pasadas": 0,
                    "falladas": 0,
                    "errores": 0,
                    "total": 0,
                    "estado_global": "no_ejecutado",
                    "detalle_fallos": [],
                },
                error="Conjunto de pruebas no autorizado para ejecución (FR-012).",
            )

        # Mínimo privilegio: allowlist de rutas (FR-025 / SC-011)
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

        # Validar comando contra allowlist de comandos seguros (SC-011, IV)
        if not self._validar_comando(comando_pruebas):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={},
                error=(
                    f"Comando de pruebas no permitido: '{comando_pruebas}'. "
                    "Solo se permiten comandos de la allowlist segura (SC-011)."
                ),
            )

        ruta = Path(ruta_raw).expanduser().resolve()
        if not ruta.exists():
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={
                    "pasadas": 0,
                    "falladas": 0,
                    "errores": 0,
                    "total": 0,
                    "estado_global": "no_ejecutado",
                    "detalle_fallos": [],
                },
            )

        # Ejecutar comando
        try:
            # Usar shell=False para seguridad, usar comando normalizado
            cmd_parts = self._normalizar_comando(comando_pruebas)
            resultado_proc = subprocess.run(
                cmd_parts,
                cwd=str(ruta),
                capture_output=True,
                text=True,
                timeout=120,  # Timeout 2 minutos
            )
            salida_completa = resultado_proc.stdout + "\n" + resultado_proc.stderr
        except subprocess.TimeoutExpired:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={
                    "pasadas": 0,
                    "falladas": 0,
                    "errores": 0,
                    "total": 0,
                    "estado_global": "no_ejecutado",
                    "detalle_fallos": [],
                },
                error="Timeout: la ejecución de pruebas excedió 120 segundos.",
            )
        except (OSError, subprocess.SubprocessError) as e:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={
                    "pasadas": 0,
                    "falladas": 0,
                    "errores": 0,
                    "total": 0,
                    "estado_global": "no_ejecutado",
                    "detalle_fallos": [],
                },
                error=f"Error ejecutando comando de pruebas: {e}",
            )

        # Parsear salida
        datos = self._parsear_salida(salida_completa, comando_pruebas)

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos=datos,
        )