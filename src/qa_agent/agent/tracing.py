"""Traza estructurada por solicitud (T213 / FR-110–113, principio VIII).

El agente ya dejaba un historial visible de acciones y un log de texto, pero
ninguna de las dos cosas responde a las preguntas que importan cuando una
respuesta sale incompleta: cuánto tardó cada herramienta, si se pidió
autorización, cuánta evidencia se acumuló, y por qué se detuvo el bucle. Los
fallos de un agente QA rara vez son excepciones — son respuestas pobres, y sin
traza son invisibles.

Tres reglas de diseño, todas consecuencia de la constitución:

1. **La traza observa, no decide** (principio I). Nada en este módulo influye
   en la selección de herramienta, la autorización ni la respuesta. Se puede
   desactivar por completo y el comportamiento del agente no cambia.
2. **Redactar antes de persistir** (principio XI / FR-111). Un evento se
   redacta al construirse, no al escribirse: así ningún camino puede saltarse
   la redacción escribiendo el evento por su cuenta.
3. **La observabilidad nunca rompe la función principal** (FR-112). Un disco
   lleno, un permiso denegado o una ruta inválida degradan la traza a nada;
   jamás abortan la solicitud del usuario.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qa_agent.security.redactor import Redactor

# --- Tipos de evento -------------------------------------------------------

#: Se recibió una solicitud del usuario.
SOLICITUD_INICIADA = "solicitud_iniciada"
#: Se ejecutó (o se intentó ejecutar) una herramienta.
PASO_EJECUTADO = "paso_ejecutado"
#: Se resolvió una decisión de autorización (concedida, denegada, pendiente).
AUTORIZACION = "autorizacion"
#: El bucle terminó; incluye la razón de parada.
SOLICITUD_TERMINADA = "solicitud_terminada"


# --- Razones de parada (FR-113) -------------------------------------------

#: La evidencia acumulada satisface la intención.
EVIDENCIA_SUFICIENTE = "evidencia_suficiente"
#: Se agotó el presupuesto de pasos antes de concluir.
PRESUPUESTO_AGOTADO = "presupuesto_agotado"
#: Ninguna herramienta del catálogo atiende la solicitud.
SIN_HERRAMIENTA = "sin_herramienta"
#: La ejecución terminó por un error.
ERROR = "error"
#: Se detuvo esperando una decisión humana.
PENDIENTE_AUTORIZACION = "pendiente_autorizacion"

RAZONES_DE_PARADA: tuple[str, ...] = (
    EVIDENCIA_SUFICIENTE,
    PRESUPUESTO_AGOTADO,
    SIN_HERRAMIENTA,
    ERROR,
    PENDIENTE_AUTORIZACION,
)


@dataclass(frozen=True)
class EventoDeTraza:
    """Un hecho observable de una solicitud.

    `solicitud_id` correlaciona todos los eventos de una misma solicitud
    (FR-110) y `secuencia` los ordena dentro de ella. `momento` es un epoch en
    milisegundos: junto con `duracion_ms` son los dos únicos campos no
    deterministas, y por eso las comparaciones de determinismo los excluyen
    explícitamente (VI / SC-010).
    """

    solicitud_id: str
    secuencia: int
    tipo: str
    momento_ms: int = 0
    herramienta: str = ""
    estado: str = ""
    autorizacion: str = ""
    duracion_ms: int = 0
    razon_parada: str = ""
    detalle: dict[str, Any] = field(default_factory=dict)

    #: Campos que dependen del reloj y por tanto no son comparables entre
    #: ejecuciones. Expuesto como constante para que los tests y el harness de
    #: evaluación usen exactamente la misma definición (SC-105).
    CAMPOS_NO_DETERMINISTAS = ("momento_ms", "duracion_ms")

    def como_dict(self) -> dict[str, Any]:
        return {
            "solicitud_id": self.solicitud_id,
            "secuencia": self.secuencia,
            "tipo": self.tipo,
            "momento_ms": self.momento_ms,
            "herramienta": self.herramienta,
            "estado": self.estado,
            "autorizacion": self.autorizacion,
            "duracion_ms": self.duracion_ms,
            "razon_parada": self.razon_parada,
            "detalle": self.detalle,
        }

    def parte_determinista(self) -> dict[str, Any]:
        """El evento sin sus campos dependientes del reloj."""
        return {
            k: v
            for k, v in self.como_dict().items()
            if k not in self.CAMPOS_NO_DETERMINISTAS
        }


class Trazador:
    """Acumula eventos de una solicitud y, opcionalmente, los escribe en JSONL.

    Sin `destino` funciona igual pero solo en memoria: útil para que el harness
    de evaluación lea la traza sin tocar el disco.
    """

    def __init__(
        self,
        destino: str | Path | None = None,
        redactor: Redactor | None = None,
    ) -> None:
        self._destino = Path(destino) if destino else None
        self._redactor = redactor or Redactor()
        self._eventos: list[EventoDeTraza] = []
        self._secuencia = 0
        #: Se registra el primer fallo de escritura para poder informarlo sin
        #: interrumpir la solicitud (FR-112). No se reintenta: si el destino no
        #: es escribible, no va a serlo a mitad de la misma solicitud.
        self.error_de_escritura: str = ""
        self._escritura_desactivada = False

    @property
    def eventos(self) -> list[EventoDeTraza]:
        """Eventos acumulados, en orden de emisión."""
        return list(self._eventos)

    @property
    def activo(self) -> bool:
        """True si la traza se está persistiendo a disco."""
        return self._destino is not None and not self._escritura_desactivada

    def emitir(
        self,
        solicitud_id: str,
        tipo: str,
        *,
        herramienta: str = "",
        estado: str = "",
        autorizacion: str = "",
        duracion_ms: int = 0,
        razon_parada: str = "",
        detalle: dict[str, Any] | None = None,
    ) -> EventoDeTraza:
        """Construye, redacta, acumula y (si procede) persiste un evento."""
        self._secuencia += 1
        evento = EventoDeTraza(
            solicitud_id=solicitud_id,
            secuencia=self._secuencia,
            tipo=tipo,
            momento_ms=int(time.time() * 1000),
            herramienta=herramienta,
            estado=estado,
            autorizacion=autorizacion,
            duracion_ms=duracion_ms,
            razon_parada=razon_parada,
            # La redacción ocurre AQUÍ, en el único punto por el que pasan
            # todos los eventos, y no en cada llamador (FR-111 / XI).
            detalle=self._redactor.redactar(dict(detalle or {})),
        )
        self._eventos.append(evento)
        self._escribir(evento)
        return evento

    def _escribir(self, evento: EventoDeTraza) -> None:
        """Anexa el evento como una línea JSON. Nunca lanza (FR-112)."""
        if self._destino is None or self._escritura_desactivada:
            return
        try:
            self._destino.parent.mkdir(parents=True, exist_ok=True)
            with self._destino.open("a", encoding="utf-8") as archivo:
                archivo.write(json.dumps(evento.como_dict(), ensure_ascii=False))
                archivo.write("\n")
        except (OSError, TypeError, ValueError) as error:
            # Un destino no escribible, un disco lleno o un detalle no
            # serializable degradan la traza — nunca la solicitud. Se desactiva
            # la escritura para no repetir el fallo en cada evento posterior.
            self._escritura_desactivada = True
            self.error_de_escritura = str(error)

    # -- Consultas usadas por el harness de evaluación ---------------------

    def herramientas_ejecutadas(self) -> list[str]:
        """Ids de herramienta que llegaron a ejecutarse con éxito, en orden."""
        return [
            e.herramienta
            for e in self._eventos
            if e.tipo == PASO_EJECUTADO and e.estado == "exito" and e.herramienta
        ]

    def pidio_autorizacion(self) -> bool:
        """True si en algún momento se solicitó una decisión humana."""
        return any(e.tipo == AUTORIZACION for e in self._eventos)

    def razon_de_parada(self) -> str:
        """Razón de parada del último cierre de solicitud, o cadena vacía."""
        for evento in reversed(self._eventos):
            if evento.tipo == SOLICITUD_TERMINADA:
                return evento.razon_parada
        return ""

    def pasos_ejecutados(self) -> int:
        return sum(1 for e in self._eventos if e.tipo == PASO_EJECUTADO)


class TrazadorNulo(Trazador):
    """Trazador que no acumula ni escribe nada.

    Es el valor por defecto del agente: la instrumentación tiene coste cero
    cuando nadie la pidió, y ningún camino del bucle necesita comprobar si hay
    trazador antes de emitir (principio X: sin condicionales de guarda
    repartidos por el código).
    """

    def __init__(self) -> None:
        super().__init__(destino=None)

    def emitir(self, solicitud_id: str, tipo: str, **kwargs: Any) -> EventoDeTraza:
        return EventoDeTraza(solicitud_id=solicitud_id, secuencia=0, tipo=tipo)
