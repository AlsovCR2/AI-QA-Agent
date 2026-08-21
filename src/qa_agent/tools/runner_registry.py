"""Registro declarativo de ecosistemas y sus runners (T223 / FR-122/124).

Antes, la detección vivía en `agent/runner_detection.py` como una cadena de
`if` con un bloque por ecosistema. Añadir JS/TS, Go y Rust habría triplicado esa
cadena y cada nuevo ecosistema habría requerido tocar dos funciones casi
idénticas (pruebas y cobertura). Aquí un ecosistema es **una fila de datos**:
sus marcadores en disco y sus dos comandos.

Reglas que este módulo respeta y que no son negociables:

- **Detección por manifiesto real** (FR-124): un ecosistema se reconoce porque
  existe su archivo de proyecto en disco, nunca por la extensión de los
  archivos que contiene. Un repositorio con un `.py` suelto dentro de un
  proyecto Maven sigue siendo Maven.
- **Todo comando debe estar en la allowlist** (FR-123 / principio IV): este
  módulo elige CUÁL comando usar; `run_tests`/`analyze_coverage` siguen siendo
  quienes validan y ejecutan. Un comando aquí que no esté en sus allowlists es
  un error de programación, y la prueba `test_todo_comando_esta_en_allowlist`
  lo detecta.
- **Este módulo no ejecuta nada** y no toca la red: solo mira si hay archivos.

El orden del registro es la prioridad de desempate en repositorios políglotas.
Se ordena de más específico a más genérico: un proyecto con `pom.xml` Y un
`requirements.txt` de utilidades es un proyecto Java con scripts, no al revés.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qa_agent.tools.exclusion_policy import es_directorio_excluido

# Profundidad máxima a la que se busca un manifiesto. Los manifiestos viven en
# la raíz o a uno o dos niveles (monorepos con `packages/*`); buscar en todo el
# árbol haría que un fixture de prueba enterrado decidiera el ecosistema entero.
PROFUNDIDAD_MAX_MARCADOR = 3


@dataclass(frozen=True)
class Ecosistema:
    """Un ecosistema de pruebas y cómo reconocerlo.

    `marcadores` son patrones glob de nombre de archivo (no rutas). `cobertura`
    es `None` cuando el ecosistema no tiene un comando de cobertura en la
    allowlist: en ese caso se reporta la ausencia en vez de inventar uno
    (FR-019).
    """

    id: str
    nombre: str
    marcadores: tuple[str, ...]
    pruebas: str
    cobertura: str | None


# El orden ES la política de desempate. Ver docstring del módulo.
ECOSISTEMAS: tuple[Ecosistema, ...] = (
    Ecosistema(
        id="dotnet",
        nombre=".NET",
        marcadores=("*.sln", "*.csproj", "*.fsproj", "*.vbproj"),
        pruebas="dotnet test",
        cobertura='dotnet test --collect:"XPlat Code Coverage"',
    ),
    Ecosistema(
        id="maven",
        nombre="Maven",
        marcadores=("pom.xml",),
        pruebas="mvn test",
        cobertura="mvn test jacoco:report",
    ),
    Ecosistema(
        id="gradle",
        nombre="Gradle",
        marcadores=("build.gradle", "settings.gradle", "build.gradle.kts"),
        pruebas="gradle test",
        # Gradle expone cobertura vía JaCoCo, pero el comando depende de cómo
        # esté configurado el build. No se inventa uno: se reporta la ausencia.
        cobertura=None,
    ),
    Ecosistema(
        id="rust",
        nombre="Rust",
        marcadores=("Cargo.toml",),
        pruebas="cargo test",
        # `cargo tarpaulin`/`llvm-cov` son plugins externos que pueden no estar
        # instalados; no se asume su presencia.
        cobertura=None,
    ),
    Ecosistema(
        id="go",
        nombre="Go",
        marcadores=("go.mod",),
        pruebas="go test ./...",
        cobertura="go test ./... -cover",
    ),
    Ecosistema(
        id="node",
        nombre="JavaScript/TypeScript",
        marcadores=("package.json",),
        pruebas="npm test",
        cobertura="npm test -- --coverage",
    ),
    Ecosistema(
        id="python",
        nombre="Python",
        # Último por diseño: es el ecosistema por defecto del agente y sus
        # marcadores (un `pyproject.toml` de utilidades) aparecen a menudo
        # dentro de proyectos de otros lenguajes.
        marcadores=("pyproject.toml", "pytest.ini", "tox.ini", "setup.py", "noxfile.py"),
        pruebas="python -m pytest",
        cobertura="pytest --cov=src --cov-report=term-missing",
    ),
)

#: Ecosistema aplicado cuando ningún manifiesto coincide. Es Python porque es el
#: caso mayoritario del agente y porque `pytest` degrada de forma segura: si no
#: hay pruebas, lo reporta como `sin_pruebas` en vez de fallar.
ECOSISTEMA_POR_DEFECTO = ECOSISTEMAS[-1]


def _hay_marcador(base: Path, patrones: tuple[str, ...]) -> bool:
    """True si algún archivo que case con `patrones` existe bajo `base`.

    Recorre a lo sumo `PROFUNDIDAD_MAX_MARCADOR` niveles y poda los directorios
    de la política de exclusión: un `package.json` dentro de `node_modules` no
    convierte un proyecto en un proyecto Node, y buscar ahí es además el camino
    más rápido a recorrer decenas de miles de archivos.
    """
    if not base.is_dir():
        return False

    pendientes: list[tuple[Path, int]] = [(base, 0)]
    while pendientes:
        directorio, nivel = pendientes.pop()
        try:
            hijos = list(directorio.iterdir())
        except OSError:
            continue
        for hijo in hijos:
            if hijo.is_dir():
                if nivel + 1 <= PROFUNDIDAD_MAX_MARCADOR and not es_directorio_excluido(
                    hijo.name
                ):
                    pendientes.append((hijo, nivel + 1))
                continue
            if any(hijo.match(patron) for patron in patrones):
                return True
    return False


def detectar_ecosistema(ruta: str) -> Ecosistema:
    """Ecosistema del proyecto en `ruta`, por manifiesto real en disco.

    Determinista y sin LLM (VI / SC-010). Si nada coincide devuelve
    `ECOSISTEMA_POR_DEFECTO` en vez de fallar: el agente debe poder intentar
    algo razonable y reportar honestamente el resultado.
    """
    base = Path(ruta).expanduser()
    if not base.exists():
        return ECOSISTEMA_POR_DEFECTO
    for ecosistema in ECOSISTEMAS:
        if _hay_marcador(base, ecosistema.marcadores):
            return ecosistema
    return ECOSISTEMA_POR_DEFECTO


def comando_de_pruebas(ruta: str) -> str:
    """Comando de pruebas del ecosistema detectado (siempre en allowlist)."""
    return detectar_ecosistema(ruta).pruebas


def comando_de_cobertura(ruta: str) -> str | None:
    """Comando de cobertura del ecosistema detectado, o `None` si no hay uno.

    Devolver `None` es deliberado: un ecosistema sin comando de cobertura
    conocido debe reportarse como tal, no recibir un comando de otro lenguaje
    que fallaría de forma confusa (FR-019 / principio IX).
    """
    return detectar_ecosistema(ruta).cobertura
