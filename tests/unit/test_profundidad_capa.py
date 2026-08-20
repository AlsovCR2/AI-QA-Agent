"""Tests de profundidad/exhaustividad del análisis de una capa/carpeta (T122).

Cubre la corrección de la regresión real con ReservaHotel: al pedir al agente
"explora todas las clases de la capa DAL", el modelo siempre reportaba el mismo
subconjunto (Bitacora/Cliente/TipoPago/Usuario) y omitía el resto de clases
(Conexion, Hotel, Pago, Mobiliario, ClienteTelefono, Reservacion,
TipoHabitacion...). El plan del LLM se genera sin ver el árbol real y se queda
en un subconjunto; además, el recorte de la observación de `explore` ocultaba
los nombres del medio del listado.

La corrección:
- Detección determinista de intención de análisis de una capa/carpeta concreta
  (`_es_analisis_capa`), que amplía el presupuesto de pasos (SC-016).
- Enriquecimiento determinista del plan (`_enriquecer_plan_analisis_capa`):
  `explore` de la capa real + `leer_archivo` de CADA archivo de código
  existente (FR-024 / FR-049), igual que el análisis global.
- Nota de cobertura al agotar el presupuesto (IX / FR-019).
- Evidencia de `explore` sin recortar los nombres del medio en el contexto del
  LLM (`_resumen_nombres` / `_contexto_observacion`, backend).
"""

from __future__ import annotations

from qa_agent.agent.loop import (
    Agent,
    _es_analisis_capa,
    _extraer_capa_solicitada,
    _resolver_capa_real,
)
from qa_agent.agent.reasoning import Observacion, PasoDePlan
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.llm.openai_compatible_backend import OpenAICompatibleBackend
from qa_agent.security.redactor import Redactor
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import (
    EstadoResultado,
    Herramienta,
    ResultadoDeHerramienta,
)


class _StubExplore(Herramienta):
    """`explore` determinista mínimo: estructura vacía."""

    id = "explore"
    nombre = "explore"
    descripcion = "Explora la estructura del proyecto."
    esquema_entrada = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "profundidad_max": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    }
    esquema_salida = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "existe": {"type": "boolean"},
            "elementos": {"type": "array"},
        },
    }
    requiere_autorizacion = False

    def ejecutar(self, parametros: dict) -> ResultadoDeHerramienta:
        return ResultadoDeHerramienta(
            herramienta_id=self.id,
            estado=EstadoResultado.EXITO,
            datos={
                "ruta": parametros.get("ruta", "."),
                "existe": True,
                "elementos": [],
            },
        )


