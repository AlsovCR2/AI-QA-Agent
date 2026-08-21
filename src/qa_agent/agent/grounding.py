"""Verificación determinista de anclaje de la respuesta a la evidencia real.

Extraído de `agent/loop.py` (I01, ADR-001) como movimiento puro: misma lógica,
mismo comportamiento observable. Implementa la honestidad del razonamiento
(SC-017 / FR-019): si el texto de la respuesta final afirma tokens
sustantivos (palabras con mayúscula inicial, números) que no aparecen en
ninguna observación real, la confianza no puede reportarse como alta —
evita que el LLM presente como hecho algo que el agente nunca observó.

Puramente determinista (VI / SC-010): no usa LLM ni estado del `Agent`, solo
el texto de la respuesta y las observaciones ya recolectadas.
"""

from __future__ import annotations

import re

from qa_agent.agent.reasoning import Observacion
from qa_agent.tools.base import EstadoResultado

# Palabras comunes del castellano (verbos en 1ª persona, conectores) que no
# son afirmaciones de datos y se excluyen de la comprobación de anclaje.
_PALABRAS_COMUNES = {
    "Encontré", "Encontre", "Observé", "Observe", "Analicé", "Analice",
    "El", "La", "Los", "Las", "Un", "Una", "Y", "Pero", "Con", "En",
    "De", "Que", "No", "Si", "Más", "Mas", "Sin", "Por", "Para",
}


def _al_inicio_de_frase(texto: str, pos: int) -> bool:
    """True si `pos` apunta al inicio de una oración (no es afirmación).

    Determinista: el token está al inicio de frase si es el primer carácter
    del texto o el último carácter no espacial previo es un signo de
    puntuación que cierra una oración.
    """
    i = pos - 1
    while i >= 0 and texto[i].isspace():
        i -= 1
    if i < 0:
        return True
    return texto[i] in ".!?;:"


def _afirmaciones_no_ancladas(
    texto: str, observaciones: list[Observacion]
) -> bool:
    """True si el texto afirma tokens sustantivos ausentes de la evidencia.

    Determinista (SC-010): extrae números y palabras con mayúscula inicial
    del texto de la respuesta y comprueba que aparezcan en los datos de
    las observaciones reales. Si alguno no aparece, la afirmación no está
    anclada (SC-017 / FR-019) y la confianza no puede ser alta.
    """
    if not observaciones:
        return bool(re.search(r"\b[A-ZÁ-Ú][a-zá-ú]+\b|\d+", texto))
    evidencia = "\n".join(
        str(getattr(o.resultado, "datos", o.resultado))
        for o in observaciones
        if getattr(getattr(o, "resultado", None), "estado", None)
        == EstadoResultado.EXITO
    )
    # Tokens sustantivos de la respuesta: palabras individuales con
    # mayúscula inicial y números. Se excluyen palabras comunes del
    # castellano (verbos en 1ª persona, conectores) que no son
    # afirmaciones de datos, y las palabras al INICIO de frase (no son
    # afirmaciones: SC-017 exige anclar afirmaciones, no el texto).
    for match in re.finditer(
        r"\b([A-ZÁ-Ú][a-zá-ú]+)\b|\b(\d+(?:\.\d+)?)\b", texto
    ):
        token = match.group(1) or match.group(2)
        if token in _PALABRAS_COMUNES:
            continue
        es_numero = match.group(2) is not None
        if es_numero:
            if token not in evidencia:
                return True
            continue
        if _al_inicio_de_frase(texto, match.start()):
            continue
        if token not in evidencia:
            return True
    return False
