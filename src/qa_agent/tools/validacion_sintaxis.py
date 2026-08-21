"""Rechazo de escrituras sintácticamente imposibles (FR-042/043, principio IX).

`crear_archivo` y `editar_archivo` reciben el contenido COMPLETO del archivo,
así que el modelo tiene que reproducirlo entero. Observado repetidamente contra
Gemini el 2026-08-21: al pedirle corregir una función de un módulo de 50 líneas
devolvía `""Módulo.""` —dos comillas en vez de tres— y sobrescribía un módulo
que funcionaba con algo que ni siquiera parsea. La suite entera dejaba de
recolectar.

La herramienta no puede hacer que el modelo escriba mejor Python, pero sí puede
negarse a destruir un archivo que funciona con contenido que es imposible que
sea correcto. Un archivo que no compila no es una edición discutible: es
basura, y escribirla no le sirve a nadie.

Alcance deliberadamente estrecho: solo formatos verificables con la biblioteca
estándar y sin ambigüedad —Python y JSON—. No se valida Markdown, texto ni YAML
(esto último exigiría una dependencia, principio XII). Ante un formato que no
se sabe validar, se escribe: el valor por defecto es no estorbar.

Esto NO es un linter. No opina sobre estilo, imports sin usar ni nombres. La
única pregunta es si el contenido puede llegar a ejecutarse.
"""

from __future__ import annotations

import json
from pathlib import PurePosixPath

#: Extensiones que se saben validar, en minúscula.
EXTENSION_PYTHON = ".py"
EXTENSION_JSON = ".json"

EXTENSIONES_VALIDADAS: tuple[str, ...] = (EXTENSION_PYTHON, EXTENSION_JSON)


def _extension(archivo_relativo: str) -> str:
    return PurePosixPath(archivo_relativo.replace("\\", "/")).suffix.lower()


def error_de_sintaxis(archivo_relativo: str, contenido: str) -> str:
    """Mensaje de error si `contenido` no parsea; cadena vacía si está bien.

    Se devuelve un `str` y no se lanza porque el contrato de herramienta es
    devolver un resultado, nunca lanzar (principio IX): quien llama convierte
    esto en un `ResultadoDeHerramienta` inválido sin traducir excepciones.
    """
    extension = _extension(archivo_relativo)

    if extension == EXTENSION_PYTHON:
        try:
            # `compile` en modo "exec" es el mismo análisis que hace el
            # intérprete al importar: si esto pasa, el archivo al menos carga.
            compile(contenido, archivo_relativo or "<contenido>", "exec")
        except SyntaxError as error:
            return _mensaje_python(error)
        except ValueError as error:
            # Bytes nulos y similares: `compile` los rechaza con ValueError.
            return f"El contenido no es Python válido: {error}"
        return ""

    if extension == EXTENSION_JSON:
        try:
            json.loads(contenido)
        except json.JSONDecodeError as error:
            return (
                f"El contenido no es JSON válido: {error.msg} "
                f"(línea {error.lineno}, columna {error.colno}). "
                "No se escribió nada."
            )
        return ""

    return ""


def _mensaje_python(error: SyntaxError) -> str:
    """Error legible y accionable, no el `repr` de la excepción.

    Se incluye la línea infractora porque el modelo suele fallar en un carácter
    concreto (comillas de docstring, paréntesis sin cerrar) y verlo citado es
    lo que le permite corregirlo en el siguiente intento.
    """
    partes = [f"El contenido no es Python válido: {error.msg}"]
    if error.lineno:
        partes.append(f"en la línea {error.lineno}")
    if error.text and error.text.strip():
        partes.append(f"→ {error.text.strip()}")
    return " ".join(partes) + ". No se escribió nada."


def reemplazar_funcion(original: str, nombre: str, codigo: str) -> tuple[str, str]:
    """Sustituye la función `nombre` por `codigo`. Devuelve `(contenido, error)`.

    Existe porque los modelos pequeños fallan sistemáticamente al CITAR código
    existente pero aciertan al ESCRIBIR la función nueva. Medido contra Gemini
    el 2026-08-21: pedirle un reemplazo exacto producía un `buscar` inventado
    —`def mediana(lista): # Implementación previa...`, que no está en el
    archivo— mientras el cuerpo nuevo que proponía era correcto.

    El localizador es `ast`, no una expresión regular: la posición de la
    función la decide el parser de Python, no una heurística de texto. Se
    incluyen los decoradores en el tramo sustituido para no dejarlos huérfanos.
    """
    import ast

    try:
        arbol = ast.parse(original)
    except SyntaxError as error:
        return "", f"El archivo actual no es Python válido ({error.msg}); no se tocó nada."

    definiciones = [
        nodo
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef)
        and nodo.name == nombre
    ]
    if not definiciones:
        return "", (
            f"No existe una función llamada '{nombre}' en el archivo. "
            "No se escribió nada."
        )
    if len(definiciones) > 1:
        return "", (
            f"Hay {len(definiciones)} funciones llamadas '{nombre}' y es "
            "ambiguo cuál sustituir. No se escribió nada."
        )

    definicion = definiciones[0]
    # `lineno` apunta al `def`; los decoradores van antes y deben ir con él.
    inicio = min(
        [definicion.lineno] + [d.lineno for d in definicion.decorator_list]
    )
    fin = definicion.end_lineno or definicion.lineno

    lineas = original.splitlines(keepends=True)
    nuevo = codigo if codigo.endswith("\n") else codigo + "\n"
    resultado = "".join(lineas[: inicio - 1]) + nuevo + "".join(lineas[fin:])

    problema = error_de_sintaxis("x.py", resultado)
    if problema:
        return "", problema
    return resultado, ""