class _CapturaResponder(FakeLLM):
    """FakeLLM que registra la intención recibida por `responder`."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.ultima_intencion: str | None = None

    def responder(self, observaciones, intencion: str = ""):
        self.ultima_intencion = intencion
        return super().responder(observaciones, intencion)


def _plan_de(n: int) -> dict:
    """Plan con `n` pasos `explore` distintos (sin colisionar con el dedup)."""
    return {
        "objetivo": "análisis",
        "criterio_exito": "cubrir todo",
        "pasos": [
            {
                "orden": i,
                "razon": f"explorar paso {i}",
                "herramienta": "explore",
                "parametros": {"ruta": ".", "profundidad_max": i},
                "criterio_salida": "",
            }
            for i in range(1, n + 1)
        ],
    }


def _agente(pasos_max: int, plan: dict, backend=FakeLLM, **kwargs) -> Agent:
    backend = backend(
        soporta_razonamiento=True,
        plan=plan,
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "análisis", "confianza": "alta", "recomendaciones": []},
        **kwargs,
    )
    return Agent(
        backend=backend,
        herramientas=[_StubExplore()],
        allowlist=Allowlist(["."]),
        redactor=Redactor(),
        pasos_max=pasos_max,
    )


# -- T122: detección determinista de análisis de capa (VI / SC-010) ----------


def test_es_analisis_capa_determinista():
    """Frases del usuario que disparan el análisis de capa (regresión real)."""
    assert _es_analisis_capa("Explora completamente todas las clases de la capa DAL")
    assert _es_analisis_capa("Revisa si existen mas clases en la capa DAL")
    assert _es_analisis_capa(
        "Explorar si existen otros archivos dentro de la carpeta DAL"
    )
    assert _es_analisis_capa("Explora la capa BLL y dame un resumen de cada clase")
    assert _es_analisis_capa("explora el directorio src")
    # Intención de DEFINIR/ESCRIBIR contenido para una capa (T123): el plan del
    # LLM no disparaba el enriquecimiento con estos verbos y exploraba rutas
    # inventadas ("Datos"/"Negocio") en vez de la capa real.
    assert _es_analisis_capa(
        "Procede a definir las pruebas unitarias y cobertura que se van a "
        "realizar a la capa DAL"
    )
    assert _es_analisis_capa("definir las pruebas unitarias de la capa BLL")
    assert _es_analisis_capa("cobertura de pruebas de la capa DAL")
    # Negativos: análisis global, puntual o menciones sin intención de explorar.
    assert not _es_analisis_capa("analiza el proyecto")
    assert not _es_analisis_capa("explora la estructura del proyecto")
    assert not _es_analisis_capa("identifica donde aparece BLL")
    assert not _es_analisis_capa("explora")
    assert not _es_analisis_capa("")


def test_extraer_capa_solicitada():
    """El nombre de la capa se extrae de distintas formulaciones."""
    assert _extraer_capa_solicitada("las clases de la capa DAL") == "dal"
    assert _extraer_capa_solicitada("los archivos de la carpeta BLL") == "bll"
    assert _extraer_capa_solicitada("explora el directorio src") == "src"
    assert _extraer_capa_solicitada("analiza el proyecto") == ""
    assert _extraer_capa_solicitada("explora") == ""


def test_resolver_capa_real_no_inventa(tmp_path):
    """La capa se resuelve contra el filesystem real (FR-019), nunca se inventa."""
    (tmp_path / "DAL").mkdir()
    assert _resolver_capa_real(str(tmp_path), "dal") == "DAL"
    assert _resolver_capa_real(str(tmp_path), "DAL") == "DAL"
    assert _resolver_capa_real(str(tmp_path), "xyz") is None


# -- T122: presupuesto de pasos (SC-016) -------------------------------------


def test_presupuesto_capa_amplia_pasos_max():
    """Intención de análisis de capa amplía el presupuesto: el plan completo se ejecuta."""
    agente = _agente(pasos_max=5, plan=_plan_de(7))
    respuesta = agente.atender("Explora todas las clases de la capa DAL")

    assert len([a for a in respuesta.acciones]) == 7


def test_presupuesto_capa_sin_ampliar_para_puntual():
    """Consulta puntual respeta `pasos_max`."""
    agente = _agente(pasos_max=5, plan=_plan_de(7))
    respuesta = agente.atender("identifica dónde aparece BLL")

    assert len([a for a in respuesta.acciones]) == 5


# -- T122: enriquecimiento determinista de la capa (FR-024 / FR-049) ---------


def test_enriquecimiento_capa_lee_todos_los_archivos(tmp_path):
    """"Explora todas las clases de la capa DAL" lee CADA archivo de código de
    esa capa, no solo el subconjunto que planifique el LLM, y no toca las
    demás capas."""
    dal = tmp_path / "DAL"
    bll = tmp_path / "BLL"
    dal.mkdir()
    bll.mkdir()
    archivos_dal = [
        "BitacoraDAL.cs", "ClienteDAL.cs", "Conexion.cs", "HotelDAL.cs",
        "PagoDAL.cs", "ReservacionDAL.cs",
    ]
    for nombre in archivos_dal:
        (dal / nombre).write_text(f"namespace DAL {{ class {nombre} {{}} }}", encoding="utf-8")
    (bll / "ClienteBLL.cs").write_text("class ClienteBLL{}\n", encoding="utf-8")

    from qa_agent.tools.explore import ExploreHerramienta
    from qa_agent.tools.leer_archivo import LeerArchivoHerramienta

    rutas = [str(tmp_path)]
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "análisis de la capa",
            "criterio_exito": "cubrir la capa",
            "pasos": [
                {"orden": 1, "razon": "ver la raíz", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path), "profundidad_max": 1},
                 "criterio_salida": ""}
            ],
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "resumen de la capa", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[ExploreHerramienta(rutas), LeerArchivoHerramienta(rutas)],
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
    )
    respuesta = agente.atender("Explora todas las clases de la capa DAL")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    exploradas = {
        a.entrada.get("ruta") for a in exitos if a.herramienta_id == "explore"
    }
    assert str(dal) in exploradas
    leidos = {
        a.entrada.get("archivo_relativo")
        for a in exitos
        if a.herramienta_id == "leer_archivo"
    }
    assert {"DAL/BitacoraDAL.cs", "DAL/Conexion.cs", "DAL/HotelDAL.cs",
            "DAL/PagoDAL.cs", "DAL/ReservacionDAL.cs"} <= leidos
    # Solo la capa solicitada: no se lee código de otras capas.
    assert not any(a.herramienta_id == "leer_archivo"
                   and a.entrada.get("archivo_relativo", "").startswith("BLL/")
                   for a in exitos)


def test_enriquecimiento_capa_no_duplica_previstos(tmp_path):
    """Si el plan ya explora/lee la capa, el enriquecimiento no duplica."""
    (tmp_path / "DAL").mkdir()
    (tmp_path / "DAL" / "ClienteDAL.cs").write_text("x\n", encoding="utf-8")

    from qa_agent.tools.explore import ExploreHerramienta
    from qa_agent.tools.leer_archivo import LeerArchivoHerramienta

    rutas = [str(tmp_path)]
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "capa",
            "criterio_exito": "todo",
            "pasos": [
                {"orden": 1, "razon": "capa", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path / "DAL"),
                                "profundidad_max": 3}, "criterio_salida": ""},
                {"orden": 2, "razon": "leer", "herramienta": "leer_archivo",
                 "parametros": {"ruta": str(tmp_path),
                                "archivo_relativo": "DAL/ClienteDAL.cs"},
                 "criterio_salida": ""},
            ],
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[ExploreHerramienta(rutas), LeerArchivoHerramienta(rutas)],
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
    )
    respuesta = agente.atender("Revisa si existen mas clases en la capa DAL")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    explores_dal = [
        a for a in exitos if a.herramienta_id == "explore"
        and a.entrada.get("ruta") == str(tmp_path / "DAL")
    ]
    assert len(explores_dal) == 1
    lecturas = [
        a for a in exitos if a.herramienta_id == "leer_archivo"
        and a.entrada.get("archivo_relativo") == "DAL/ClienteDAL.cs"
    ]
    assert len(lecturas) == 1


def test_enriquecimiento_capa_solo_si_existe(tmp_path):
    """Capa inexistente → sin pasos inventados (FR-019): solo se ejecuta el plan."""
    (tmp_path / "src").mkdir()

    from qa_agent.tools.explore import ExploreHerramienta
    from qa_agent.tools.leer_archivo import LeerArchivoHerramienta

    rutas = [str(tmp_path)]
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "capa",
            "criterio_exito": "todo",
            "pasos": [
                {"orden": 1, "razon": "raíz", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path), "profundidad_max": 1},
                 "criterio_salida": ""},
            ],
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[ExploreHerramienta(rutas), LeerArchivoHerramienta(rutas)],
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
    )
    respuesta = agente.atender("Explora todas las clases de la capa XYZ")

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    assert not any(a.herramienta_id == "leer_archivo" for a in exitos)


def test_enriquecimiento_capa_con_intencion_de_definir_pruebas(tmp_path):
    """"Procede a definir las pruebas unitarias y cobertura de la capa DAL"
    (T123) dispara el enriquecimiento determinista de capa aunque el plan del
    LLM proponga rutas inventadas: la cobertura se apoya en la capa REAL, no
    en el subconjunto que planifique el modelo (regresión real: el LLM
    exploraba "Datos"/"Negocio" en vez de la capa DAL real)."""
    dal = tmp_path / "DAL"
    bll = tmp_path / "BLL"
    dal.mkdir()
    bll.mkdir()
    for nombre in ("ClienteDAL.cs", "Conexion.cs", "HotelDAL.cs"):
        (dal / nombre).write_text(
            f"namespace DAL {{ class {nombre} {{}} }}", encoding="utf-8"
        )
    (bll / "ClienteBLL.cs").write_text("class ClienteBLL{}\n", encoding="utf-8")

    from qa_agent.tools.explore import ExploreHerramienta
    from qa_agent.tools.leer_archivo import LeerArchivoHerramienta

    rutas = [str(tmp_path)]
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "definir pruebas de la capa",
            "criterio_exito": "cubrir la capa",
            "pasos": [
                {"orden": 1, "razon": "ver la raíz", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path), "profundidad_max": 1},
                 "criterio_salida": ""},
                {"orden": 2, "razon": "capa inventada", "herramienta": "explore",
                 "parametros": {"ruta": str(tmp_path / "Datos"),
                                "profundidad_max": 2}, "criterio_salida": ""},
            ],
        },
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "pruebas definidas", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[ExploreHerramienta(rutas), LeerArchivoHerramienta(rutas)],
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
    )
    respuesta = agente.atender(
        "Procede a definir las pruebas unitarias y cobertura que se van a "
        "realizar a la capa DAL"
    )

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    exploradas = {
        a.entrada.get("ruta") for a in exitos if a.herramienta_id == "explore"
    }
    assert str(dal) in exploradas
    leidos = {
        a.entrada.get("archivo_relativo")
        for a in exitos
        if a.herramienta_id == "leer_archivo"
    }
    assert {"DAL/ClienteDAL.cs", "DAL/Conexion.cs", "DAL/HotelDAL.cs"} <= leidos
    # La capa inventada por el LLM no existe: el `explore` reporta la ausencia
    # sin fabricar contenido (FR-019).
    assert not any(a.herramienta_id == "leer_archivo"
                   and a.entrada.get("archivo_relativo", "").startswith("Datos/")
                   for a in exitos)


# -- T122: nota de cobertura al agotar el presupuesto (IX / FR-019) ----------


def test_respuesta_capa_incluye_nota_cuando_agota_presupuesto():
    """Análisis de capa que agota el presupuesto añade la nota de cobertura."""
    agente = _agente(
        pasos_max=3,
        plan=_plan_de(20),
        backend=_CapturaResponder,
    )
    respuesta = agente.atender("Explora todas las clases de la capa DAL")

    assert len([a for a in respuesta.acciones]) == 18
    assert "NOTA DE COBERTURA" in agente._backend.ultima_intencion
    assert respuesta.texto


# -- T122: la evidencia de `explore` no oculta nombres del medio (backend) ---


def _backend_sin_red():
    return OpenAICompatibleBackend(
        base_url="https://api.example.com/v1",
        model="test-model",
        api_key="sk-test",
    )


def _observacion_explore(nombres: list[str]) -> Observacion:
    paso = PasoDePlan(
        orden=1, razon="", herramienta="explore", parametros={"ruta": "/proyecto"}
    )
    resultado = ResultadoDeHerramienta(
        herramienta_id="explore",
        estado=EstadoResultado.EXITO,
        datos={
            "ruta": "/proyecto",
            "existe": True,
            "elementos": [
                {"nombre": n, "tipo": "archivo", "ruta_relativa": n}
                for n in nombres
            ],
        },
    )
    return Observacion(paso=paso, resultado=resultado, evaluacion="")


def test_contexto_explore_no_oculta_nombres_del_medio():
    """El contexto de `explore` muestra TODOS los nombres (regresión real: el
    recorte crudo ocultaba Conexion/Hotel/Pago/Mobiliario en la capa DAL)."""
    backend = _backend_sin_red()
    nombres = [f"Clase{i}DAL.cs" for i in range(40)]
    observacion = _observacion_explore(nombres)
    contexto = backend._contexto_observacion(observacion, max_chars=700)

    for nombre in nombres:
        assert nombre in contexto
    # Comparación: el JSON crudo recortado sí pierde nombres del medio.
    crudo = backend._acotar(str(observacion.resultado), max_chars=700)
    assert any(nombre not in crudo for nombre in nombres)


def test_contexto_explore_vacio_deja_evidencia_cruda():
    """Sin listado de nombres (`explore` de ruta inexistente), se usa la evidencia cruda."""
    backend = _backend_sin_red()
    paso = PasoDePlan(orden=1, razon="", herramienta="explore")
    resultado = ResultadoDeHerramienta(
        herramienta_id="explore",
        estado=EstadoResultado.EXITO,
        datos={"ruta": "/nope", "existe": False, "elementos": []},
    )
    observacion = Observacion(paso=paso, resultado=resultado, evaluacion="")
    assert backend._contexto_observacion(observacion) != ""


def _observacion_leer(archivo: str, contenido: str, total_lineas: int) -> Observacion:
    paso = PasoDePlan(
        orden=1, razon="", herramienta="leer_archivo",
        parametros={"ruta": "/proyecto", "archivo_relativo": archivo},
    )
    resultado = ResultadoDeHerramienta(
        herramienta_id="leer_archivo",
        estado=EstadoResultado.EXITO,
        datos={
            "archivo": archivo,
            "existe": True,
            "contenido": contenido,
            "total_lineas": total_lineas,
            "truncado": False,
        },
    )
    return Observacion(paso=paso, resultado=resultado, evaluacion="")


def test_contexto_leer_archivo_preserva_contenido_completo():
    """T123: el contenido de un archivo típico (UsuarioDAL.cs, ~4.7 KB) entra
    COMPLETO en el contexto del LLM: sin `[+N chars]` y con todas las firmas,
    aunque el llamador pida un presupuesto menor (`max_chars=700`)."""
    contenido = "\n".join(
        [
            "using System;",
            "namespace DAL {",
            "    public class UsuarioDAL {",
        ]
        + [
            f"        public int Metodo{i}(int a, string b) {{ return a; }}"
            for i in range(10)
        ]
        + ["    }", "}"]
    )
    observacion = _observacion_leer("DAL/UsuarioDAL.cs", contenido, 13)
    backend = _backend_sin_red()
    contexto = backend._contexto_observacion(observacion, max_chars=700)

    assert "[+" not in contexto
    assert "Metodo0" in contexto
    assert "Metodo9" in contexto


def test_contexto_leer_archivo_grande_incluye_firmas_deterministas():
    """T123: un archivo que supera incluso el presupuesto ampliado añade las
    firmas deterministas al final (no se recortan): el LLM siempre puede
    enumerar TODOS los métodos aunque el cuerpo del código quede elidido."""
    contenido = "\n".join(
        [
            "using System;",
            "namespace DAL {",
            "    public class Grande {",
        ]
        + [f"        public void Metodo{i}(int p{i}) {{ }}"
           for i in range(60)]
        + [
            "        // " + "relleno largo x " * 300,
            "        // " + "relleno largo y " * 300,
            "    }",
            "}",
        ]
    )
    observacion = _observacion_leer("DAL/Grande.cs", contenido, 66)
    backend = _backend_sin_red()
    contexto = backend._contexto_observacion(observacion)

    assert "[+" in contexto, "el cuerpo grande sí se recorta"
    assert "FIRMAS_DETERMINISTAS" in contexto
    assert "Metodo0" in contexto
    assert "Metodo59" in contexto


def test_resumen_firmas_extrae_firmas_csharp_y_python():
    """T123: `_resumen_firmas` extrae firmas con modificador de acceso (C#),
    excluye propiedades sin `(`, y reconoce `def` de Python, con línea real."""
    contenido = (
        "using System;\n"
        "namespace DAL\n{\n"
        "    public class UsuarioDAL\n    {\n"
        "        private Usuario MappearFila(SqlDataReader dr) { return null; }\n"
        "        public int Insertar(Usuario usuario) { return 1; }\n"
        "        public static void Registrar(string a) { }\n"
        "        public string NombreCompleto { get; set; }\n"
        "    }\n}\n"
        "\n"
        "def sumar(a, b):\n"
        "    return a + b\n"
    )
    observacion = _observacion_leer("DAL/UsuarioDAL.cs", contenido, 15)
    backend = _backend_sin_red()
    firmas = backend._resumen_firmas(observacion.resultado)

    assert "L6: private Usuario MappearFila" in firmas
    assert "L7: public int Insertar" in firmas
    assert "L8: public static void Registrar" in firmas
    assert "L13: def sumar" in firmas
    assert "NombreCompleto" not in firmas


# -- T124: rail de `explore` (ruta real + capas reales) ----------------------


class _ResponderEvidencia(FakeLLM):
    """FakeLLM cuya respuesta final enumera los directorios reales observados."""

    def responder(self, observaciones, intencion: str = ""):
        capas = []
        for obs in observaciones:
            datos = getattr(getattr(obs, "resultado", None), "datos", {}) or {}
            if datos.get("existe") and datos.get("ruta"):
                nombre = (
                    str(datos["ruta"]).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
                )
                if nombre:
                    capas.append(nombre)
        return {
            "texto": "Capas reales observadas: " + ", ".join(sorted(set(capas))),
            "confianza": "alta",
            "recomendaciones": [],
        }


def _agente_sobre(
    tmp_path, herramientas, plan, pasos_max: int = 12, backend_cls=FakeLLM
) -> Agent:
    rutas = [str(tmp_path)]
    backend = backend_cls(
        soporta_razonamiento=True,
        plan=plan,
        evaluar={"satisfecha": False, "razon": "sigue"},
        responder={"texto": "ok", "confianza": "alta", "recomendaciones": []},
    )
    return Agent(
        backend=backend,
        herramientas=herramientas,
        allowlist=Allowlist(rutas),
        redactor=Redactor(),
        pasos_max=pasos_max,
    )


def test_extraer_capa_solicitada_salta_conectores():
    """"la capa de DAL" y "carpeta del proyecto BLL" extraen el token real: el
    patrón previo tomaba "de" y no disparaba el enriquecimiento determinista de
    capa (regresión real: "explora a profundidad la capa de DAL" dejaba el plan
    del LLM sin enriquecer)."""
    assert _extraer_capa_solicitada("Explora a profundidad la capa de DAL") == "dal"
    assert _extraer_capa_solicitada("las clases de la capa DAL") == "dal"
    assert _extraer_capa_solicitada("los archivos de la carpeta de BLL") == "bll"
    assert _extraer_capa_solicitada("Que otros archivos hay en esa capa?") == ""
    assert _extraer_capa_solicitada("analiza el proyecto") == ""


def test_resolver_directorio_real_encuentra_directorio_por_nombre(tmp_path):
    """`_resolver_directorio_real` corrige a un directorio real con el mismo
    nombre dentro del perímetro (análogo a `_resolver_archivo_real`, T124)."""
    (tmp_path / "DAL").mkdir()
    agente = _agente_sobre(tmp_path, [], _plan_de(1))
    propuesta = str(tmp_path / "inexistente" / "DAL")
    assert agente._resolver_directorio_real(propuesta) == str(tmp_path / "DAL")
    # Ruta existente → se devuelve tal cual; sin coincidencia → None.
    assert agente._resolver_directorio_real(str(tmp_path / "DAL")) == str(
        tmp_path / "DAL"
    )
    assert agente._resolver_directorio_real(str(tmp_path / "inexistente" / "XYZ")) is None


def test_explore_capa_inexistente_enriquece_capas_reales(tmp_path):
    """Regresión T124: el LLM planifica `explore` sobre una capa inexistente
    ('Datos', nombre derivado de Datos.csproj) y el agente, en vez de quedarse
    en un `explore` vacío (existe=False), enriquece deterministamente las capas
    REALES de primer nivel y responde anclado en esa evidencia."""
    for capa in ("BLL", "DAL", "EDL"):
        (tmp_path / capa).mkdir()
    (tmp_path / "Datos.csproj").write_text("<Project/>\n", encoding="utf-8")
    (tmp_path / "DAL" / "ClienteDAL.cs").write_text("x\n", encoding="utf-8")

    from qa_agent.tools.explore import ExploreHerramienta

    plan = {
        "objetivo": "listar archivos de la capa",
        "criterio_exito": "tener el listado real",
        "pasos": [
            {"orden": 1, "razon": "explorar la capa de datos",
             "herramienta": "explore",
             "parametros": {"ruta": str(tmp_path / "Datos"), "profundidad_max": 3},
             "criterio_salida": ""},
        ],
    }
    agente = _agente_sobre(
        tmp_path, [ExploreHerramienta([str(tmp_path)])], plan,
        backend_cls=_ResponderEvidencia,
    )
    respuesta = agente.atender("Que otros archivos hay en esa capa?", autorizacion=True)

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    rutas = {a.entrada.get("ruta") for a in exitos if a.herramienta_id == "explore"}
    # La ruta inventada se reporta honestamente y las capas reales se exploran.
    assert str(tmp_path / "Datos") in rutas
    for capa in ("BLL", "DAL", "EDL"):
        assert str(tmp_path / capa) in rutas
    # La respuesta final queda anclada en las capas reales observadas.
    assert "DAL" in respuesta.texto
    assert "BLL" in respuesta.texto


def test_explore_ruta_con_mismo_nombre_se_corrige_sin_fallback(tmp_path):
    """Si la ruta propuesta no existe pero hay un directorio real con el mismo
    nombre, el `explore` se corrige a la ruta real y NO se enriquece el plan
    (la corrección basta, T124)."""
    (tmp_path / "DAL").mkdir()
    (tmp_path / "BLL").mkdir()

    from qa_agent.tools.explore import ExploreHerramienta

    plan = {
        "objetivo": "capa",
        "criterio_exito": "listo",
        "pasos": [
            {"orden": 1, "razon": "explorar", "herramienta": "explore",
             "parametros": {"ruta": str(tmp_path / "padre_erroneo" / "DAL"),
                            "profundidad_max": 2}, "criterio_salida": ""},
        ],
    }
    agente = _agente_sobre(tmp_path, [ExploreHerramienta([str(tmp_path)])], plan)
    respuesta = agente.atender("Explora la capa DAL", autorizacion=True)

    exitos = [a for a in respuesta.acciones if a.estado.value == "exito"]
    rutas = {a.entrada.get("ruta") for a in exitos if a.herramienta_id == "explore"}
    assert str(tmp_path / "DAL") in rutas
    assert str(tmp_path / "padre_erroneo" / "DAL") not in rutas
    # Sin fallback: no explora otras capas.
    assert str(tmp_path / "BLL") not in rutas