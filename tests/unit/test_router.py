"""Tests del enrutador determinista de solicitudes a herramientas (T064).

Verifica que frases en lenguaje natural disparan la herramienta QA correcta
sin depender del LLM (determinista, VI / SC-010), y que sin coincidencia se
delega (`None` → el LLM decide).
"""

from __future__ import annotations

from qa_agent.agent.router import (
    enrutar_solicitud,
    extraer_contenido,
    extraer_nombre_archivo,
    extraer_objetivo_cripticidad,
    extraer_patron_busqueda,
    listar_herramientas_enrutables,
    obtener_palabras_clave,
)


def test_analiza_resultados_de_prueba_apunta_a_analyze_test_results():
    """T064 CoD 1: 'analiza estos resultados de prueba' → analyze_test_results."""
    assert (
        enrutar_solicitud("analiza estos resultados de prueba")
        == "analyze_test_results"
    )


def test_genera_casos_de_prueba_apunta_a_generate_test_cases():
    """T064 CoD 2: 'genera casos de prueba para X' → generate_test_cases."""
    assert (
        enrutar_solicitud("genera casos de prueba para la clase Usuario")
        == "generate_test_cases"
    )
    assert (
        enrutar_solicitud("genera casos de prueba para la función sumar")
        == "generate_test_cases"
    )


def test_analiza_cobertura_apunta_a_analyze_coverage():
    """T064 CoD 3: 'analiza la cobertura' → analyze_coverage."""
    assert enrutar_solicitud("analiza la cobertura") == "analyze_coverage"
    assert enrutar_solicitud("muestra la cobertura de los tests") == "analyze_coverage"


def test_frases_qa_no_se_contaminan_entre_si():
    """Las frases QA del CoD nunca se enrutan a otra herramienta QA."""
    assert (
        enrutar_solicitud("analiza estos resultados de prueba")
        == "analyze_test_results"
    )
    assert (
        enrutar_solicitud("genera casos de prueba para X")
        == "generate_test_cases"
    )
    assert enrutar_solicitud("analiza la cobertura") == "analyze_coverage"


def test_otras_herramientas_siguen_enrutando():
    """El resto de herramientas no se ve afectado por el enrutador."""
    assert enrutar_solicitud("ejecuta los tests del proyecto") == "run_tests"
    assert enrutar_solicitud("explora la estructura del proyecto") == "explore"
    assert enrutar_solicitud("busca el patrón config") == "search"
    assert enrutar_solicitud("localiza la función config") == "locate"


def test_sin_coincidencia_devuelve_none_para_delegar_al_llm():
    """Sin palabra clave → None (el LLM decide)."""
    assert enrutar_solicitud("hola") is None
    assert enrutar_solicitud("") is None


def test_herramientas_qa_estan_enrutables():
    """Las tres herramientas QA/Testing son enrutables."""
    enrutables = listar_herramientas_enrutables()
    for hid in (
        "analyze_test_results",
        "generate_test_cases",
        "analyze_coverage",
    ):
        assert hid in enrutables


def test_obtener_palabras_clave_devuelve_frases():
    """Palabras clave documentadas por herramienta (visibles para tests)."""
    frases = obtener_palabras_clave("analyze_coverage")
    assert frases
    assert obtener_palabras_clave("inexistente") == []


# -- extracción de objetivo/cripticidad ---------------------------------------


def test_extrae_objetivo_tras_para_limpiando_muletillas():
    objetivo, _ = extraer_objetivo_cripticidad(
        "genera casos de prueba para la clase config"
    )
    assert objetivo == "config"


def test_extrae_objetivo_tras_de_con_funcion():
    objetivo, _ = extraer_objetivo_cripticidad(
        "genera casos de prueba de la función sumar"
    )
    assert objetivo == "sumar"


def test_cripticidad_por_defecto_happy_path():
    objetivo, cripticidad = extraer_objetivo_cripticidad(
        "genera casos de prueba para la clase config"
    )
    assert objetivo == "config"
    assert cripticidad == "happy_path"


def test_cripticidad_edge_cases_por_palabras_clave():
    _, cripticidad = extraer_objetivo_cripticidad(
        "genera casos límite para la función sumar"
    )
    assert cripticidad == "edge_cases"
    _, cripticidad = extraer_objetivo_cripticidad(
        "genera casos de borde para dividir"
    )
    assert cripticidad == "edge_cases"


def test_cripticidad_usuarios_no_validos_por_palabras_clave():
    _, cripticidad = extraer_objetivo_cripticidad(
        "genera casos con usuarios no válidos para login"
    )
    assert cripticidad == "usuarios_no_validos"
    _, cripticidad = extraer_objetivo_cripticidad(
        "genera casos negativos para validar email"
    )
    assert cripticidad == "usuarios_no_validos"


def test_sin_delimitador_objetivo_es_el_texto_normalizado():
    objetivo, _ = extraer_objetivo_cripticidad("analiza la cobertura")
    assert objetivo == "analiza la cobertura"


# -- extraer_patron_busqueda (T049 / FR-010) -----------------------------------


def test_extrae_patron_tras_patron_en_el_codigo():
    assert (
        extraer_patron_busqueda("busca el patrón zzzNada en el código")
        == "zzzNada"
    )


def test_extrae_patron_tras_expresion():
    assert (
        extraer_patron_busqueda("busca la expresión [a-z]+\\d+ en el código")
        == "[a-z]+\\d+"
    )


def test_extrae_nombre_tras_funcion_o_clase():
    assert (
        extraer_patron_busqueda("localiza la función sumar") == "sumar"
    )
    assert (
        extraer_patron_busqueda("encuentra la clase Usuario") == "Usuario"
    )


