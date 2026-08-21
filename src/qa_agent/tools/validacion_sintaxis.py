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


def _firma(definicion) -> list[str]:
    """Nombres de parámetros en orden, incluidos `*args` y `**kwargs`."""
    args = definicion.args
    nombres = [a.arg for a in (*args.posonlyargs, *args.args)]
    if args.vararg:
        nombres.append("*" + args.vararg.arg)
    nombres += [a.arg for a in args.kwonlyargs]
    if args.kwarg:
        nombres.append("**" + args.kwarg.arg)
    return nombres


def _anotados(definicion) -> set[str]:
    """Parámetros que llevan anotación de tipo, más 'return' si la hay."""
    import ast

    args = definicion.args
    todos = [
        *args.posonlyargs,
        *args.args,
        *args.kwonlyargs,
        *(x for x in (args.vararg, args.kwarg) if x is not None),
    ]
    anotados = {a.arg for a in todos if a.annotation is not None}
    if definicion.returns is not None:
        anotados.add("return")
    _ = ast
    return anotados


def _llamadas(nodo) -> set[str]:
    """Nombres invocados dentro del cuerpo (solo llamadas simples por nombre)."""
    import ast

    return {
        h.func.id
        for h in ast.walk(nodo)
        if isinstance(h, ast.Call) and isinstance(h.func, ast.Name)
    }


def _degradaciones(vieja, nueva, ayudantes: set[str]) -> list[str]:
    """Qué perdió la versión nueva respecto de la vieja.

    Cada comprobación existe porque se observó la regresión concreta contra
    Gemini el 2026-08-21: al pedirle "corrige `mediana`" devolvía una función
    correcta que además renombraba el parámetro, borraba el docstring, quitaba
    las anotaciones y duplicaba a mano la validación que hacía `_validar`.
    Todo eso pasaba las pruebas del proyecto, así que ninguna suite lo veía.

    Se comprueba PÉRDIDA, no igualdad: mejorar el docstring o añadir un tipo
    que faltaba es legítimo; quitarlos no.
    """
    import ast

    problemas: list[str] = []

    firma_vieja, firma_nueva = _firma(vieja), _firma(nueva)
    if firma_vieja != firma_nueva:
        problemas.append(
            f"la firma cambió de ({', '.join(firma_vieja)}) a "
            f"({', '.join(firma_nueva)}); renombrar un parámetro rompe a quien "
            "llame por nombre"
        )

    if ast.get_docstring(vieja) and not ast.get_docstring(nueva):
        problemas.append(
            "se eliminó el docstring, que es la especificación contra la que se "
            "detectan los errores de esta función"
        )

    perdidas = _anotados(vieja) - _anotados(nueva)
    if perdidas:
        problemas.append(
            "se perdieron anotaciones de tipo en: " + ", ".join(sorted(perdidas))
        )

    usados_antes = _llamadas(vieja) & ayudantes
    perdidos = usados_antes - _llamadas(nueva)
    if perdidos:
        problemas.append(
            "ya no se llama a "
            + ", ".join(f"`{n}`" for n in sorted(perdidos))
            + "; duplicar esa lógica en línea la hace divergir del resto del "
            "módulo"
        )

    return problemas


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

    Además se RECHAZA la sustitución que degrade la función: cambiar la firma,
    borrar el docstring, quitar anotaciones o dejar de usar los ayudantes del
    módulo. Una corrección no puede empeorar lo que no se le pidió tocar, y las
    pruebas del proyecto no ven ese tipo de daño (ver `_degradaciones`).
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

    problema = error_de_sintaxis("x.py", codigo)
    if problema:
        return "", problema

    nuevas = [
        n
        for n in ast.parse(codigo).body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        and n.name == nombre
    ]
    if len(nuevas) != 1:
        return "", (
            f"El código nuevo debe definir exactamente una función '{nombre}'. "
            "No se escribió nada."
        )

    ayudantes = {
        n.name
        for n in arbol.body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    degradaciones = _degradaciones(definiciones[0], nuevas[0], ayudantes)
    if degradaciones:
        return "", (
            f"La versión nueva de '{nombre}' degrada la existente: "
            + "; ".join(degradaciones)
            + ". Corrige SOLO lo pedido y conserva lo demás tal cual. "
            "No se escribió nada."
        )

    definicion = definiciones[0]
    # `lineno` apunta al `def`; los decoradores van antes y deben ir con él.
    inicio = min(
        [definicion.lineno] + [d.lineno for d in definicion.decorator_list]
    )
    fin = definicion.end_lineno or definicion.lineno

    lineas = original.splitlines(keepends=True)
    nuevo_codigo = codigo if codigo.endswith("\n") else codigo + "\n"
    resultado = "".join(lineas[: inicio - 1]) + nuevo_codigo + "".join(lineas[fin:])

    problema = error_de_sintaxis("x.py", resultado)
    if problema:
        return "", problema
    return resultado, ""
