"""Una escritura que no compila no llega al disco (FR-042/043, IX).

`crear_archivo` y `editar_archivo` reciben el archivo COMPLETO, así que el
modelo debe reproducirlo entero. Observado tres veces seguidas contra Gemini el
2026-08-21 sobre un módulo de 50 líneas: devolvía `""Módulo.""` —dos comillas
en vez de tres— y sobrescribía un módulo que funcionaba. La suite del proyecto
dejaba de recolectar entera.

El caso que da nombre a estos tests es `test_el_caso_real_de_las_comillas`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qa_agent.tools.base import EstadoResultado
from qa_agent.tools.crear_archivo import CrearArchivoHerramienta
from qa_agent.tools.editar_archivo import EditarArchivoHerramienta
from qa_agent.tools.validacion_sintaxis import error_de_sintaxis

_MODULO_BUENO = '"""Módulo."""\n\n\ndef f() -> int:\n    return 1\n'
#: Exactamente lo que escribió el modelo: docstring con dos comillas.
_MODULO_ROTO = '""Módulo de cálculos estadísticos.""\n\ndef f():\n    return 1\n'


def _proyecto(tmp_path: Path) -> Path:
    (tmp_path / "paquete").mkdir()
    (tmp_path / "paquete" / "mod.py").write_text(_MODULO_BUENO, encoding="utf-8")
    return tmp_path


# --- La función pura -------------------------------------------------------


def test_el_caso_real_de_las_comillas():
    assert error_de_sintaxis("mod.py", _MODULO_ROTO)


def test_python_valido_no_reporta_nada():
    assert error_de_sintaxis("mod.py", _MODULO_BUENO) == ""


@pytest.mark.parametrize(
    "contenido",
    [
        "def f(:\n    pass\n",
        "if True\n    pass\n",
        "return 1\n",
        "x = (1, 2\n",
    ],
)
def test_python_roto_se_detecta(contenido):
    assert error_de_sintaxis("mod.py", contenido)


def test_el_mensaje_cita_la_linea_infractora():
    """El modelo corrige mejor si ve el texto exacto que falló."""
    mensaje = error_de_sintaxis("mod.py", "def f(:\n    pass\n")

    assert "línea 1" in mensaje
    assert "No se escribió nada" in mensaje


def test_json_invalido_se_detecta():
    assert error_de_sintaxis("datos.json", '{"a": 1,}')


def test_json_valido_pasa():
    assert error_de_sintaxis("datos.json", '{"a": [1, 2]}') == ""


@pytest.mark.parametrize("nombre", ["notas.md", "LEEME.txt", "config.yaml", "sin_extension"])
def test_los_formatos_que_no_se_saben_validar_no_se_bloquean(nombre):
    """Ante la duda, escribir: el valor por defecto es no estorbar."""
    assert error_de_sintaxis(nombre, "esto {no es} [python] ni json") == ""


def test_la_extension_no_distingue_mayusculas():
    assert error_de_sintaxis("MOD.PY", _MODULO_ROTO)


# --- editar_archivo: el archivo bueno sobrevive ----------------------------


def test_editar_con_python_roto_no_toca_el_archivo(tmp_path):
    raiz = _proyecto(tmp_path)
    herramienta = EditarArchivoHerramienta([str(raiz)])

    resultado = herramienta.ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "paquete/mod.py",
            "contenido": _MODULO_ROTO,
        }
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert (raiz / "paquete" / "mod.py").read_text(encoding="utf-8") == _MODULO_BUENO


def test_editar_con_python_roto_no_deja_respaldo_huerfano(tmp_path):
    """No se respalda lo que no se va a modificar."""
    raiz = _proyecto(tmp_path)

    EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "paquete/mod.py",
            "contenido": _MODULO_ROTO,
        }
    )

    assert not (raiz / ".qa-backup").exists()


def test_editar_con_python_valido_sigue_funcionando(tmp_path):
    """La validación no puede estorbar a una edición legítima."""
    raiz = _proyecto(tmp_path)
    nuevo = '"""Módulo."""\n\n\ndef f() -> int:\n    return 2\n'

    resultado = EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {"ruta": str(raiz), "archivo_relativo": "paquete/mod.py", "contenido": nuevo}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert (raiz / "paquete" / "mod.py").read_text(encoding="utf-8") == nuevo


def test_editar_un_markdown_con_sintaxis_rara_sigue_permitido(tmp_path):
    raiz = _proyecto(tmp_path)
    (raiz / "LEEME.md").write_text("original\n", encoding="utf-8")

    resultado = EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "LEEME.md",
            "contenido": "# Título\n\ndef f(: esto no es python\n",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO


# --- crear_archivo ---------------------------------------------------------


def test_crear_con_python_roto_no_escribe_el_archivo(tmp_path):
    raiz = _proyecto(tmp_path)

    resultado = CrearArchivoHerramienta([str(raiz)]).ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "tests/test_nuevo.py",
            "contenido": "def:\n    test_algo()\n",
        }
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert resultado.datos["creado"] is False
    assert not (raiz / "tests" / "test_nuevo.py").exists()


def test_crear_con_python_valido_sigue_funcionando(tmp_path):
    raiz = _proyecto(tmp_path)

    resultado = CrearArchivoHerramienta([str(raiz)]).ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "tests/test_nuevo.py",
            "contenido": "def test_algo():\n    assert True\n",
        }
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert (raiz / "tests" / "test_nuevo.py").exists()


# --- Edición por reemplazo exacto ------------------------------------------


def test_reemplazo_acotado_no_toca_el_resto_del_archivo(tmp_path):
    """El punto de `reemplazos`: no obliga a reproducir lo que no cambia."""
    raiz = _proyecto(tmp_path)

    resultado = EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "paquete/mod.py",
            "reemplazos": [{"buscar": "return 1", "reemplazar": "return 2"}],
        }
    )

    contenido = (raiz / "paquete" / "mod.py").read_text(encoding="utf-8")
    assert resultado.estado == EstadoResultado.EXITO
    assert "return 2" in contenido
    assert contenido.startswith('"""Módulo."""')


def test_reemplazo_que_no_aparece_se_rechaza(tmp_path):
    """Cero coincidencias = el modelo citó de memoria, no copió."""
    raiz = _proyecto(tmp_path)

    resultado = EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "paquete/mod.py",
            "reemplazos": [{"buscar": "return 99", "reemplazar": "return 2"}],
        }
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert (raiz / "paquete" / "mod.py").read_text(encoding="utf-8") == _MODULO_BUENO


def test_reemplazo_ambiguo_se_rechaza(tmp_path):
    """Varias coincidencias: adivinar cuál sería peor que fallar."""
    raiz = tmp_path
    (raiz / "m.py").write_text("x = 1\ny = 1\n", encoding="utf-8")

    resultado = EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "m.py",
            "reemplazos": [{"buscar": "1", "reemplazar": "2"}],
        }
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert "ambiguo" in resultado.error
    assert (raiz / "m.py").read_text(encoding="utf-8") == "x = 1\ny = 1\n"


def test_un_reemplazo_que_rompe_la_sintaxis_se_rechaza(tmp_path):
    """La validación se aplica al RESULTADO, no solo a `contenido`."""
    raiz = _proyecto(tmp_path)

    resultado = EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "paquete/mod.py",
            "reemplazos": [{"buscar": "def f() -> int:", "reemplazar": "def f(:"}],
        }
    )

    assert resultado.estado == EstadoResultado.INVALIDO
    assert (raiz / "paquete" / "mod.py").read_text(encoding="utf-8") == _MODULO_BUENO


def test_varios_reemplazos_se_aplican_en_orden(tmp_path):
    raiz = tmp_path
    (raiz / "m.py").write_text("a = 1\nb = 2\n", encoding="utf-8")

    EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {
            "ruta": str(raiz),
            "archivo_relativo": "m.py",
            "reemplazos": [
                {"buscar": "a = 1", "reemplazar": "a = 10"},
                {"buscar": "b = 2", "reemplazar": "b = 20"},
            ],
        }
    )

    assert (raiz / "m.py").read_text(encoding="utf-8") == "a = 10\nb = 20\n"


def test_sin_contenido_ni_reemplazos_se_rechaza(tmp_path):
    raiz = _proyecto(tmp_path)

    resultado = EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {"ruta": str(raiz), "archivo_relativo": "paquete/mod.py"}
    )

    assert resultado.estado == EstadoResultado.INVALIDO


def test_contenido_completo_sigue_funcionando(tmp_path):
    """`reemplazos` se añade sin romper el camino existente."""
    raiz = _proyecto(tmp_path)
    nuevo = '"""Otro."""\n\n\ndef g() -> int:\n    return 3\n'

    resultado = EditarArchivoHerramienta([str(raiz)]).ejecutar(
        {"ruta": str(raiz), "archivo_relativo": "paquete/mod.py", "contenido": nuevo}
    )

    assert resultado.estado == EstadoResultado.EXITO
    assert (raiz / "paquete" / "mod.py").read_text(encoding="utf-8") == nuevo
