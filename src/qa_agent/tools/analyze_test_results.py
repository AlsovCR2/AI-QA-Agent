"""Herramienta `analyze_test_results`: analiza la salida real de `run_tests`
(resumen determinista + causas limitadas a evidencia).

El análisis cuantitativo (resumen, agrupación por ruta) es determinista (VI / SC-010).
Las `posible_causa` se limitan a lo que la evidencia sustenta; si no hay
evidencia, se indica "sin evidencia suficiente" (FR-014, UC-007).
Solo usa resultados y rutas reales; nunca inventa fallos ni causas (FR-019).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)


class AnalyzeTestResultsHerramienta(Herramienta):
    """Analiza resultados de pruebas y genera resumen con causas basadas en evidencia."""

    id = "analyze_test_results"
    nombre = "analyze_test_results"
    descripcion = (
        "Analiza los resultados de una ejecución de pruebas (salida de run_tests) "
        "y genera un resumen cuantitativo determinista agrupando fallos por "
        "ruta/archivo, limitando las posibles causas a lo que la evidencia "
        "sustenta. No inventa fallos ni causas. Úsala cuando el usuario pida "
        "analizar resultados de tests ya ejecutados."
    )
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "description": "Raíz del proyecto"},
            "resultado_tests": {
                "type": "object",
                "description": "Resultado de run_tests",
                "properties": {
                    "pasadas": {"type": "integer"},
                    "falladas": {"type": "integer"},
                    "errores": {"type": "integer"},
                    "total": {"type": "integer"},
                    "estado_global": {
                        "type": "string",
                        "enum": ["exito", "fallo", "no_ejecutado"],
                    },
                    "detalle_fallos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nombre": {"type": "string"},
                                "mensaje_error": {"type": "string"},
                                "ruta_relativa": {"type": "string"},
                            },
                        },
                    },
                },
                "required": [
                    "pasadas",
                    "falladas",
                    "errores",
                    "total",
                    "estado_global",
                    "detalle_fallos",
                ],
            },
        },
        "required": ["ruta", "resultado_tests"],
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "resumen": {
                "type": "string",
                "description": "Resumen cuantitativo del estado real",
            },
            "fallos_agrupados": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ruta_relativa": {"type": "string"},
                        "error_comun": {"type": "string"},
                        "posible_causa": {
                            "type": "string",
                            "description": "Causa respaldada por evidencia o 'sin evidencia suficiente'",
                        },
                    },
                    "required": ["ruta_relativa", "error_comun", "posible_causa"],
                },
            },
        },
        "required": ["resumen", "fallos_agrupados"],
    }
    requiere_autorizacion = False

    def __init__(self, rutas_permitidas: list[str] | None = None) -> None:
        if rutas_permitidas is None:
            rutas_permitidas = []
        self._allowlist = Allowlist(rutas_permitidas) if rutas_permitidas else None

    def _extraer_causa_desde_error(self, mensaje_error: str) -> str:
        """Extrae una causa posible basada solo en la evidencia del mensaje de error."""
        mensaje_lower = mensaje_error.lower()

        # Patrones comunes de errores con causas evidentes
        if "assertionerror" in mensaje_lower or "assert " in mensaje_lower:
            if "!=" in mensaje_error or "==" in mensaje_error:
                return "Valor inesperado en aserción (evidencia: mensaje de error)"
            return "Aserción fallida (evidencia: AssertionError)"
        elif "timeout" in mensaje_lower or "timed out" in mensaje_lower:
            return "Tiempo de espera excedido (evidencia: TimeoutError)"
        elif "valueerror" in mensaje_lower:
            return "Valor inválido proporcionado (evidencia: ValueError)"
        elif "keyerror" in mensaje_lower:
            return "Clave no encontrada en diccionario (evidencia: KeyError)"
        elif "attributeerror" in mensaje_lower:
            return "Atributo inexistente (evidencia: AttributeError)"
        elif "importerror" in mensaje_lower or "modulenotfounderror" in mensaje_lower:
            return "Módulo o dependencia faltante (evidencia: ImportError)"
        elif "typeerror" in mensaje_lower:
            return "Tipo de dato incorrecto (evidencia: TypeError)"
        elif "filenotfounderror" in mensaje_lower:
            return "Archivo no encontrado (evidencia: FileNotFoundError)"
        elif "permissionerror" in mensaje_lower:
            return "Permisos insuficientes (evidencia: PermissionError)"
        elif "connectionerror" in mensaje_lower or "connectionrefused" in mensaje_lower:
            return "Error de conexión (evidencia: ConnectionError)"

        # Si no hay patrón reconocido, indicar insuficiencia de evidencia
        return "sin evidencia suficiente para determinar causa (solo se reporta el error observado)"

    def _agrupar_fallos_por_ruta(
        self, detalle_fallos: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Agrupa fallos por ruta_relativa y extrae error común."""
        grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for fallo in detalle_fallos:
            ruta = fallo.get("ruta_relativa", "desconocido")
            grupos[ruta].append(fallo)

        resultado = []
        for ruta, fallos in grupos.items():
            # Determinar error común (el más frecuente o el primero)
            mensajes = [f.get("mensaje_error", "") for f in fallos]
            error_comun = mensajes[0] if mensajes else "Sin mensaje de error"

            # Extraer causa basada en evidencia del primer fallo del grupo
            causa = self._extraer_causa_desde_error(error_comun)

            resultado.append(
                {
                    "ruta_relativa": ruta,
                    "error_comun": error_comun[:200],  # Limitar longitud
                    "posible_causa": causa,
                }
            )

        return resultado

    def ejecutar(self, parametros: dict[str, Any]) -> ResultadoDeHerramienta:
        ruta_raw = parametros.get("ruta", ".")
        resultado_tests = parametros.get("resultado_tests", {})

        # Validar ruta
        if self._allowlist is not None and not self._allowlist.contiene(ruta_raw):
            return ResultadoDeHerramienta(
                herramienta_id=self.id,
                estado=EstadoResultado.ERROR,
                datos={},
                error=(
                    "La ruta solicitada queda fuera de las rutas autorizadas "
                    "(FR-025)."
                ),
            )

        # Validar estructura de resultado_tests
        campos_requeridos = [
            "pasadas",
            "falladas",
            "errores",
            "total",
            "estado_global",
            "detalle_fallos",
        ]
        for campo in campos_requeridos:
            if campo not in resultado_tests:
                return ResultadoDeHerramienta(
                    herramienta_id=self.id,
                    estado=EstadoResultado.INVALIDO,
                    datos={"resumen": "", "fallos_agrupados": []},
                    error=f"Campo requerido faltante en resultado_tests: {campo}",
                )

        pasadas = int(resultado_tests.get("pasadas", 0))
        falladas = int(resultado_tests.get("falladas", 0))
        errores = int(resultado_tests.get("errores", 0))
        total = int(resultado_tests.get("total", 0))
        estado_global = resultado_tests.get("estado_global", "no_ejecutado")
        detalle_fallos = resultado_tests.get("detalle_fallos", [])

        # Generar resumen cuantitativo determinista
        resumen_partes = []
        if total > 0:
            resumen_partes.append(f"{pasadas} pasadas")
            if falladas > 0:
                resumen_partes.append(f"{falladas} falladas")
            if errores > 0:
                resumen_partes.append(f"{errores} errores")
            resumen_partes.append(f"de {total} total")
        else:
            resumen_partes.append("Sin tests ejecutados")

        resumen = f"Resumen: {', '.join(resumen_partes)}. Estado global: {estado_global}."

        # Agrupar fallos por ruta (determinista)
        fallos_agrupados = self._agrupar_fallos_por_ruta(detalle_fallos)

        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "resumen": resumen,
                "fallos_agrupados": fallos_agrupados,
            },
        )