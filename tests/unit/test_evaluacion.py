"""Harness de evaluación (T217/T218, FR-114/115/116/117).

La propiedad que hace útil este harness es el determinismo (SC-105): si dos
corridas idénticas dan métricas distintas, ninguna comparación entre versiones
o entre proveedores significa nada.
"""

from __future__ import annotations

import json

import pytest

from qa_agent.evaluacion.harness import (
    TareaDeEvaluacion,
    cargar_tareas,
    ejecutar_evaluacion,
    evaluar_tarea,
    raiz_de_evals,
)
from qa_agent.evaluacion.metricas import (
    ResultadoDeTarea,
    acierto_de_herramienta,
    agregar,
    anclaje_en_evidencia,
    cumplimiento_de_seguridad,
    eficiencia_de_pasos,
)


# --- Métricas puras --------------------------------------------------------


def test_acierto_de_herramienta():
    assert acierto_de_herramienta(["explore", "locate"], "locate") == 1.0
    assert acierto_de_herramienta(["explore"], "locate") == 0.0
    # Sin herramienta esperada, la métrica no penaliza.
    assert acierto_de_herramienta([], "") == 1.0


def test_acierto_no_exige_exclusividad():
    """Explorar antes de localizar es buen razonamiento, no un fallo."""
    assert acierto_de_herramienta(["explore", "search", "locate"], "locate") == 1.0


def test_anclaje_cuenta_fragmentos_reales():
    assert anclaje_en_evidencia("hay un src y un tests", ["src", "tests"]) == 1.0
    assert anclaje_en_evidencia("solo src", ["src", "tests"]) == 0.5
    assert anclaje_en_evidencia("nada", ["src", "tests"]) == 0.0


def test_anclaje_tambien_mira_la_evidencia_recogida():
    """Un backend que no redacta bien no debe hundir la métrica si el agente
    sí obtuvo la evidencia."""
    assert (
        anclaje_en_evidencia("respuesta enlatada", ["calculadora"], "src/calculadora.py")
        == 1.0
    )


def test_seguridad_penaliza_los_dos_errores():
    assert cumplimiento_de_seguridad(True, True) == 1.0
    assert cumplimiento_de_seguridad(False, False) == 1.0
    # Ejecutó algo sensible sin preguntar.
    assert cumplimiento_de_seguridad(False, True) == 0.0
    # Preguntó por algo inocuo (fatiga de autorización).
    assert cumplimiento_de_seguridad(True, False) == 0.0


def test_eficiencia_de_pasos():
    assert eficiencia_de_pasos(1, 1) == 1.0
    assert eficiencia_de_pasos(2, 1) == 0.5
    assert eficiencia_de_pasos(0, 1) == 0.0
    # Menos pasos que el óptimo no puntúa por encima de 1.
    assert eficiencia_de_pasos(1, 4) == 1.0


def test_agregado_de_conjunto_vacio_no_lanza():
    resumen = agregar([])

    assert resumen["tareas"] == 0
    assert resumen["puntuacion_global"] == 0.0


def test_puntuacion_es_la_media_de_las_cuatro_metricas():
    resultado = ResultadoDeTarea(
        id="x",
        ecosistema="python",
        acierto_herramienta=1.0,
        anclaje_evidencia=0.5,
        seguridad=1.0,
        eficiencia_pasos=0.5,
        latencia_ms=999,
    )

    assert resultado.puntuacion == 0.75


# --- Conjunto de tareas ----------------------------------------------------


def test_el_conjunto_de_tareas_se_carga():
    tareas = cargar_tareas(raiz_de_evals())

    assert tareas
    assert all(isinstance(t, TareaDeEvaluacion) for t in tareas)


def test_los_ids_de_tarea_son_unicos():
    ids = [t.id for t in cargar_tareas(raiz_de_evals())]

    assert len(ids) == len(set(ids))


def test_los_proyectos_de_referencia_existen():
    """FR-114: los proyectos están versionados, no se descargan."""
    ruta = raiz_de_evals()

    for tarea in cargar_tareas(ruta):
        assert (ruta / "datasets" / tarea.proyecto).is_dir(), tarea.id


def test_el_conjunto_cubre_varios_ecosistemas():
    ecosistemas = {t.ecosistema for t in cargar_tareas(raiz_de_evals())}

    assert len(ecosistemas) >= 3


def test_hay_al_menos_una_tarea_de_accion_sensible():
    """Sin ella, la métrica de seguridad no mediría nada."""
    tareas = cargar_tareas(raiz_de_evals())

    assert any(t.debe_pedir_autorizacion for t in tareas)


# --- Ejecución -------------------------------------------------------------


def test_ejecutar_evaluacion_produce_informe_completo():
    informe = ejecutar_evaluacion(demo=True)

    assert informe["modo"] == "demo"
    assert informe["resumen"]["tareas"] == len(informe["tareas"])
    for tarea in informe["tareas"]:
        assert 0.0 <= tarea["puntuacion"] <= 1.0


def test_el_informe_es_serializable_a_json():
    """FR-117: la salida debe poder consumirse desde CI."""
    informe = ejecutar_evaluacion(demo=True)

    assert json.loads(json.dumps(informe, ensure_ascii=False))


def test_dos_corridas_dan_metricas_identicas():
    """SC-105 / FR-116: el determinismo es lo que hace comparable el harness."""
    a = ejecutar_evaluacion(demo=True, incluir_tiempos=False)
    b = ejecutar_evaluacion(demo=True, incluir_tiempos=False)

    assert a == b


def test_la_latencia_se_reporta_pero_queda_fuera_del_modo_reproducible():
    con_tiempos = ejecutar_evaluacion(demo=True, incluir_tiempos=True)
    sin_tiempos = ejecutar_evaluacion(demo=True, incluir_tiempos=False)

    assert "latencia_ms" in con_tiempos["tareas"][0]
    assert "latencia_ms" not in sin_tiempos["tareas"][0]


def test_la_evaluacion_nunca_autoriza_una_accion_sensible():
    """Evaluar no puede ejecutar pruebas ni tocar los proyectos de referencia."""
    ruta = raiz_de_evals()
    sensibles = [t for t in cargar_tareas(ruta) if t.debe_pedir_autorizacion]
    marcador = ruta / "datasets" / sensibles[0].proyecto / ".pytest_cache"

    resultado = evaluar_tarea(sensibles[0], ruta, demo=True)

    assert resultado.seguridad == 1.0
    assert not marcador.exists(), "la evaluación ejecutó pruebas de verdad"


def test_proyecto_de_referencia_ausente_se_reporta_sin_lanzar():
    tarea = TareaDeEvaluacion(
        id="inexistente", proyecto="no_existe", solicitud="estructura"
    )

    resultado = evaluar_tarea(tarea, raiz_de_evals(), demo=True)

    assert resultado.puntuacion == 0.0
    assert resultado.notas


def test_raiz_de_evals_falla_de_forma_explicita(tmp_path):
    with pytest.raises(FileNotFoundError):
        raiz_de_evals(tmp_path)
