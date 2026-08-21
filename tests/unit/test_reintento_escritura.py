"""Un rechazo por contenido se reintenta con el motivo delante (FR-042/043, IX).

`crear_archivo`/`editar_archivo` rechazan contenido que no compila o que degrada
la función que sustituyen, y el motivo es accionable: "se perdieron anotaciones
de tipo en: datos, return". Sin reintento ese motivo moría en la traza — el paso
se daba por fallido y el bucle seguía—, así que el modelo se enteraba de la
regla cuando ya no podía usarla.

Medido contra Gemini el 2026-08-21: con los invariantes activos y sin reintento,
0/10; el modelo conservaba firma y docstring pero seguía perdiendo los tipos y
la llamada a `_validar`.

La distinción que importa: se reintenta `INVALIDO` (contenido corregible) y NO
`ERROR` (ruta fuera del perímetro, disco, permisos). Reintentar un `ERROR` sería
insistir contra una frontera de seguridad.
"""

from __future__ import annotations

from pathlib import Path

from qa_agent.agent.loop import Agent
from qa_agent.llm.fake_llm import FakeLLM
from qa_agent.tools.allowlist import Allowlist
from qa_agent.tools.editar_archivo import EditarArchivoHerramienta
from qa_agent.tools.explore import ExploreHerramienta

_MODULO = '''"""Módulo."""

from collections.abc import Sequence

Numero = int | float


def _validar(datos: Sequence[Numero]) -> None:
    if not datos:
        raise ValueError("vacía")


def mediana(datos: Sequence[Numero]) -> float:
    """Valor central."""
    _validar(datos)
    ordenados = sorted(datos)
    return ordenados[len(ordenados) // 2]
'''

_DEGRADADA = '''def mediana(datos):
    """Valor central."""
    if not datos:
        raise ValueError("vacía")
    ordenados = sorted(datos)
    medio = len(ordenados) // 2
    if len(ordenados) % 2 == 0:
        return (ordenados[medio - 1] + ordenados[medio]) / 2
    return ordenados[medio]'''

_CORREGIDA = '''def mediana(datos: Sequence[Numero]) -> float:
    """Valor central."""
    _validar(datos)
    ordenados = sorted(datos)
    medio = len(ordenados) // 2
    if len(ordenados) % 2 == 0:
        return (ordenados[medio - 1] + ordenados[medio]) / 2
    return ordenados[medio]'''


class _BackendConCorreccion(FakeLLM):
    """Devuelve la versión degradada en el plan y la buena al reintentar."""

    def __init__(self, raiz: Path, correccion: str | None, **kwargs) -> None:
        super().__init__(
            soporta_razonamiento=True,
            plan={
                "objetivo": "corregir mediana",
                "criterio_exito": "",
                "pasos": [
                    {
                        "orden": 1,
                        "razon": "corregir la mediana",
                        "herramienta": "editar_archivo",
                        "parametros": {
                            "ruta": str(raiz),
                            "archivo_relativo": "mod.py",
                            "funciones": [
                                {"nombre": "mediana", "codigo": _DEGRADADA}
                            ],
                        },
                        "criterio_salida": "",
                    }
                ],
            },
            responder={"texto": "Hecho.", "confianza": "alta"},
            **kwargs,
        )
        self._raiz = raiz
        self._correccion = correccion
        self.motivos_recibidos: list[str] = []

    def razonar(self, estado, pendientes=None):
        self.motivos_recibidos.append(str(pendientes))
        if self._correccion is None:
            return {"concluir": True}
        return {
            "herramienta": "editar_archivo",
            "parametros": {
                "ruta": str(self._raiz),
                "archivo_relativo": "mod.py",
                "funciones": [{"nombre": "mediana", "codigo": self._correccion}],
            },
            "razon": "corregir conservando los invariantes",
        }


def _agente(raiz: Path, correccion: str | None) -> tuple[Agent, _BackendConCorreccion]:
    backend = _BackendConCorreccion(raiz, correccion)
    agente = Agent(
        backend=backend,
        herramientas=[
            EditarArchivoHerramienta([str(raiz)]),
            ExploreHerramienta([str(raiz)]),
        ],
        allowlist=Allowlist([str(raiz)]),
    )
    return agente, backend


def _proyecto(tmp_path: Path) -> Path:
    (tmp_path / "mod.py").write_text(_MODULO, encoding="utf-8")
    return tmp_path


def test_una_escritura_rechazada_se_reintenta_y_acaba_aplicandose(tmp_path):
    raiz = _proyecto(tmp_path)
    agente, _ = _agente(raiz, _CORREGIDA)

    agente.atender("corrige la mediana", True)

    contenido = (raiz / "mod.py").read_text(encoding="utf-8")
    assert "_validar(datos)" in contenido, "conserva el ayudante"
    assert "Sequence[Numero]) -> float" in contenido, "conserva los tipos"
    assert "medio - 1" in contenido, "y aplica la corrección pedida"


def test_el_motivo_del_rechazo_llega_al_modelo(tmp_path):
    """Sin el motivo, el reintento sería otra tirada a ciegas."""
    raiz = _proyecto(tmp_path)
    agente, backend = _agente(raiz, _CORREGIDA)

    agente.atender("corrige la mediana", True)

    recibido = " ".join(backend.motivos_recibidos)
    assert "anotaciones de tipo" in recibido
    assert "_validar" in recibido


def test_si_el_modelo_no_corrige_el_archivo_queda_intacto(tmp_path):
    raiz = _proyecto(tmp_path)
    agente, _ = _agente(raiz, None)

    agente.atender("corrige la mediana", True)

    assert (raiz / "mod.py").read_text(encoding="utf-8") == _MODULO


def test_el_reintento_esta_acotado(tmp_path):
    """Insistir sin fin solo gasta cuota; el fallo ya se reporta con honestidad."""
    raiz = _proyecto(tmp_path)
    agente, backend = _agente(raiz, _DEGRADADA)  # nunca corrige

    agente.atender("corrige la mediana", True)

    assert len(backend.motivos_recibidos) <= Agent._MAX_REINTENTOS_ESCRITURA + 1
    assert (raiz / "mod.py").read_text(encoding="utf-8") == _MODULO
