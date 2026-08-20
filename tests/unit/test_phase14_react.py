"""Tests de integración ReAct + acciones destructivas (Phase 14, T101).

Cubre el flujo completo human-in-the-loop de `crear_archivo`/`editar_archivo`/
`eliminar_archivo` en el bucle: suspensión pendiente de autorización sin
modificar nada (FR-015/016 / SC-004), ejecución autorizada (FR-042/043/044),
denegación que no aborta (re-planificación, FR-036), y rechazo de rutas fuera
del perímetro (FR-025 / SC-022).
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.loop import Agent
from qa_agent.agent.response import EstadoAccion
from qa_agent.agent.router import extraer_contenido, extraer_nombre_archivo
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.security.redactor import Redactor
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.base import Herramienta
from qa_agent.tools.crear_archivo import CrearArchivoHerramienta
from qa_agent.tools.editar_archivo import EditarArchivoHerramienta
from qa_agent.tools.eliminar_archivo import EliminarArchivoHerramienta
from qa_agent.tools.leer_archivo import LeerArchivoHerramienta


def _catalogo(tmp_path: Path) -> list[Herramienta]:
    from qa_agent.tools.explore import ExploreHerramienta

    rutas = [str(tmp_path)]
    return [
        CrearArchivoHerramienta(rutas),
        EditarArchivoHerramienta(rutas),
        EliminarArchivoHerramienta(rutas),
        ExploreHerramienta(rutas),
    ]


def _agente(tmp_path: Path, **kwargs) -> Agent:
    plan = kwargs.pop(
        "plan",
        {
            "objetivo": "crear el archivo",
            "criterio_exito": "archivo creado",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "crear el archivo pedido",
                    "herramienta": "crear_archivo",
                    "parametros": {
                        "ruta": str(tmp_path),
                        "archivo_relativo": "src/app.py",
                        "contenido": "DEBUG = True\n",
                    },
                    "criterio_salida": "",
                }
            ],
        },
    )
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan=plan,
        responder=kwargs.pop(
            "responder",
            {"texto": "Archivo creado.", "confianza": "alta", "recomendaciones": []},
        ),
    )
    return Agent(
        backend=backend,
        herramientas=_catalogo(tmp_path),
        allowlist=Allowlist([str(tmp_path)]),
        redactor=Redactor(),
    )


def test_pendiente_autorizacion_suspende_sin_modificar(tmp_path):
    """T101: sin decisión → acción pendiente y el archivo NO se crea (SC-004)."""
    agente = _agente(tmp_path)
    respuesta = agente.atender("crea el archivo src/app.py")

    pendientes = [
        a
        for a in respuesta.acciones
        if a.estado == EstadoAccion.PENDIENTE_AUTORIZACION
    ]
    assert pendientes
    assert pendientes[0].herramienta_id == "crear_archivo"
    assert not (tmp_path / "src" / "app.py").exists()


def test_autorizada_ejecuta_y_crea_el_archivo(tmp_path):
    """T101: autorizada → se crea el archivo con el contenido real (FR-042)."""
    agente = _agente(tmp_path)
    respuesta = agente.atender("crea el archivo src/app.py", autorizacion=True)

    exito = [a for a in respuesta.acciones if a.estado == EstadoAccion.EXITO]
    assert any(a.herramienta_id == "crear_archivo" for a in exito)
    archivo = tmp_path / "src" / "app.py"
    assert archivo.exists()
    assert archivo.read_text(encoding="utf-8") == "DEBUG = True\n"


def test_denegada_replanifica_y_no_aborta(tmp_path):
    """T101: denegada → no se ejecuta y se continúa (FR-036 / FR-046)."""
    plan = {
        "objetivo": "tarea",
        "criterio_exito": "analizar",
        "pasos": [
            {
                "orden": 1,
                "razon": "crear archivo",
                "herramienta": "crear_archivo",
                "parametros": {
                    "ruta": str(tmp_path),
                    "archivo_relativo": "src/app.py",
                    "contenido": "x",
                },
                "criterio_salida": "",
            },
            {
                "orden": 2,
                "razon": "explorar estructura",
                "herramienta": "explore",
                "parametros": {"ruta": str(tmp_path), "profundidad_max": 2},
                "criterio_salida": "",
            },
        ],
    }
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan=plan,
        evaluar={"satisfecha": True, "razon": "hay evidencia"},
        responder={
            "texto": "No autorizado; continué con explore.",
            "confianza": "limitada",
            "recomendaciones": [],
        },
    )
    agente = Agent(
        backend=backend,
        herramientas=_catalogo(tmp_path),
        allowlist=Allowlist([str(tmp_path)]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("crea y analiza", autorizacion=False)

    denegadas = [a for a in respuesta.acciones if a.estado == EstadoAccion.ERROR]
    assert denegadas
    assert "denegada" in str(denegadas[0].salida).lower()
    assert not (tmp_path / "src" / "app.py").exists()


def test_paso_fuera_de_perimetro_se_rechaza_sin_crear(tmp_path):
    """T101: fuera del perímetro → la herramienta rechaza y nada se modifica."""
    plan = {
        "pasos": [
            {
                "orden": 1,
                "razon": "crear fuera",
                "herramienta": "crear_archivo",
                "parametros": {
                    "ruta": str(tmp_path),
                    "archivo_relativo": "../fuera.py",
                    "contenido": "x",
                },
                "criterio_salida": "",
            }
        ]
    }
    agente = _agente(tmp_path, plan=plan)
    respuesta = agente.atender("crea fuera", autorizacion=True)

    errores = [a for a in respuesta.acciones if a.estado == EstadoAccion.ERROR]
    assert errores
    assert not (tmp_path.parent / "fuera.py").exists()


def test_pasada_unica_con_parametros_extraidos(tmp_path):
    """T101: flujo de una pasada extrae archivo/contenido deterministamente."""
    from qa_agent.tools.explore import ExploreHerramienta

    backend = FakeLLM(
        seleccion={"herramienta": "crear_archivo"},
        responder={"texto": "Creado.", "confianza": "alta", "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[
            CrearArchivoHerramienta([str(tmp_path)]),
            ExploreHerramienta([str(tmp_path)]),
        ],
        allowlist=Allowlist([str(tmp_path)]),
        redactor=Redactor(),
    )
    solicitud = "crea el archivo src/x.py con contenido 'DEBUG = True'"
    respuesta = agente.atender(solicitud, autorizacion=True)

    assert respuesta.basada_en_herramientas
    archivo = tmp_path / "src" / "x.py"
    assert archivo.exists()
    assert archivo.read_text(encoding="utf-8") == "DEBUG = True"


def test_extraccion_determinista_del_contenido():
    """T101: los extractores del router alimentan los parámetros (VI / SC-010)."""
    texto = "edita el archivo src/config.py con contenido \"MODO = 'prod'\""
    assert extraer_nombre_archivo(texto) == "src/config.py"
    assert extraer_contenido(texto) == "MODO = 'prod'"


# -- T123: corrección determinista de escritura (crear → editar) --------------
# Regresión real con ReservaHotel: al pedir definir pruebas unitarias, el LLM
# planificaba `crear_archivo` sobre "UnitTest.md" (raíz, inexistente) cuando el
# archivo real estaba en "docs/UnitTest.md" y el usuario quería MODIFICARLO.
# El paso se corrige contra el filesystem: ruta real + `editar_archivo`
# (FR-042/043/025), sin duplicar ni rechazar por un nombre mal resuelto.
# Igualmente, la LECTURA propuesta por el LLM sobre una ruta inexistente pero
# con un archivo real del mismo nombre se corrige a la ruta real (regresión:
# leía 'Datos/ClienteDAL.cs' cuando la carpeta real es 'DAL'), para no perder
# la evidencia (FR-048/FR-019).


def _agente_escritura(tmp_path: Path, plan: dict) -> Agent:
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan=plan,
        evaluar={"satisfecha": True, "razon": "listo"},
        responder={"texto": "Listo.", "confianza": "alta", "recomendaciones": []},
    )
    return Agent(
        backend=backend,
        herramientas=_catalogo(tmp_path),
        allowlist=Allowlist([str(tmp_path)]),
        redactor=Redactor(),
    )


def test_crear_archivo_en_ruta_erronea_se_corrige_a_editar(tmp_path):
    """T123: `crear_archivo` sobre "UnitTest.md" (raíz) con el archivo real en
    "docs/UnitTest.md" se corrige a `editar_archivo` sobre la ruta real: se
    modifica el archivo existente y no se crea un duplicado en la raíz."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "UnitTest.md").write_text("V1\n", encoding="utf-8")

    agente = _agente_escritura(
        tmp_path,
        {
            "objetivo": "definir pruebas",
            "criterio_exito": "archivo actualizado",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "definir las pruebas en el archivo",
                    "herramienta": "crear_archivo",
                    "parametros": {
                        "ruta": str(tmp_path),
                        "archivo_relativo": "UnitTest.md",
                        "contenido": "V2\n",
                    },
                    "criterio_salida": "",
                }
            ],
        },
    )
    respuesta = agente.atender(
        "define las pruebas unitarias en UnitTest.md", autorizacion=True
    )

    exitos = [a for a in respuesta.acciones if a.estado == EstadoAccion.EXITO]
    editados = [a for a in exitos if a.herramienta_id == "editar_archivo"]
    assert editados, "el paso debió corregirse a editar_archivo"
    assert editados[0].entrada.get("archivo_relativo") == "docs/UnitTest.md"
    assert (docs / "UnitTest.md").read_text(encoding="utf-8") == "V2\n"
    assert not (tmp_path / "UnitTest.md").exists()


