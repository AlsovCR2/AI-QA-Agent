"""Enrutador determinista de solicitudes a herramientas.

Mapea solicitudes en lenguaje natural a herramientas usando palabras clave
deterministas. Esto permite que el agente responda correctamente a solicitudes
comunes sin depender exclusivamente del LLM para la selección.

Reglas:
- Determinista (VI / SC-010): misma entrada = mismo resultado
- Sin LLM (III / SC-006): no usa red ni inferencia remota
- Tiene prioridad sobre el LLM para palabras clave específicas
- Si no hay coincidencia, retorna None y el LLM decide
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _normalizar(texto: str) -> str:
    """Normaliza a minúsculas y sin acentos para comparaciones robustas."""
    normalizado = unicodedata.normalize("NFD", texto.lower().strip())
    return "".join(c for c in normalizado if not unicodedata.combining(c))


# Mapeo de palabras clave a herramientas (orden de prioridad: más específico primero)
_PATRONES_HERRAMIENTAS: list[tuple[str, str, list[str]]] = [
    # analyze_coverage: la palabra "cobertura" es inequívoca → va primero para
    # ganar a "analyze_test_results" cuando ambas keywords aparecen juntas.
    (
        "analyze_coverage",
        r"\b(analiz[ae]|examin[ae]|muestra[mr]?|ver|consulta[ar]?)\b.*\b(cobertura)\b",
        ["analizar cobertura", "revisar cobertura", "mostrar cobertura"],
    ),
    # Acciones destructivas (Phase 14 / US-13). Van ANTES de generate_test_cases
    # para ganar a "crea... tests/pruebas" y a leer_archivo. Exigen verbo de
    # crear/editar/eliminar + "archivo|fichero".
    (
        "crear_archivo",
        r"\b(cre[ae]|crear|gener[ae]|generar)\b.*\b(archivo|fichero)\b",
        ["crear el archivo", "crear fichero", "generar el archivo"],
    ),
    (
        "editar_archivo",
        r"\b(edit[ae]|editar|modific[ae]|modificar|reemplaz[ae]|reemplazar|"
        r"actualiz[ae]|actualizar|reescrib[ae]|reescribir)\b.*\b(archivo|fichero)\b",
        ["editar el archivo", "modificar archivo", "reemplazar el archivo"],
    ),
    (
        "eliminar_archivo",
        r"\b(elimin[ae]|eliminar|borr[ae]|borrar|quit[ae]|quitar|suprim[ae]|suprimir)\b.*"
        r"\b(archivo|fichero)\b",
        ["eliminar el archivo", "borrar archivo", "quitar el fichero"],
    ),
    # analyze_test_results
    (
        "analyze_test_results",
        r"\b(analiz[ae]|examin[ae]|revisa[ar]?)\b.*\b(resultados?|tests?|pruebas?).*\b"
        r"(prueba|test|ejecucion)",
        ["análisis de resultados de pruebas", "revisar resultados de tests"],
    ),
    # generate_test_cases
    (
        "generate_test_cases",
        r"\b(gener[ae]|cre[ae]|propon[ae]|sugier[ae])\b.*\b(casos?|tests?|pruebas?)\b",
        ["generar casos de prueba", "crear tests para", "proponer tests"],
    ),
    # leer_archivo: "lee/muestra/abre el archivo X", "muestra el contenido de X",
    # "qué contiene X", "qué hace/explícame <archivo.ext>". Va antes de explore
    # para ganar a "muestra ... archivo".
    (
        "leer_archivo",
        r"\b(lee[r]?|leer|abre|abrir)\b.*\b(archivo|c[oó]digo fuente|contenido)\b|"
        r"\b(muestra|muestrame|ver|mostrar)\b.*\b(contenido)\b.*\b(archivo|c[oó]digo)\b|"
        r"\b(analiz[ae]|examin[ae])\b.*\b(archivo)\b|"
        r"\b(qu[eé] contiene|que contiene|contenido del|contenido de)\b|"
        r"\b(qu[eé] hace|que hace|expl[íi]came|expl[íi]ca|entiende|entender)\b.*"
        r"\b[\w./\\-]+\.\w+\b",
        ["leer el archivo", "mostrar el contenido del archivo", "qué contiene", "qué hace <archivo.ext>"],
    ),
    # run_tests
    (
        "run_tests",
        r"\b(ejecut[ae]|corr[ae]|lanza[ar]|haz|run)\b.*\b(test|tests|pruebas?)\b|"
        r"\b(falla[aá]?|fallando|fallo|fallan)\b.*\b(test|tests|pruebas?)\b",
        ["ejecutar tests", "correr pruebas", "ejecutar pytest", "por qué falla el test"],
    ),
    # explore
    (
        "explore",
        r"\b(explor[ae]|muestra[mr]?|lista[ar]?)\b.*\b(estructura|proyecto|directorios?|carpetas?|archivos?)\b|"
        r"\b(c[uú]al es|c[uú]al|qu[eé]|c[oó]mo est[aá])\b.*\b(estructura|organizaci[oó]n)\b",
        ["explorar estructura", "mostrar estructura del proyecto", "cuál es la estructura del proyecto"],
    ),
    # search
    (
        "search",
        r"\b(busc[ae]|encontr[ae]|localiz[ae])\b.*\b(patron|codigo|regex|expresion)\b|"
        r"\b(llamadas?)\b.*\b(funci[oó]n|m[ée]todo|clase|patr[oó]n)\b",
        ["buscar patrón en código", "encontrar regex", "llamadas a la función"],
    ),
    # locate
    (
        "locate",
        r"\b(busc[ae]|encontr[ae]|localiz[ae]|ubic[ae])\b.*\b(funcion|clase|componente|archivo|variable)\b",
        ["buscar función", "localizar componente", "encontrar archivo"],
    ),
]


def enrutar_solicitud(texto: str) -> str | None:
    """Enruta una solicitud a una herramienta usando patrones deterministas.

    Args:
        texto: Solicitud del usuario en lenguaje natural.

    Returns:
        El ID de la herramienta si hay coincidencia, None en caso contrario.
    """
    texto_lower = _normalizar(texto)

    for herramienta_id, patron, _ in _PATRONES_HERRAMIENTAS:
        if re.search(patron, texto_lower, re.IGNORECASE):
            return herramienta_id

    return None


def obtener_palabras_clave(herramienta_id: str) -> list[str]:
    """Obtiene las palabras clave/frases asociadas a una herramienta.

    Args:
        herramienta_id: ID de la herramienta.

    Returns:
        Lista de frases/palabras clave que activan la herramienta.
    """
    for hid, _, frases in _PATRONES_HERRAMIENTAS:
        if hid == herramienta_id:
            return list(frases)
    return []


def listar_herramientas_enrutables() -> list[str]:
    """Lista los IDs de herramientas que tienen enrutamiento determinista."""
    return [hid for hid, _, _ in _PATRONES_HERRAMIENTAS]


# -- Extracción de parámetros desde la solicitud (T064 ampliado) -------------

_ARTICULOS = r"(?:el|la|los|las)\s+"
_TIPOS_OBJETIVO = r"(?:clase|funcion|metodo|modulo|componente|archivo|servicio)\s+"


def _limpiar_objetivo(objetivo: str) -> str:
    """Limpia muletillas y determinantes del objetivo extraído."""
    resultado = objetivo.strip().rstrip(".")
    resultado = re.sub(rf"^{_ARTICULOS}", "", resultado)
    resultado = re.sub(rf"^{_TIPOS_OBJETIVO}", "", resultado)
    return resultado


def _inferir_cripticidad(texto: str) -> str:
    """Infere la cripticidad a partir de palabras clave de la solicitud."""
    norm = _normalizar(texto)
    if re.search(r"\b(l[íi]mite|borde|extremo|edge|esquina)\b", norm):
        return "edge_cases"
    if re.search(
        r"\b(invalido|invalidos|negativo|negativos|no valido|no validos)\b", norm
    ):
        return "usuarios_no_validos"
    return "happy_path"


def extraer_objetivo_cripticidad(texto: str) -> tuple[str, str]:
    """Extrae `(objetivo, cripticidad)` de una solicitud de generación de casos.

    El objetivo es el texto posterior a "para"/"sobre"/"de" que nombra la
    función, componente o escenario a cubrir. La cripticidad se infiere de
    palabras clave ("límite"/"borde"/"extremo" → edge_cases; "inválido"/
    "negativo" → usuarios_no_validos; por defecto happy_path).
    Determinista y sin LLM (VI / SC-010).
    """
    norm = _normalizar(texto)
    objetivo = ""
    for delimitador in ("para", "sobre"):
        match = re.search(rf"\b{delimitador}\b", norm)
        if match:
            objetivo = _limpiar_objetivo(norm[match.end():])
            break
    if not objetivo:
        # "de" aparece en "casos de prueba de X"; el objetivo es lo último.
        matches = list(re.finditer(r"\bde\b", norm))
        if matches:
            match = matches[-1]
            objetivo = _limpiar_objetivo(norm[match.end():])
    if not objetivo:
        objetivo = norm
    cripticidad = _inferir_cripticidad(texto)
    return objetivo, cripticidad


# -- Extracción de patrón de búsqueda (T049 / FR-010) -------------------------


def extraer_patron_busqueda(texto: str) -> str:
    """Extrae el patrón a buscar de una solicitud de `search`/`locate`.

    Determinista y sin LLM (VI / SC-010). Cubre las formas habituales:
    - "busca el patrón <X> en el código" / "busca la expresión <X>"
    - "localiza la función <X>" / "encuentra la clase <X>"

    Devuelve `""` si no puede extraerse un patrón concreto (la herramienta
    entonces informa la ausencia de patrón sin buscar un regex vacío, que
    coincidiría con todo y falsificaría resultados (FR-019, SC-002)).
    """
    patrones_clave = r"\b(?:patr[oó]n|regex|expresi[oó]n|expresion)\b"
    match = re.search(
        rf"{patrones_clave}\s+(.+?)\s*\b(?:en\s+(?:el\s+)?(?:c[oó]digo|proyecto))\s*$",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip().rstrip(".,;:")
    match = re.search(
        r"\bllamadas?\s+(?:a|de)\s+(?:la|el|las|los)?\s*"
        r"(?:funci[oó]n|clase|componente|m[ée]todo|patr[oó]n)\s+(\S+)",
        texto,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip().rstrip(".,;:")
    match = re.search(
        r"\b(?:busca|encuentra|localiza|ubicar|localizar)\b\s+(?:el|la|los|las)\s+"
        r"(?:funci[oó]n|clase|componente|archivo|variable|m[ée]todo|m[oó]dulo)\s+"
        r"(\S+)",
        texto,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip().rstrip(".,;:")
    return ""


# -- Extracción de nombre de archivo (leer_archivo, T104 / FR-048) ------------


def extraer_nombre_archivo(texto: str) -> str:
    """Extrae el nombre/ruta de un archivo de una solicitud de `leer_archivo`.

    Determinista y sin LLM (VI / SC-010). Toma el primer token con extensión
    (p. ej. `tests/test_main.py`, `src\\app.py`). Devuelve `""` si no hay
    ningún token con extensión (la herramienta informa la ausencia de archivo
    sin ejecutar, FR-019 / SC-002).
    """
    match = re.search(r"\b[\w./\\-]+\.\w+\b", texto)
    if not match:
        return ""
    return match.group(0).strip().rstrip(".,;:")


# -- Extracción de contenido a escribir (Phase 14, T096/097) ------------------


def extraer_contenido(texto: str) -> str:
    """Extrae el contenido a escribir de una solicitud destructiva.

    Determinista y sin LLM (VI / SC-010). Formas soportadas:
    - contenido entre comillas (``"..."`` o ``'...'``);
    - texto tras "con contenido" / "contenido:" hasta el final de la solicitud.
    Devuelve ``""`` si no puede extraerse (la herramienta informa la ausencia
    de contenido sin ejecutar, FR-019 / SC-002).
    """
    match = re.search(r"([“\"'”])(.+?)\1", texto, re.DOTALL)
    if match:
        return match.group(2).strip()
    match = re.search(r"\bcon\s+contenido\b\s*:?\s*(.*)$", texto, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip().rstrip(".,;:")
    match = re.search(r"\bcontenido\s*:\s*(.*)$", texto, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip().rstrip(".,;:")
    return ""
