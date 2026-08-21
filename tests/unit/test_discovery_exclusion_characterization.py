"""Caracterización de las políticas de exclusión de descubrimiento (I07).

Antes de centralizar las exclusiones duplicadas entre `Allowlist`,
`explore`, `locate`, `search` y `generate_test_cases`, este módulo fija
mediante fixtures un árbol de directorios "de ruido" representativo y
verifica EXACTAMENTE qué incluye/excluye cada mecanismo hoy (medido
directamente contra el código antes de tocarlo, no supuesto).

Sirve dos propósitos:

1. Caracterización: prueba de regresión para que centralizar no cambie el
   comportamiento observable por accidente, salvo donde se documenta una
   decisión explícita (ruling).
2. Documentación ejecutable de inconsistencias reales descubiertas:

   a) `explore` (y `locate`/`search`, que reutilizan su set de nombres de
      directorio) excluían por nombre de directorio solo
      `{.git, .vs, bin, obj, packages, node_modules}`, mientras que
      `generate_test_cases` excluía además
      `{__pycache__, .venv, venv, .idea, .vscode}`. `locate`/`search`
      además consultan `Allowlist` por archivo, lo que ya les hacía excluir
      `__pycache__`/`.venv` (vía patrones), pero no `venv` (sin punto)
      ni `.idea`/`.vscode`.
   b) `Allowlist.contiene()` (FR-025, mínimo privilegio — Constitución IV)
      no incluía `bin/obj/packages/.vs/.idea/.vscode/venv` en sus patrones
      por defecto, aunque el recorrido de árbol de las demás herramientas ya
      podaba varios de esos nombres. Una ruta explícita dentro de esos
      directorios se consideraba "autorizada" si se consultaba directamente.

   Resolución (ruling I07, ver `docs/improvements/person-4-result.md`):
   unión de los conjuntos — nunca se reduce protección, solo se amplía.
   Los tests marcados "_antes_de_i07" caracterizan el estado previo (deben
   seguir pasando tal cual, documentan el hallazgo); los marcados
   "_post_ruling" caracterizan el estado nuevo tras centralizar.
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.loop import Agent
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.exclusion_policy import es_directorio_excluido
from qa_agent.tools.explore import ExploreHerramienta
from qa_agent.tools.generate_test_cases import GenerateTestCasesHerramienta
from qa_agent.tools.locate import LocateHerramienta
from qa_agent.tools.search import SearchHerramienta

# Directorios de ruido que YA excluían por nombre de directorio tanto
# `explore`/`locate`/`search` como `generate_test_cases` antes de I07 (VCS,
# build .NET, dependencias node). Deben seguir excluidos siempre.
RUIDO_DIRNAME_COMUN = (".git", ".vs", "bin", "obj", "packages", "node_modules")

# Directorios que antes de I07 SOLO excluía `generate_test_cases` por
# nombre de directorio (la inconsistencia descubierta, parte a). Tras I07
# deben excluirse también en `explore`/`locate`/`search`.
RUIDO_DIRNAME_SOLO_GENERATE_ANTES = (".venv", "venv", ".idea", ".vscode", "__pycache__")

TODO_EL_RUIDO_DIRNAME = RUIDO_DIRNAME_COMUN + RUIDO_DIRNAME_SOLO_GENERATE_ANTES

# `dist`/`build`/`.pytest_cache` nunca formaron parte de ningún set de
# nombres de directorio (solo existían como patrones de `Allowlist`, sin
# duplicación real con las otras herramientas) → fuera del alcance del
# ruling de unión de nombres de directorio. `explore` no consulta
# `Allowlist` por archivo, así que sigue "viendo" estos directorios antes Y
# después de I07 (limitación preexistente, no introducida por I07;
# documentada en decisiones, no corregida en este alcance).
RUIDO_SOLO_PATRON_ALLOWLIST = ("dist", "build", ".pytest_cache")


def _primer_segmento(ruta_relativa: str) -> str:
    """Primer componente de una ruta relativa (compatible `/` y `\\`)."""
    return ruta_relativa.replace("\\", "/").split("/", 1)[0]


def _bajo_directorio(rutas: set[str], nombre_directorio: str) -> bool:
    """True si alguna ruta cuelga exactamente del directorio `nombre_directorio`
    (comparación exacta del primer segmento, no prefijo de cadena: evita que
    `.vscode` haga falso positivo con `.vs`)."""
    return any(_primer_segmento(r) == nombre_directorio for r in rutas)


def _crear_arbol_con_ruido(base: Path) -> Path:
    """Crea un proyecto con código real y todos los directorios de ruido."""
    proyecto = base / "proyecto"
    (proyecto / "src").mkdir(parents=True)
    (proyecto / "src" / "app.py").write_text(
        "def hola_real():\n    return 'real'\n", encoding="utf-8"
    )
    for nombre in TODO_EL_RUIDO_DIRNAME + RUIDO_SOLO_PATRON_ALLOWLIST:
        directorio = proyecto / nombre
        directorio.mkdir(parents=True, exist_ok=True)
        (directorio / "ruido.py").write_text(
            "def funcion_ruido():\n    return 'ruido'\n", encoding="utf-8"
        )
    (proyecto / ".env").write_text("SECRET=x\n", encoding="utf-8")
    return proyecto


# --------------------------------------------------------------------------
# explore: recorrido de árbol, poda solo por nombre de directorio (no
# consulta `Allowlist` por cada elemento descubierto, solo para la raíz).
# --------------------------------------------------------------------------


def test_explore_excluye_ruido_comun_antes_de_i07(tmp_path):
    proyecto = _crear_arbol_con_ruido(tmp_path)
    herramienta = ExploreHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar({"ruta": str(proyecto), "profundidad_max": 2})
    nombres = {e["nombre"] for e in resultado.datos["elementos"]}
    for ruido in RUIDO_DIRNAME_COMUN:
        assert ruido not in nombres
    assert "src" in nombres


def test_explore_excluye_ruido_ampliado_post_ruling(tmp_path):
    """Post-I07 (ruling 1): antes de centralizar, `explore` SÍ mostraba
    estos directorios (a diferencia de `generate_test_cases`) — ver
    `test_discovery_exclusion_characterization.py`, commit anterior, y
    `docs/improvements/person-4-result.md`. Tras la unión, `explore`
    también los excluye."""
    proyecto = _crear_arbol_con_ruido(tmp_path)
    herramienta = ExploreHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar({"ruta": str(proyecto), "profundidad_max": 2})
    nombres = {e["nombre"] for e in resultado.datos["elementos"]}
    for ruido in RUIDO_DIRNAME_SOLO_GENERATE_ANTES:
        assert ruido not in nombres
    assert "src" in nombres


def test_explore_sigue_mostrando_ruido_solo_patron_allowlist(tmp_path):
    """`dist`/`build`/`.pytest_cache` nunca estuvieron en el set de nombres
    de directorio de `explore`; fuera del alcance del ruling de unión de
    nombres. Se mantiene igual antes y después de I07 (gap preexistente
    documentado, no introducido por la centralización)."""
    proyecto = _crear_arbol_con_ruido(tmp_path)
    herramienta = ExploreHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar({"ruta": str(proyecto), "profundidad_max": 2})
    nombres = {e["nombre"] for e in resultado.datos["elementos"]}
    for ruido in RUIDO_SOLO_PATRON_ALLOWLIST:
        assert ruido in nombres


# --------------------------------------------------------------------------
# locate: recorrido por rglob, poda por nombre de directorio + `Allowlist`
# por archivo (si se construyó con `rutas_permitidas`).
# --------------------------------------------------------------------------


def test_locate_excluye_ruido_comun_antes_de_i07(tmp_path):
    proyecto = _crear_arbol_con_ruido(tmp_path)
    herramienta = LocateHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron": "funcion_ruido", "ruta": str(proyecto), "tipo": "cualquiera"}
    )
    rutas = {c["ruta_relativa"] for c in resultado.datos["coincidencias"]}
    # `__pycache__`/`.venv` ya se excluían aquí vía patrones de `Allowlist`,
    # aunque no estuvieran en el set de nombres de directorio de `explore`.
    for ruido in RUIDO_DIRNAME_COMUN + ("__pycache__", ".venv") + RUIDO_SOLO_PATRON_ALLOWLIST:
        assert not _bajo_directorio(rutas, ruido)


def test_locate_excluye_venv_idea_vscode_post_ruling(tmp_path):
    """Post-I07 (ruling 1): antes de centralizar, `venv` (sin punto),
    `.idea` y `.vscode` no estaban cubiertos ni por el set de nombres de
    `explore` ni por los patrones por defecto de `Allowlist`. Tras la
    unión, `locate` también los excluye."""
    proyecto = _crear_arbol_con_ruido(tmp_path)
    herramienta = LocateHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron": "funcion_ruido", "ruta": str(proyecto), "tipo": "cualquiera"}
    )
    rutas = {c["ruta_relativa"] for c in resultado.datos["coincidencias"]}
    for ruido in ("venv", ".idea", ".vscode"):
        assert not _bajo_directorio(rutas, ruido)


# --------------------------------------------------------------------------
# search: mismo mecanismo que `locate`.
# --------------------------------------------------------------------------


def test_search_excluye_ruido_comun_antes_de_i07(tmp_path):
    proyecto = _crear_arbol_con_ruido(tmp_path)
    herramienta = SearchHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron_regex": "funcion_ruido", "ruta": str(proyecto)}
    )
    rutas = {o["ruta_relativa"] for o in resultado.datos["ocurrencias"]}
    for ruido in RUIDO_DIRNAME_COMUN + ("__pycache__", ".venv") + RUIDO_SOLO_PATRON_ALLOWLIST:
        assert not _bajo_directorio(rutas, ruido)


def test_search_excluye_venv_idea_vscode_post_ruling(tmp_path):
    """Post-I07 (ruling 1): ver `test_locate_excluye_venv_idea_vscode_post_ruling`."""
    proyecto = _crear_arbol_con_ruido(tmp_path)
    herramienta = SearchHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"patron_regex": "funcion_ruido", "ruta": str(proyecto)}
    )
    rutas = {o["ruta_relativa"] for o in resultado.datos["ocurrencias"]}
    for ruido in ("venv", ".idea", ".vscode"):
        assert not _bajo_directorio(rutas, ruido)


# --------------------------------------------------------------------------
# generate_test_cases: ya excluía el set ampliado antes de I07 (referencia,
# no debe cambiar tras centralizar).
# --------------------------------------------------------------------------


def test_generate_test_cases_excluye_todo_el_ruido(tmp_path):
    proyecto = _crear_arbol_con_ruido(tmp_path)
    herramienta = GenerateTestCasesHerramienta([str(proyecto)])
    resultado = herramienta.ejecutar(
        {"ruta": str(proyecto), "objetivo": "ruido", "cripticidad": "happy_path"}
    )
    fuentes = resultado.datos["fuentes"]
    assert fuentes == []


# --------------------------------------------------------------------------
# Allowlist: patrones gitwildmatch por defecto (mecanismo distinto, se
# consulta también directamente por `locate`/`search`/`generate_test_cases`
# por cada archivo descubierto, y potencialmente por cualquier otra
# herramienta que reciba una ruta arbitraria).
# --------------------------------------------------------------------------

_ALLOWLIST_EXCLUIDOS_ANTES = (".git", "node_modules", ".venv", "__pycache__") + RUIDO_SOLO_PATRON_ALLOWLIST
_ALLOWLIST_FUGA_ANTES = (".vs", "bin", "obj", "packages", "venv", ".idea", ".vscode")


def test_allowlist_excluye_patrones_propios_antes_de_i07(tmp_path):
    proyecto = _crear_arbol_con_ruido(tmp_path)
    allowlist = Allowlist([proyecto])
    for ruido in _ALLOWLIST_EXCLUIDOS_ANTES:
        assert allowlist.contiene(proyecto / ruido / "ruido.py") is False
    assert allowlist.contiene(proyecto / ".env") is False
    assert allowlist.contiene(proyecto / "src" / "app.py") is True


def test_allowlist_excluye_bin_obj_packages_post_ruling(tmp_path):
    """Post-I07 (ruling 2): antes de centralizar, `Allowlist` consideraba
    estas rutas "autorizadas" pese a que el recorrido de árbol de
    `explore`/`generate_test_cases` ya las podaba por nombre — una laguna
    real de mínimo privilegio (Constitución IV / FR-025), porque
    `Allowlist.contiene()` puede consultarse directamente con cualquier
    ruta, sin pasar por esa poda. Tras la unión, `Allowlist` también las
    excluye."""
    proyecto = _crear_arbol_con_ruido(tmp_path)
    allowlist = Allowlist([proyecto])
    for ruido in _ALLOWLIST_FUGA_ANTES:
        assert allowlist.contiene(proyecto / ruido / "ruido.py") is False


# --------------------------------------------------------------------------
# agent.loop.Agent._buscar_archivo_por_nombre / _buscar_directorio_por_nombre
# (T123/T124): hasta la revisión final (I-3), estos dos métodos tenían su
# propia copia inline del set ESTRECHO pre-I07
# (`{.git, .vs, bin, obj, packages, node_modules}`), con docstrings que
# afirmaban paridad con `explore`/`_resolver_capa_real` — cierto cuando se
# escribieron, falso una vez que este módulo amplió el set de `explore`.
# Ambos métodos ahora llaman a
# `qa_agent.tools.exclusion_policy.es_directorio_excluido`, cerrando ese
# cableado cruzado. Estos tests caracterizan el comportamiento post-cierre.
# --------------------------------------------------------------------------


def _agent_sobre(proyecto: Path) -> Agent:
    return Agent(FakeLLM(), herramientas=[], allowlist=Allowlist([proyecto]))


def test_ruido_ampliado_es_directorio_excluido():
    """La política centralizada (consumida ahora también por `loop.py`)
    reconoce el set ampliado post-I07, no solo el estrecho pre-I07."""
    for directorio in RUIDO_DIRNAME_SOLO_GENERATE_ANTES:
        assert es_directorio_excluido(directorio) is True


def test_buscar_archivo_por_nombre_excluye_ruido_ampliado_post_i3(tmp_path):
    proyecto = _crear_arbol_con_ruido(tmp_path)
    agente = _agent_sobre(proyecto)
    # Caso positivo directo: un archivo que SOLO existe bajo `__pycache__`
    # (parte del set ampliado, no del set estrecho pre-I07) no debe
    # encontrarse tras el cierre de cableado.
    solo_en_pycache = proyecto / "__pycache__" / "unico_en_pycache.py"
    solo_en_pycache.write_text("x = 1\n", encoding="utf-8")
    assert agente._buscar_archivo_por_nombre("unico_en_pycache.py") is None
    # Un archivo real fuera de cualquier directorio de ruido sí se encuentra.
    assert agente._buscar_archivo_por_nombre("app.py") is not None


def test_buscar_archivo_por_nombre_sigue_excluyendo_ruido_comun(tmp_path):
    proyecto = _crear_arbol_con_ruido(tmp_path)
    agente = _agent_sobre(proyecto)
    solo_en_bin = proyecto / "bin" / "unico_en_bin.py"
    solo_en_bin.write_text("x = 1\n", encoding="utf-8")
    assert agente._buscar_archivo_por_nombre("unico_en_bin.py") is None


def test_buscar_directorio_por_nombre_excluye_ruido_ampliado_post_i3(tmp_path):
    proyecto = _crear_arbol_con_ruido(tmp_path)
    agente = _agent_sobre(proyecto)
    # `.venv` es en sí mismo un directorio excluido: no debe resolverse
    # como destino (aunque exista físicamente en el árbol de ruido).
    assert agente._buscar_directorio_por_nombre(".venv") is None
    assert agente._buscar_directorio_por_nombre("venv") is None
    assert agente._buscar_directorio_por_nombre(".idea") is None
    assert agente._buscar_directorio_por_nombre(".vscode") is None
    # Un subdirectorio anidado DENTRO de un directorio excluido tampoco debe
    # resolverse, aunque su propio nombre no esté en el set de exclusión.
    anidado = proyecto / "__pycache__" / "subcarpeta_normal"
    anidado.mkdir(parents=True)
    assert agente._buscar_directorio_por_nombre("subcarpeta_normal") is None
    # Un directorio real fuera de cualquier directorio de ruido sí se
    # encuentra.
    assert agente._buscar_directorio_por_nombre("src") is not None


def test_buscar_directorio_por_nombre_sigue_excluyendo_ruido_comun(tmp_path):
    proyecto = _crear_arbol_con_ruido(tmp_path)
    agente = _agent_sobre(proyecto)
    assert agente._buscar_directorio_por_nombre("node_modules") is None
    assert agente._buscar_directorio_por_nombre("bin") is None
