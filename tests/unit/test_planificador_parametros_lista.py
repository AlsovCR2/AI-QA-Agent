"""El planificador no puede caerse por la forma de un parámetro (IX).

`planificar` deduplica pasos idénticos con una clave construida a partir de los
parámetros. La clave era `tuple(sorted(parametros.items()))`, que revienta con
`TypeError: unhashable type: 'list'` en cuanto un parámetro es una lista.

Nadie lo había visto porque ninguna herramienta recibía listas. Al añadir
`reemplazos` a `editar_archivo` —una lista de objetos— la excepción tumbaba la
planificación ENTERA: la solicitud terminaba con cero pasos y el agente
respondía con texto en vez de usar la herramienta, sin ningún error visible.

Es un fallo de robustez, no de esa herramienta concreta: cualquier herramienta
futura con un parámetro de tipo array habría reproducido lo mismo.
"""

from __future__ import annotations

import json

import pytest

from qa_agent.llm.openai_compatible_backend import OpenAICompatibleBackend


class _ClienteFalso:
    """Devuelve un plan fijo; no toca la red."""

    def __init__(self, plan: dict) -> None:
        self._plan = plan

    class _Respuesta:
        def __init__(self, contenido: str) -> None:
            self.choices = [
                type(
                    "C", (), {"message": type("M", (), {"content": contenido})()}
                )()
            ]

    @property
    def chat(self):
        cliente = self

        class _Completions:
            def create(self, **_kwargs):
                return _ClienteFalso._Respuesta(
                    json.dumps(cliente._plan, ensure_ascii=False)
                )

        return type("Chat", (), {"completions": _Completions()})()


class _HerramientaConLista:
    id = "editar_archivo"
    nombre = "editar_archivo"
    descripcion = "Edita un archivo."
    esquema_entrada = {
        "type": "object",
        "properties": {"reemplazos": {"type": "array"}},
    }


class _Intencion:
    texto = "edita el archivo x.py"
    contexto = ""


def _backend(plan: dict) -> OpenAICompatibleBackend:
    backend = OpenAICompatibleBackend.__new__(OpenAICompatibleBackend)
    backend._client = _ClienteFalso(plan)
    backend._model = "falso"
    backend._temperatura = 0
    backend.soporta_razonamiento = True
    return backend


def _plan_con(parametros: dict, veces: int = 1) -> dict:
    return {
        "objetivo": "editar",
        "criterio_exito": "",
        "pasos": [
            {
                "orden": i + 1,
                "razon": "cambiar la función",
                "herramienta": "editar_archivo",
                "parametros": parametros,
                "criterio_salida": "",
            }
            for i in range(veces)
        ],
    }


def test_un_parametro_lista_no_tumba_la_planificacion():
    """El caso real: `reemplazos` es una lista de objetos."""
    parametros = {
        "ruta": ".",
        "archivo_relativo": "mod.py",
        "reemplazos": [{"buscar": "return 1", "reemplazar": "return 2"}],
    }

    plan = _backend(_plan_con(parametros)).planificar(
        _Intencion(), [_HerramientaConLista()], {}
    )

    assert len(plan.pasos) == 1
    assert plan.pasos[0].parametros["reemplazos"][0]["buscar"] == "return 1"


@pytest.mark.parametrize(
    "valor",
    [
        [1, 2, 3],
        [{"a": 1}],
        {"anidado": {"profundo": [1]}},
        [[1], [2]],
    ],
)
def test_cualquier_parametro_no_hashable_se_tolera(valor):
    plan = _backend(_plan_con({"x": valor})).planificar(
        _Intencion(), [_HerramientaConLista()], {}
    )

    assert len(plan.pasos) == 1


def test_la_deduplicacion_sigue_funcionando_con_listas():
    """Arreglar el crash no puede desactivar el dedup."""
    parametros = {"reemplazos": [{"buscar": "a", "reemplazar": "b"}]}

    plan = _backend(_plan_con(parametros, veces=3)).planificar(
        _Intencion(), [_HerramientaConLista()], {}
    )

    assert len(plan.pasos) == 1


def test_pasos_con_listas_distintas_no_se_deduplican():
    backend = _backend(
        {
            "objetivo": "editar",
            "criterio_exito": "",
            "pasos": [
                {
                    "orden": 1,
                    "razon": "primero",
                    "herramienta": "editar_archivo",
                    "parametros": {"reemplazos": [{"buscar": "a", "reemplazar": "b"}]},
                    "criterio_salida": "",
                },
                {
                    "orden": 2,
                    "razon": "segundo",
                    "herramienta": "editar_archivo",
                    "parametros": {"reemplazos": [{"buscar": "c", "reemplazar": "d"}]},
                    "criterio_salida": "",
                },
            ],
        }
    )

    plan = backend.planificar(_Intencion(), [_HerramientaConLista()], {})

    assert len(plan.pasos) == 2
