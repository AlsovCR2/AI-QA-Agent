"""Política determinista de detección de intención exhaustiva (I02).

Extraído de `agent/loop.py` como movimiento puro (Constitution X / XII): mismas
frases, mismos regex, mismo comportamiento observable. Ninguna semántica
cambia — solo la responsabilidad queda aislada en su propio módulo, separada
de la orquestación del bucle agente-herramienta.

Cubre dos intenciones que el agente trata como análisis exhaustivo (FR-049):
- Análisis global del proyecto completo (`_es_analisis_global`).
- Sugerencia/definición de pruebas (`_es_intencion_pruebas`).

Ambas heurísticas son deterministas sobre el texto normalizado de la
solicitud (sin LLM, VI / SC-010): el agente las usa para ampliar el
presupuesto de pasos y enriquecer el plan por capa de forma determinista, en
vez de depender únicamente de un plan superficial del LLM.
"""

from __future__ import annotations

# Análisis global del proyecto (FR-049): presupuesto ampliado de pasos y
# frases que lo disparan. Para estas solicitudes el agente no depende solo del
# plan del LLM: enriquece el plan de forma determinista para recorrer las
# capas reales del proyecto (FR-024 / VI).
# Cubre las variantes más comunes: "analiza/explica/describe la estructura",
# "qué capas hay", "cómo está organizado", etc. (T120: el detector era sensible
# a la frase exacta — "analiza la estructura del proyecto" no disparaba el
# enriquecimiento y el plan del flash quedaba superficial).
# Equivalentes en inglés (T226 / FR-128). El detector era exclusivamente en
# español, así que una pregunta en inglés no ampliaba el presupuesto de pasos ni
# disparaba el enriquecimiento por capa: el agente respondía con un plan
# superficial sin ninguna señal de que había entendido peor la pregunta.
_FRASES_ANALISIS_GLOBAL_EN = (
    "analyze the project",
    "analyze this project",
    "analyze the code",
    "analyze the codebase",
    "analyze the repository",
    "analyze the structure",
    "analyze the architecture",
    "full analysis",
    "complete analysis",
    "explore the project",
    "explore the structure",
    "project structure",
    "overall structure",
    "explain the structure",
    "explain the architecture",
    "describe the project",
    "describe the structure",
    "how is the project organized",
    "how is this project organized",
    "what layers",
    "walk me through the project",
    "give me an overview",
    "overview of the project",
)

_FRASES_ANALISIS_GLOBAL = (
    "analiza el proyecto",
    "analiza el código",
    "analiza el repositorio",
    "analiza todo el proyecto",
    "analiza este proyecto",
    "analiza la estructura",
    "analiza la estructura del proyecto",
    "analiza la arquitectura",
    "analiza la organización",
    "analiza la organizacion",
    "análisis completo",
    "analisis completo",
    "análisis de la estructura",
    "analisis de la estructura",
    "explora el proyecto",
    "explora todo el proyecto",
    "explora la estructura",
    "explora la estructura del proyecto",
    "estructura completa",
    "estructura del proyecto",
    "explica la estructura",
    "explica la estructura del proyecto",
    # Hueco detectado por los tests parametrizados de T226: la lista tenía
    # "analiza la arquitectura" y "describe la arquitectura", pero no la
    # variante con "explica", que es igual de común.
    "explica la arquitectura",
    "explica el proyecto",
    "explica la organización",
    "explica la organizacion",
    "describe el proyecto",
    "describe la estructura",
    "describe la arquitectura",
    "qué capas hay",
    "que capas hay",
    "cuáles son las capas",
    "cuales son las capas",
    "las capas del proyecto",
    "cómo está organizado",
    "como esta organizado",
    "cómo está organizado el proyecto",
    "como esta organizado el proyecto",
    "organización del proyecto",
    "organizacion del proyecto",
    "distribución por capas",
    "distribucion por capas",
    "revisa el proyecto",
    "revisa todo el proyecto",
    "dime la estructura",
    "cuál es la estructura",
    "cual es la estructura",
    "arquitectura del proyecto",
)

