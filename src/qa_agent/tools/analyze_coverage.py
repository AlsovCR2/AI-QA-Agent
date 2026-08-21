"""Herramienta `analyze_coverage`: ejecuta el comando de cobertura autorizado
(allowlist) y reporta cobertura real (FR-017/018/019, FR-025).

Solo ejecuta comandos de cobertura autorizados (FR-025, SC-011).
Reporta cobertura real (FR-019); si no puede ejecutarse
(`estado == no_ejecutado`), se informa explícitamente (FR-017/018).
Determinística (VI / SC-010).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)
from qa_agent.tools.ejecucion import (
    CAUSAS,
    COMANDO_NO_PERMITIDO,
    EJECUTADO,
    ERROR_DE_EJECUCION,
    REPORTE_NO_ENCONTRADO,
    RUNNER_NO_DISPONIBLE,
    RUTA_INVALIDA,
    SIN_PRUEBAS,
    TIMEOUT,
    MetadatosDeEjecucion,
    clasificar_salida,
    ejecutar_comando,
    metadatos_sin_ejecutar,
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
    # JS/TS: se delega en el script del proyecto igual que en `run_tests`.
    "npm test -- --coverage",
    "npm run coverage",
    "yarn test --coverage",
    "pnpm test --coverage",
    # Go: cobertura integrada en la toolchain.
    "go test ./... -cover",
    "go test ./... -coverprofile=coverage.out",
}


# Cobertura ejecuta toda la suite además de instrumentarla: necesita más
# presupuesto de tiempo que `run_tests`.
TIMEOUT_COBERTURA_SEGUNDOS = 180


def _datos_sin_cobertura(
    metadatos: MetadatosDeEjecucion, estado: str
) -> dict[str, Any]:
    """Resultado sin cobertura medida, acompañado de la causa (FR-107)."""
    return {
        "cobertura_global": 0.0,
        "por_archivo": [],
        "estado": estado,
        **metadatos.como_dict(),
    }


_MENSAJE_POR_CAUSA = {
    TIMEOUT: "Timeout: la ejecución de cobertura excedió el tiempo permitido.",
    RUNNER_NO_DISPONIBLE: (
        "La herramienta de cobertura no está disponible en este entorno; "
        "la cobertura no se midió."
    ),
    ERROR_DE_EJECUCION: "Error del sistema al ejecutar el comando de cobertura.",
    RUTA_INVALIDA: "La ruta del proyecto no es válida; la cobertura no se ejecutó.",
    COMANDO_NO_PERMITIDO: "El comando de cobertura no está permitido.",
    REPORTE_NO_ENCONTRADO: (
        "El comando de cobertura terminó correctamente pero no se localizó "
        "ningún informe de cobertura que analizar."
    ),
    SIN_PRUEBAS: (
        "El comando de cobertura se ejecutó pero el proyecto no tiene pruebas "
        "que medir."
    ),
}


def _ruta_desde_referencia(referencia: str) -> Path | None:
    """Convierte una referencia de reporte impresa por un runner en una `Path`.

    Los plugins de cobertura anuncian el informe generado de formas distintas:
    ruta desnuda (`target/site/jacoco/jacoco.xml`), URI POSIX
    (`file:///home/u/p/jacoco.xml`) o URI de Windows
    (`file:///C:/proj/jacoco.xml`). Se normaliza el esquema `file:` y se deja
    que `Path` interprete los separadores de forma nativa: reescribir `/` a `\\`
    incondicionalmente resolvía solo en Windows (FR-102).

    Devuelve `None` si la referencia no puede interpretarse como ruta.
    """
    texto = referencia.strip().strip("'\"")
    if not texto:
        return None
    if texto.lower().startswith("file:"):
        partes = urlparse(texto)
        ruta = unquote(partes.path)
        if re.fullmatch(r"[A-Za-z]:", partes.netloc or ""):
            # "file://C:/proj/…" — algunos plugins de Windows emiten la letra
            # de unidad como autoridad del URI.
            ruta = f"{partes.netloc}{ruta}"
        elif re.match(r"^/[A-Za-z]:", ruta):
            # "file:///C:/proj/…" — la barra inicial delante de la letra de
            # unidad es espuria fuera del URI.
            ruta = ruta[1:]
        texto = ruta
    if not texto:
        return None
    try:
        return Path(texto).expanduser()
    except (OSError, ValueError):
        return None


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
            # Metadatos de ejecución (T209 / FR-107). Aditivos: no entran en
            # `required` para preservar la compatibilidad de ADR-002 (FR-109).
            "exit_code": {"type": "integer"},
            "runner_detectado": {"type": "string"},
            "duracion_ms": {"type": "integer"},
            "stdout_tail": {"type": "string"},
            "stderr_tail": {"type": "string"},
            "causa_no_ejecutado": {"type": "string", "enum": list(CAUSAS)},
        },
        "required": ["cobertura_global", "por_archivo", "estado"],
    }
    # Obtener cobertura ejecuta código del repositorio objetivo; aplica la
    # misma frontera humana que run_tests (FR-015/016, principio V).
    requiere_autorizacion = True

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
        # `&&` no es un operador cuando se ejecuta con shell=False (IV): sería
        # un argumento literal para pytest. Los comandos compuestos de la
        # allowlist se recortan a su primer tramo, que es el que produce los
        # datos de cobertura; el segundo (`coverage report`) solo re-imprime lo
        # ya medido y su ausencia se cubre por el parseo del informe XML.
        if "&&" in cmd:
            cmd = cmd.split("&&", 1)[0].strip()
        # Igual que en `run_tests`: se usa el intérprete ACTUAL, nunca el
        # literal "python", que no existe en macOS ni en distribuciones que
        # solo instalan `python3` (FR-101).
        if cmd.startswith("pytest "):
            partes = cmd.split()
            return [sys.executable, "-m"] + partes
        elif cmd.startswith("coverage "):
            # coverage puede no estar disponible como comando directo
            partes = cmd.split()
            return [sys.executable, "-m"] + partes
        elif cmd.startswith("python -m pytest"):
            return [sys.executable] + cmd.split()[1:]
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
                # Los grupos 2 y 3 (sentencias totales y no cubiertas) los
                # captura el patrón para anclar el formato de la tabla, pero el
                # esquema de salida solo expone el porcentaje y las líneas
                # faltantes; no se ligan a variables para no sugerir que se usan.
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

        # maven: localizar jacoco.xml. Se intenta primero la referencia impresa
        # en la salida (`file://<ruta>/jacoco.xml`) y, si no resuelve, la
        # ubicación convencional del plugin bajo la raíz del proyecto. La
        # referencia del stdout NO se reescribe cambiando separadores: eso solo
        # funcionaba en Windows y rompía la resolución en POSIX (FR-102).
        candidatos: list[Path] = []
        m_jacoco = re.search(r"([^\s]+jacoco\.xml)", salida)
        if m_jacoco:
            referencia = _ruta_desde_referencia(m_jacoco.group(1))
            if referencia is not None:
                candidatos.append(referencia)
        candidatos.append(ruta_proyecto / "target" / "site" / "jacoco" / "jacoco.xml")

        for ruta_xml in candidatos:
            if not ruta_xml.exists():
                continue
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
                datos=metadatos_sin_ejecutar(
                    RUTA_INVALIDA, comando_cobertura
                ).como_dict(),
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
                datos=metadatos_sin_ejecutar(
                    COMANDO_NO_PERMITIDO, comando_cobertura
                ).como_dict(),
                error=(
                    f"Comando de cobertura no permitido: '{comando_cobertura}'. "
                    "Solo se permiten comandos de la allowlist segura (SC-011)."
                ),
            )

        ruta = Path(ruta_raw).expanduser().resolve()
        if not ruta.exists():
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos=_datos_sin_cobertura(
                    metadatos_sin_ejecutar(RUTA_INVALIDA, comando_cobertura),
                    "no_ejecutado",
                ),
                error="La ruta del proyecto no existe; la cobertura no se ejecutó.",
            )

        proceso, metadatos = ejecutar_comando(
            self._normalizar_comando(comando_cobertura),
            cwd=str(ruta),
            comando_original=comando_cobertura,
            timeout=TIMEOUT_COBERTURA_SEGUNDOS,
        )

        if proceso is None:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos=_datos_sin_cobertura(metadatos, "no_ejecutado"),
                error=_MENSAJE_POR_CAUSA.get(
                    metadatos.causa_no_ejecutado,
                    "La cobertura no se ejecutó.",
                ),
            )

        salida_completa = proceso.stdout + "\n" + proceso.stderr

        # Parsear salida
        datos = self._parsear_salida(salida_completa, ruta)

        causa_textual = clasificar_salida(salida_completa)
        if (
            datos.get("estado") == "no_ejecutado"
            and causa_textual == SIN_PRUEBAS
            and proceso.returncode in {0, 5}
        ):
            # El comando corrió correctamente; simplemente no había pruebas que
            # medir. Es un éxito con causa explícita, no un fallo (FR-107).
            datos.update(metadatos.con_causa(SIN_PRUEBAS).como_dict())
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.EXITO,
                datos=datos,
            )

        if proceso.returncode != 0 or datos.get("estado") != "exito":
            # Se distingue "el comando falló" de "el comando corrió pero no se
            # localizó ningún informe de cobertura" (FR-107): antes ambos casos
            # colapsaban en el mismo `estado: "error"` sin causa.
            if proceso.returncode != 0:
                causa = causa_textual if causa_textual else ERROR_DE_EJECUCION
            else:
                causa = REPORTE_NO_ENCONTRADO
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos=_datos_sin_cobertura(metadatos.con_causa(causa), "error"),
                error=_MENSAJE_POR_CAUSA.get(
                    causa,
                    (
                        "La ejecución de cobertura no produjo un resultado "
                        f"compatible (returncode={proceso.returncode})."
                    ),
                ),
            )

        datos.update(metadatos.con_causa(EJECUTADO).como_dict())
        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos=datos,
        )
