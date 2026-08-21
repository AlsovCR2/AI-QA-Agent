"""Pruebas directas de `agent/grounding.py` (I01, extracción de loop.py).

`_afirmaciones_no_ancladas` ya se ejercita indirectamente a través de
`Agent._respuesta_react` en `test_reasoning.py`/`test_honesty.py`; este
archivo fija el contrato del módulo extraído de forma aislada, sin depender
de `Agent` ni de un backend LLM (SC-017 / FR-019, VI / SC-010).
"""

from __future__ import annotations

from qa_agent.agent.grounding import _afirmaciones_no_ancladas, _al_inicio_de_frase
from qa_agent.agent.reasoning import Observacion, PasoDePlan
from qa_agent.tools.base import EstadoResultado, ResultadoDeHerramienta


def _observacion(datos: dict) -> Observacion:
    paso = PasoDePlan(orden=1, razon="", herramienta="search", parametros={})
    resultado = ResultadoDeHerramienta(
        herramienta_id="search", estado=EstadoResultado.EXITO, datos=datos
    )
    return Observacion(paso=paso, resultado=resultado, evaluacion="")


def test_sin_observaciones_cualquier_afirmacion_no_esta_anclada():
    assert _afirmaciones_no_ancladas("Encontré 3 clases en BLL.", [])
    assert not _afirmaciones_no_ancladas("no encontré nada relevante", [])


def test_afirmacion_presente_en_evidencia_esta_anclada():
    observaciones = [_observacion({"coincidencias": ["BLL/Cliente.cs"]})]
    assert not _afirmaciones_no_ancladas(
        "Encontré Cliente en BLL.", observaciones
    )


def test_afirmacion_ausente_de_evidencia_no_esta_anclada():
    observaciones = [_observacion({"coincidencias": ["BLL/Cliente.cs"]})]
    assert _afirmaciones_no_ancladas(
        "Encontré Reservacion en la capa DAL.", observaciones
    )


def test_numero_ausente_de_evidencia_no_esta_anclado():
    observaciones = [_observacion({"total": 3})]
    assert _afirmaciones_no_ancladas("Hay 42 pruebas fallando.", observaciones)


def test_palabra_al_inicio_de_frase_no_es_afirmacion():
    observaciones = [_observacion({"coincidencias": []})]
    # "Cliente" al inicio de frase no se exige anclado (T107).
    assert not _afirmaciones_no_ancladas("Cliente. Aplicación los usa.", observaciones)


def test_al_inicio_de_frase_primer_caracter_y_tras_puntuacion():
    assert _al_inicio_de_frase("Hola", 0)
    assert _al_inicio_de_frase("Uno. Dos", 5)
    assert not _al_inicio_de_frase("Uno Dos", 4)
