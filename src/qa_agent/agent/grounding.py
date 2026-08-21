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


# --- Fallos de herramienta (FR-018 / IX) -----------------------------------

#: Estados que significan "esta observación no es evidencia utilizable".
ESTADOS_FALLIDOS = (EstadoResultado.ERROR, EstadoResultado.INVALIDO)


def observaciones_fallidas(observaciones: list[Observacion]) -> list[Observacion]:
    """Observaciones cuya herramienta terminó en ERROR o INVALIDO.

    `_afirmaciones_no_ancladas` construye la evidencia SOLO con las
    observaciones exitosas, así que un fallo nunca contradice al texto: se
    descarta. Con una única herramienta eso no importa —sin evidencia la
    confianza cae sola—, pero al mezclar éxitos y fallos las exitosas anclan el
    texto y el fallo desaparece. Esta función lo recupera.
    """
    return [
        o
        for o in observaciones
        if getattr(getattr(o, "resultado", None), "estado", None) in ESTADOS_FALLIDOS
    ]


def nota_de_fallos(fallidas: list[Observacion]) -> str:
    """Aviso factual sobre las herramientas que fallaron. Vacío si no hubo.

    Determinista (VI): se construye a partir del id de herramienta y de la
    `causa_no_ejecutado` de ADR-006, que es una taxonomía cerrada. No se
    reproduce la salida del comando: eso ya está en el panel de razonamiento y
    aquí solo aumentaría la superficie por la que puede escapar contenido del
    proyecto (XI).
    """
    if not fallidas:
        return ""
    partes = []
    for observacion in fallidas:
        resultado = observacion.resultado
        identificador = getattr(resultado, "herramienta_id", "") or "desconocida"
        datos = getattr(resultado, "datos", None) or {}
        causa = datos.get("causa_no_ejecutado") if isinstance(datos, dict) else ""
        partes.append(f"'{identificador}'" + (f" (causa: {causa})" if causa else ""))
    herramientas = ", ".join(partes)
    plural = "herramientas fallaron" if len(partes) > 1 else "herramienta falló"
    return (
        f"\n\nAviso: durante esta solicitud {plural} {herramientas}. "
        "Lo anterior no puede darse por verificado."
    )


def texto_ya_declara(texto: str, fallidas: list[Observacion]) -> bool:
    """True si el texto ya nombra todas las herramientas que fallaron.

    Evita castigar con una nota redundante a un backend que sí fue honesto.
    """
    return all(
        (getattr(o.resultado, "herramienta_id", "") or "") in texto for o in fallidas
    )


# --- Fallo reportado en el payload (ADR-006) -------------------------------

#: Valores de `estado_global` que significan "lo observado salió mal".
_ESTADOS_GLOBALES_MALOS = ("fallo", "no_ejecutado")

#: Palabras que, en el texto de la respuesta, cuentan como declarar el fallo.
_PALABRAS_DE_FALLO = ("fall", "error", "no se ejecut", "roto")


def _payload_reporta_fallo(datos: object) -> bool:
    """True si los DATOS de una herramienta exitosa describen un mal resultado.

    Una herramienta puede terminar en EXITO y aun así haber observado un
    desastre: `run_tests` que corre bien y encuentra 2 pruebas rotas devuelve
    EXITO con `estado_global='fallo'`. Es justo la distinción que ADR-006
    introdujo —la herramienta funcionó, el proyecto no— y por eso el estado del
    resultado no basta para juzgar honestidad.
    """
    if not isinstance(datos, dict):
        return False
    if str(datos.get("estado_global", "")) in _ESTADOS_GLOBALES_MALOS:
        return True
    for clave in ("falladas", "errores"):
        try:
            if int(datos.get(clave, 0)) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def observaciones_con_fallo_reportado(
    observaciones: list[Observacion],
) -> list[Observacion]:
    """Observaciones exitosas cuyo contenido describe un resultado fallido."""
    resultado_de = lambda o: getattr(o, "resultado", None)  # noqa: E731
    return [
        o
        for o in observaciones
        if getattr(resultado_de(o), "estado", None) == EstadoResultado.EXITO
        and _payload_reporta_fallo(getattr(resultado_de(o), "datos", None))
    ]


def texto_declara_el_fallo(texto: str, observaciones: list[Observacion]) -> bool:
    """True si la respuesta reconoce el mal resultado que observó.

    A diferencia de un fallo de herramienta, aquí la observación SÍ es
    evidencia válida: informar de que 2 pruebas fallan es una respuesta
    correcta y no debe penalizarse. Lo que no puede pasar es que la respuesta
    lo omita y presente el trabajo como limpio.
    """
    bajo = texto.lower()
    if any(palabra in bajo for palabra in _PALABRAS_DE_FALLO):
        return True
    return all(
        (getattr(o.resultado, "herramienta_id", "") or "") in texto
        for o in observaciones
    )


def nota_de_resultado_fallido(observaciones: list[Observacion]) -> str:
    """Aviso factual sobre resultados malos que la respuesta no mencionó.

    Se citan solo cifras y el `estado_global`, que son campos de contrato, no
    la salida del comando: reproducirla aquí ampliaría sin necesidad la
    superficie por la que puede escapar contenido del proyecto (XI).
    """
    if not observaciones:
        return ""
    partes = []
    for observacion in observaciones:
        resultado = observacion.resultado
        identificador = getattr(resultado, "herramienta_id", "") or "desconocida"
        datos = getattr(resultado, "datos", None) or {}
        detalle = []
        if isinstance(datos, dict):
            if datos.get("estado_global"):
                detalle.append(f"estado_global={datos['estado_global']}")
            for clave in ("falladas", "errores"):
                try:
                    if int(datos.get(clave, 0)) > 0:
                        detalle.append(f"{clave}={datos[clave]}")
                except (TypeError, ValueError):
                    continue
        sufijo = f" ({', '.join(detalle)})" if detalle else ""
        partes.append(f"'{identificador}'{sufijo}")
    return (
        "\n\nAviso: la respuesta anterior no menciona el resultado observado "
        f"por {', '.join(partes)}. Revisa el panel Razonamiento antes de dar el "
        "trabajo por bueno."
    )