def test_crear_archivo_ya_existente_se_corrige_a_editar(tmp_path):
    """T123: `crear_archivo` sobre un archivo que YA existe (mismo path) se
    mapea a `editar_archivo`: modifica el archivo en vez de rechazarlo
    (FR-042 → FR-043)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("A\n", encoding="utf-8")

    agente = _agente_escritura(
        tmp_path,
        {
            "objetivo": "actualizar",
            "criterio_exito": "archivo actualizado",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "crear el archivo",
                    "herramienta": "crear_archivo",
                    "parametros": {
                        "ruta": str(tmp_path),
                        "archivo_relativo": "src/app.py",
                        "contenido": "B\n",
                    },
                    "criterio_salida": "",
                }
            ],
        },
    )
    respuesta = agente.atender("crea el archivo src/app.py", autorizacion=True)

    exitos = [a for a in respuesta.acciones if a.estado == EstadoAccion.EXITO]
    assert any(a.herramienta_id == "editar_archivo" for a in exitos)
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "B\n"


def test_editar_archivo_inexistente_no_se_invierte_a_crear(tmp_path):
    """T123: `editar_archivo` sobre un archivo inexistente se mantiene y la
    herramienta lo rechaza honestamente (FR-043): el rail no inventa un archivo
    que no existe ni lo convierte en `crear_archivo` por sorpresa."""
    agente = _agente_escritura(
        tmp_path,
        {
            "objetivo": "editar",
            "criterio_exito": "archivo editado",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "editar el archivo",
                    "herramienta": "editar_archivo",
                    "parametros": {
                        "ruta": str(tmp_path),
                        "archivo_relativo": "docs/inexistente.md",
                        "contenido": "X\n",
                    },
                    "criterio_salida": "",
                }
            ],
        },
    )
    respuesta = agente.atender(
        "edita el archivo docs/inexistente.md", autorizacion=True
    )

    assert not (tmp_path / "docs" / "inexistente.md").exists()
    editadas = [
        a for a in respuesta.acciones if a.herramienta_id == "editar_archivo"
    ]
    assert editadas, "el paso se mantiene como editar_archivo"
    assert editadas[0].estado == EstadoAccion.INVALIDO


def test_leer_archivo_en_ruta_erronea_se_corrige_a_ruta_real(tmp_path):
    """T123: `leer_archivo` sobre una ruta inexistente pero con un archivo real
    del mismo nombre se corrige a la ruta real dentro del perímetro (regresión
    real: el LLM leía 'Datos/ClienteDAL.cs' cuando la carpeta real es 'DAL'),
    recuperando la evidencia en vez de reportar existe=False."""
    dal = tmp_path / "DAL"
    dal.mkdir()
    (dal / "ClienteDAL.cs").write_text(
        "public class ClienteDAL { public Cliente BuscarPorCedula(...) }",
        encoding="utf-8",
    )

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "definir métodos a probar",
            "criterio_exito": "evidencia real",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "leer los métodos de la capa de datos",
                    "herramienta": "leer_archivo",
                    "parametros": {
                        "ruta": str(tmp_path),
                        "archivo_relativo": "Datos/ClienteDAL.cs",
                    },
                    "criterio_salida": "",
                }
            ],
        },
        evaluar={"satisfecha": True, "razon": "listo"},
        responder={"texto": "Métodos identificados.", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[LeerArchivoHerramienta([str(tmp_path)])],
        allowlist=Allowlist([str(tmp_path)]),
        redactor=Redactor(),
    )
    respuesta = agente.atender(
        "Define en UnitTest.md los métodos del DAL a probar", autorizacion=True
    )

    exitos = [a for a in respuesta.acciones if a.estado == EstadoAccion.EXITO]
    lecturas = [a for a in exitos if a.herramienta_id == "leer_archivo"]
    assert lecturas, "la lectura debió ejecutarse"
    assert lecturas[0].entrada.get("archivo_relativo") == "DAL/ClienteDAL.cs"
    assert lecturas[0].salida.get("existe") is True
    assert "BuscarPorCedula" in lecturas[0].salida.get("contenido", "")


def test_leer_archivo_sin_archivo_real_se_mantiene_y_reporta_ausencia(tmp_path):
    """T123: `leer_archivo` sobre una ruta sin archivo real equivalente se
    mantiene y la herramienta reporta la ausencia honestamente (FR-019), sin
    inventar contenido."""
    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "leer",
            "criterio_exito": "evidencia",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "leer el archivo",
                    "herramienta": "leer_archivo",
                    "parametros": {
                        "ruta": str(tmp_path),
                        "archivo_relativo": "docs/inexistente.md",
                    },
                    "criterio_salida": "",
                }
            ],
        },
        evaluar={"satisfecha": True, "razon": "listo"},
        responder={"texto": "No existe.", "confianza": "limitada",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[LeerArchivoHerramienta([str(tmp_path)])],
        allowlist=Allowlist([str(tmp_path)]),
        redactor=Redactor(),
    )
    respuesta = agente.atender("lee el archivo docs/inexistente.md")

    exitos = [a for a in respuesta.acciones if a.estado == EstadoAccion.EXITO]
    lecturas = [a for a in exitos if a.herramienta_id == "leer_archivo"]
    assert lecturas
    assert lecturas[0].entrada.get("archivo_relativo") == "docs/inexistente.md"
    assert lecturas[0].salida.get("existe") is False
    assert lecturas[0].salida.get("contenido") == ""


def test_escritura_se_replanifica_anclada_en_evidencia_real(tmp_path):
    """T123: un paso de escritura del plan se re-planifica cuando la solicitud
    ya acumuló evidencia real (lectura previa), de modo que el contenido se
    ancla en lo observado y no en la convención que el LLM planificó ANTES de
    ejecutar las lecturas (FR-019 / FR-043)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "UnitTest.md").write_text("V1\n", encoding="utf-8")
    dal = tmp_path / "DAL"
    dal.mkdir()
    (dal / "ClienteDAL.cs").write_text(
        "public class ClienteDAL { public Cliente BuscarPorCedula(...) }",
        encoding="utf-8",
    )

    backend = FakeLLM(
        soporta_razonamiento=True,
        plan={
            "objetivo": "definir métodos a probar",
            "criterio_exito": "UnitTest.md actualizado",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "leer los métodos de la capa de datos",
                    "herramienta": "leer_archivo",
                    "parametros": {
                        "ruta": str(tmp_path),
                        "archivo_relativo": "Datos/ClienteDAL.cs",
                    },
                    "criterio_salida": "",
                },
                {
                    "orden": 2,
                    "razon": "definir los métodos a probar",
                    "herramienta": "editar_archivo",
                    "parametros": {
                        "ruta": str(tmp_path),
                        "archivo_relativo": "docs/UnitTest.md",
                        "contenido": "contenido previo del plan\n",
                    },
                    "criterio_salida": "",
                },
            ],
        },
        razonar={
            "herramienta": "editar_archivo",
            "parametros": {
                "contenido": "Métodos observados: BuscarPorCedula\n",
            },
            "razon": "escribir anclado en la lectura real",
        },
        evaluar={"satisfecha": True, "razon": "listo"},
        responder={"texto": "Listo.", "confianza": "alta",
                   "recomendaciones": []},
    )
    agente = Agent(
        backend=backend,
        herramientas=[
            LeerArchivoHerramienta([str(tmp_path)]),
            EditarArchivoHerramienta([str(tmp_path)]),
        ],
        allowlist=Allowlist([str(tmp_path)]),
        redactor=Redactor(),
    )
    respuesta = agente.atender(
        "Define en docs/UnitTest.md los métodos del DAL a probar",
        autorizacion=True,
    )

    assert (docs / "UnitTest.md").read_text(encoding="utf-8") == (
        "Métodos observados: BuscarPorCedula\n"
    )
    editadas = [
        a for a in respuesta.acciones if a.herramienta_id == "editar_archivo"
    ]
    assert editadas, "el paso re-planificado debió ejecutarse"
    assert editadas[0].estado == EstadoAccion.EXITO
    assert editadas[0].salida.get("editado") is True
    lecturas = [
        a for a in respuesta.acciones if a.herramienta_id == "leer_archivo"
    ]
    assert lecturas, "la lectura previa aportó la evidencia real"
    assert lecturas[0].salida.get("existe") is True