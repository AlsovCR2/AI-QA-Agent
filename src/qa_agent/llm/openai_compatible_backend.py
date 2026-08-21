"""`OpenAICompatibleBackend`: backend de producción (LLMBackend).

Implementa `LLMBackend` usando la API de Chat Completions de cualquier servicio
compatible con OpenAI. **Proveedor por defecto: DeepSeek**; NVIDIA NIM y OpenAI
se soportan cambiando solo la configuración de entorno
(`contracts/llm-backend-contract.md`).

La configuración se lee exclusivamente de variables de entorno (`.env` vía
`python-dotenv`), nunca de valores en código (XI / FR-021). Si falta la API key
en producción, se lanza un error explícito (no silencioso).
"""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from qa_agent.agent.reasoning import PasoDePlan, Plan
from qa_agent.llm.backend import LLMBackend

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"

# Evidencia que recibe `responder` (T119): cada observación se acota a
# `_MAX_CHARS_EVIDENCIA_RESPONDER` caracteres para que quepa en el contexto
# del modelo. Ante un fallo de la API (p. ej. `context_length_exceeded` con
# muchas lecturas de archivos en un análisis global) se reintenta UNA vez con
# una evidencia compacta: solo las observaciones más recientes
# (`_MAX_OBSERVACIONES_RESPONDER`) y más acotadas aún.
_MAX_CHARS_EVIDENCIA_RESPONDER = 700
_MAX_OBSERVACIONES_RESPONDER = 6
_MAX_CHARS_EVIDENCIA_RESPONDER_RETRY = 400

# Presupuesto de evidencia para `leer_archivo` (T123): el contenido de una
# clase/archivo de tamaño típico (p. ej. UsuarioDAL.cs, 118 líneas / ~4.7 KB)
# debe entrar COMPLETO en el contexto para que el LLM pueda enumerar métodos y
# firmas. Acotarlo a 700/1500 caracteres ocultaba el MEDIO del contenido (donde
# están la mayoría de las firmas) y el LLM respondía honestamente "está
# truncado" aunque la herramienta hubiera leído el archivo entero. Si aun así
# se supera, `_resumen_firmas` añade las firmas deterministas al final, que
# nunca se recortan (VI / FR-019).
_MAX_CHARS_EVIDENCIA_LEER_ARCHIVO = 6000