def test_sin_patron_extraible_devuelve_vacio():
    assert extraer_patron_busqueda("explora la estructura del proyecto") == ""


# -- leer_archivo: enrutado y extracción de nombre (T104 / FR-048) -------------


def test_leer_archivo_apunta_a_leer_archivo():
    """T104 CoD 1: pedir que lea/muestre el contenido de un archivo → leer_archivo."""
    assert (
        enrutar_solicitud("lee el archivo tests/test_app.py")
        == "leer_archivo"
    )
    assert (
        enrutar_solicitud("muestra el contenido del archivo src/app.py")
        == "leer_archivo"
    )
    assert (
        enrutar_solicitud("abre el archivo de código fuente config.py")
        == "leer_archivo"
    )


def test_leer_archivo_con_analiza_archivo():
    """'analiza el archivo X' → leer_archivo (leer para explicar)."""
    assert (
        enrutar_solicitud("analiza el archivo src/services.py")
        == "leer_archivo"
    )


def test_leer_archivo_que_hace_archivo_con_extension():
    """'qué hace / explícame <archivo.ext>' → leer_archivo (explicar leyendo)."""
    assert (
        enrutar_solicitud("qué hace src/qa_agent/tools/leer_archivo.py")
        == "leer_archivo"
    )
    assert (
        enrutar_solicitud("explícame qué pruebas hace tests/test_app.py")
        == "leer_archivo"
    )


def test_leer_archivo_sin_archivo_concreto_sigue_siendo_otras_herramientas():
    """'qué hace la capa de dominio' (sin archivo.ext) no fuerza leer_archivo."""
    assert enrutar_solicitud("explora la estructura del proyecto") == "explore"
    assert enrutar_solicitud("qué hace la capa de dominio") is None


def test_leer_archivo_gana_a_explore_cuando_pide_contenido():
    """'muestra ... contenido del archivo' no debe caer en explore (T104)."""
    assert (
        enrutar_solicitud("muestra el contenido del archivo src/main.py")
        == "leer_archivo"
    )
    # Sin pedir contenido de un archivo concreto, explore sigue enrutando
    assert enrutar_solicitud("explora la estructura del proyecto") == "explore"


def test_leer_archivo_enrutable():
    assert "leer_archivo" in listar_herramientas_enrutables()


def test_extrae_nombre_archivo_primera_ruta_con_extension():
    assert extraer_nombre_archivo("lee el archivo tests/test_app.py") == "tests/test_app.py"
    assert (
        extraer_nombre_archivo("muestra el contenido del archivo src/app.py")
        == "src/app.py"
    )


def test_extrae_nombre_archivo_con_rutas_con_guiones_y_puntos():
    assert (
        extraer_nombre_archivo("abre config.prod.yaml")
        == "config.prod.yaml"
    )


def test_extrae_nombre_archivo_sin_archivo_devuelve_vacio():
    assert extraer_nombre_archivo("explora la estructura del proyecto") == ""


# -- Phase 14: enrutamiento de acciones destructivas (T100) -------------------


def test_enruta_crear_archivo():
    """'crea el archivo X' → crear_archivo (Phase 14 / US-13)."""
    assert (
        enrutar_solicitud("crea el archivo src/config/ajustes.py con contenido")
        == "crear_archivo"
    )
    assert enrutar_solicitud("crea un fichero README.md") == "crear_archivo"


def test_enruta_editar_archivo():
    """'edita/modifica el archivo X' → editar_archivo (Phase 14 / US-13)."""
    assert (
        enrutar_solicitud("edita el archivo src/app.py con contenido")
        == "editar_archivo"
    )
    assert enrutar_solicitud("modifica el archivo config.py") == "editar_archivo"


def test_enruta_eliminar_archivo():
    """'elimina/borra el archivo X' → eliminar_archivo (Phase 14 / US-13)."""
    assert enrutar_solicitud("elimina el archivo src/viejo.py") == "eliminar_archivo"
    assert enrutar_solicitud("borra el fichero temporal.txt") == "eliminar_archivo"


def test_crear_archivo_gana_a_generate_test_cases():
    """'crea el archivo tests/test_app.py' no cae en generate_test_cases (T100)."""
    assert (
        enrutar_solicitud("crea el archivo tests/test_app.py")
        == "crear_archivo"
    )


def test_genera_casos_sigue_apuntando_a_generate_test_cases():
    """'crea casos de prueba' (sin archivo) sigue en generate_test_cases."""
    assert (
        enrutar_solicitud("crea casos de prueba para la clase Usuario")
        == "generate_test_cases"
    )


def test_herramientas_destructivas_enrutables():
    """Las tres herramientas destructivas son enrutables."""
    enrutables = listar_herramientas_enrutables()
    for hid in ("crear_archivo", "editar_archivo", "eliminar_archivo"):
        assert hid in enrutables


def test_extrae_contenido_entre_comillas():
    """Contenido entre comillas se extrae tal cual (T096/097)."""
    assert (
        extraer_contenido("crea el archivo x.py con contenido 'DEBUG = True'")
        == "DEBUG = True"
    )


def test_extrae_contenido_tras_con_contenido():
    """Contenido tras 'con contenido' hasta el final de la solicitud."""
    assert (
        extraer_contenido("edita x.py con contenido: DEBUG = True")
        == "DEBUG = True"
    )


def test_extrae_contenido_sin_contenido_devuelve_vacio():
    """Sin contenido explícito → vacío (la herramienta informa la ausencia)."""
    assert extraer_contenido("elimina el archivo x.py") == ""
