"""Bucle agente-herramienta: `Agent`.

Implementa el flujo fundamental del agente (FR-001..005, FR-020):
interpretar → seleccionar herramienta → ejecutar → validar → autorizar si
sensible → responder, registrando el historial visible en `Sesion`.

El bucle es determinista excepto las tres operaciones delegadas al `LLMBackend`
(interpretar, seleccionar, generar respuesta). Nunca inventa información
(FR-019 / IX) y redacta secretos antes de exponer respuesta o historial
(FR-021 / SC-008 / XI).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from qa_agent.agent.intent_policy import (
    _es_analisis_exhaustivo,
    _es_analisis_global,
    _es_intencion_pruebas,
)
from qa_agent.agent.layer_policy import (
    _es_analisis_capa,
    _es_archivo_codigo,
    _extraer_capa_solicitada,
    _resolver_capa_real,
)
from qa_agent.agent.reasoning import (
    EstadoDelAgente,
    Intencion,
    Observacion,
    PasoDePlan,
    Plan,
)
from qa_agent.agent.runner_detection import (
    _detectar_comando_cobertura,
    _detectar_comando_pruebas,
)
from qa_agent.agent.response import (
    Confianza,
    EstadoAccion,
    RespuestaDelAgente,
)
from qa_agent.agent.router import (
    enrutar_solicitud,
    extraer_contenido,
    extraer_nombre_archivo,
    extraer_objetivo_cripticidad,
    extraer_patron_busqueda,
)
from qa_agent.agent.session import Sesion
from qa_agent.llm.backend import LLMBackend
from qa_agent.security.authorization import GestorDeAutorizacion
from qa_agent.security.redactor import Redactor
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
    validar_resultado,
    validar_resultado_esquema,
)


# Análisis global del proyecto (FR-049): presupuesto ampliado de pasos para
# las intenciones de análisis exhaustivo. Las tablas de frases/regex que
# detectan esas intenciones (análisis global, sugerencia de pruebas, capa
# concreta) viven en `intent_policy.py` y `layer_policy.py` (I02): este módulo
# solo orquesta el bucle e importa los detectores deterministas.
_PRESUPUESTO_ANALISIS_GLOBAL = 18

# Nota de cobertura añadida a la intención cuando un análisis exhaustivo (global
# o de una capa/carpeta concreta) agota el presupuesto de pasos: la respuesta
# debe entregar lo observado y declarar lo que quedó sin analizar (honestidad,
# IX / FR-019), no recomendar re-preguntar.
_NOTAS_COBERTURA_GLOBAL = (
    "\n\n[NOTA DE COBERTURA] Este análisis alcanzó el límite de pasos del "
    "agente antes de agotar el objetivo. Organiza la respuesta por capa y "
    "entrega TODO lo que alcanzaste a observar con su estado real; indica "
    "explícitamente qué capas o archivos quedaron sin analizar. NO sugieras al "
    "usuario volver a preguntar sin antes entregar todo lo analizado."
)

# Herramientas que MODIFICAN el proyecto: requieren autorización y, cuando el
# plan del LLM ya ejecutó lecturas/exploraciones, su paso de escritura se
# re-planifica para anclar el contenido en la evidencia real (T123 / FR-019).
_HERRAMIENTAS_ESCRITURA = ("crear_archivo", "editar_archivo")

# Herramientas que PRODUCEN evidencia real (lecturas, exploraciones, búsquedas
# y casos sugeridos): su presencia en las observaciones habilita la
# re-planificación de la escritura (T123).
_HERRAMIENTAS_EVIDENCIA = (
    "leer_archivo",
    "explore",
    "locate",
    "search",
    "analyze_test_results",
    "generate_test_cases",
)


class Agent:
    """Agente orientado a herramientas (contrato agent-interface-contract.md)."""

    def __init__(
        self,
        backend: LLMBackend,
        herramientas: list[Herramienta],
        allowlist: Any | None = None,
        redactor: Redactor | None = None,
        pasos_max: int = 12,
    ) -> None:
        self._backend = backend
        self._herramientas = {h.id: h for h in herramientas}
        self._allowlist = allowlist
        self._redactor = redactor or Redactor()
        self._sesion = Sesion(self._redactor)
        self._autorizaciones = GestorDeAutorizacion()
        self._indice_solicitud = 0
        self._pasos_max = pasos_max

    @property
    def sesion(self) -> Sesion:
        """Historial visible de la conversación (FR-020 / SC-007)."""
        return self._sesion

    def _registrar_accion(
        self,
        herramienta_id: str,
        entrada: dict[str, Any],
        salida: dict[str, Any],
        estado_: EstadoAccion,
    ) -> None:
        # Entrada/salida ya pasan por el Redactor dentro de `Sesion` (SC-008).
        self._sesion.agregar_accion(herramienta_id, entrada, salida, estado_)

    def _seleccionar_herramienta(self, solicitud_texto: str) -> str | None:
        """Selecciona el id de herramienta o `None` si ninguna es adecuada.

        Primero intenta enrutamiento determinista por palabras clave.
        Si no hay coincidencia, delega al LLMBackend.
        """
        # Enrutamiento determinista por palabras clave (T064)
        herramienta_id = enrutar_solicitud(solicitud_texto)
        if herramienta_id and herramienta_id in self._herramientas:
            return herramienta_id

        # Fallback: delegación al LLMBackend
        catalogo = list(self._herramientas.values())
        seleccion = self._backend.seleccionar_herramienta(
            self._redactor.redactar({"texto": solicitud_texto}), catalogo
        )
        if not isinstance(seleccion, dict):
            return None
        if seleccion.get("ninguna"):
            return None
        return seleccion.get("herramienta")

    def _ruta_base(self) -> str:
        """Raíz autorizada del proyecto (primer perímetro de la allowlist)."""
        if self._allowlist is not None:
            try:
                return str(self._allowlist.perimetros[0])
            except (AttributeError, IndexError, TypeError):
                pass
        return "."

    def _tiene_evidencia_real(self, estado: EstadoDelAgente) -> bool:
        """`True` si la solicitud ya acumuló observaciones de herramientas que
        producen evidencia real (lecturas, exploraciones, búsquedas o casos
        sugeridos), de modo que un paso de escritura pendiente puede
        re-planificarse anclado en lo observado (T123 / FR-019). Determinista,
        sin LLM (VI / SC-010)."""
        for observacion in getattr(estado, "observaciones", []) or []:
            paso = getattr(observacion, "paso", None)
            if getattr(paso, "herramienta", None) in _HERRAMIENTAS_EVIDENCIA:
                return True
        return False

    # -- análisis global del proyecto (FR-049 / T116..T118) ------------------

    def _presupuesto_pasos(self, texto: str) -> int:
        """Presupuesto de pasos del bucle (SC-016), ampliado para análisis
        exhaustivo (análisis global, sugerencia de pruebas o análisis de una
        capa/carpeta concreta): el plan enriquecido por capa necesita más pasos
        que el mínimo."""
        if _es_analisis_exhaustivo(texto) or _es_analisis_capa(texto):
            return max(self._pasos_max, _PRESUPUESTO_ANALISIS_GLOBAL)
        return self._pasos_max

    def _enriquecer_plan_analisis_global(
        self, plan: Plan | None, texto: str
    ) -> Plan | None:
        """Añade pasos deterministas para garantizar cobertura por capa.

        Para una intención de análisis global, detecta con `explore` las capas
        (directorios) de primer nivel REALES de la raíz y añade al plan: un
        `explore` por capa (el listado de todo el árbol se trunca en el
        contexto del LLM) y una lectura (`leer_archivo`) de los archivos de
        código principales de cada capa. El LLM planifica, pero la cobertura
        mínima la garantiza el agente de forma determinista (FR-024 / VI).
        """
        if plan is None or not _es_analisis_exhaustivo(texto):
            return plan
        explore = self._herramientas.get("explore")
        leer = self._herramientas.get("leer_archivo")
        if explore is None or leer is None:
            return plan

        try:
            resultado_raiz = explore.ejecutar(
                {"ruta": self._ruta_base(), "profundidad_max": 1}
            )
        except Exception:  # noqa: BLE001 - sin enriquecer ante errores
            return plan
        if resultado_raiz.estado != EstadoResultado.EXITO:
            return plan
        capas = sorted(
            {
                e.get("ruta_relativa", "")
                for e in (resultado_raiz.datos.get("elementos") or [])
                if e.get("tipo") == "directorio" and e.get("ruta_relativa")
            }
        )
        # Capas de primer nivel (ignora directorios ocultos), acotadas para no
        # desbordar el presupuesto de pasos del análisis.
        capas = [c for c in capas if not c.startswith(".")][:4]
        if not capas:
            return plan

        pasos_extra: list[PasoDePlan] = []
        orden = max((p.orden for p in plan.pasos), default=len(plan.pasos))
        for capa in capas:
            if not self._plan_ya_explora_capa(plan, capa):
                orden += 1
                pasos_extra.append(
                    PasoDePlan(
                        orden=orden,
                        razon=(
                            f"explorar la capa real '{capa}' detectada en la "
                            "raíz"
                        ),
                        herramienta="explore",
                        parametros={
                            "ruta": str(Path(self._ruta_base()) / capa),
                            "profundidad_max": 3,
                        },
                        criterio_salida="estructura completa de la capa",
                    )
                )
            for archivo in self._archivos_codigo_de_capa(explore, capa):
                if self._plan_ya_lee_archivo(plan, archivo):
                    continue
                orden += 1
                pasos_extra.append(
                    PasoDePlan(
                        orden=orden,
                        razon=(
                            f"leer el código real de '{archivo}' de la capa "
                            f"'{capa}'"
                        ),
                        herramienta="leer_archivo",
                        parametros={
                            "ruta": self._ruta_base(),
                            "archivo_relativo": archivo,
                        },
                        criterio_salida="contenido real del archivo",
                    )
                )
        if not pasos_extra:
            return plan
        plan.pasos.extend(pasos_extra)
        plan.pendientes.extend(pasos_extra)
        return plan

    def _enriquecer_plan_pruebas(
        self, plan: Plan | None, texto: str
    ) -> Plan | None:
        """Añade pasos deterministas para una intención de sugerencia de
        pruebas ("¿qué pruebas podemos aplicar?"): localiza las clases reales
        (`locate`) y genera casos de prueba sugeridos (`generate_test_cases`).

        La cobertura por capa ya la garantiza `_enriquecer_plan_analisis_global`
        (se invoca antes y dispara también para estas intenciones). Solo se
        añaden pasos de herramientas presentes en el catálogo y si el plan del
        LLM no los prevé ya (FR-024 / VI).
        """
        if plan is None or not _es_intencion_pruebas(texto):
            return plan
        pasos_extra: list[PasoDePlan] = []
        orden = max((p.orden for p in plan.pasos), default=len(plan.pasos))

        locate = self._herramientas.get("locate")
        if locate is not None and not any(
            p.herramienta == "locate" for p in plan.pasos
        ):
            orden += 1
            pasos_extra.append(
                PasoDePlan(
                    orden=orden,
                    razon=(
                        "localizar las clases reales del proyecto (evidencia "
                        "de qué unidades cubrir con pruebas)"
                    ),
                    herramienta="locate",
                    parametros={
                        "ruta": self._ruta_base(),
                        "patron": r"\bclass\s+\w+",
                        "tipo": "clase",
                    },
                    criterio_salida="clases reales localizadas",
                )
            )

        generar = self._herramientas.get("generate_test_cases")
        if generar is not None and not any(
            p.herramienta == "generate_test_cases" for p in plan.pasos
        ):
            objetivo, cripticidad = extraer_objetivo_cripticidad(texto)
            orden += 1
            pasos_extra.append(
                PasoDePlan(
                    orden=orden,
                    razon="generar casos de prueba sugeridos para la solicitud",
                    herramienta="generate_test_cases",
                    parametros={
                        "ruta": self._ruta_base(),
                        "objetivo": objetivo,
                        "cripticidad": cripticidad,
                    },
                    criterio_salida="casos propuestos basados en código real",
                )
            )
        if not pasos_extra:
            return plan
        plan.pasos.extend(pasos_extra)
        plan.pendientes.extend(pasos_extra)
        return plan

    def _enriquecer_plan_analisis_capa(
        self, plan: Plan | None, texto: str
    ) -> Plan | None:
        """Añade pasos deterministas para analizar UNA capa/carpeta concreta.

        Para intenciones como "explora todas las clases de la capa DAL", el
        plan del LLM suele quedarse en un subconjunto de archivos (los modelos
        rápidos planifican por convención de nombres, no por el árbol real).
        Se enriquece de forma determinista: `explore` de la capa real + una
        `leer_archivo` por cada archivo de código existente hasta el
        presupuesto de pasos (SC-016), de modo que la cobertura de la capa no
        dependa del plan del LLM (FR-024 / VI).
        Solo actúa si la capa existe realmente (FR-019): nunca inventa rutas.
        """
        if plan is None or not _es_analisis_capa(texto):
            return plan
        explore = self._herramientas.get("explore")
        leer = self._herramientas.get("leer_archivo")
        if explore is None or leer is None:
            return plan
        capa = _resolver_capa_real(
            self._ruta_base(), _extraer_capa_solicitada(texto)
        )
        if not capa:
            return plan

        pasos_extra: list[PasoDePlan] = []
        orden = max((p.orden for p in plan.pasos), default=len(plan.pasos))
        ya_explora = self._plan_ya_explora_capa(plan, capa)
        if not ya_explora:
            orden += 1
            pasos_extra.append(
                PasoDePlan(
                    orden=orden,
                    razon=(
                        f"explorar la capa real '{capa}' solicitada por el "
                        "usuario"
                    ),
                    herramienta="explore",
                    parametros={
                        "ruta": str(Path(self._ruta_base()) / capa),
                        "profundidad_max": 3,
                    },
                    criterio_salida="estructura completa de la capa",
                )
            )
        # Límite adaptativo (SC-016): lee los archivos de la capa que quepan en
        # el presupuesto restante del bucle, sin excederlo. Con el tope fijo
        # (p. ej. 12) la capa DAL real de ReservaHotel quedaba incompleta
        # (TipoPagoDAL.cs y UsuarioDAL.cs nunca se leían).
        presupuesto = self._presupuesto_pasos(texto)
        max_lecturas = max(
            0, presupuesto - len(plan.pasos) - (1 if not ya_explora else 0)
        )
        for archivo in self._archivos_codigo_de_capa(
            explore, capa, max_archivos=max_lecturas
        ):
            if self._plan_ya_lee_archivo(plan, archivo):
                continue
            orden += 1
            pasos_extra.append(
                PasoDePlan(
                    orden=orden,
                    razon=(
                        f"leer el código real de '{archivo}' de la capa "
                        f"'{capa}'"
                    ),
                    herramienta="leer_archivo",
                    parametros={
                        "ruta": self._ruta_base(),
                        "archivo_relativo": archivo,
                    },
                    criterio_salida="contenido real del archivo",
                )
            )
        if not pasos_extra:
            return plan
        plan.pasos.extend(pasos_extra)
        plan.pendientes.extend(pasos_extra)
        return plan

    def _archivos_codigo_de_capa(
        self, explore: Herramienta, capa: str, max_archivos: int = 2
    ) -> list[str]:
        """Archivos de código REALES de la capa, relativos a la raíz.

        Descubrimiento determinista con `explore` (FR-024): devuelve los
        archivos que existen, nunca inventados (FR-019).
        """
        try:
            resultado = explore.ejecutar(
                {
                    "ruta": str(Path(self._ruta_base()) / capa),
                    "profundidad_max": 3,
                }
            )
        except Exception:  # noqa: BLE001
            return []
        if resultado.estado != EstadoResultado.EXITO:
            return []
        archivos = sorted(
            str(Path(capa) / e["ruta_relativa"]).replace("\\", "/")
            for e in (resultado.datos.get("elementos") or [])
            if e.get("tipo") == "archivo"
            and _es_archivo_codigo(e.get("ruta_relativa", ""))
        )
        return archivos[:max_archivos]

    def _plan_ya_explora_capa(self, plan: Plan, capa: str) -> bool:
        """True si el plan ya explora esa capa (misma ruta de raíz)."""
        raiz = str(Path(self._ruta_base()) / capa)
        return any(
            p.herramienta == "explore" and p.parametros.get("ruta") == raiz
            for p in plan.pasos
        )

    def _plan_ya_lee_archivo(self, plan: Plan, archivo: str) -> bool:
        """True si el plan ya lee ese archivo (mismo `archivo_relativo`)."""
        return any(
            p.herramienta == "leer_archivo"
            and p.parametros.get("archivo_relativo") == archivo
            for p in plan.pasos
        )

    def _parametros_para(
        self, herramienta: Herramienta, solicitud_texto: str
    ) -> dict[str, Any]:
        """Construye parámetros de ejecución a partir de la solicitud (T064).

        Cada herramienta obtiene los parámetros que su contrato requiere,
        derivados deterministamente de la solicitud y de la ruta autorizada:
        - `ruta` = raíz autorizada (FR-025).
        - `generate_test_cases`: `objetivo`/`cripticidad` extraídos del texto.
        - `run_tests`: el conjunto dentro de la raíz autorizada se considera
          autorizado (la `Allowlist` es el mecanismo de autorización, FR-025);
          la herramienta re-verifica la ruta con su propia allowlist.
        - `analyze_test_results`: encadena `run_tests` y pasa su resultado real.
        """
        ruta_base = self._ruta_base()
        if herramienta.id == "run_tests":
            return {
                "ruta": ruta_base,
                "conjunto_autorizado": True,
                "comando_pruebas": _detectar_comando_pruebas(ruta_base),
            }
        if herramienta.id == "analyze_coverage":
            return {
                "ruta": ruta_base,
                "comando_cobertura": _detectar_comando_cobertura(ruta_base),
            }
        if herramienta.id == "generate_test_cases":
            objetivo, cripticidad = extraer_objetivo_cripticidad(solicitud_texto)
            return {"ruta": ruta_base, "objetivo": objetivo, "cripticidad": cripticidad}
        if herramienta.id == "analyze_test_results":
            return {
                "ruta": ruta_base,
                "resultado_tests": self._resultado_de_pruebas(ruta_base),
            }
        if herramienta.id == "search":
            # Sin patrón extraído → la herramienta informa la ausencia en vez de
            # buscar con un regex vacío que coincidiría con todo (FR-019, SC-002).
            return {
                "ruta": ruta_base,
                "patron_regex": extraer_patron_busqueda(solicitud_texto),
            }
        if herramienta.id == "locate":
            return {
                "ruta": ruta_base,
                "patron": extraer_patron_busqueda(solicitud_texto),
            }
        if herramienta.id == "leer_archivo":
            return {
                "ruta": ruta_base,
                "archivo_relativo": extraer_nombre_archivo(solicitud_texto),
            }
        if herramienta.id == "crear_archivo":
            return {
                "ruta": ruta_base,
                "archivo_relativo": extraer_nombre_archivo(solicitud_texto),
                "contenido": extraer_contenido(solicitud_texto),
            }
        if herramienta.id == "editar_archivo":
            return {
                "ruta": ruta_base,
                "archivo_relativo": extraer_nombre_archivo(solicitud_texto),
                "contenido": extraer_contenido(solicitud_texto),
            }
        if herramienta.id == "eliminar_archivo":
            return {
                "ruta": ruta_base,
                "archivo_relativo": extraer_nombre_archivo(solicitud_texto),
            }
        return {"ruta": ruta_base}

    def _resultado_de_pruebas(self, ruta_base: str) -> dict[str, Any]:
        """Ejecuta `run_tests` (si está disponible) y devuelve su resultado real.

        Usado como entrada de `analyze_test_results` (secuencia
        run_tests → analyze_test_results). Ante fallo o ausencia de la
        herramienta, reporta `no_ejecutado` de forma explícita (FR-017/018).
        """
        vacio = {
            "pasadas": 0,
            "falladas": 0,
            "errores": 0,
            "total": 0,
            "estado_global": "no_ejecutado",
            "detalle_fallos": [],
        }
        run_tests = self._herramientas.get("run_tests")
        if run_tests is None:
            return dict(vacio)
        try:
            resultado = run_tests.ejecutar(
                {
                    "ruta": ruta_base,
                    "conjunto_autorizado": True,
                    "comando_pruebas": _detectar_comando_pruebas(ruta_base),
                }
            )
        except Exception:  # noqa: BLE001 - nunca inventar resultados
            return dict(vacio)
        if resultado.estado == EstadoResultado.EXITO:
            # La ejecución real de run_tests queda registrada en el historial
            # (secuencia run_tests → analyze_test_results, FR-020).
            self._registrar_accion(
                "run_tests", {}, resultado.datos, EstadoAccion.EXITO
            )
            if isinstance(resultado.datos, dict):
                return resultado.datos
        if resultado.estado in (EstadoResultado.ERROR, EstadoResultado.INVALIDO):
            self._registrar_accion(
                "run_tests", {}, resultado.datos, EstadoAccion.ERROR
            )
        return dict(vacio)

    def _ejecutar_herramienta(
        self, herramienta: Herramienta, solicitud_texto: str
    ) -> ResultadoDeHerramienta:
        """Ejecuta una herramienta con el resultado real (FR-003/004).

        Los parámetros de entrada se derivan de la solicitud y de la ruta
        autorizada de forma determinista (VI); cada herramienta aplica sus
        propios defaults por contrato.
        """
        parametros = self._parametros_para(herramienta, solicitud_texto)
        return herramienta.ejecutar(parametros)

    def _validar_y_usar(
        self, herramienta: Herramienta, resultado: ResultadoDeHerramienta
    ) -> bool:
        """Valida el resultado contra el esquema de salida (FR-005)."""
        return validar_resultado(herramienta, resultado)

    def atender(
        self,
        solicitud_texto: str,
        autorizacion: bool | None = None,
        contexto: dict[str, Any] | None = None,
    ) -> RespuestaDelAgente:
        """Procesa una solicitud y genera una respuesta basada en evidencia.

        `autorizacion` es la decisión del usuario sobre una acción sensible:
        - `None`: sin decisión → se crea la acción pendiente, se suspende la
          ejecución y se solicita autorización (FR-015/016, SC-004).
        - `True`: autorizada → se ejecuta la herramienta.
        - `False`: denegada → no se ejecuta y se notifica (FR-016).

        `contexto` (opcional, Phase 13 / T088) es contexto conversacional
        (historial reciente, resumen, tareas) que se inyecta en
        `Intencion.contexto` antes de `planificar` para que el LLM razone con
        la memoria de la sesión.

        Cuando el backend soporta razonamiento (`soporta_razonamiento=True`,
        Phase 12 / T078), se usa el bucle ReAct: percibir → pensar (plan) →
        actuar → observar → reflexionar → decidir. En caso contrario se usa el
        flujo de una sola pasada (compatibilidad).
        """
        texto = (solicitud_texto or "").strip()
        self._indice_solicitud += 1
        solicitud_id = f"s{self._indice_solicitud}"
        if not texto:
            return RespuestaDelAgente(
                texto="Recibí una solicitud vacía. Por favor, indica qué quieres "
                "analizar o validar del proyecto (FR-001).",
                solicitud_id=solicitud_id,
                confianza=Confianza.SIN_INFORMACION,
            )
        self._sesion.registrar_solicitud(
            {"id": solicitud_id, "texto": self._redactor.redactar(texto)}
        )

        if getattr(self._backend, "soporta_razonamiento", False):
            return self._atender_react(texto, solicitud_id, autorizacion, contexto)

        return self._atender_una_pasada(texto, solicitud_id, autorizacion, contexto)

    def _atender_una_pasada(
        self,
        texto: str,
        solicitud_id: str,
        autorizacion: bool | None,
        contexto: dict[str, Any] | None = None,
    ) -> RespuestaDelAgente:
        """Flujo de una sola pasada (compatibilidad, sin razonamiento LLM)."""

        # Interpretación (puede requerir LLM) — actualmente la selección de
        # herramienta es el único paso que delega al backend.
        herramienta_id = self._seleccionar_herramienta(texto)

        if herramienta_id is None or herramienta_id not in self._herramientas:
            # FR-022/023, SC-009: notificación + sugerencia sin ejecutar.
            return RespuestaDelAgente(
                texto=(
                    "No dispongo de una herramienta adecuada para atender esa "
                    "solicitud. Prueba a pedir explorar la estructura, localizar "
                    "archivos, buscar patrones o ejecutar pruebas (FR-022)."
                ),
                solicitud_id=solicitud_id,
                confianza=Confianza.SIN_INFORMACION,
            )

        herramienta = self._herramientas[herramienta_id]

        # analyze_test_results es determinista si recibe resultados, pero esta
        # ruta de una pasada los obtiene ejecutando run_tests en
        # _parametros_para; por eso hereda su frontera antes de construir
        # parámetros (T126 / FR-015/016).
        requiere_autorizacion = (
            herramienta.requiere_autorizacion
            or (
                herramienta.id == "analyze_test_results"
                and "run_tests" in self._herramientas
            )
        )

        # Acción sensible → suspender y solicitar autorización (FR-015/016).
        if requiere_autorizacion:
            accion = self._autorizaciones.crear(
                id=f"a{self._indice_solicitud}",
                descripcion=(
                    f"Ejecutar la herramienta '{herramienta.id}' para la "
                    "solicitud solicitada."
                ),
                herramienta_id=herramienta.id,
            )
            if autorizacion is False:
                # Denegada → no se ejecuta y se notifica (FR-016).
                self._autorizaciones.denegar(accion.id)
                self._autorizaciones.marcar_no_ejecutada(accion.id)
                self._registrar_accion(
                    herramienta.id,
                    {},
                    {"estado": "denegada"},
                    EstadoAccion.ERROR,
                )
                return RespuestaDelAgente(
                    texto=(
                        f"La acción que requiere la herramienta "
                        f"'{herramienta.id}' fue denegada y no se ejecutó "
                        "(FR-016)."
                    ),
                    solicitud_id=solicitud_id,
                    acciones=[a for a in self._sesion.acciones],
                    confianza=Confianza.SIN_INFORMACION,
                )
            if autorizacion is not True:
                # Pendiente de autorización → ejecución suspendida (SC-004).
                self._registrar_accion(
                    herramienta.id,
                    {"requiere_autorizacion": True},
                    {"estado": "pendiente_autorizacion"},
                    EstadoAccion.PENDIENTE_AUTORIZACION,
                )
                return RespuestaDelAgente(
                    texto=(
                        f"La acción que requiere la herramienta '{herramienta.id}' "
                        "está pendiente de autorización y no se ejecutará hasta "
                        "que sea autorizada (FR-015/016)."
                    ),
                    solicitud_id=solicitud_id,
                    acciones=[a for a in self._sesion.acciones],
                    confianza=Confianza.SIN_INFORMACION,
                )
            # Autorizada → la ejecución puede proceder (SC-004).
            self._autorizaciones.autorizar(accion.id)

        # Ejecutar la herramienta (determinista) y validar (FR-005) ante la
        # allowlist (mínimo privilegio, FR-025).
        if self._allowlist is not None:
            try:
                permitida = self._allowlist.contiene(self._ruta_base())
            except Exception:
                permitida = False
            if not permitida:
                return RespuestaDelAgente(
                    texto=(
                        "No puedo acceder a la ruta solicitada porque queda "
                        "fuera de las rutas autorizadas (FR-025)."
                    ),
                    solicitud_id=solicitud_id,
                    confianza=Confianza.SIN_INFORMACION,
                )

        try:
            resultado = self._ejecutar_herramienta(herramienta, texto)
        except Exception as error:  # noqa: BLE001 - manejo de errores seguro
            self._registrar_accion(
                herramienta.id, {}, {"error": str(error)}, EstadoAccion.ERROR
            )
            return RespuestaDelAgente(
                texto=(
                    f"La herramienta '{herramienta.id}' falló al ejecutarse. "
                    f"Error: {self._redactor.redactar(str(error))} (FR-018)."
                ),
                solicitud_id=solicitud_id,
                acciones=[a for a in self._sesion.acciones],
                confianza=Confianza.LIMITADA,
            )

        if not self._validar_y_usar(herramienta, resultado):
            # Resultado inválido o con error → se registra y comunica
            # explícitamente; nunca se usa como fuente de verdad (FR-018, SC-005).
            estado_registro = (
                EstadoAccion.ERROR
                if resultado.estado == EstadoResultado.ERROR
                else EstadoAccion.INVALIDO
            )
            self._registrar_accion(
                herramienta.id,
                {},
                resultado.datos,
                estado_registro,
            )
            return RespuestaDelAgente(
                texto=(
                    f"La herramienta '{herramienta.id}' devolvió un resultado "
                    f"{'con error' if resultado.estado == EstadoResultado.ERROR else 'inválido'}"
                    " y no lo presento como válido (FR-005/018)."
                ),
                solicitud_id=solicitud_id,
                acciones=[a for a in self._sesion.acciones],
                confianza=Confianza.LIMITADA,
            )

        self._registrar_accion(
            herramienta.id,
            {},
            resultado.datos,
            EstadoAccion.EXITO,
        )

        if requiere_autorizacion:
            # Comando autorizado ejecutado → autorizada → ejecutada (data-model).
            self._autorizaciones.marcar_ejecutada(f"a{self._indice_solicitud}")

        # Generar la respuesta basada en el resultado real validado (FR-004).
        respuesta_generada = self._backend.generar_respuesta(
            self._redactor.redactar({"texto": texto, "id": solicitud_id}),
            self._redactor.redactar([resultado]),
        )
        if not isinstance(respuesta_generada, dict):
            respuesta_generada = {}

        confianza_raw = respuesta_generada.get(
            "confianza", Confianza.ALTA.value
        )
        try:
            confianza = Confianza(confianza_raw)
        except ValueError:
            confianza = Confianza.ALTA

        respuesta = RespuestaDelAgente(
            texto=self._redactor.redactar(
                respuesta_generada.get("texto", "")
            ) or "No tengo una respuesta basada en evidencia para eso.",
            solicitud_id=solicitud_id,
            acciones=[a for a in self._sesion.acciones],
            confianza=confianza,
            basada_en_herramientas=True,
            recomendaciones=self._recomendaciones_redactadas(respuesta_generada),
        )
        self._sesion.registrar_respuesta(respuesta)
        return respuesta

    def _recomendaciones_redactadas(self, respuesta_generada: dict[str, Any]) -> list[str]:
        """Recomendaciones del backend, redactadas antes de exponerlas (SC-008)."""
        recomendaciones = respuesta_generada.get("recomendaciones", [])
        if not isinstance(recomendaciones, list):
            return []
        return [
            self._redactor.redactar(str(item))
            for item in recomendaciones
            if str(item).strip()
        ]

    # -- bucle ReAct (Phase 12 / T078) ------------------------------------

    def _atender_react(
        self,
        texto: str,
        solicitud_id: str,
        autorizacion: bool | None,
        contexto: dict[str, Any] | None = None,
    ) -> RespuestaDelAgente:
        """Bucle percibir → pensar → actuar → observar → reflexionar → decidir.

        - **Percibir**: construye la `Intencion` (objetivo, entidad, contexto).
        - **Pensar**: genera un plan multi-paso con criterio de éxito (FR-032).
        - **Actuar/Observar**: ejecuta pasos reales y acumula observaciones.
        - **Reflexionar/Decidir**: evalúa si la evidencia satisface la
          intención; concluye o itera, dentro de `pasos_max` (SC-016).

        `contexto` (Phase 13 / T088) fusiona memoria conversacional en el
        contexto de la intención (historial reciente, resumen, tareas).
        """
        intencion = Intencion(
            texto=texto,
            contexto={
                "ruta_base": self._ruta_base(),
                "catalogo": [
                    {"id": h.id, "descripcion": h.descripcion,
                     "esquema_entrada": h.esquema_entrada}
                    for h in self._herramientas.values()
                ],
            },
        )
        if contexto:
            intencion.contexto.update(contexto)
        try:
            plan = self._backend.planificar(
                self._redactor.redactar(intencion),
                list(self._herramientas.values()),
                self._redactor.redactar(intencion.contexto),
            )
        except Exception:  # noqa: BLE001 - degradar sin romper el agente
            plan = None
        # Cobertura determinista del análisis global (FR-049): el plan del LLM
        # se enriquece con pasos que recorren las capas reales del proyecto
        # (explore por capa + leer_archivo de su código principal).
        plan = self._enriquecer_plan_analisis_global(plan, texto)
        plan = self._enriquecer_plan_pruebas(plan, texto)
        # Cobertura determinista del análisis de una capa/carpeta concreta
        # (FR-049 / T122): el plan se enriquece con `explore` de la capa real y
        # `leer_archivo` de CADA archivo de código existente, para que el
        # resultado no dependa del subconjunto que planifique el LLM.
        plan = self._enriquecer_plan_analisis_capa(plan, texto)

        estado = EstadoDelAgente(
            intencion=intencion,
            plan=plan,
            pasos_max=self._presupuesto_pasos(texto),
        )
        observaciones: list[Observacion] = []

        if plan is not None:
            while not estado.excedio_pasos_max():
                # Mientras queden pasos pendientes, el plan ya define qué
                # ejecutar: se toma el siguiente pendiente sin otra llamada LLM
                # (optimización: `razonar` solo re-planifica cuando se agota el
                # plan, p.ej. evidencia insuficiente o paso denegado).
                if plan.pendientes:
                    pendiente = plan.pendientes[0]
                    siguiente = {
                        "herramienta": pendiente.herramienta,
                        "parametros": dict(pendiente.parametros),
                        "razon": pendiente.razon,
                    }
                    # T123: re-planificar la escritura con la evidencia real.
                    # El `contenido` de un paso `crear_archivo`/`editar_archivo`
                    # del plan se generó ANTES de ejecutar las lecturas/
                    # exploraciones y puede no estar anclado en lo observado
                    # (FR-019). Si la solicitud ya acumuló evidencia real, se le
                    # pide al backend regenerar el paso de escritura; si no
                    # produce uno (p.ej. `concluir`), se usa el del plan, que el
                    # rail de ruta y la allowlist validan igual.
                    if (
                        pendiente.herramienta in _HERRAMIENTAS_ESCRITURA
                        and self._tiene_evidencia_real(estado)
                    ):
                        try:
                            replan = self._backend.razonar(
                                self._redactor.redactar(estado),
                                self._redactor.redactar(plan.pendientes),
                            )
                        except Exception:  # noqa: BLE001
                            replan = None
                        if (
                            isinstance(replan, dict)
                            and replan.get("herramienta")
                            in _HERRAMIENTAS_ESCRITURA
                        ):
                            parametros = dict(pendiente.parametros)
                            parametros.update(replan.get("parametros") or {})
                            siguiente = {
                                "herramienta": replan["herramienta"],
                                "parametros": parametros,
                                "razon": (
                                    replan.get("razon") or pendiente.razon
                                ),
                            }
                else:
                    try:
                        siguiente = self._backend.razonar(
                            self._redactor.redactar(estado),
                            self._redactor.redactar(plan.pendientes),
                        )
                    except Exception:  # noqa: BLE001
                        siguiente = None
                    if not isinstance(siguiente, dict):
                        break
                    if siguiente.get("concluir"):
                        break

                observacion = self._ejecutar_siguiente_paso(
                    estado, siguiente, autorizacion
                )
                if observacion is None:
                    # Paso no ejecutable (denegado/inválido/sin herramienta):
                    # se omite y se continúa con el siguiente pendiente, o se
                    # concluye si no queda ninguno (FR-036).
                    if not plan.pendientes:
                        break
                    continue
                observaciones.append(observacion)
                estado.registrar_observacion(observacion)
                if observacion.paso is not None:
                    plan.marcar_completado(observacion.paso)
                # Reflexionar solo cuando el plan se agota o se alcanza el
                # límite de pasos (ahorra llamadas LLM en planes multi-paso).
                if not plan.pendientes or estado.excedio_pasos_max():
                    try:
                        evaluacion = self._backend.evaluar(
                            self._redactor.redactar(estado),
                            self._redactor.redactar(observaciones),
                        )
                    except Exception:  # noqa: BLE001
                        evaluacion = {"satisfecha": False, "razon": ""}
                    if evaluacion.get("satisfecha"):
                        break

        return self._respuesta_react(
            texto,
            solicitud_id,
            observaciones,
            agotado_presupuesto=estado.excedio_pasos_max(),
        )

    def _resolver_archivo_real(self, archivo_relativo: str) -> str | None:
        """Ruta REAL del archivo (relativa al perímetro), o `None` si no existe.

        Si la ruta propuesta no existe como archivo, busca dentro del perímetro
        (FR-025) un archivo real con el mismo nombre (case-insensitive) y
        devuelve su ruta real (p. ej. 'Datos/ClienteDAL.cs' → 'DAL/ClienteDAL.cs'
        cuando el proyecto usa esa carpeta). Determinista y sin LLM (VI /
        SC-010). Devuelve `None` si no hay ningún archivo real con ese nombre
        (la herramienta informa la ausencia honestamente, FR-019).
        """
        archivo = (archivo_relativo or "").strip()
        if not archivo:
            return None
        ruta_base = Path(self._ruta_base())
        propuesta = ruta_base / archivo
        destino = propuesta if propuesta.is_file() else None
        if destino is None:
            destino = self._buscar_archivo_por_nombre(propuesta.name)
        if destino is None:
            return None
        try:
            return destino.relative_to(ruta_base).as_posix()
        except ValueError:
            # Fuera del perímetro: la allowlist / la herramienta lo rechazan.
            return None

    def _corregir_escritura(
        self, herramienta_id: str, parametros: dict[str, Any], texto: str
    ) -> tuple[str, dict[str, Any]] | None:
        """Resuelve la ruta REAL de un paso `crear_archivo`/`editar_archivo`.

        El LLM propone `archivo_relativo` por convención, sin verificar el
        filesystem (regresión real con ReservaHotel: pedía modificar
        'docs/UnitTest.md' y el paso creaba 'UnitTest.md' en la raíz).
        Devuelve `(id_herramienta, parametros)` corregidos, o `None` si no hay
        cambio (determinista, sin LLM, VI / SC-010):
        - Si `archivo_relativo` está vacío o es un placeholder, se deriva de la
          solicitud con `extraer_nombre_archivo` (igual que en `leer_archivo`).
        - Si el destino propuesto no existe pero hay un archivo real con el
          mismo nombre dentro del perímetro (FR-025), `archivo_relativo` pasa a
          la ruta real.
        - Si el destino final YA existe y el paso es `crear_archivo`, se mapea
          a `editar_archivo` (FR-042): crear sobre un archivo existente se
          rechaza sin modificar nada y la intención real era modificarlo.
        - `editar_archivo` sobre un destino inexistente se deja igual: la
          herramienta lo rechaza honestamente sin modificar nada (FR-043).
        """
        archivo = (parametros.get("archivo_relativo") or "").strip()
        if not archivo or "{" in archivo or "}" in archivo:
            archivo = extraer_nombre_archivo(texto).strip()
            if not archivo:
                return None
        archivo_real = self._resolver_archivo_real(archivo)
        if archivo_real is None:
            return None
        nuevo_id = (
            "editar_archivo" if herramienta_id == "crear_archivo" else herramienta_id
        )
        if nuevo_id == herramienta_id and archivo_real == archivo:
            return None
        corregidos = dict(parametros)
        corregidos["archivo_relativo"] = archivo_real
        return (nuevo_id, corregidos)

    def _buscar_archivo_por_nombre(self, nombre: str) -> Path | None:
        """Primer archivo REAL con ese nombre dentro del perímetro (T123).

        Recorrido del árbol autorizado (FR-025) ignorando artefactos de
        build/control de versiones y directorios ocultos (igual que
        `explore`/`_resolver_capa_real`); coincidencia case-insensitive.
        Determinista y sin LLM (VI / SC-010). Devuelve `None` si no existe
        ningún archivo con ese nombre.
        """
        base = Path(self._ruta_base())
        if not base.is_dir():
            return None
        ignorados = {".git", ".vs", "bin", "obj", "packages", "node_modules"}
        por_visitar = [base]
        while por_visitar:
            actual = por_visitar.pop(0)
            try:
                hijos = list(actual.iterdir())
            except OSError:
                continue
            for hijo in hijos:
                if hijo.name in ignorados or (
                    hijo.is_dir() and hijo.name.startswith(".")
                ):
                    continue
                if hijo.is_file() and hijo.name.lower() == nombre.lower():
                    return hijo
                if hijo.is_dir():
                    por_visitar.append(hijo)
        return None

    def _buscar_directorio_por_nombre(self, nombre: str) -> Path | None:
        """Primer directorio REAL con ese nombre dentro del perímetro (T124).

        Análogo a `_buscar_archivo_por_nombre` para `explore`: recorre el árbol
        autorizado (FR-025) ignorando artefactos de build/control de versiones
        y directorios ocultos; coincidencia case-insensitive. Determinista y
        sin LLM (VI / SC-010). Devuelve `None` si no existe ningún directorio
        con ese nombre.
        """
        base = Path(self._ruta_base())
        if not base.is_dir():
            return None
        ignorados = {".git", ".vs", "bin", "obj", "packages", "node_modules"}
        por_visitar = [base]
        while por_visitar:
            actual = por_visitar.pop(0)
            try:
                hijos = list(actual.iterdir())
            except OSError:
                continue
            for hijo in hijos:
                if hijo.name in ignorados or (
                    hijo.is_dir() and hijo.name.startswith(".")
                ):
                    continue
                if hijo.is_dir() and hijo.name.lower() == nombre.lower():
                    return hijo
                if hijo.is_dir():
                    por_visitar.append(hijo)
        return None

    def _resolver_directorio_real(self, ruta: str) -> str | None:
        """Ruta REAL (absoluta) de un directorio, o `None` si no existe (T124).

        Si la ruta propuesta no existe como directorio, busca dentro del
        perímetro (FR-025) un directorio real con el mismo nombre
        (case-insensitive) y devuelve su ruta real. Determinista y sin LLM
        (VI / SC-010). Devuelve `None` si no hay ningún directorio real con ese
        nombre (la herramienta informa la ausencia honestamente, FR-019).
        """
        propuesta = Path(ruta)
        if propuesta.is_dir():
            return str(propuesta)
        destino = self._buscar_directorio_por_nombre(propuesta.name)
        return str(destino) if destino is not None else None

    def _capas_reales(self) -> list[str]:
        """Directorios REALES de primer nivel de la raíz (T124).

        Descubrimiento determinista con `explore` (FR-024 / VI): devuelve solo
        directorios que existen, nunca inventados (FR-019), sin ocultos.
        """
        explore = self._herramientas.get("explore")
        if explore is None:
            return []
        try:
            resultado = explore.ejecutar(
                {"ruta": self._ruta_base(), "profundidad_max": 1}
            )
        except Exception:  # noqa: BLE001
            return []
        if resultado.estado != EstadoResultado.EXITO:
            return []
        capas = sorted(
            {
                e.get("ruta_relativa", "")
                for e in (resultado.datos.get("elementos") or [])
                if e.get("tipo") == "directorio" and e.get("ruta_relativa")
            }
        )
        return [c for c in capas if not c.startswith(".")]

    def _encolar_explore_capas_reales(self, estado: EstadoDelAgente) -> None:
        """Encola `explore` de cada capa REAL de primer nivel (T124 / FR-024).

        Regresión real con ReservaHotel: el LLM planifica `explore` sobre una
        capa cuyo nombre inventa por convención de archivos `.csproj`
        ('Datos' en vez de la carpeta real 'DAL'), la ruta no existe y el
        agente solo reporta `existe=False` sin evidencia útil. Cuando un
        `explore` pendiente apunta a una ruta inexistente se enriquecen las
        capas reales detectadas deterministamente, acotadas al presupuesto
        restante (SC-016), para que la respuesta se ancle en la estructura real
        (FR-019) en vez de solo en la ausencia.
        """
        plan = getattr(estado, "plan", None)
        if plan is None:
            return
        disponibles = max(
            0,
            estado.pasos_max - estado.pasos_ejecutados - len(plan.pendientes),
        )
        orden = max((p.orden for p in plan.pasos), default=len(plan.pasos))
        nuevos: list[PasoDePlan] = []
        for capa in self._capas_reales():
            if disponibles <= 0:
                break
            if self._plan_ya_explora_capa(plan, capa):
                continue
            disponibles -= 1
            orden += 1
            nuevos.append(
                PasoDePlan(
                    orden=orden,
                    razon=(
                        f"explorar la capa real '{capa}' (la ruta del plan del "
                        "LLM no existe)"
                    ),
                    herramienta="explore",
                    parametros={
                        "ruta": str(Path(self._ruta_base()) / capa),
                        "profundidad_max": 3,
                    },
                    criterio_salida="estructura completa de la capa",
                )
            )
        if not nuevos:
            return
        plan.pasos.extend(nuevos)
        # Al frente de los pendientes: la evidencia real de las capas se
        # recoge antes de cualquier paso posterior del plan del LLM.
        plan.pendientes[:0] = nuevos

    def _ejecutar_siguiente_paso(
        self,
        estado: EstadoDelAgente,
        siguiente: dict[str, Any],
        autorizacion: bool | None,
    ) -> Observacion | None:
        """Ejecuta el paso razonado (o devuelve `None` si no es ejecutable).

        Valida que la herramienta exista, que los parámetros cumplan el
        esquema y estén dentro de la allowlist (FR-033 / FR-025), gestiona la
        autorización (SC-004) y ejecuta el resultado real.
        """
        herramienta_id = siguiente.get("herramienta")
        herramienta = self._herramientas.get(herramienta_id)
        if herramienta is None:
            return None

        parametros = siguiente.get("parametros") or {}

        # Corrección determinista de escritura (T123 / FR-042..047): el LLM
        # suele proponer `archivo_relativo` por convención sin haber localizado
        # el archivo real (regresión real con ReservaHotel: pedía modificar
        # 'docs/UnitTest.md' y el paso creaba 'UnitTest.md' en la raíz, porque
        # `crear_archivo` rechaza un archivo existente y en la raíz no hay ese
        # archivo). Se resuelve la ruta real dentro del perímetro (FR-025) y,
        # si el destino ya existe, se usa `editar_archivo` en vez de
        # `crear_archivo` (FR-042), sin duplicar ni rechazar por un nombre mal
        # resuelto.
        herramienta_id_original = herramienta.id
        if herramienta.id in ("crear_archivo", "editar_archivo"):
            corregido = self._corregir_escritura(
                herramienta.id,
                parametros,
                getattr(estado.intencion, "texto", "") or "",
            )
            if corregido is not None:
                herramienta_id, parametros = corregido
                herramienta = self._herramientas.get(herramienta_id)
                if herramienta is None:
                    return None

        # Identificar el paso del plan (o construir uno) y marcarlo completado
        # de inmediato si pertenece al plan: tanto si se ejecuta como si se
        # omite (denegado/inválido), el bucle continúa con el siguiente
        # pendiente (FR-036) sin reintentar. Solo se emparejan pasos PENDIENTES:
        # un paso ya ejecutado no debe reutilizarse para dar forma a un paso
        # nuevo del razonamiento (T114 / FR-035) — eso mezclaba la razón y los
        # parámetros del plan con los parámetros realmente ejecutados y rompía
        # la trazabilidad y el dedup de pasos idénticos.
        paso = None
        for p in getattr(estado.plan, "pendientes", []) or []:
            if getattr(p, "herramienta", None) == herramienta.id:
                paso = p
                break
        if paso is None:
            from qa_agent.agent.reasoning import PasoDePlan

            paso = PasoDePlan(
                orden=estado.pasos_ejecutados + 1,
                razon=siguiente.get("razon", ""),
                herramienta=herramienta.id,
                parametros=parametros,
            )
        if getattr(estado.plan, "pendientes", None) and paso in estado.plan.pendientes:
            estado.plan.marcar_completado(paso)
        if herramienta.id != herramienta_id_original:
            # El paso del plan apuntaba a la herramienta original (p. ej.
            # `crear_archivo` → `editar_archivo` tras la corrección): se marca
            # completado para que no quede pendiente ni se reintente (FR-036).
            for p in getattr(estado.plan, "pendientes", []) or []:
                if getattr(p, "herramienta", None) == herramienta_id_original:
                    estado.plan.marcar_completado(p)
                    break

        # Saneo de `leer_archivo` en el path ReAct (T111 / FR-033, FR-048):
        # el LLM puede proponer un placeholder (p. ej. "{{ruta_relativa_archivo_prueba}}")
        # o un nombre vacío en vez de un archivo real. Se deriva el archivo de la
        # solicitud (extraer_nombre_archivo); si no puede resolverse, el paso se
        # rechaza sin ejecutar (una lectura con un placeholder solo reportaría
        # existe=false y desperdiciaría el paso) para forzar la re-planificación.
        if herramienta.id == "leer_archivo":
            archivo_propuesto = parametros.get("archivo_relativo")
            if not isinstance(archivo_propuesto, str) or not archivo_propuesto.strip():
                archivo_propuesto = ""
            es_placeholder = "{" in archivo_propuesto or "}" in archivo_propuesto
            if not archivo_propuesto or es_placeholder:
                derivado = extraer_nombre_archivo(
                    getattr(estado.intencion, "texto", "") or ""
                )
                if derivado:
                    parametros["archivo_relativo"] = derivado
                else:
                    self._registrar_accion(
                        herramienta.id,
                        dict(parametros),
                        {"estado": "archivo_no_identificado"},
                        EstadoAccion.ERROR,
                    )
                    return None
            # T123: resolver la ruta REAL dentro del perímetro cuando el LLM
            # propone una ruta de lectura que no existe pero hay un archivo con
            # el mismo nombre (regresión real con ReservaHotel: el LLM leía
            # 'Datos/ClienteDAL.cs' cuando la carpeta real es 'DAL', y la
            # evidencia se perdía: existe=False). La lectura se corrige a la
            # ruta real (FR-025); si no hay ningún archivo real con ese nombre,
            # se deja como está y la herramienta informa la ausencia (FR-019).
            archivo = (parametros.get("archivo_relativo") or "").strip()
            real = self._resolver_archivo_real(archivo)
            if real is not None and real != archivo:
                parametros["archivo_relativo"] = real

        # Rail de `explore` (T124 / FR-048, FR-019): igual que la lectura, la
        # ruta de exploración que propone el LLM suele inventarse por convención
        # de nombres (regresión real con ReservaHotel: planificaba 'Datos'
        # cuando la carpeta real es 'DAL'). Si la ruta no existe, se resuelve a
        # un directorio real con el mismo nombre dentro del perímetro (FR-025);
        # y si aun así no existe, se enriquecen deterministamente las capas
        # reales de primer nivel para que la respuesta no quede anclada solo en
        # un `explore` vacío (existe=False) sino en la estructura real.
        if herramienta.id == "explore":
            ruta_explore = parametros.get("ruta")
            if isinstance(ruta_explore, str) and ruta_explore.strip():
                real_dir = self._resolver_directorio_real(ruta_explore)
                if real_dir is not None and real_dir != ruta_explore:
                    parametros["ruta"] = real_dir
            ruta_explore_final = str(
                parametros.get("ruta") or self._ruta_base()
            )
            if not Path(ruta_explore_final).exists():
                self._encolar_explore_capas_reales(estado)

        # Evitar pasos repetidos (T112 / FR-034): si un paso idéntico (misma
        # herramienta y mismos parámetros) ya se ejecutó en esta solicitud, se
        # omite. Re-ejecutarlo es determinista y no aporta evidencia nueva; solo
        # desperdicia el presupuesto de pasos (regresión: `locate` repetido 4
        # veces en una sesión real con ReservaHotel). La `ruta` se compara
        # normalizada (vacía → raíz autorizada, se inyecta después): pasos que
        # apuntan a subárboles DISTINTOS (p. ej. un `explore` por capa del
        # análisis global, T117) no son repeticiones aunque compartan el resto
        # de parámetros.
        for observacion in getattr(estado, "observaciones", []) or []:
            paso_previo = getattr(observacion, "paso", None)
            previos = {
                k: v
                for k, v in (getattr(paso_previo, "parametros", None) or {}).items()
                if k != "ruta"
            }
            ruta_previa = (getattr(paso_previo, "parametros", None) or {}).get("ruta")
            misma_ruta = (
                ruta_previa or self._ruta_base()
            ) == (parametros.get("ruta") or self._ruta_base())
            if (
                getattr(paso_previo, "herramienta", None) == herramienta.id
                and misma_ruta
                and previos
                == {k: v for k, v in parametros.items() if k != "ruta"}
            ):
                self._registrar_accion(
                    herramienta.id,
                    dict(parametros),
                    {"estado": "paso_repetido"},
                    EstadoAccion.INVALIDO,
                )
                return None

        # Razón del paso, redactada antes de exponerse (FR-035 / SC-008).
        razon = paso.razon
        if razon and self._redactor is not None:
            razon = self._redactor.redactar(razon)
        entrada_mostrada = dict(parametros)
        if razon:
            entrada_mostrada["razon"] = razon

        # Validación de parámetros propuestos contra el esquema de entrada
        # (FR-033): un parámetro inválido se rechaza sin ejecutar.
        if not validar_resultado_esquema(parametros, herramienta.esquema_entrada):
            self._registrar_accion(
                herramienta.id,
                entrada_mostrada,
                {"estado": "parametros_invalidos"},
                EstadoAccion.ERROR,
            )
            return None

        # Mínimo privilegio: ruta dentro de la allowlist (FR-025). Se
        # normaliza la ruta propuesta (el LLM puede escaparla en JSON con
        # dobles backslashes en Windows).
        ruta_paso = str(parametros.get("ruta") or self._ruta_base())
        ruta_paso = ruta_paso.replace("\\\\", "\\")
        if self._allowlist is not None and not self._allowlist.contiene(ruta_paso):
            self._registrar_accion(
                herramienta.id,
                entrada_mostrada,
                {"estado": "ruta_no_autorizada"},
                EstadoAccion.ERROR,
            )
            return None

        # Si la herramienta espera `ruta` y el LLM no la propuso (o propuso un
        # nombre distinto, p.ej. `ruta_base`), se inyecta la raíz autorizada
        # para que la herramienta nunca opere fuera del perímetro (FR-025).
        if "ruta" in herramienta.esquema_entrada.get("properties", {}):
            parametros.setdefault("ruta", self._ruta_base())

        # Acción sensible → autorización (SC-004, FR-015/016).
        if herramienta.requiere_autorizacion:
            accion = self._autorizaciones.crear(
                id=f"a{self._indice_solicitud}",
                descripcion=(
                    f"Ejecutar la herramienta '{herramienta.id}' para la "
                    "solicitud solicitada."
                ),
                herramienta_id=herramienta.id,
            )
            if autorizacion is False:
                self._autorizaciones.denegar(accion.id)
                self._autorizaciones.marcar_no_ejecutada(accion.id)
                self._registrar_accion(
                    herramienta.id,
                    entrada_mostrada,
                    {"estado": "denegada"},
                    EstadoAccion.ERROR,
                )
                return None
            if autorizacion is not True:
                self._registrar_accion(
                    herramienta.id,
                    entrada_mostrada,
                    {"estado": "pendiente_autorizacion"},
                    EstadoAccion.PENDIENTE_AUTORIZACION,
                )
                return None
            self._autorizaciones.autorizar(accion.id)

        try:
            resultado = herramienta.ejecutar(parametros)
        except Exception as error:  # noqa: BLE001 - nunca inventar resultados
            self._registrar_accion(
                herramienta.id,
                entrada_mostrada,
                {"error": self._redactor.redactar(str(error))},
                EstadoAccion.ERROR,
            )
            return Observacion(
                paso=paso,
                resultado=ResultadoDeHerramienta(
                    herramienta_id=herramienta.id,
                    estado=EstadoResultado.ERROR,
                    datos={},
                    error=str(error),
                ),
                evaluacion="error de ejecución",
            )

        if not self._validar_y_usar(herramienta, resultado):
            estado_registro = (
                EstadoAccion.ERROR
                if resultado.estado == EstadoResultado.ERROR
                else EstadoAccion.INVALIDO
            )
            self._registrar_accion(
                herramienta.id, entrada_mostrada, resultado.datos, estado_registro
            )
            return Observacion(
                paso=paso,
                resultado=resultado,
                evaluacion="resultado inválido o con error (no se usa como fuente)",
            )

        self._registrar_accion(
            herramienta.id, entrada_mostrada, resultado.datos, EstadoAccion.EXITO
        )
        if herramienta.requiere_autorizacion:
            self._autorizaciones.marcar_ejecutada(f"a{self._indice_solicitud}")

        from qa_agent.agent.reasoning import PasoDePlan

        # La observación expone una copia del paso con la razón ya redactada
        # (SC-008) y con los parámetros REALMENTE ejecutados (sanearizados y con
        # la ruta autorizada inyectada, T114 / FR-035): el razonamiento visible
        # nunca contiene secretos ni muestra parámetros que no coincidan con la
        # ejecución real.
        paso_visible = PasoDePlan(
            orden=paso.orden,
            razon=razon or paso.razon,
            herramienta=paso.herramienta,
            parametros=dict(parametros),
            criterio_salida=paso.criterio_salida,
        )
        return Observacion(
            paso=paso_visible,
            resultado=resultado,
            evaluacion=f"ejecutado '{herramienta.id}' con éxito",
        )

    def _respuesta_react(
        self,
        texto: str,
        solicitud_id: str,
        observaciones: list[Observacion],
        agotado_presupuesto: bool = False,
    ) -> RespuestaDelAgente:
        """Genera la respuesta final anclada en las observaciones reales.

        Si el análisis global agotó el presupuesto de pasos, se añade a la
        intención la nota de cobertura para que la respuesta entregue lo
        observado y declare lo que quedó sin analizar (honestidad, IX).
        """
        intencion_para_responder = texto
        if agotado_presupuesto and (
            _es_analisis_exhaustivo(texto) or _es_analisis_capa(texto)
        ):
            intencion_para_responder += _NOTAS_COBERTURA_GLOBAL
        error_respuesta = ""
        try:
            respuesta_generada = self._backend.responder(
                self._redactor.redactar(observaciones),
                self._redactor.redactar(intencion_para_responder),
            )
        except Exception as error:  # noqa: BLE001
            # Honestidad (IX / FR-019): un fallo del proveedor LLM no se traga
            # ni se disfraza de "sin evidencia": se expone el error real.
            respuesta_generada = {}
            error_respuesta = (
                f"{type(error).__name__}: {error}"
                if str(error)
                else type(error).__name__
            )
        if not isinstance(respuesta_generada, dict):
            respuesta_generada = {}

        confianza_raw = respuesta_generada.get(
            "confianza", Confianza.ALTA.value
        )
        try:
            confianza = Confianza(confianza_raw)
        except ValueError:
            confianza = Confianza.ALTA

        texto_final = self._redactor.redactar(
            respuesta_generada.get("texto", "")
        )
        if not texto_final:
            confianza = Confianza.SIN_INFORMACION
            if error_respuesta:
                texto_final = self._redactor.redactar(
                    "El proveedor LLM falló al generar la respuesta final "
                    f"({error_respuesta}). El agente recopiló evidencia real "
                    "en sus pasos, pero no pudo redactar la respuesta; revisa "
                    "el panel Razonamiento."
                )
            else:
                texto_final = (
                    "No tengo una respuesta basada en evidencia para eso."
                )

        # Honestidad del razonamiento (SC-017 / FR-019): si el backend afirma
        # datos que no aparecen en ninguna observación real, la confianza no
        # puede ser alta.
        if (
            confianza == Confianza.ALTA
            and self._afirmaciones_no_ancladas(texto_final, observaciones)
        ):
            confianza = Confianza.LIMITADA

        return RespuestaDelAgente(
            texto=texto_final,
            solicitud_id=solicitud_id,
            acciones=[a for a in self._sesion.acciones],
            confianza=confianza,
            basada_en_herramientas=bool(observaciones),
            recomendaciones=self._recomendaciones_redactadas(respuesta_generada),
            razonamiento=list(observaciones),
        )

    def _afirmaciones_no_ancladas(
        self, texto: str, observaciones: list[Observacion]
    ) -> bool:
        """True si el texto afirma tokens sustantivos ausentes de la evidencia.

        Determinista (SC-010): extrae números y palabras con mayúscula inicial
        del texto de la respuesta y comprueba que aparezcan en los datos de
        las observaciones reales. Si alguno no aparece, la afirmación no está
        anclada (SC-017 / FR-019) y la confianza no puede ser alta.
        """
        import re

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
        palabras_comunes = {
            "Encontré", "Encontre", "Observé", "Observe", "Analicé", "Analice",
            "El", "La", "Los", "Las", "Un", "Una", "Y", "Pero", "Con", "En",
            "De", "Que", "No", "Si", "Más", "Mas", "Sin", "Por", "Para",
        }
        for match in re.finditer(
            r"\b([A-ZÁ-Ú][a-zá-ú]+)\b|\b(\d+(?:\.\d+)?)\b", texto
        ):
            token = match.group(1) or match.group(2)
            if token in palabras_comunes:
                continue
            es_numero = match.group(2) is not None
            if es_numero:
                if token not in evidencia:
                    return True
                continue
            if self._al_inicio_de_frase(texto, match.start()):
                continue
            if token not in evidencia:
                return True
        return False

    @staticmethod
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
