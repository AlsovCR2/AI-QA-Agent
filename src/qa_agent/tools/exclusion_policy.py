"""Política centralizada de exclusión de rutas para las herramientas de
descubrimiento (I07 — mínimo privilegio, Constitución IV).

Antes de este módulo, los mismos directorios "de ruido" (VCS, artefactos de
build, dependencias, entornos virtuales, configuración de IDE) estaban
definidos por separado en `allowlist.py`, `explore.py` y
`generate_test_cases.py` (además de una copia de solo lectura en
`agent/loop.py`, inicialmente fuera del alcance de este cambio — cableado
más tarde, ver nota "Cierre de cableado (I-3)" al final de este docstring).
`locate.py` y `search.py` reutilizaban únicamente el set de `explore.py`.

Este módulo unifica esas definiciones en un único lugar. Conviven dos
mecanismos porque resuelven problemas distintos:

- `NOMBRES_DIRECTORIO_EXCLUIDOS`: nombres de directorio que se excluyen en
  cualquier nivel del árbol durante el recorrido (poda de `Path.iterdir`/
  `Path.rglob`, comparando solo el nombre del directorio). Lo consumen
  `explore`, `locate`, `search` y `generate_test_cases`.
- `PATRONES_EXCLUSION_ALLOWLIST`: patrones estilo `.gitignore`
  (`gitwildmatch`, vía `pathspec`) que usa `Allowlist.contiene()` para
  decidir si una ruta arbitraria está autorizada dentro del perímetro
  (FR-025). Es el mecanismo de autorización real y puede consultarse con
  cualquier ruta, no solo durante un recorrido de árbol.

RULINGS (I07) — inconsistencias descubiertas al centralizar, documentadas
también en `docs/improvements/person-4-result.md`:

1. Antes de centralizar, `explore.py` (y por tanto `locate.py`/`search.py`,
   que reutilizaban su set) excluían por nombre de directorio solo
   `{.git, .vs, bin, obj, packages, node_modules}`, mientras que
   `generate_test_cases.py` excluía además
   `{__pycache__, .venv, venv, .idea, .vscode}`. Es una inconsistencia
   genuina entre herramientas con el mismo propósito (podar directorios que
   no son código fuente real). Resolución: unión de ambos conjuntos — nunca
   se reduce protección, solo se amplía. Verificado contra la suite de tests
   existente (incluida la caracterización de
   `test_discovery_exclusion_characterization.py`) que ningún test dependía
   de la exclusión más estrecha.
2. El set de patrones por defecto de `Allowlist` no incluía
   `bin/obj/packages/.vs/.idea/.vscode` ni `venv/` (sin punto), pese a que
   el recorrido de árbol de las demás herramientas ya podaba esos nombres.
   Dado que `Allowlist.contiene()` es el mecanismo de autorización de
   mínimo privilegio y puede consultarse directamente con una ruta
   arbitraria (sin pasar por la poda del recorrido), esa laguna permitía
   que una ruta explícita dentro de esos directorios se considerara
   "autorizada". Resolución: unión — se añaden como patrones de directorio,
   preservando también los patrones exclusivos de `Allowlist` (`*.pyc`,
   `dist/`, `build/`, `.pytest_cache/`, `.env`) que no tienen equivalente
   en `NOMBRES_DIRECTORIO_EXCLUIDOS` (nunca estuvieron duplicados en otro
   archivo, están fuera del alcance de la unión de nombres de directorio).

Cierre de la laguna declarada (T211, FR-126): la versión anterior de este
docstring dejaba constancia de que `explore.py` no podaba `dist/`, `build/`
ni `.pytest_cache/` durante el recorrido, porque solo consulta `Allowlist`
para la ruta raíz. Resultó no necesitar ningún cambio de algoritmo: bastaba
con que esos nombres estuvieran en `NOMBRES_DIRECTORIO_EXCLUIDOS`, que es lo
que `explore`/`locate`/`search` ya consultan por cada descendiente. Ver
RULING 3 abajo. La laguna queda cerrada.

Cierre de cableado (I-3, revisión final post-integración): `agent/loop.py`
mantenía dos copias inline del set estrecho pre-I07
(`{.git, .vs, bin, obj, packages, node_modules}`) en
`Agent._buscar_archivo_por_nombre` / `_buscar_directorio_por_nombre`, con
comentarios que afirmaban paridad con `explore`/`_resolver_capa_real` — cierto
cuando se escribieron, falso después de que este módulo ampliara el set de
`explore`. Ambos puntos ahora llaman a `es_directorio_excluido()` (arriba),
por lo que `loop.py` usa exactamente la misma política que
`explore`/`locate`/`search`/`generate_test_cases`. Esto amplía lo que
`loop.py` excluía (añade `__pycache__`, `.venv`, `venv`, `.idea`, `.vscode`),
consistente con la decisión de unión-nunca-reducción del RULING 1 anterior.
"""

