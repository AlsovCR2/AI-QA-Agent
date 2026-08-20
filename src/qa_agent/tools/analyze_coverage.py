"""Herramienta `analyze_coverage`: ejecuta el comando de cobertura autorizado
(allowlist) y reporta cobertura real (FR-017/018/019, FR-025).

Solo ejecuta comandos de cobertura autorizados (FR-025, SC-011).
Reporta cobertura real (FR-019); si no puede ejecutarse
(`estado == no_ejecutado`), se informa explícitamente (FR-017/018).
Determinística (VI / SC-010).
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


# Allowlist de comandos de cobertura seguros (pytest, dotnet, maven).
# Multi-lenguaje (T073): comandos fijos sin argumentos adicionales (SC-011 / IV).
_COMANDOS_COBERTURA_PERMITIDOS = {
    "pytest --cov=src",
    "pytest --cov=src --cov-report=term",
    "pytest --cov=src --cov-report=term-missing",
    "pytest --cov=src --cov-report=xml",
    "pytest --cov=src --cov-report=html",
    "pytest --cov=. --cov-report=term",
    "pytest --cov=. --cov-report=term-missing",
    "python -m pytest --cov=src",
    "python -m pytest --cov=src --cov-report=term",
    "python -m pytest --cov=src --cov-report=term-missing",
    "python -m pytest --cov=. --cov-report=term",
    "coverage run -m pytest",
    "coverage run -m pytest && coverage report",
    "coverage run -m pytest && coverage report -m",
    # .NET / C#: genera coverage.cobertura.xml
    'dotnet test --collect:"XPlat Code Coverage"',
    'dotnet test --collect:"XPlat Code Coverage" --no-restore',
    # Maven / Java: genera target/site/jacoco/jacoco.xml
    "mvn test jacoco:report",
    "mvn test jacoco:report -q",
}


class AnalyzeCoverageHerramienta(Herramienta):
    """Analiza cobertura de código ejecutando comando autorizado."""

    id = "analyze_coverage"
    nombre = "analyze_coverage"
    descripcion = (
        "Ejecuta un comando de cobertura autorizado (p. ej. pytest --cov=src) "
        "y reporta la cobertura real global y por archivo, incluyendo líneas "
        "faltantes. Solo usa comandos de una allowlist predefinida. Si no "
        "puede ejecutarse, reporta estado explícito (error/no_ejecutado). "
        "Úsala cuando el usuario pida analizar la cobertura de tests."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto"},
            "comando_cobertura": {
                "type": "string",
                "description": "Comando autorizado y acotado (p. ej. 'pytest --cov=src --cov-report=term')",
            },
        },
        "required": ["ruta", "comando_cobertura"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "cobertura_global": {
                "type": "number",
                "description": "Porcentaje 0-100",
            },
            "por_archivo": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ruta_relativa": {"type": "string"},
                        "cobertura": {"type": "number"},
                        "lineas_faltantes": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["ruta_relativa", "cobertura", "lineas_faltantes"],
                },
            },
            "estado": {
                "type": "string",
                "enum": ["exito", "error", "no_ejecutado"],
            },
        },
        "required": ["cobertura_global", "por_archivo", "estado"],
    }
    requiere_autorizacion = False

    def __init__(self, rutas_permitidas: list[str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def _validar_comando(self, comando: str) -> bool:
        """Valida que el comando esté en la allowlist."""
        return comando.strip() in _COMANDOS_COBERTURA_PERMITIDOS

    def _normalizar_comando(self, comando: str) -> list[str]:
        """Normaliza el comando para ejecución segura."""
        cmd = comando.strip()
        if cmd.startswith("pytest "):
            partes = cmd.split()
            return ["python", "-m"] + partes
        elif cmd.startswith("coverage "):
            # coverage puede no estar disponible como comando directo
            partes = cmd.split()
            return ["python", "-m"] + partes
        elif cmd.startswith("python -m pytest"):
            return cmd.split()
        else:
            return cmd.split()

    def _parsear_cobertura_term(self, salida: str) -> dict[str, Any]:
        """Parsea la salida de `coverage report` o `pytest --cov-report=term`."""
        por_archivo: list[dict[str, Any]] = []
        cobertura_global = 0.0

        # Buscar líneas del formato: "archivo.py     100    5    95%"
        # o "src/archivo.py      4      1    75%"
        patron_linea = re.compile(
            r"^(\S+)\s+(\d+)\s+(\d+)\s+(\d+)%$"
        )

        lineas = salida.strip().split("\n")
        for linea in lineas:
            linea = linea.strip()
            # Saltar líneas de encabezado, separadores y TOTAL
            if (linea.startswith("Name") or linea.startswith("---") or 
                linea.startswith("TOTAL") or linea == ""):
                continue
            match = patron_linea.match(linea)
            if match:
                archivo = match.group(1)
                stmts = int(match.group(2))
                miss = int(match.group(3))
                cobertura = int(match.group(4))

                # Calcular líneas faltantes aproximadas (no disponibles en term simple)
                # Para term-missing se vería: "archivo.py 100 5 95%  10-15, 20"
                lineas_faltantes: list[int] = []

                # Intentar extraer líneas faltantes si formato term-missing
                missing_match = re.search(r"(\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*$)", linea)
                if missing_match:
                    missing_str = missing_match.group(1)
                    for part in missing_str.split(","):
                        part = part.strip()
                        if "-" in part:
                            inicio, fin = part.split("-")
                            lineas_faltantes.extend(range(int(inicio), int(fin) + 1))
                        else:
                            lineas_faltantes.append(int(part))

                por_archivo.append(
                    {
                        "ruta_relativa": archivo,
                        "cobertura": float(cobertura),
                        "lineas_faltantes": lineas_faltantes,
                    }
                )

        # Buscar línea TOTAL para cobertura global
        for linea in reversed(lineas):
            if linea.strip().startswith("TOTAL"):
                total_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", linea)
                if total_match:
                    cobertura_global = float(total_match.group(1))
                break

        # Si no hay TOTAL, calcular promedio
        if cobertura_global == 0.0 and por_archivo:
            cobertura_global = sum(p["cobertura"] for p in por_archivo) / len(por_archivo)

        return {
            "cobertura_global": cobertura_global,
            "por_archivo": por_archivo,
            "estado": "exito" if por_archivo else "no_ejecutado",
        }

    def _parsear_salida(self, salida: str, ruta_proyecto: Path) -> dict[str, Any]:
        """Despacha el parser según el formato detectado en la salida.

        Prioridad: informe XML generado (dotnet Cobertura / maven JaCoCo) y,
        si no se encuentra, salida de terminal estilo coverage.py.
        """
        # dotnet: localizar coverage.cobertura.xml en la salida (Attachments:)
        m_cobertura = re.search(r"([^\s]+coverage\.cobertura\.xml)", salida)
        if m_cobertura:
            ruta_xml = Path(m_cobertura.group(1)).expanduser().resolve()
            if ruta_xml.exists():
                try:
                    return self._parsear_cobertura_xml(ruta_xml.read_text(encoding="utf-8"))
                except Exception:
                    return {
                        "cobertura_global": 0.0,
                        "por_archivo": [],
                        "estado": "error",
                    }

        # maven: localizar jacoco.xml en la salida (file://<ruta>/jacoco.xml)
        m_jacoco = re.search(r"([^\s]+jacoco\.xml)", salida)
        if m_jacoco:
            ruta_xml = m_jacoco.group(1).split("//", 1)[-1]
            ruta_xml = ruta_xml.replace("/", "\\")
            ruta_xml = Path(ruta_xml).expanduser().resolve()
            if ruta_xml.exists():
                try:
                    return self._parsear_jacoco_xml(ruta_xml.read_text(encoding="utf-8"))
                except Exception:
                    return {
                        "cobertura_global": 0.0,
                        "por_archivo": [],
                        "estado": "error",
                    }

        # Fallback: formato terminal (pytest-cov / coverage.py)
        return self._parsear_cobertura_term(salida)

    @staticmethod
    def _parsear_cobertura_xml(xml_texto: str) -> dict[str, Any]:
        """Parsea un informe Cobertura XML (dotnet `--collect:\"XPlat Code Coverage\"`)."""
        import xml.etree.ElementTree as ET

        raiz = ET.fromstring(xml_texto)
        por_archivo: list[dict[str, Any]] = []

        for clase in raiz.iter("class"):
            nombre = clase.get("filename", "")
            if not nombre:
                continue
            lineas_faltantes: list[int] = []
            for linea in clase.iter("line"):
                hits = int(linea.get("hits", "0"))
                if hits == 0:
                    lineas_faltantes.append(int(linea.get("number", "0")))
            try:
                cobertura = float(clase.get("line-rate", "0")) * 100
            except ValueError:
                cobertura = 0.0
            por_archivo.append(
                {
                    "ruta_relativa": nombre,
                    "cobertura": round(cobertura, 1),
                    "lineas_faltantes": lineas_faltantes,
                }
            )

        try:
            cobertura_global = float(raiz.get("line-rate", "0")) * 100
        except ValueError:
            cobertura_global = 0.0

        return {
            "cobertura_global": round(cobertura_global, 1),
            "por_archivo": por_archivo,
            "estado": "exito" if por_archivo else "no_ejecutado",
        }

    @staticmethod
    def _parsear_jacoco_xml(xml_texto: str) -> dict[str, Any]:
        """Parsea un informe JaCoCo XML (maven `jacoco:report`)."""
        import xml.etree.ElementTree as ET

        raiz = ET.fromstring(xml_texto)
        por_archivo: list[dict[str, Any]] = []

        for clase in raiz.iter("class"):
            nombre = clase.get("sourcefilename", "")
            if not nombre:
                continue
            # Cobertura por clase a partir de su contador LINE directo
            # (no el de <method>, que solo cubre ese método)
            cobertura = 0.0
            for contador in clase.findall("counter"):
                if contador.get("type") == "LINE":
                    cubiertas = int(contador.get("covered", "0"))
                    perdidas = int(contador.get("missed", "0"))
                    total = cubiertas + perdidas
                    if total > 0:
                        cobertura = cubiertas * 100.0 / total
                    break
            por_archivo.append(
                {
                    "ruta_relativa": nombre,
                    "cobertura": round(cobertura, 1),
                    "lineas_faltantes": [],
                }
            )

        # Cobertura global desde el contador LINE directo del informe (raíz)
        cobertura_global = 0.0
        for contador in raiz.findall("counter"):
            if contador.get("type") == "LINE":
                cubiertas = int(contador.get("covered", "0"))
                perdidas = int(contador.get("missed", "0"))
                total = cubiertas + perdidas
                if total > 0:
                    cobertura_global = cubiertas * 100.0 / total
                break

        return {
            "cobertura_global": round(cobertura_global, 1),
            "por_archivo": por_archivo,
            "estado": "exito" if por_archivo else "no_ejecutado",
        }

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        ruta_raw = parametros.get("ruta", ".")
        comando_cobertura = parametros.get("comando_cobertura", "pytest --cov=src --cov-report=term")

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

        # Validar comando contra allowlist de comandos seguros (SC-011)
        if not self._validar_comando(comando_cobertura):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={},
                error=(
                    f"Comando de cobertura no permitido: '{comando_cobertura}'. "
                    "Solo se permiten comandos de la allowlist segura (SC-011)."
                ),
            )

        ruta = Path(ruta_raw).expanduser().resolve()
        if not ruta.exists():
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos={
                    "cobertura_global": 0.0,
                    "por_archivo": [],
                    "estado": "no_ejecutado",
                },
            )

        # Ejecutar comando
        try:
            cmd_parts = self._normalizar_comando(comando_cobertura)
            resultado_proc = subprocess.run(
                cmd_parts,
                cwd=str(ruta),
                capture_output=True,
                text=True,
                timeout=180,  # Timeout 3 minutos para cobertura
            )
            salida_completa = resultado_proc.stdout + "\n" + resultado_proc.stderr
        except subprocess.TimeoutExpired:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={
                    "cobertura_global": 0.0,
                    "por_archivo": [],
                    "estado": "no_ejecutado",
                },
                error="Timeout: la ejecución de cobertura excedió 180 segundos.",
            )
        except (OSError, subprocess.SubprocessError) as e:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={
                    "cobertura_global": 0.0,
                    "por_archivo": [],
                    "estado": "error",
                },
                error=f"Error ejecutando comando de cobertura: {e}",
            )

        # Parsear salida
        datos = self._parsear_salida(salida_completa, ruta)

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos=datos,
        )