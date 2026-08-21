"""Política determinista de detección y resolución de capa/carpeta (I02).

Extraído de `agent/loop.py` como movimiento puro (Constitution X / XII): mismo
regex, mismos conectores/verbos, mismo comportamiento observable. Ninguna
semántica cambia — solo la responsabilidad queda aislada en su propio módulo.

Cubre el análisis de UNA capa/carpeta concreta ("explora todas las clases de
la capa DAL", "los archivos de la carpeta BLL"): detección de la intención
(`_es_analisis_capa`), extracción determinista del nombre solicitado
(`_extraer_capa_solicitada`) y su resolución real contra el filesystem
(`_resolver_capa_real`, nunca inventa una capa — FR-019 / VI), más la
clasificación de archivos de código usada al recorrer una capa
(`_es_archivo_codigo`).
"""

from __future__ import annotations

import re
from pathlib import Path

# El patrón captura el RESTO tras la palabra clave ("capa/carpeta/directorio")
# para poder saltar conectores/preposiciones (T124): "la capa de DAL",
# "la carpeta del proyecto" → el nombre real viene después de "de/del".
_PATRON_CAPA_O_CARPETA = re.compile(
    r"\b(?:capa|carpeta|directorio)\b\s+(.+)$", re.IGNORECASE
)
# Conectores/preposiciones que no son nombres de directorio y se saltan al
# extraer la capa solicitada.
_CONECTORES_CAPA = frozenset(
    {
        "de", "del", "en", "el", "la", "los", "las", "un", "una", "y", "o",
        "e", "u", "que", "para", "al", "con", "actual", "a",
    }
)
# Palabras que indican que la solicitud pide analizar/explorar el contenido de
# la capa (y no solo menciona la capa de paso).
_VERBOS_ANALISIS_CAPA = (
    "explora", "explorar", "explore", "explorando",
    "analiza", "analizar", "analizando",
    "revisa", "revisar", "revisando",
    "resume", "resumir", "resumen",
    "lista", "listar", "describe", "describir", "ver", "muestra",
    "todas las clases", "todos los archivos",
    "las clases de la capa", "los archivos de la capa",
    "archivos de la carpeta", "clases en la capa", "archivos en la capa",
    "estructura", "completa", "profundiza", "profundizar",
    "existen", "hay", "qué hay", "que hay",
    "dime las clases", "dame las clases",
    # Definición/escritura de contenido de una capa (T123): "procede a definir
    # las pruebas unitarias y cobertura que se van a realizar a la capa DAL",
    # "definas en UnitTest.md ... de la capa de datos". Sin estos verbos, una
    # intención de crear/editar contenido para una capa concreta no disparaba
    # el enriquecimiento y el LLM exploraba rutas inventadas ("Datos"/"Negocio"
    # en vez de la capa DAL real).
    "define", "definir", "definas", "definiendo",
    "redacta", "redactar", "redactando",
    "escribe", "escribir", "escribiendo",
    "documenta", "documentar", "documentando",
    "procede", "proceder", "procediendo",
    "realiza", "realizar", "realizando",
    "cobertura", "porcentaje de cobertura",
    "los casos de prueba", "casos de prueba para",
    "se van a realizar",
)

_EXTENSIONES_CODIGO = frozenset(
    {
        "py", "cs", "js", "ts", "tsx", "jsx", "java", "go", "rs", "kt",
        "swift", "rb", "php", "cpp", "c", "h", "hpp", "vue",
    }
)


def _extraer_capa_solicitada(texto: str) -> str:
    """Extrae el nombre de capa/carpeta concreto solicitado (p. ej. 'DAL' en
    'las clases de la capa DAL' o 'BLL' en 'los archivos de la carpeta BLL').

    Devuelve una cadena vacía si la solicitud no nombra una capa/carpeta
    concreta (heurística determinista, sin LLM, VI / SC-010). El valor es el
    token textual (en minúsculas); su existencia real se valida después con
    `_resolver_capa_real` para no inventar rutas (FR-019).
    """
    if not texto:
        return ""
    normalizado = " ".join(texto.lower().split())
    coincidencia = _PATRON_CAPA_O_CARPETA.search(normalizado)
    if not coincidencia:
        return ""
    # Salta conectores/preposiciones y toma el primer token que parece un
    # nombre de capa/carpeta (T124): "la capa de DAL" → "dal".
    for token in coincidencia.group(1).split():
        candidato = token.strip(".,;:()\"'¿?")
        if candidato and candidato not in _CONECTORES_CAPA:
            return candidato
    return ""


def _es_analisis_capa(texto: str) -> bool:
    """True si la solicitud pide analizar/explorar UNA capa o carpeta concreta.

    Heurística determinista sin LLM (VI / SC-010): amplía el presupuesto de
    pasos y enriquece el plan con la exploración y lectura exhaustiva de esa
    capa (FR-049), de modo que el resultado no dependa solo de un plan
    superficial del LLM (T122 / FR-024).
    """
    if not _extraer_capa_solicitada(texto):
        return False
    normalizado = " ".join((texto or "").lower().split())
    return any(verbo in normalizado for verbo in _VERBOS_ANALISIS_CAPA)


def _resolver_capa_real(base: str, capa_solicitada: str) -> str | None:
    """Nombre REAL (en disco) del directorio solicitado, o `None` si no existe.

    Nunca inventa una capa (FR-019 / VI): busca coincidencia exacta o
    case-insensitive sobre los directorios de primer nivel de `base` y
    canoniza el nombre a como existe realmente (p. ej. 'dal' → 'DAL').
    Admite subrutas (p. ej. 'DAL/Properties'). Ignora directorios ocultos.
    """
    raiz = Path(base)
    if not raiz.is_dir():
        return None
    pedida = Path(capa_solicitada)
    real = None
    for hijo in raiz.iterdir():
        if (
            hijo.is_dir()
            and not hijo.name.startswith(".")
            and hijo.name.lower() == pedida.parts[0].lower()
        ):
            real = hijo.name
            break
    if real is None:
        return None
    if len(pedida.parts) <= 1:
        return real
    return str(Path(real, *pedida.parts[1:]))


def _es_archivo_codigo(ruta_relativa: str) -> bool:
    """True si la extensión del archivo es de código fuente."""
    return ruta_relativa.rsplit(".", 1)[-1].lower() in _EXTENSIONES_CODIGO