# Intenciones de sugerencia de pruebas ("¿qué pruebas podemos aplicar?"): se
# tratan como análisis exhaustivo (T121). Amplían el presupuesto de pasos,
# garantizan la cobertura por capa y añaden `locate` de clases reales +
# `generate_test_cases`, para que la respuesta no dependa solo de un plan
# superficial del LLM.
# Equivalentes en inglés de la intención de pruebas (T226 / FR-128).
_FRASES_INTENCION_PRUEBAS_EN = (
    "what kind of tests",
    "what type of tests",
    "types of tests",
    "which tests",
    "what tests should",
    "what tests would",
    "test cases for",
    "test strategy",
    "testing strategy",
    "how should i test",
    "how do i test",
    "how to test the project",
    "suggest tests",
    "recommend tests",
    "propose tests",
    "what should i cover with tests",
)

_FRASES_INTENCION_PRUEBAS = (
    "qué tipo de pruebas",
    "que tipo de pruebas",
    "tipos de pruebas",
    "qué pruebas podemos",
    "que pruebas podemos",
    "qué pruebas aplicar",
    "que pruebas aplicar",
    "qué pruebas recomiendas",
    "que pruebas recomiendas",
    "qué pruebas harías",
    "que pruebas harías",
    "qué pruebas hacer",
    "que pruebas hacer",
    "qué pruebas crear",
    "que pruebas crear",
    "qué pruebas sugerir",
    "que pruebas sugerir",
    "qué casos de prueba",
    "que casos de prueba",
    "casos de prueba para",
    "casos de prueba al",
    "cómo probar el proyecto",
    "como probar el proyecto",
    "cómo probar este proyecto",
    "como probar este proyecto",
    "cómo probar el código",
    "como probar el codigo",
    "estrategia de pruebas",
    "qué cubrir con pruebas",
    "que cubrir con pruebas",
    "pruebas al proyecto",
    "pruebas para el proyecto",
    # Definición/redacción de pruebas y cobertura (T123): "procede a definir
    # las pruebas unitarias y cobertura de la capa DAL", "define las pruebas
    # unitarias en UnitTest.md", "el porcentaje de cobertura", etc. Sin estos
    # términos, la intención de escritura de pruebas no disparaba el
    # enriquecimiento determinista y el LLM planificaba rutas inventadas
    # ("Datos"/"Negocio" en vez de la capa DAL real).
    "pruebas unitarias",
    "pruebas de unidad",
    "define las pruebas",
    "definir las pruebas",
    "definas las pruebas",
    "definir pruebas",
    "redacta las pruebas",
    "redactar las pruebas",
    "escribe las pruebas",
    "escribir las pruebas",
    "documenta las pruebas",
    "documentar las pruebas",
    "pruebas y cobertura",
    "porcentaje de cobertura",
    "cobertura de pruebas",
    "cobertura de código",
    "cobertura de codigo",
    "cobertura del proyecto",
    "y cobertura",
)


def _es_analisis_global(texto: str) -> bool:
    """True si la solicitud pide analizar/explorar TODO el proyecto.

    Heurística determinista sobre el texto normalizado (sin LLM, VI / SC-010):
    si es un análisis global, el agente amplía el presupuesto de pasos y
    enriquece el plan por capa (FR-049).
    """
    normalizado = " ".join((texto or "").lower().split())
    return any(
        frase in normalizado
        for frase in _FRASES_ANALISIS_GLOBAL + _FRASES_ANALISIS_GLOBAL_EN
    )


def _es_intencion_pruebas(texto: str) -> bool:
    """True si la solicitud pide sugerir/decidir qué pruebas aplicar.

    Heurística determinista sin LLM (VI / SC-010): dispara el presupuesto
    ampliado y el enriquecimiento del plan (cobertura por capa + `locate` de
    clases + `generate_test_cases`), de modo que la respuesta no dependa solo
    de un plan superficial del LLM (T121 / FR-049).
    """
    normalizado = " ".join((texto or "").lower().split())
    return any(
        frase in normalizado
        for frase in _FRASES_INTENCION_PRUEBAS + _FRASES_INTENCION_PRUEBAS_EN
    )


def _es_analisis_exhaustivo(texto: str) -> bool:
    """True si la solicitud requiere cobertura amplia (análisis global del
    proyecto o sugerencia de pruebas): amplía el presupuesto de pasos y
    enriquece el plan por capa (FR-049 / SC-016)."""
    return _es_analisis_global(texto) or _es_intencion_pruebas(texto)
