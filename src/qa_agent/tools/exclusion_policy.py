"""Política centralizada de exclusión de rutas para las herramientas de
descubrimiento (I07 — mínimo privilegio, Constitución IV).

Antes de este módulo, los mismos directorios "de ruido" (VCS, artefactos de
build, dependencias, entornos virtuales, configuración de IDE) estaban
definidos por separado en `allowlist.py`, `explore.py` y
`generate_test_cases.py` (además de una copia de solo lectura en
`agent/loop.py`, fuera del alcance de este cambio). `locate.py` y
`search.py` reutilizaban únicamente el set de `explore.py`.

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

No incluido en este ruling: `explore.py` no consulta `Allowlist` por cada
elemento descubierto (solo para la ruta raíz), así que sigue sin podar
`dist/`, `build/` ni `.pytest_cache/` durante el recorrido. Es una
limitación preexistente (no introducida por I07) que queda fuera de este
alcance — corregirla requeriría cambiar el algoritmo de recorrido de
`explore.py`, no solo centralizar constantes duplicadas.
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
)


def es_directorio_excluido(nombre: str) -> bool:
    """True si `nombre` (nombre de un directorio, no una ruta completa)
    debe excluirse del recorrido de descubrimiento en cualquier nivel."""
    return nombre in NOMBRES_DIRECTORIO_EXCLUIDOS


def contiene_directorio_excluido(partes: tuple[str, ...] | list[str]) -> bool:
    """True si alguna de las `partes` de una ruta relativa coincide con un
    directorio excluido (usado para filtrar archivos ya descubiertos vía
    `rglob`, cuyo camino completo hay que revisar componente a componente)."""
    return any(parte in NOMBRES_DIRECTORIO_EXCLUIDOS for parte in partes)