class OpenAICompatibleBackend(LLMBackend):
    """Backend real vía API Chat Completions, configurable por entorno."""

    nombre = "openai-compatible"
    requiere_api_key = True
    proveedor_requerido = True
    soporta_razonamiento = True

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        temperatura: float = 0.0,
    ) -> None:
        if not api_key:
            raise ValueError(
                "Falta LLM_API_KEY. Configúrala en el entorno / .env (XI). "
                "Usa --demo o el FakeLLM para pruebas sin proveedor."
            )
        self._base_url = base_url
        self._model = model
        self._temperatura = temperatura
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model(self) -> str:
        return self._model

    # -- helpers --------------------------------------------------------

    def _completar_json(self, sistema: str, usuario: str) -> dict[str, Any]:
        """Llama a Chat Completions y extrae un objeto JSON de la respuesta.

        El LLM real no siempre devuelve JSON puro: puede añadir prosa,
        delimitadores markdown o negarse. Se extrae el primer objeto JSON
        balanceado que se encuentre; si no hay ninguno válido, se devuelve
        `{}` (nunca se lanza `JSONDecodeError`, FR-017/018).
        """
        respuesta = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperatura,
            messages=[
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
        )
        contenido = respuesta.choices[0].message.content or "{}"
        return self._extraer_json(contenido)

    @staticmethod
    def _acotar(texto: str, max_chars: int = 1500) -> str:
        """Recorta un texto largo conservando cabecera y cola (evidencia compacta).

        Truncar solo desde el inicio hacía que el LLM viera únicamente la parte
        inicial del resultado (p. ej. `.git` en `explore`, primero
        alfabéticamente) y respondiera sin anclaje en la estructura real.
        Conservar el final mantiene visible el contenido útil de la cola.
        """
        if len(texto) <= max_chars:
            return texto
        marca = f"… [+{len(texto) - max_chars} chars] …"
        resto = max_chars - len(marca)
        mitad = resto // 2
        return texto[:mitad] + marca + texto[-mitad:]

    @staticmethod
    def _describir_herramienta(h: Any) -> str:
        """Describe una herramienta con su esquema de entrada (parámetros)."""
        propiedades = (h.esquema_entrada or {}).get("properties", {})
        if not propiedades:
            return f"- {h.id}: {h.descripcion}."
        # Se incluye la `description` de cada parámetro, no solo su tipo. Antes
        # solo viajaba `nombre=tipo`, así que toda la guía escrita en el esquema
        # —qué parámetro preferir, qué debe conservar una edición— no llegaba
        # nunca al modelo: se enteraba de las reglas al violarlas.
        partes = []
        for nombre, prop in propiedades.items():
            texto = f"{nombre}={prop.get('type', '?')}"
            detalle = (prop.get("description") or "").strip()
            if detalle:
                texto += f" ({OpenAICompatibleBackend._acotar(detalle, 520)})"
            partes.append(texto)
        params = "; ".join(partes)
        return f"- {h.id}: {h.descripcion}. Parámetros: {params or 'ninguno'}"

    @staticmethod
    def _resumen_nombres(resultado: Any) -> str:
        """Listado compacto de nombres para `explore`, sin recortarse en el contexto.

        El JSON crudo de `explore` con muchas entradas supera el límite de
        caracteres y `_acotar` oculta los nombres del MEDIO del listado: el
        modelo no podía enumerar todo lo observado ni proponer leer los
        archivos ocultos (regresión real con ReservaHotel: Conexion.cs,
        HotelDAL.cs, PagoDAL.cs, etc. nunca aparecían). Un listado solo de
        nombres (ruta + nombres separados por coma) es compacto y conserva la
        información esencial de la estructura (FR-019 / VI).
        """
        datos = getattr(resultado, "datos", None)
        if not isinstance(datos, dict) or datos.get("existe") is not True:
            return ""
        elementos = datos.get("elementos")
        if not isinstance(elementos, list):
            return ""
        nombres = [
            e.get("nombre")
            for e in elementos
            if isinstance(e, dict) and e.get("nombre")
        ]
        if not nombres:
            return ""
        return f"{datos.get('ruta', '')}: {', '.join(nombres)}"

    @staticmethod
    def _resumen_firmas(resultado: Any) -> str:
        """Firmas de métodos/funciones del archivo leído (nombre + línea).

        Para `leer_archivo`: listado compacto y determinista (sin LLM) que el
        LLM SIEMPRE ve aunque el contenido completo no quepa en el contexto.
        `_acotar` conserva cabecera y cola, y este bloque se añade al final
        para que las firmas del MEDIO (las que el recorte ocultaba, T123)
        nunca se pierdan. Soporta firmas con modificador de acceso (C#/Java) y
        `def` (Python). No sirve para calcular nada: solo expone nombres y
        líneas reales del archivo (FR-019 / VI / SC-010).
        """
        datos = getattr(resultado, "datos", None)
        if not isinstance(datos, dict) or datos.get("existe") is not True:
            return ""
        contenido = datos.get("contenido")
        if not isinstance(contenido, str) or not contenido:
            return ""
        patron_acceso = (
            r"^(?:public|private|protected|internal)\s+"
            r"(?:static\s+)?[\w<>\[\]?,\.]+\s+\w+\s*\("
        )
        firmas: list[str] = []
        for numero, linea in enumerate(contenido.splitlines(), 1):
            linea_limpia = linea.strip()
            es_firma = (
                re.match(patron_acceso, linea_limpia) is not None
                or (linea_limpia.startswith("def ") and "(" in linea_limpia)
            )
            if es_firma:
                firmas.append(f"L{numero}: {linea_limpia[:120]}")
        return "\n".join(firmas)

    def _contexto_observacion(self, observacion: Any, max_chars: int = 1500) -> str:
        """Representación de una observación para el contexto del LLM.

        Para `explore` usa el listado compacto de nombres (completo dentro del
        límite) en vez del JSON crudo recortado por la mitad: el razonamiento y
        la respuesta final pueden enumerar TODAS las capas/archivos observados
        aunque el listado sea largo (FR-019 / VI).

        Para `leer_archivo` amplía el presupuesto a
        `_MAX_CHARS_EVIDENCIA_LEER_ARCHIVO` para que un archivo típico entre
        COMPLETO en el contexto (T123) y, si aún se recorta, añade las firmas
        deterministas de métodos al final para que la lista de métodos nunca se
        pierda.
        """
        herramienta = getattr(observacion.paso, "herramienta", "")
        if herramienta == "leer_archivo":
            max_chars = max(max_chars, _MAX_CHARS_EVIDENCIA_LEER_ARCHIVO)
        if herramienta == "explore":
            resumen = self._resumen_nombres(observacion.resultado)
            if resumen:
                return self._acotar(resumen, max_chars)
        texto = str(observacion.resultado)
        if herramienta == "leer_archivo":
            firmas = self._resumen_firmas(observacion.resultado)
            if firmas:
                texto = f"{texto}\n\nFIRMAS_DETERMINISTAS:\n{firmas}"
        return self._acotar(texto, max_chars)

    @staticmethod
    def _extraer_json(contenido: str) -> dict[str, Any]:
        """Extrae el primer objeto JSON válido del texto, o `{}` si no existe."""
        texto = contenido.strip()
        # Limpiar delimitadores de bloque code (```json ... ```).
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```$", "", texto)
        pos_inicio = texto.find("{")
        while pos_inicio != -1:
            try:
                # `raw_decode` devuelve (objeto, fin); no requiere que el texto
                # termine justo después del JSON (tolera prosa posterior).
                objeto, _ = json.JSONDecoder().raw_decode(texto[pos_inicio:])
                if isinstance(objeto, dict):
                    return objeto
            except json.JSONDecodeError:
                pass
            pos_inicio = texto.find("{", pos_inicio + 1)
        return {}

    # -- contrato LLMBackend -------------------------------------------

    def interpretar(self, solicitud: dict[str, Any]) -> dict[str, Any]:
        """Interpreta la solicitud del usuario en una acción de agente."""
        sistema = (
            "Eres el intérprete de un agente de QA/Ingeniería de Software. "
            "Devuelve SOLO un objeto JSON con la clave 'accion' que resume la "
            "solicitud del usuario. Ejemplo: {\"accion\": \"ejecutar_pruebas\"}."
        )
        return self._completar_json(sistema, str(solicitud.get("texto", "")))

    def seleccionar_herramienta(
        self, solicitud: dict[str, Any], herramientas: list[Any]
    ) -> dict[str, Any]:
        """Selecciona la herramienta adecuada entre las disponibles.

        Devuelve `{"herramienta": <id>}` o `{"ninguna": true}` si ninguna es
        adecuada (FR-022/023, SC-009).
        """
        catalogo = "\n".join(
            f"- {h.id}: {h.descripcion}" for h in herramientas
        )
        sistema = (
            "Selecciona la herramienta adecuada para la solicitud del usuario. "
            f"Herramientas disponibles:\n{catalogo}\n"
            'Devuelve SOLO JSON: {"herramienta": "<id>"} o {"ninguna": true}.'
        )
        return self._completar_json(sistema, str(solicitud.get("texto", "")))

    def generar_respuesta(
        self, solicitud: dict[str, Any], resultados: list[Any]
    ) -> dict[str, Any]:
        """Genera la respuesta final basada en resultados reales validados.

        Si la evidencia no responde directamente a la pregunta (p. ej. una
        pregunta de recomendación/estrategia sin datos suficientes), el LLM
        puede incluir `recomendaciones`: sugerencias claramente etiquetadas
        como tales, basadas en lo que sí se observa (estructura, framework,
        ausencia de tests) y nunca presentadas como hechos del proyecto
        (FR-019 / IX).
        """
        evidencia = "\n".join(str(getattr(r, "datos", r)) for r in resultados)
        sistema = (
            "Responde al usuario basándote EXCLUSIVAMENTE en la evidencia "
            "real de las herramientas. No inventes información (FR-019). "
            "Cuando la evidencia responda directamente la pregunta, "
            "PROFUNDIZA: organiza por capa/módulo, nombra los archivos "
            "concretos observados y describe qué hace cada uno según su "
            "contenido real; no te limites a repetir nombres o la estructura. "
            "Si la evidencia no responde directamente a la pregunta pero "
            "permite orientar (por ejemplo, una pregunta de estrategia o "
            "recomendación), incluye 'recomendaciones' como una lista de "
            "sugerencias claramente marcadas como recomendaciones y "
            "basadas en lo que sí se observa (estructura, framework, "
            "ausencia de tests); nunca las presentes como hechos del "
            'proyecto. Devuelve SOLO JSON: {"texto": "...", "confianza": '
            '"alta"|"limitada"|"sin_informacion", "recomendaciones": ["..."]}.'
        )
        return self._completar_json(sistema, f"{solicitud.get('texto', '')}\n\n{evidencia}")

    # -- contrato de razonamiento (Phase 12 / T077) ----------------------

    def planificar(
        self, intencion: Any, catalogo: list[Any], contexto: dict[str, Any]
    ) -> Plan:
        """Genera un plan multi-paso usando solo herramientas del catálogo.

        El catálogo se describe con sus esquemas de entrada (parámetros y
        tipos) para que el planificador pueda proponer parámetros válidos; se
        deduplican pasos idénticos (herramienta + parámetros iguales).
        """
        catalogo_str = "\n".join(
            self._describir_herramienta(h) for h in catalogo
        )
        sistema = (
            "Eres el planificador de un agente de QA/Ingeniería de Software. "
            "Dada la intención del usuario, diseña un plan multi-paso que "
            "obtenga la EVIDENCIA REAL necesaria para responder. NO te "
            "conformes con una sola herramienta superficial: usa la herramienta "
            "adecuada para cada tipo de información que falte.\n"
            "Herramientas disponibles (con sus parámetros de entrada):\n"
            f"{catalogo_str}\n"
            "Reglas:\n"
            "- Cada paso usa SOLO una herramienta real del catálogo y parámetros "
            "válidos según su esquema.\n"
            "- No inventes herramientas, rutas ni resultados.\n"
            "- No repitas un paso ya previsto (misma herramienta y mismos "
            "parámetros).\n"
            "- Si la intención pide 'clases a probar' o similar, incluye pasos "
            "que LOCALICEN/BUSQUEN las definiciones reales (locate/search), no "
            "solo explorar la estructura.\n"
            "- Si la intención pide EXPLICAR o ENTENDER el código (qué hace una "
            "capa, qué pruebas cubre un archivo, cómo funciona un módulo), el "
            "plan DEBE incluir pasos de `leer_archivo` sobre los archivos "
            "concretos identificados (p. ej. cada archivo de test por capa o el "
            "archivo principal de cada capa), NO conformarse con explorar la "
            "estructura ni con nombres de archivos.\n"
            "- Prefiere `leer_archivo` sobre `search` con regex amplios cuando "
            "necesites el contenido completo de un archivo concreto.\n"
            "- Los parámetros de `leer_archivo` usan 'ruta' (raíz del proyecto) "
            "y 'archivo_relativo' (ruta del archivo relativa a la raíz).\n"
            "- Para la estructura COMPLETA de un proyecto con varios "
            "directorios/capas (BLL/DAL/EDL/UIL, src/test, etc.): NO hagas un "
            "solo `explore` de todo el árbol (su listado es largo y se trunca "
            "en el contexto, ocultando la mayoría de los archivos). Planifica "
            "un `explore` por directorio/capa ('ruta'=capa, 'profundidad_max' "
            "acotada) y, cuando la intención sea explicar, pasos de "
            "`leer_archivo` por archivo relevante de cada capa.\n"
            "- Si la intención es analizar o explorar TODO el proyecto (p. ej. "
            "'analiza el proyecto', 'explora la estructura', 'estructura "
            "completa'): el plan DEBE recorrer CADA capa de primer nivel real "
            "(un `explore` por directorio/capa con 'ruta'=capa) y leer con "
            "`leer_archivo` los archivos de código principales de cada capa "
            "para describir qué hace realmente el contenido. NO diseñes un "
            "plan que solo explore la raíz: la estructura de nivel 1 no revela "
            "las clases ni sus responsabilidades.\n"
            "Devuelve SOLO JSON: "
            '{"objetivo": "...", "criterio_exito": "...", "pasos": ['
            '{"orden": 1, "razon": "...", "herramienta": "<id>", '
            '"parametros": {...}, "criterio_salida": "..."}]}.'
        )
        datos = self._completar_json(
            sistema, f"{intencion.texto}\n\n{intencion.contexto}"
        )
        ids_validos = {h.id for h in catalogo}
        vistos: set[str] = set()
        pasos = []
        for paso_dict in datos.get("pasos", []):
            if paso_dict.get("herramienta") not in ids_validos:
                continue
            parametros = dict(paso_dict.get("parametros") or {})
            # Deduplicar pasos idénticos (misma herramienta + parámetros).
            # La clave se serializa a JSON porque un parámetro puede ser una
            # lista o un dict —`editar_archivo` recibe `reemplazos`, una lista
            # de objetos— y `tuple(sorted(...))` reventaba con
            # "unhashable type: 'list'", tumbando la planificación entera y
            # dejando la solicitud sin ningún paso. `sort_keys` hace la clave
            # estable, y `default=str` evita que un valor exótico repita el
            # mismo fallo.
            clave = json.dumps(
                [paso_dict["herramienta"], parametros],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            if clave in vistos:
                continue
            vistos.add(clave)
            pasos.append(
                PasoDePlan(
                    orden=paso_dict.get("orden", len(pasos) + 1),
                    razon=paso_dict.get("razon", ""),
                    herramienta=paso_dict["herramienta"],
                    parametros=parametros,
                    criterio_salida=paso_dict.get("criterio_salida", ""),
                )
                )
        return Plan(
            objetivo=datos.get("objetivo", ""),
            criterio_exito=datos.get("criterio_exito", ""),
            pasos=list(pasos),
            pendientes=list(pasos),
        )

    def razonar(self, estado: Any, pendientes: list[Any]) -> dict[str, Any]:
        """Elige el siguiente paso o decide concluir (basado en observaciones)."""
        contexto = "\n".join(
            f"- paso {o.paso.orden} ({o.paso.herramienta}): "
            f"{self._contexto_observacion(o)}"
            for o in estado.observaciones
        )
        catalogo_str = "\n".join(
            self._describir_herramienta(h)
            for h in estado.intencion.contexto.get("catalogo", [])
        )
        sistema = (
            "Eres el razonador de un agente de QA. Si el plan pendiente está "
            "vacío pero la evidencia no basta para la intención, propones un "
            "paso NUEVO para obtener más evidencia real; si la evidencia ya "
            f"basta, concluyes. Herramientas disponibles:\n{catalogo_str}\n"
            "Reglas:\n"
            "- NO repitas un paso ya ejecutado (misma herramienta y mismos "
            "parámetros): es determinista y no aporta evidencia nueva.\n"
            "- Si la intención pide explicar/entender el código o detectar "
            "pruebas, propón `leer_archivo` sobre un archivo concreto y real "
            "(ruta con extensión) en lugar de re-explorar o re-localizar la "
            "misma estructura.\n"
            "- Si una búsqueda no encontró nada, cambia de estrategia (otro "
            "patrón, o lee archivos reales) en vez de repetirla.\n"
            "- Para completar la estructura de un proyecto con varias capas, "
            "explora CADA directorio por separado (un `explore` por capa) en "
            "vez de repetir un `explore` gigante de todo el árbol, cuyo "
            "listado se trunca en el contexto y oculta la mayoría de los "
            "archivos.\n"
            "- Para un análisis global (analizar/explorar todo el proyecto): "
            "si quedan capas de primer nivel sin explorar, propón `explore` de "
            "la capa pendiente o `leer_archivo` de un archivo de esa capa; NO "
            "concluyas mientras falte cubrir capas.\n"
            "- No inventes resultados ni herramientas fuera del catálogo; usa "
            "las observaciones reales previas.\n"
            'Devuelve SOLO JSON: {"herramienta": "<id>", "parametros": {...}, '
            '"razon": "..."} o {"concluir": true}.'
        )
        pendientes_str = "\n".join(
            f"- orden {p.orden}: herramienta={p.herramienta} razon={p.razon}"
            for p in pendientes
        )
        return self._completar_json(
            sistema,
            f"Intención: {estado.intencion.texto}\n\n"
            f"Pendientes:\n{pendientes_str or '(ninguno)'}\n\n"
            f"Observaciones:\n{contexto}",
        )

    def evaluar(self, estado: Any, observaciones: list[Any]) -> dict[str, Any]:
        """Evalúa si la evidencia satisface la intención."""
        contexto = "\n".join(
            f"- paso {o.paso.orden}: {self._contexto_observacion(o)}"
            for o in observaciones
        )
        sistema = (
            "Eres el evaluador de un agente de QA. Determina si la EVIDENCIA "
            "REAL recopilada responde DIRECTAMENTE a la intención del usuario.\n"
            "Reglas:\n"
            "- satisfecha=true SOLO si la evidencia permite responder la "
            "intención concreta (p.ej. si pide 'clases a probar', hace falta "
            "la lista de clases reales, no solo la estructura de carpetas).\n"
            "- Si la intención pide explicar/entender el código (qué hace una "
            "capa, qué pruebas cubre), el contenido de los archivos relevantes "
            "debe haberse leído (leer_archivo); solo la estructura NO satisface.\n"
            "- Para un análisis global (analizar/explorar todo el proyecto): "
            "satisfecha=true SOLO si la evidencia cubre cada capa de primer "
            "nivel observada (la raíz no basta); si quedan capas sin explorar, "
            "satisfecha=false.\n"
            "- Si falta información necesaria, satisfecha=false y explica qué "
            "falta en 'razon'.\n"
            "- Si dudas, satisfecha=false (sigue recopilando evidencia).\n"
            'Devuelve SOLO JSON: {"satisfecha": bool, "razon": "..."}.'
        )
        return self._completar_json(
            sistema,
            f"Intención: {estado.intencion.texto}\n\n"
            f"Criterio de éxito: {estado.plan.criterio_exito if estado.plan else ''}\n\n"
            f"Observaciones:\n{contexto}",
        )

    def responder(self, observaciones: list[Any], intencion: str = "") -> dict[str, Any]:
        """Genera la respuesta final anclada en las observaciones reales.

        `intencion` (opcional) es la pregunta del usuario: la respuesta debe
        responder directamente a ella usando solo la evidencia real. Sin
        observaciones (conversación general del chat, Phase 13), responde como
        asistente conversacional usando el contexto incluido en `intencion`.

        La evidencia se acota por observación (`_MAX_CHARS_EVIDENCIA_RESPONDER`)
        para no exceder el contexto del modelo. Ante un fallo de la API se
        reintenta UNA vez con evidencia compacta (observaciones más recientes,
        más acotadas); si el reintento también falla, se propaga el error para
        que el agente lo reporte con honestidad (T119).
        """
        if observaciones:
            sistema = (
                "Responde al usuario basándote EXCLUSIVAMENTE en la evidencia real "
                "de las observaciones (FR-019). No inventes información.\n"
                "Reglas:\n"
                "- Responde DIRECTAMENTE a la intención del usuario: si preguntó "
                "qué clases probar, prioriza las clases reales observadas con su "
                "capa y por qué son importantes (lógica de negocio > datos > UI).\n"
                "- PROFUNDIZA en la respuesta cuando la evidencia lo permita: "
                "organízala por capa/módulo, nombra los archivos concretos "
                "observados, describe qué hace cada uno según su contenido real "
                "(clases, funciones, pruebas), explica el 'por qué' y conecta "
                "esa información con la pregunta concreta. No te limites a "
                "resumir la estructura ni a repetir nombres de archivos.\n"
                "- Si una capa o archivo aparece en las observaciones, cita lo "
                "que su contenido indica (p. ej. 'DateRangeTests.cs valida "
                "rangos de fechas del dominio') basándote SOLO en lo leído; si "
                "el contenido no fue observado, no lo afirmes.\n"
                "- Si la intención es un análisis GLOBAL del proyecto (analizar/"
                "explorar todo): organiza la respuesta por capa/módulo cubriendo "
                "TODAS las capas observadas; para cada una nombra los archivos "
                "reales y qué hace su contenido según lo leído. Si alguna capa "
                "no pudo analizarse, dilo explícitamente (qué se cubrió y qué "
                "no) en vez de recomendar al usuario re-preguntar.\n"
                "- Si la evidencia no permite responder la intención, dilo con "
                "honestidad y sugiere el siguiente paso en 'recomendaciones'.\n"
                "- 'recomendaciones' son sugerencias etiquetadas, nunca hechos.\n"
                'Devuelve SOLO JSON: {"texto": "...", "confianza": '
                '"alta"|"limitada"|"sin_informacion", "recomendaciones": ["..."]}.'
            )
            usuario = self._usuario_responder(
                intencion, self._evidencia_responder(observaciones)
            )
        else:
            sistema = (
                "Eres un asistente conversacional de un agente de QA. "
                "Responde de forma natural y útil a la PREGUNTA concreta del "
                "usuario en este turno. NO repitas la respuesta anterior del "
                "asistente ni des una respuesta genérica: adáptate a lo que "
                "preguntan.\n"
                "Reglas:\n"
                "- Responde DIRECTAMENTE a la pregunta del turno. Si pregunta "
                "qué puedes hacer, enumera tus capacidades concretas (explorar "
                "la estructura, localizar archivos/clases, buscar patrones, "
                "leer archivos, ejecutar y analizar pruebas, analizar "
                "cobertura, generar casos de prueba sugeridos).\n"
                "- Si mencionas tareas o hechos del contexto, usa SOLO los que "
                "aparecen en el contexto proporcionado; no los inventes.\n"
                "- Si pide un análisis técnico (clases, cobertura, pruebas), "
                "di que puede hacerlo con la herramienta adecuada.\n"
                "- 'recomendaciones' son sugerencias, nunca hechos inventados.\n"
                'Devuelve SOLO JSON: {"texto": "...", "confianza": '
                '"alta"|"limitada"|"sin_informacion", "recomendaciones": ["..."]}.'
            )
            usuario = f"{intencion}"
        try:
            return self._completar_json(sistema, usuario)
        except Exception:
            if not observaciones:
                raise
            usuario_compacto = self._usuario_responder(
                intencion,
                self._evidencia_responder(
                    observaciones,
                    max_observaciones=_MAX_OBSERVACIONES_RESPONDER,
                    max_chars=_MAX_CHARS_EVIDENCIA_RESPONDER_RETRY,
                ),
            )
            return self._completar_json(sistema, usuario_compacto)

    def _evidencia_responder(
        self,
        observaciones: list[Any],
        max_observaciones: int | None = None,
        max_chars: int = _MAX_CHARS_EVIDENCIA_RESPONDER,
    ) -> str:
        """Evidencia acotada por observación, conservando el anclaje (FR-019).

        Cuando se acota el número, se conservan las observaciones MÁS recientes
        (las últimas ejecutadas son las más relevantes para la respuesta).
        """
        ultimas = (
            observaciones[-max_observaciones:]
            if max_observaciones
            else list(observaciones)
        )
        return "\n".join(
            f"- paso {o.paso.orden}: {self._contexto_observacion(o, max_chars)}"
            for o in ultimas
        )

    @staticmethod
    def _usuario_responder(intencion: str, evidencia: str) -> str:
        """Mensaje de usuario de `responder`: intención + evidencia real."""
        return f"Intención del usuario: {intencion}\n\nEvidencia real:\n{evidencia}"