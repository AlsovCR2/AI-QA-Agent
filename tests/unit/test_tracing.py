"""Traza estructurada por solicitud (T213–T216, FR-110/111/112/113).

Lo que estas pruebas fijan, en orden de importancia:

1. La traza nunca filtra secretos (FR-111) — es un artefacto que se persiste.
2. La traza nunca rompe la solicitud (FR-112) — un destino no escribible
   degrada la observabilidad, no la función principal.
3. La traza no cambia el comportamiento del agente (principio I).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_agent.agent.loop import Agent
from qa_agent.agent.tracing import (
    AUTORIZACION,
    EVIDENCIA_SUFICIENTE,
    PASO_EJECUTADO,
    RAZONES_DE_PARADA,
    SOLICITUD_INICIADA,
    SOLICITUD_TERMINADA,
    EventoDeTraza,
    Trazador,
    TrazadorNulo,
)
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.explore import ExploreHerramienta
from qa_agent.tools.run_tests import RunTestsHerramienta


def _proyecto(tmp_path: Path) -> Path:
    raiz = tmp_path / "proyecto"
    (raiz / "src").mkdir(parents=True)
    (raiz / "src" / "app.py").write_text("def hola():\n    return 1\n", encoding="utf-8")
    return raiz


def _agente(raiz: Path, trazador: Trazador | None = None) -> Agent:
    # La `Allowlist` es lo que fija la raíz autorizada del agente (`_ruta_base`);
    # sin ella las herramientas operarían sobre "." y `explore` fallaría.
    return Agent(
        backend=FakeLLM(),
        herramientas=[
            ExploreHerramienta([str(raiz)]),
            RunTestsHerramienta([str(raiz)]),
        ],
        allowlist=Allowlist([str(raiz)]),
        trazador=trazador,
    )


# --- Emisión y correlación (FR-110) ---------------------------------------


def test_una_solicitud_produce_apertura_y_cierre(tmp_path):
    raiz = _proyecto(tmp_path)
    trazador = Trazador()
    _agente(raiz, trazador).atender(f"explora la estructura de {raiz}", None)

    tipos = [e.tipo for e in trazador.eventos]

    assert tipos[0] == SOLICITUD_INICIADA
    assert tipos[-1] == SOLICITUD_TERMINADA


def test_todos_los_eventos_comparten_el_id_de_solicitud(tmp_path):
    raiz = _proyecto(tmp_path)
    trazador = Trazador()
    _agente(raiz, trazador).atender(f"explora {raiz}", None)

    assert len({e.solicitud_id for e in trazador.eventos}) == 1


def test_la_secuencia_es_monotona(tmp_path):
    raiz = _proyecto(tmp_path)
    trazador = Trazador()
    _agente(raiz, trazador).atender(f"explora {raiz}", None)

    secuencias = [e.secuencia for e in trazador.eventos]

    assert secuencias == sorted(secuencias)
    assert secuencias == list(range(1, len(secuencias) + 1))


def test_hay_un_evento_por_paso_ejecutado(tmp_path):
    raiz = _proyecto(tmp_path)
    trazador = Trazador()
    agente = _agente(raiz, trazador)
    agente.atender(f"explora la estructura de {raiz}", None)

    pasos = [e for e in trazador.eventos if e.tipo == PASO_EJECUTADO]

    assert len(pasos) == len(agente.sesion.acciones)


def test_la_razon_de_parada_es_una_de_las_declaradas(tmp_path):
    raiz = _proyecto(tmp_path)
    trazador = Trazador()
    _agente(raiz, trazador).atender(f"explora {raiz}", None)

    assert trazador.razon_de_parada() in RAZONES_DE_PARADA


def test_solicitud_sin_herramienta_adecuada_lo_registra(tmp_path):
    raiz = _proyecto(tmp_path)
    trazador = Trazador()
    _agente(raiz, trazador).atender("cuéntame un chiste sobre el clima", None)

    assert trazador.razon_de_parada() in RAZONES_DE_PARADA


# --- Autorización (FR-110) -------------------------------------------------


def test_una_accion_pendiente_de_autorizacion_deja_traza(tmp_path):
    raiz = _proyecto(tmp_path)
    trazador = Trazador()
    # Sin decisión de autorización, `run_tests` queda suspendida (SC-004).
    _agente(raiz, trazador).atender(f"ejecuta las pruebas de {raiz}", None)

    eventos_auth = [e for e in trazador.eventos if e.tipo == AUTORIZACION]

    assert eventos_auth, "la decisión humana debe quedar registrada"
    assert trazador.pidio_autorizacion() is True


# --- Redacción (FR-111) ----------------------------------------------------


def test_la_traza_no_contiene_secretos(tmp_path):
    destino = tmp_path / "traza.jsonl"
    trazador = Trazador(destino)

    trazador.emitir(
        "s1",
        PASO_EJECUTADO,
        herramienta="explore",
        detalle={"entrada": {"token": "sk-abcdefgh12345678"}},
    )

    contenido = destino.read_text(encoding="utf-8")
    assert "sk-abcdefgh12345678" not in contenido
    assert "***" in contenido


def test_la_redaccion_ocurre_al_construir_no_al_escribir():
    """El evento en memoria ya está redactado: ningún consumidor ve el secreto."""
    trazador = Trazador()

    evento = trazador.emitir(
        "s1", PASO_EJECUTADO, detalle={"clave": "api_key=sk-abcdefgh12345678"}
    )

    assert "sk-abcdefgh12345678" not in json.dumps(evento.como_dict())


# --- Formato JSONL ---------------------------------------------------------


def test_cada_evento_es_una_linea_json_valida(tmp_path):
    destino = tmp_path / "traza.jsonl"
    trazador = Trazador(destino)

    for i in range(3):
        trazador.emitir("s1", PASO_EJECUTADO, herramienta=f"h{i}")

    lineas = destino.read_text(encoding="utf-8").strip().split("\n")

    assert len(lineas) == 3
    for linea in lineas:
        assert json.loads(linea)["solicitud_id"] == "s1"


def test_el_directorio_del_destino_se_crea(tmp_path):
    destino = tmp_path / "sub" / "dir" / "traza.jsonl"
    Trazador(destino).emitir("s1", SOLICITUD_INICIADA)

    assert destino.exists()


# --- Robustez: la traza nunca rompe la solicitud (FR-112) -----------------


def test_destino_no_escribible_no_lanza(tmp_path):
    # Un directorio donde se espera un archivo: la escritura fallará siempre.
    destino = tmp_path / "soy_un_directorio"
    destino.mkdir()
    trazador = Trazador(destino)

    evento = trazador.emitir("s1", SOLICITUD_INICIADA)

    assert evento is not None
    assert trazador.error_de_escritura != ""
    assert trazador.activo is False


def test_la_solicitud_se_completa_aunque_la_traza_falle(tmp_path):
    raiz = _proyecto(tmp_path)
    destino = tmp_path / "bloqueado"
    destino.mkdir()

    respuesta = _agente(raiz, Trazador(destino)).atender(f"explora {raiz}", None)

    assert respuesta.texto, "la respuesta al usuario no depende de la traza"


def test_detalle_no_serializable_no_lanza(tmp_path):
    destino = tmp_path / "traza.jsonl"
    trazador = Trazador(destino)

    evento = trazador.emitir("s1", PASO_EJECUTADO, detalle={"objeto": object()})

    assert evento is not None
    assert trazador.error_de_escritura != ""


def test_el_fallo_de_escritura_no_se_reintenta(tmp_path):
    destino = tmp_path / "dir"
    destino.mkdir()
    trazador = Trazador(destino)

    trazador.emitir("s1", SOLICITUD_INICIADA)
    primer_error = trazador.error_de_escritura
    trazador.emitir("s1", PASO_EJECUTADO)

    # Los eventos se siguen acumulando en memoria aunque el disco esté caído.
    assert len(trazador.eventos) == 2
    assert trazador.error_de_escritura == primer_error


# --- La traza observa, no decide (principio I) ----------------------------


def test_el_agente_se_comporta_igual_con_y_sin_traza(tmp_path):
    raiz = _proyecto(tmp_path)

    sin_traza = _agente(raiz).atender(f"explora la estructura de {raiz}", None)
    con_traza = _agente(raiz, Trazador()).atender(
        f"explora la estructura de {raiz}", None
    )

    assert sin_traza.texto == con_traza.texto
    assert sin_traza.confianza == con_traza.confianza


def test_el_trazador_por_defecto_no_acumula(tmp_path):
    raiz = _proyecto(tmp_path)
    agente = _agente(raiz)
    agente.atender(f"explora {raiz}", None)

    assert isinstance(agente.trazador, TrazadorNulo)
    assert agente.trazador.eventos == []


# --- Determinismo (VI / SC-010) -------------------------------------------


def test_dos_ejecuciones_producen_la_misma_traza_salvo_tiempos(tmp_path):
    raiz = _proyecto(tmp_path)
    pregunta = f"explora la estructura de {raiz}"

    a, b = Trazador(), Trazador()
    _agente(raiz, a).atender(pregunta, None)
    _agente(raiz, b).atender(pregunta, None)

    assert [e.parte_determinista() for e in a.eventos] == [
        e.parte_determinista() for e in b.eventos
    ]


@pytest.mark.parametrize("campo", EventoDeTraza.CAMPOS_NO_DETERMINISTAS)
def test_los_campos_temporales_estan_declarados(campo):
    """El harness de evaluación usa esta misma lista (SC-105)."""
    assert campo in EventoDeTraza(solicitud_id="s1", secuencia=1, tipo="x").como_dict()
    assert campo not in EventoDeTraza(
        solicitud_id="s1", secuencia=1, tipo="x"
    ).parte_determinista()


def test_razon_de_parada_evidencia_suficiente_es_el_caso_normal(tmp_path):
    raiz = _proyecto(tmp_path)
    trazador = Trazador()
    _agente(raiz, trazador).atender(f"explora la estructura de {raiz}", None)

    assert trazador.razon_de_parada() == EVIDENCIA_SUFICIENTE
