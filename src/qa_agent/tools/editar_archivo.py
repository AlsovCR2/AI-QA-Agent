"""Herramienta `editar_archivo`: modifica el contenido de un archivo existente.

Acción destructiva (Phase 14, US-13 / FR-043): requiere autorización explícita
(FR-046 / SC-004 / UC-006), opera SOLO dentro de la `Allowlist` (FR-025 /
SC-022), respalda el estado previo en `.qa-backup/` antes de modificar
(FR-045 / SC-023) y rechaza editar un archivo inexistente o fuera del perímetro
SIN modificar nada (FR-043 / SC-024). Determinística (VI / SC-010).
"""

from __future__ import annotations

from typing import Any

from qa_agent.agent.backup import BackupManager
from qa_agent.tools.validacion_sintaxis import error_de_sintaxis, reemplazar_funcion
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
    resolver_archivo_en_perimetro,
)


class EditarArchivoHerramienta(Herramienta):
    """Modifica el contenido de un archivo existente dentro del perímetro."""

    id = "editar_archivo"
    nombre = "editar_archivo"
    descripcion = (
        "Modifica un archivo existente del proyecto. Para cambiar una función de "
        "un archivo Python usa `funciones` (nombre + código nuevo): es la vía "
        "más fiable. Para otros cambios acotados usa `reemplazos`. Reserva "
        "`contenido` para reescrituras completas. "
        "Requiere autorización explícita y respalda "
        "el estado previo en .qa-backup/ antes de modificar. Úsala cuando el "
        "usuario pida editar o modificar un archivo (p. ej. 'edita "
        "src/ajustes.py con contenido ...'). Rechaza sin modificar nada si el "
        "archivo no existe o queda fuera de las rutas autorizadas."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto"},
            "archivo_relativo": {
                "type": "string",
                "description": "Ruta del archivo a editar, relativa a `ruta`",
            },
            "funciones": {
                "type": "array",
                "description": (
                    "LA FORMA MÁS FIABLE de cambiar una función Python: objetos "
                    "{nombre, codigo} con el nombre de la función y su código "
                    "nuevo completo. La localiza el parser; no cites el código "
                    "viejo ni reproduzcas el resto del archivo. OBLIGATORIO "
                    "conservar de la versión actual: mismos nombres de "
                    "parámetros, docstring, anotaciones de tipo y llamadas a "
                    "los ayudantes del módulo (validadores). Corrige SOLO lo "
                    "pedido: se rechaza la edición que degrade algo de eso."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "nombre": {
                            "type": "string",
                            "description": "Nombre de la función a sustituir, p. ej. 'mediana'.",
                        },
                        "codigo": {
                            "type": "string",
                            "description": (
                                "Definición completa de la función nueva, "
                                "empezando por 'def '. OBLIGATORIO conservar de "
                                "la versión actual: los MISMOS nombres de "
                                "parámetros, el docstring, las anotaciones de "
                                "tipo y las llamadas a funciones auxiliares del "
                                "módulo (validadores, etc.). Corrige SOLO lo "
                                "pedido; la edición se rechaza si degrada algo "
                                "de eso."
                            ),
                        },
                    },
                    "required": ["nombre", "codigo"],
                },
            },
            "reemplazos": {
                "type": "array",
                "description": (
                    "PREFERIDO para modificar un archivo existente. Lista de "
                    "reemplazos exactos; solo se toca lo que indiques y el "
                    "resto del archivo queda intacto. Cada `buscar` debe "
                    "aparecer UNA sola vez en el archivo: incluye suficiente "
                    "contexto (la firma de la función y su cuerpo) para que "
                    "sea inequívoco."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "buscar": {
                            "type": "string",
                            "description": "Texto EXACTO a sustituir, tal cual aparece.",
                        },
                        "reemplazar": {
                            "type": "string",
                            "description": "Texto nuevo que ocupa su lugar.",
                        },
                    },
                    "required": ["buscar", "reemplazar"],
                },
            },
            "contenido": {
                "type": "string",
                "description": (
                    "Archivo COMPLETO nuevo. Usa esto SOLO si el cambio afecta "
                    "a casi todo el archivo; para cambios acotados usa "
                    "`reemplazos`, que no obliga a reproducir lo que no cambia."
                ),
            },
        },
        "required": ["ruta", "archivo_relativo"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "archivo": {"type": "string"},
            "editado": {"type": "boolean"},
            "existia": {"type": "boolean"},
            "backup": {"type": "string"},
        },
        "required": ["archivo", "editado", "existia", "backup"],
    }
    requiere_autorizacion = True

    def __init__(self, rutas_permitidas: list[str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        ruta_raw = parametros.get("ruta", ".")
        archivo_relativo = (parametros.get("archivo_relativo") or "").strip()
        contenido = parametros.get("contenido")
        reemplazos = parametros.get("reemplazos") or []
        funciones = parametros.get("funciones") or []

        archivo, error = resolver_archivo_en_perimetro(
            ruta_raw, archivo_relativo, self._allowlist
        )
        if error is not None:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=error,
            )

        if not isinstance(contenido, str) and not reemplazos and not funciones:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={},
                error=(
                    "No se especificó qué cambiar: usa `reemplazos` para un "
                    "cambio acotado o `contenido` para reescribir el archivo."
                ),
            )

        if not archivo.exists() or archivo.is_dir():
            # Rechaza editar un archivo inexistente sin modificar nada (FR-043).
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={},
                error=(
                    "El archivo no existe; no se editó nada. "
                    "Usa crear_archivo para crearlo (FR-043)."
                ),
            )

        try:
            original = archivo.read_text(encoding="utf-8")
        except OSError as error_caught:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=f"No se pudo leer el archivo: {error_caught}",
            )

        # `funciones` va primero: es el camino más fiable con modelos pequeños,
        # porque solo exige escribir la función nueva —cosa que hacen bien— y no
        # citar la vieja —cosa que fallan—. La localiza `ast`, no el modelo.
        if funciones:
            for indice, entrada in enumerate(funciones, start=1):
                if not isinstance(entrada, dict):
                    return ResultadoDeHerramienta(
                        herramienta_id=self.id,
                        estado=EstadoResultado.INVALIDO,
                        datos={},
                        error=f"La entrada {indice} de `funciones` no es un objeto.",
                    )
                nombre = entrada.get("nombre")
                codigo = entrada.get("codigo")
                if not isinstance(nombre, str) or not isinstance(codigo, str):
                    return ResultadoDeHerramienta(
                        herramienta_id=self.id,
                        estado=EstadoResultado.INVALIDO,
                        datos={},
                        error=(
                            f"La entrada {indice} de `funciones` necesita "
                            "`nombre` y `codigo`."
                        ),
                    )
                base = contenido if isinstance(contenido, str) else original
                base = base if indice > 1 else original
                nuevo_contenido, problema_funcion = reemplazar_funcion(
                    base, nombre, codigo
                )
                if problema_funcion:
                    return ResultadoDeHerramienta(
                        herramienta_id=self.id,
                        estado=EstadoResultado.INVALIDO,
                        datos={},
                        error=problema_funcion,
                    )
                contenido = nuevo_contenido
                original = nuevo_contenido if indice < len(funciones) else original

        # `reemplazos` tiene precedencia: es el camino que no obliga al modelo a
        # reproducir el archivo entero, que es de donde salían los destrozos.
        elif reemplazos:
            contenido, problema_reemplazo = _aplicar_reemplazos(original, reemplazos)
            if problema_reemplazo:
                return ResultadoDeHerramienta(
                    herramienta_id=self.id,
                    estado=EstadoResultado.INVALIDO,
                    datos={},
                    error=problema_reemplazo,
                )

        # Se valida ANTES de respaldar y escribir: si el resultado no puede
        # ejecutarse, no hay edición que discutir y el archivo bueno se queda
        # como está (ver `tools/validacion_sintaxis.py`).
        problema = error_de_sintaxis(archivo_relativo, contenido)
        if problema:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.INVALIDO,
                datos={},
                error=problema,
            )

        try:
            backup = BackupManager(ruta_raw).respaldar(archivo_relativo, original)
            archivo.write_text(contenido, encoding="utf-8")
        except OSError as error_caught:
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=(
                    f"No se pudo modificar el archivo: {error_caught}. "
                    "El respaldo previo queda disponible en .qa-backup/."
                ),
            )

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "archivo": archivo_relativo,
                "editado": True,
                "existia": True,
                "backup": str(backup),
            },
        )


