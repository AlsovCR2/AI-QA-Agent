"""Enriquecimiento determinista del plan por capa (I01, ADR-001).

Extraído de `agent/loop.py`: mismos parámetros, misma lógica, mismo
comportamiento observable. Cuando la solicitud pide un análisis exhaustivo
(global, de una capa concreta, o sugerencia de pruebas), el plan que propone
el LLM se complementa de forma determinista con pasos `explore`/`leer_archivo`
/`locate`/`generate_test_cases` que recorren la estructura REAL del proyecto
(FR-024 / FR-049 / VI): el LLM planifica, pero la cobertura mínima la
garantiza el agente sin depender de que el modelo "adivine" el árbol real.

Estas funciones son deterministas y no dependen de estado del `Agent`: reciben
explícitamente el catálogo de herramientas y la ruta base autorizada, lo que
las hace probables de forma aislada (Constitution III). `Agent` conserva
métodos delegadores del mismo nombre para no tocar los puntos de llamada del
bucle ReAct (`_atender_react`).
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.intent_policy import _es_analisis_exhaustivo, _es_intencion_pruebas
from qa_agent.agent.layer_policy import (
    _es_analisis_capa,
    _es_archivo_codigo,
    _extraer_capa_solicitada,
    _resolver_capa_real,
)
from qa_agent.agent.reasoning import PasoDePlan, Plan
from qa_agent.agent.router import extraer_objetivo_cripticidad
from qa_agent.tools.base import EstadoResultado, Herramienta

# Presupuesto de pasos ampliado para análisis exhaustivo (mismo valor que
# `agent/loop.py`, que es quien define la constante pública _PRESUPUESTO_
# ANALISIS_GLOBAL; se importa perezosamente dentro de `presupuesto_pasos`
# para evitar un ciclo de import loop.py -> plan_enrichment.py -> loop.py).


def presupuesto_pasos(texto: str, pasos_max: int, presupuesto_global: int) -> int:
    """Presupuesto de pasos del bucle (SC-016), ampliado para análisis
    exhaustivo (análisis global, sugerencia de pruebas o análisis de una
    capa/carpeta concreta): el plan enriquecido por capa necesita más pasos
    que el mínimo."""
    if _es_analisis_exhaustivo(texto) or _es_analisis_capa(texto):
        return max(pasos_max, presupuesto_global)
    return pasos_max


def plan_ya_explora_capa(plan: Plan, capa: str, ruta_base: str) -> bool:
    """True si el plan ya explora esa capa (misma ruta de raíz)."""
    raiz = str(Path(ruta_base) / capa)
    return any(
        p.herramienta == "explore" and p.parametros.get("ruta") == raiz
        for p in plan.pasos
    )


def plan_ya_lee_archivo(plan: Plan, archivo: str) -> bool:
    """True si el plan ya lee ese archivo (mismo `archivo_relativo`)."""
    return any(
        p.herramienta == "leer_archivo"
        and p.parametros.get("archivo_relativo") == archivo
        for p in plan.pasos
    )


def archivos_codigo_de_capa(
    explore: Herramienta, ruta_base: str, capa: str, max_archivos: int = 2
) -> list[str]:
    """Archivos de código REALES de la capa, relativos a la raíz.

    Descubrimiento determinista con `explore` (FR-024): devuelve los
    archivos que existen, nunca inventados (FR-019).
    """
    try:
        resultado = explore.ejecutar(
            {
                "ruta": str(Path(ruta_base) / capa),
                "profundidad_max": 3,
            }
        )
    except Exception:  # noqa: BLE001
        return []
    if resultado.estado != EstadoResultado.EXITO:
        return []
    archivos = sorted(
        str(Path(capa) / e["ruta_relativa"]).replace("\\", "/")
        for e in (resultado.datos.get("elementos") or [])
        if e.get("tipo") == "archivo"
        and _es_archivo_codigo(e.get("ruta_relativa", ""))
    )
    return archivos[:max_archivos]


def enriquecer_plan_analisis_global(
    plan: Plan | None,
    texto: str,
    herramientas: dict[str, Herramienta],
    ruta_base: str,
) -> Plan | None:
    """Añade pasos deterministas para garantizar cobertura por capa.

    Para una intención de análisis global, detecta con `explore` las capas
    (directorios) de primer nivel REALES de la raíz y añade al plan: un
    `explore` por capa (el listado de todo el árbol se trunca en el
    contexto del LLM) y una lectura (`leer_archivo`) de los archivos de
    código principales de cada capa. El LLM planifica, pero la cobertura
    mínima la garantiza el agente de forma determinista (FR-024 / VI).
    """
    if plan is None or not _es_analisis_exhaustivo(texto):
        return plan
    explore = herramientas.get("explore")
    leer = herramientas.get("leer_archivo")
    if explore is None or leer is None:
        return plan

    try:
        resultado_raiz = explore.ejecutar({"ruta": ruta_base, "profundidad_max": 1})
    except Exception:  # noqa: BLE001 - sin enriquecer ante errores
        return plan
    if resultado_raiz.estado != EstadoResultado.EXITO:
        return plan
    capas = sorted(
        {
            e.get("ruta_relativa", "")
            for e in (resultado_raiz.datos.get("elementos") or [])
            if e.get("tipo") == "directorio" and e.get("ruta_relativa")
        }
    )
    # Capas de primer nivel (ignora directorios ocultos), acotadas para no
    # desbordar el presupuesto de pasos del análisis.
    capas = [c for c in capas if not c.startswith(".")][:4]
    if not capas:
        return plan

    pasos_extra: list[PasoDePlan] = []
    orden = max((p.orden for p in plan.pasos), default=len(plan.pasos))
    for capa in capas:
        if not plan_ya_explora_capa(plan, capa, ruta_base):
            orden += 1
            pasos_extra.append(
                PasoDePlan(
                    orden=orden,
                    razon=(
                        f"explorar la capa real '{capa}' detectada en la "
                        "raíz"
                    ),
                    herramienta="explore",
                    parametros={
                        "ruta": str(Path(ruta_base) / capa),
                        "profundidad_max": 3,
                    },
                    criterio_salida="estructura completa de la capa",
                )
            )
        for archivo in archivos_codigo_de_capa(explore, ruta_base, capa):
            if plan_ya_lee_archivo(plan, archivo):
                continue
            orden += 1
            pasos_extra.append(
                PasoDePlan(
                    orden=orden,
                    razon=(
                        f"leer el código real de '{archivo}' de la capa "
                        f"'{capa}'"
                    ),
                    herramienta="leer_archivo",
                    parametros={
                        "ruta": ruta_base,
                        "archivo_relativo": archivo,
                    },
                    criterio_salida="contenido real del archivo",
                )
            )
    if not pasos_extra:
        return plan
    plan.pasos.extend(pasos_extra)
    plan.pendientes.extend(pasos_extra)
    return plan


def enriquecer_plan_pruebas(
    plan: Plan | None,
    texto: str,
    herramientas: dict[str, Herramienta],
    ruta_base: str,
) -> Plan | None:
    """Añade pasos deterministas para una intención de sugerencia de
    pruebas ("¿qué pruebas podemos aplicar?"): localiza las clases reales
    (`locate`) y genera casos de prueba sugeridos (`generate_test_cases`).

    La cobertura por capa ya la garantiza `enriquecer_plan_analisis_global`
    (se invoca antes y dispara también para estas intenciones). Solo se
    añaden pasos de herramientas presentes en el catálogo y si el plan del
    LLM no los prevé ya (FR-024 / VI).
    """
    if plan is None or not _es_intencion_pruebas(texto):
        return plan
    pasos_extra: list[PasoDePlan] = []
    orden = max((p.orden for p in plan.pasos), default=len(plan.pasos))

    locate = herramientas.get("locate")
    if locate is not None and not any(p.herramienta == "locate" for p in plan.pasos):
        orden += 1
        pasos_extra.append(
            PasoDePlan(
                orden=orden,
                razon=(
                    "localizar las clases reales del proyecto (evidencia "
                    "de qué unidades cubrir con pruebas)"
                ),
                herramienta="locate",
                parametros={
                    "ruta": ruta_base,
                    "patron": r"\bclass\s+\w+",
                    "tipo": "clase",
                },
                criterio_salida="clases reales localizadas",
            )
        )

    generar = herramientas.get("generate_test_cases")
    if generar is not None and not any(
        p.herramienta == "generate_test_cases" for p in plan.pasos
    ):
        objetivo, cripticidad = extraer_objetivo_cripticidad(texto)
        orden += 1
        pasos_extra.append(
            PasoDePlan(
                orden=orden,
                razon="generar casos de prueba sugeridos para la solicitud",
                herramienta="generate_test_cases",
                parametros={
                    "ruta": ruta_base,
                    "objetivo": objetivo,
                    "cripticidad": cripticidad,
                },
                criterio_salida="casos propuestos basados en código real",
            )
        )
    if not pasos_extra:
        return plan
    plan.pasos.extend(pasos_extra)
    plan.pendientes.extend(pasos_extra)
    return plan


def enriquecer_plan_analisis_capa(
    plan: Plan | None,
    texto: str,
    herramientas: dict[str, Herramienta],
    ruta_base: str,
    pasos_max: int,
    presupuesto_global: int,
) -> Plan | None:
    """Añade pasos deterministas para analizar UNA capa/carpeta concreta.

    Para intenciones como "explora todas las clases de la capa DAL", el
    plan del LLM suele quedarse en un subconjunto de archivos (los modelos
    rápidos planifican por convención de nombres, no por el árbol real).
    Se enriquece de forma determinista: `explore` de la capa real + una
    `leer_archivo` por cada archivo de código existente hasta el
    presupuesto de pasos (SC-016), de modo que la cobertura de la capa no
    dependa del plan del LLM (FR-024 / VI).
    Solo actúa si la capa existe realmente (FR-019): nunca inventa rutas.
    """
    if plan is None or not _es_analisis_capa(texto):
        return plan
    explore = herramientas.get("explore")
    leer = herramientas.get("leer_archivo")
    if explore is None or leer is None:
        return plan
    capa = _resolver_capa_real(ruta_base, _extraer_capa_solicitada(texto))
    if not capa:
        return plan

    pasos_extra: list[PasoDePlan] = []
    orden = max((p.orden for p in plan.pasos), default=len(plan.pasos))
    ya_explora = plan_ya_explora_capa(plan, capa, ruta_base)
    if not ya_explora:
        orden += 1
        pasos_extra.append(
            PasoDePlan(
                orden=orden,
                razon=(
                    f"explorar la capa real '{capa}' solicitada por el "
                    "usuario"
                ),
                herramienta="explore",
                parametros={
                    "ruta": str(Path(ruta_base) / capa),
                    "profundidad_max": 3,
                },
                criterio_salida="estructura completa de la capa",
            )
        )
    # Límite adaptativo (SC-016): lee los archivos de la capa que quepan en
    # el presupuesto restante del bucle, sin excederlo. Con el tope fijo
    # (p. ej. 12) la capa DAL real de ReservaHotel quedaba incompleta
    # (TipoPagoDAL.cs y UsuarioDAL.cs nunca se leían).
    presupuesto = presupuesto_pasos(texto, pasos_max, presupuesto_global)
    max_lecturas = max(
        0, presupuesto - len(plan.pasos) - (1 if not ya_explora else 0)
    )
    for archivo in archivos_codigo_de_capa(
        explore, ruta_base, capa, max_archivos=max_lecturas
    ):
        if plan_ya_lee_archivo(plan, archivo):
            continue
        orden += 1
        pasos_extra.append(
            PasoDePlan(
                orden=orden,
                razon=(
                    f"leer el código real de '{archivo}' de la capa "
                    f"'{capa}'"
                ),
                herramienta="leer_archivo",
                parametros={
                    "ruta": ruta_base,
                    "archivo_relativo": archivo,
                },
                criterio_salida="contenido real del archivo",
            )
        )
    if not pasos_extra:
        return plan
    plan.pasos.extend(pasos_extra)
    plan.pendientes.extend(pasos_extra)
    return plan
