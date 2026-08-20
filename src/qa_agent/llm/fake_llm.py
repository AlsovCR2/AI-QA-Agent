"""`FakeLLM`: backend determinista para pruebas y modo `--demo`.

Implementa `LLMBackend` sin red (principio III / SC-006). Devuelve selecciones,
interpretaciones y respuestas configuradas de forma determinista (scripted),
lo que permite probar el bucle del agente, el historial visible, la
autorización y la honestidad sin depender de un proveedor real.

Para el bucle de razonamiento (Phase 12 / T077) soporta además `planificar`,
`razonar`, `evaluar` y `responder` con respuestas configurables por atributo.
"""

from __future__ import annotations

from typing import Any

from qa_agent.agent.reasoning import Plan, PasoDePlan
from qa_agent.llm.backend import LLMBackend


class FakeLLM(LLMBackend):
    """Backend determinista (scripted) para pruebas.

    Configura el comportamiento mediante los atributos:

    - `seleccion`: dict con `{"herramienta": <id>}` o `{"ninguna": True}`.
    - `respuestas_por_solicitud`: mapeo de texto de solicitud -> dict.
    - `por_defecto`: dict devuelto para solicitudes no mapeadas.
    - `plan`: dict con `objetivo`/`criterio_exito`/`pasos` (ver `planificar`).
    - `razonar`: dict con `{"concluir": true}` o `{herramienta, parametros, razon}`.
    - `evaluar`: dict con `{"satisfecha": bool, "razon": str}`.
    - `responder`: dict con `{"texto", "confianza", "recomendaciones"}`.
    """

    nombre = "fake"
    requiere_api_key = False
    proveedor_requerido = False

    def __init__(
        self,
        seleccion: dict[str, Any] | None = None,
        respuestas_por_solicitud: dict[str, dict[str, Any]] | None = None,
        por_defecto: dict[str, Any] | None = None,
        plan: dict[str, Any] | None = None,
        razonar: dict[str, Any] | None = None,
        evaluar: dict[str, Any] | None = None,
        responder: dict[str, Any] | None = None,
        soporta_razonamiento: bool = False,
    ) -> None:
        self._seleccion = seleccion if seleccion is not None else {"ninguna": True}
        self._respuestas_por_solicitud = respuestas_por_solicitud or {}
        self._por_defecto = por_defecto or {
            "texto": "Respuesta determinista del FakeLLM.",
            "confianza": "alta",
            "basada_en_herramientas": False,
        }
        self._plan_config = plan
        self._razonar_config = razonar
        self._evaluar_config = evaluar
        self._responder_config = responder or {
            "texto": "Respuesta determinista del FakeLLM.",
            "confianza": "alta",
            "recomendaciones": [],
        }
        self.soporta_razonamiento = soporta_razonamiento

    # -- helpers --------------------------------------------------------

    def _respuesta_para(self, solicitud: dict[str, Any]) -> dict[str, Any]:
        texto = solicitud.get("texto", "")
        return self._respuestas_por_solicitud.get(texto, self._por_defecto)

    # -- contrato LLMBackend -------------------------------------------

    def interpretar(self, solicitud: dict[str, Any]) -> dict[str, Any]:
        """Interpreta la solicitud de forma determinista.

        Devuelve una intención con `accion` y, opcionalmente, la selección
        configurada para esta solicitud.
        """
        base = self._respuesta_para(solicitud).get("interpretacion", {})
        if isinstance(base, dict):
            return base
        return {"accion": "responder", "solicitud_id": solicitud.get("id")}

    def seleccionar_herramienta(
        self, solicitud: dict[str, Any], herramientas: list[Any]
    ) -> dict[str, Any]:
        """Devuelve la selección configurada (id de herramienta o "ninguna")."""
        seleccion = self._respuesta_para(solicitud).get("seleccion", self._seleccion)
        if isinstance(seleccion, dict):
            return seleccion
        if isinstance(seleccion, str):
            return {"herramienta": seleccion}
        return {"ninguna": True}

    def generar_respuesta(
        self, solicitud: dict[str, Any], resultados: list[Any]
    ) -> dict[str, Any]:
        """Genera la respuesta configurada para la prueba."""
        respuesta = self._respuesta_para(solicitud)
        texto = respuesta.get("texto") or self._por_defecto["texto"]
        confianza = respuesta.get("confianza", self._por_defecto["confianza"])
        return {
            "texto": texto,
            "solicitud_id": solicitud.get("id"),
            "confianza": confianza,
            "basada_en_herramientas": bool(resultados),
            "recomendaciones": respuesta.get("recomendaciones") or [],
        }

    # -- contrato de razonamiento (Phase 12 / T077) ----------------------

    def planificar(
        self, intencion: Any, catalogo: list[Any], contexto: dict[str, Any]
    ) -> Plan:
        """Genera el plan configurado, usando solo herramientas del catálogo.

        Los pasos cuya herramienta no exista en el catálogo se descartan
        (el plan nunca referencia herramientas inexistentes, FR-032).
        """
        config = self._plan_config or {}
        ids_validos = {h.id for h in catalogo}
        pasos = []
        for paso_dict in config.get("pasos", []):
            if paso_dict.get("herramienta") in ids_validos:
                pasos.append(
                    PasoDePlan(
                        orden=paso_dict.get("orden", 0),
                        razon=paso_dict.get("razon", ""),
                        herramienta=paso_dict["herramienta"],
                        parametros=paso_dict.get("parametros") or {},
                        criterio_salida=paso_dict.get("criterio_salida", ""),
                    )
                )
        return Plan(
            objetivo=config.get("objetivo", ""),
            criterio_exito=config.get("criterio_exito", ""),
            pasos=list(pasos),
            pendientes=list(pasos),
        )

    def razonar(self, estado: Any, pendientes: list[Any]) -> dict[str, Any]:
        """Devuelve `{"concluir": true}` o el siguiente paso configurado."""
        if self._razonar_config is None:
            if not pendientes:
                return {"concluir": True}
            paso = pendientes[0]
            return {
                "herramienta": paso.herramienta,
                "parametros": paso.parametros,
                "razon": paso.razon,
            }
        return dict(self._razonar_config)

    def evaluar(self, estado: Any, observaciones: list[Any]) -> dict[str, Any]:
        """Devuelve la evaluación configurada (determinista).

        Sin configuración explícita, evalúa dinámicamente: satisfecha solo
        cuando no quedan pasos pendientes en el plan (criterio de éxito por
        defecto: agotar el plan).
        """
        if self._evaluar_config is not None:
            return {
                "satisfecha": self._evaluar_config.get("satisfecha", True),
                "razon": self._evaluar_config.get("razon", ""),
            }
        plan = getattr(estado, "plan", None)
        quedan = len(getattr(plan, "pendientes", []) or []) > 0
        return {
            "satisfecha": not quedan,
            "razon": "plan completo" if not quedan else "aún hay pasos pendientes",
        }

    def responder(self, observaciones: list[Any], intencion: str = "") -> dict[str, Any]:
        """Devuelve la respuesta final configurada, anclada en observaciones."""
        return {
            "texto": self._responder_config.get(
                "texto", self._por_defecto["texto"]
            ),
            "confianza": self._responder_config.get("confianza", "alta"),
            "recomendaciones": self._responder_config.get("recomendaciones") or [],
        }