def _aplicar_reemplazos(
    original: str, reemplazos: list[Any]
) -> tuple[str, str]:
    """Aplica sustituciones exactas. Devuelve `(contenido, error)`.

    Cada `buscar` debe aparecer EXACTAMENTE una vez. Cero coincidencias suele
    significar que el modelo citó de memoria en vez de copiar del archivo;
    varias, que el fragmento es demasiado corto para ser inequívoco. En ambos
    casos se rechaza sin escribir: adivinar cuál de dos coincidencias quería
    sería peor que fallar.
    """
    contenido = original
    for indice, reemplazo in enumerate(reemplazos, start=1):
        if not isinstance(reemplazo, dict):
            return "", f"El reemplazo {indice} no es un objeto con `buscar` y `reemplazar`."
        buscar = reemplazo.get("buscar")
        reemplazar = reemplazo.get("reemplazar")
        if not isinstance(buscar, str) or not buscar:
            return "", f"El reemplazo {indice} no indica `buscar`."
        if not isinstance(reemplazar, str):
            return "", f"El reemplazo {indice} no indica `reemplazar`."

        apariciones = contenido.count(buscar)
        if apariciones == 0:
            return "", (
                f"El texto del reemplazo {indice} no aparece en el archivo. "
                "Cópialo EXACTAMENTE del contenido leído, con su indentación. "
                "No se escribió nada."
            )
        if apariciones > 1:
            return "", (
                f"El texto del reemplazo {indice} aparece {apariciones} veces y "
                "es ambiguo. Añade contexto alrededor para que sea único. "
                "No se escribió nada."
            )
        contenido = contenido.replace(buscar, reemplazar, 1)

    return contenido, ""