from __future__ import annotations

# Nombres de directorio que nunca son código fuente real ni aportan
# información de estructura: VCS, artefactos de build, entornos virtuales,
# dependencias y configuración de IDE. Se excluyen en cualquier nivel del
# árbol (T094 / UC-002). Ver RULING 1 en el docstring del módulo.
NOMBRES_DIRECTORIO_EXCLUIDOS: frozenset[str] = frozenset(
    {
        ".git",
        ".vs",
        ".idea",
        ".vscode",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        "bin",
        "obj",
        "packages",
        # Añadidos por T211 (FR-126). RULING 3: `dist`, `build` y
        # `.pytest_cache` ya estaban en PATRONES_EXCLUSION_ALLOWLIST, es decir,
        # una ruta dentro de ellos YA se consideraba no autorizada — pero el
        # recorrido de árbol no los podaba, así que `explore`/`locate`/`search`
        # los recorrían igualmente y gastaban presupuesto listando artefactos.
        # Esa es exactamente la laguna que el docstring declaraba pendiente.
        # Añadirlos aquí no amplía lo prohibido: alinea el recorrido con la
        # autorización que ya existía.
        "dist",
        "build",
        ".pytest_cache",
        # RULING 4: salidas de cobertura y cachés de herramientas de calidad.
        # No son código fuente y su volumen (un HTML por archivo medido) domina
        # cualquier exploración. `coverage` como nombre de directorio es una
        # salida de herramienta, no un paquete: un paquete Python se llamaría
        # `coverage/` solo en el propio proyecto coverage.py, que no es un
        # objetivo realista de análisis para este agente.
        "htmlcov",
        "coverage",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        # RULING 5: directorio de build de Maven y de Cargo. Se añade junto con
        # el soporte de esos ecosistemas (T223): sin esto, analizar un proyecto
        # Java o Rust compilado recorrería miles de clases y artefactos.
        "target",
    }
)

# Patrones de exclusión por defecto de `Allowlist` (gitwildmatch/pathspec).
# Mecanismo distinto de `NOMBRES_DIRECTORIO_EXCLUIDOS`: aquí se matchea la
# ruta relativa completa contra patrones estilo `.gitignore`. Ver RULING 2.
PATRONES_EXCLUSION_ALLOWLIST: tuple[str, ...] = (
    ".git/",
    "__pycache__/",
    "*.pyc",
    ".venv/",
    "venv/",
    "node_modules/",
    "dist/",
    "build/",
    ".pytest_cache/",
    ".env",
    "bin/",
    "obj/",
    "packages/",
    ".vs/",
    ".idea/",
    ".vscode/",
    # Contrapartida en el mecanismo de autorización de los nombres añadidos por
    # T211 (RULING 3–5): lo que no se recorre tampoco debe poder consultarse
    # como ruta explícita autorizada.
    "htmlcov/",
    "coverage/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".tox/",
    "target/",
)


def es_directorio_excluido(nombre: str) -> bool:
    """True si `nombre` (nombre de un directorio, no una ruta completa)
    debe excluirse del recorrido de descubrimiento en cualquier nivel.

    Usado por `explore`/`locate`/`search`/`generate_test_cases` y por
    `agent.loop.Agent._buscar_archivo_por_nombre` /
    `_buscar_directorio_por_nombre` (I-3, cierre del cableado I07)."""
    return nombre in NOMBRES_DIRECTORIO_EXCLUIDOS
