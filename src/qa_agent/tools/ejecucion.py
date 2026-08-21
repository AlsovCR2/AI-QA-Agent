"""Ejecución portable de subprocesos con metadatos deterministas (T206).

Fuente única de la mecánica de ejecución que comparten `run_tests` y
`analyze_coverage`, y de la taxonomía de causas de FR-106. Antes de este módulo
cada herramienta duplicaba el bloque `subprocess.run` con su propio manejo de
timeout y de errores, y ninguna de las dos podía explicar POR QUÉ no se había
ejecutado algo: solo emitían `estado_global = "no_ejecutado"`, que es
indistinguible entre «no hay pruebas», «el runner no está instalado» y «la
colección falló». Esa ambigüedad era el fallo más común y menos diagnosticable
del agente (FR-105/FR-106, principio IX).

Este módulo NO decide nada sobre autorización ni sobre permisos de ruta: eso
sigue siendo responsabilidad de cada herramienta y del bucle (principio I).
Aquí solo se ejecuta un `argv` ya validado y se describe lo que ocurrió.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Any

from qa_agent.security.redactor import Redactor

# Longitud máxima de las colas de salida conservadas como evidencia. Suficiente
# para el resumen final de cualquier runner conocido sin arrastrar miles de
# líneas de log a la respuesta ni a la traza (VIII).
MAX_COLA_CARACTERES = 2000

# Timeout por defecto de una ejecución de pruebas o cobertura.
TIMEOUT_SEGUNDOS = 120


# --- Taxonomía de causas (FR-106) -----------------------------------------

#: La ejecución ocurrió y produjo un resultado interpretable.
EJECUTADO = ""
#: El binario o módulo del runner no existe en esta máquina.
RUNNER_NO_DISPONIBLE = "runner_no_disponible"
#: El runner corrió pero el proyecto no tiene pruebas que ejecutar.
SIN_PRUEBAS = "sin_pruebas"
#: El runner falló al importar/recolectar antes de ejecutar prueba alguna.
FALLO_DE_COLECCION = "fallo_de_coleccion"
#: La ejecución superó el presupuesto de tiempo.
TIMEOUT = "timeout"
#: El comando no está en la allowlist (IV).
COMANDO_NO_PERMITIDO = "comando_no_permitido"
#: La ruta objetivo no existe o queda fuera del perímetro autorizado.
RUTA_INVALIDA = "ruta_invalida"
#: El runner terminó pero su salida no encaja con ningún formato conocido.
SALIDA_NO_PARSEABLE = "salida_no_parseable"
#: El comando de cobertura corrió pero no se localizó ningún informe.
REPORTE_NO_ENCONTRADO = "reporte_no_encontrado"
#: Fallo del sistema operativo al lanzar el proceso, distinto de los anteriores.
ERROR_DE_EJECUCION = "error_de_ejecucion"

CAUSAS: tuple[str, ...] = (
    EJECUTADO,
    RUNNER_NO_DISPONIBLE,
    SIN_PRUEBAS,
    FALLO_DE_COLECCION,
    TIMEOUT,
    COMANDO_NO_PERMITIDO,
    RUTA_INVALIDA,
    SALIDA_NO_PARSEABLE,
    REPORTE_NO_ENCONTRADO,
    ERROR_DE_EJECUCION,
)

#: `exit_code` cuando el proceso nunca llegó a arrancar. Se usa un centinela
#: explícito en vez de `None` para que el campo tenga siempre el mismo tipo y
#: el esquema no necesite una unión (VII).
SIN_EJECUTAR = -1

_REDACTOR = Redactor()


# --- Detección de runner ---------------------------------------------------

# Prefijo de comando → nombre canónico del runner. El orden importa: se toma la
# primera coincidencia por prefijo más largo, de modo que "python -m pytest"
# gane sobre "python".
_RUNNERS: tuple[tuple[str, str], ...] = (
    ("python -m pytest", "pytest"),
    ("python -m coverage", "coverage"),
    ("coverage", "coverage"),
    ("pytest", "pytest"),
    ("dotnet", "dotnet"),
    ("mvn", "maven"),
    ("gradle", "gradle"),
    ("./gradlew", "gradle"),
    ("gradlew", "gradle"),
    ("npm", "npm"),
    ("yarn", "yarn"),
    ("pnpm", "pnpm"),
    ("go", "go"),
    ("cargo", "cargo"),
)


def detectar_runner_de_comando(comando: str) -> str:
    """Nombre canónico del runner implicado por `comando`.

    Determinista y sin tocar el disco: describe lo que el comando ES, no lo que
    hay instalado. Devuelve `"desconocido"` si no coincide con ninguno conocido.
    """
    normalizado = " ".join((comando or "").strip().split())
    for prefijo, nombre in _RUNNERS:
        if normalizado == prefijo or normalizado.startswith(prefijo + " "):
            return nombre
    return "desconocido"


# --- Metadatos -------------------------------------------------------------


@dataclass(frozen=True)
class MetadatosDeEjecucion:
    """Qué pasó al intentar ejecutar un comando (FR-105).

    Todos los campos son deterministas salvo `duracion_ms`, que es la única
    magnitud temporal y por eso se excluye de las comparaciones de determinismo
    (VI / SC-010).
    """

    exit_code: int = SIN_EJECUTAR
    runner_detectado: str = "desconocido"
    duracion_ms: int = 0
    stdout_tail: str = ""
    stderr_tail: str = ""
    causa_no_ejecutado: str = EJECUTADO

    def como_dict(self) -> dict[str, Any]:
        """Representación plana para incorporar al resultado de una herramienta."""
        return {
            "exit_code": self.exit_code,
            "runner_detectado": self.runner_detectado,
            "duracion_ms": self.duracion_ms,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "causa_no_ejecutado": self.causa_no_ejecutado,
        }

    def con_causa(self, causa: str) -> MetadatosDeEjecucion:
        """Copia con otra causa; el resto de la evidencia se conserva."""
        return MetadatosDeEjecucion(
            exit_code=self.exit_code,
            runner_detectado=self.runner_detectado,
            duracion_ms=self.duracion_ms,
            stdout_tail=self.stdout_tail,
            stderr_tail=self.stderr_tail,
            causa_no_ejecutado=causa,
        )


def metadatos_sin_ejecutar(causa: str, comando: str = "") -> MetadatosDeEjecucion:
    """Metadatos de un intento que nunca llegó a lanzar el proceso."""
    return MetadatosDeEjecucion(
        exit_code=SIN_EJECUTAR,
        runner_detectado=detectar_runner_de_comando(comando),
        duracion_ms=0,
        causa_no_ejecutado=causa,
    )


def cola_redactada(texto: str, maximo: int = MAX_COLA_CARACTERES) -> str:
    """Últimos `maximo` caracteres de `texto`, con los secretos ya redactados.

    La redacción se aplica ANTES de que el texto salga de este módulo, porque
    la cola acaba en la respuesta visible, en el historial y en la traza
    (FR-108 / principio XI). Se recorta primero y se redacta después para no
    pagar el coste de redactar megabytes de log.
    """
    if not texto:
        return ""
    recorte = texto[-maximo:] if len(texto) > maximo else texto
    return str(_REDACTOR.redactar(recorte))


# --- Ejecución -------------------------------------------------------------


def ejecutar_comando(
    argv: list[str],
    cwd: str,
    *,
    comando_original: str = "",
    timeout: int = TIMEOUT_SEGUNDOS,
) -> tuple[subprocess.CompletedProcess[str] | None, MetadatosDeEjecucion]:
    """Ejecuta `argv` en `cwd` y describe el intento.

    Siempre con `shell=False` (principio IV): `argv` ya viene tokenizado y
    validado contra la allowlist por la herramienta que llama.

    Devuelve `(proceso, metadatos)`. `proceso` es `None` cuando no se llegó a
    ejecutar, y en ese caso `metadatos.causa_no_ejecutado` explica por qué:
    un binario ausente se reporta como `runner_no_disponible` en vez de como un
    error genérico, que era exactamente la confusión que producía el literal
    `python` inexistente en macOS (FR-101/FR-106).
    """
    runner = detectar_runner_de_comando(comando_original or " ".join(argv))
    inicio = time.monotonic()

    def _transcurrido() -> int:
        return int((time.monotonic() - inicio) * 1000)

    try:
        proceso = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as expirado:
        return None, MetadatosDeEjecucion(
            exit_code=SIN_EJECUTAR,
            runner_detectado=runner,
            duracion_ms=_transcurrido(),
            stdout_tail=cola_redactada(_texto(expirado.stdout)),
            stderr_tail=cola_redactada(_texto(expirado.stderr)),
            causa_no_ejecutado=TIMEOUT,
        )
    except FileNotFoundError:
        # El binario o el módulo del runner no existe en esta máquina. Es una
        # causa propia y accionable ("instala pytest"), no un error opaco.
        return None, MetadatosDeEjecucion(
            exit_code=SIN_EJECUTAR,
            runner_detectado=runner,
            duracion_ms=_transcurrido(),
            causa_no_ejecutado=RUNNER_NO_DISPONIBLE,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, MetadatosDeEjecucion(
            exit_code=SIN_EJECUTAR,
            runner_detectado=runner,
            duracion_ms=_transcurrido(),
            stderr_tail=cola_redactada(str(error)),
            causa_no_ejecutado=ERROR_DE_EJECUCION,
        )

    return proceso, MetadatosDeEjecucion(
        exit_code=proceso.returncode,
        runner_detectado=runner,
        duracion_ms=_transcurrido(),
        stdout_tail=cola_redactada(_texto(proceso.stdout)),
        stderr_tail=cola_redactada(_texto(proceso.stderr)),
        causa_no_ejecutado=EJECUTADO,
    )


def _texto(valor: Any) -> str:
    """Normaliza a `str` una salida capturada que puede venir en bytes o `None`."""
    if valor is None:
        return ""
    if isinstance(valor, bytes):
        return valor.decode("utf-8", errors="replace")
    return str(valor)


# --- Clasificación de la salida -------------------------------------------

# Marcas textuales con las que los runners conocidos anuncian "no había nada
# que ejecutar". Se comparan en minúsculas sobre la salida combinada.
_MARCAS_SIN_PRUEBAS: tuple[str, ...] = (
    "no tests ran",
    "collected 0 items",
    "no tests found",
    "no test is available",
    "no test files",
    "there are no tests to run",
    "no tests to run",
)

# Marcas de fallo ANTES de ejecutar una sola prueba (import, configuración,
# recolección). Distinto de "hay pruebas y fallaron".
_MARCAS_FALLO_COLECCION: tuple[str, ...] = (
    "error collecting",
    "errors during collection",
    "importerror",
    "modulenotfounderror",
    "collection failure",
    "usage error",
)


def clasificar_salida(salida: str) -> str:
    """Causa deducible del texto de salida, o `EJECUTADO` si no la hay.

    El orden es deliberado: un fallo de colección puede coexistir con
    "collected 0 items", y la causa accionable es el fallo, no la ausencia.
    """
    normalizada = (salida or "").lower()
    if any(marca in normalizada for marca in _MARCAS_FALLO_COLECCION):
        return FALLO_DE_COLECCION
    if any(marca in normalizada for marca in _MARCAS_SIN_PRUEBAS):
        return SIN_PRUEBAS
    return EJECUTADO
