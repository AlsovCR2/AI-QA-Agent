# ADR-007: Traza estructurada por solicitud (T213–T216)

- Status: Accepted
- Date: 2026-08-21
- Related: `specs/002-production-readiness/spec.md` (FR-110–113),
  `src/qa_agent/agent/tracing.py`, `src/qa_agent/agent/loop.py`,
  `tests/unit/test_tracing.py`
- Principios: I (la observación no decide), VI (determinismo), VIII
  (observabilidad), X (sin condicionales de guarda repartidos), XI (secretos)

## Contexto

El agente ya tenía historial de acciones y log de texto. Ninguno de los dos
responde a las preguntas que importan cuando una respuesta sale pobre: cuánto
tardó cada herramienta, si se pidió autorización, cuánta evidencia se acumuló y
por qué se detuvo el bucle.

Esto no es un detalle de comodidad. Los fallos de un agente QA casi nunca son
excepciones — son respuestas plausibles construidas sobre poca evidencia. Una
excepción se ve en el log; una respuesta pobre no deja rastro. Sin traza, el
único síntoma es un usuario insatisfecho, y no hay forma de distinguir "el
modelo eligió mal la herramienta" de "la herramienta no encontró nada" de "se
agotó el presupuesto de pasos".

## Decisión

Un módulo `agent/tracing.py` con `EventoDeTraza` (dataclass congelada) y
`Trazador`, que acumula en memoria y opcionalmente anexa JSONL. Cuatro tipos de
evento y cinco razones de parada declaradas como constantes.

## Ruling: la traza observa, no decide

Nada en el módulo influye en selección de herramienta, autorización ni
respuesta. La comprobación no es una convención sino un invariante verificable:
desactivar la traza por completo no cambia ninguna salida del agente.

Esto es lo que separa una traza de un side channel. En cuanto un valor de la
traza retroalimenta una decisión, la traza deja de ser evidencia de lo que pasó
y pasa a ser parte de lo que pasa — y la evaluación (ADR-008), que lee la traza
para puntuar el comportamiento, estaría puntuándose a sí misma.

## Ruling: redactar al construir, no al escribir

`Trazador.emitir` redacta el `detalle` en el constructor del evento, no en
`_escribir`. Es el punto por el que pasan todos los eventos sin excepción.

Alternativa descartada: redactar en el momento de la escritura. Habría dejado
eventos sin redactar en memoria, que es precisamente de donde los lee el harness
de evaluación y de donde podrían acabar en un informe. La redacción tiene que
ocurrir antes de que el evento exista en cualquier forma consultable.

## Ruling: un fallo de traza degrada la traza, nunca la solicitud (FR-112)

`_escribir` captura `OSError`, `TypeError` y `ValueError`, desactiva la escritura
y guarda el motivo en `error_de_escritura`. No reintenta: si el destino no es
escribible, no va a serlo a mitad de la misma solicitud, y reintentar por evento
convierte un disco lleno en N fallos idénticos.

Los tres tipos capturados corresponden a las tres cosas que pueden fallar aquí —
el disco (`OSError`), un `detalle` no serializable (`TypeError`) y un valor JSON
inválido (`ValueError`). No se captura `Exception`: un fallo fuera de esa lista
es un defecto del trazador y debe verse.

## Ruling: `TrazadorNulo` en vez de `if trazador is not None`

El valor por defecto del agente es un `TrazadorNulo` que devuelve un evento
vacío. La alternativa —un `Trazador | None` comprobado en cada punto de
emisión— repartiría una guarda por cada llamada en el bucle, y basta olvidar
una para que la instrumentación quede desigual sin que ningún test lo note
(principio X).

## Ruling: qué campos no son deterministas

`momento_ms` y `duracion_ms` dependen del reloj. Se declaran en
`CAMPOS_NO_DETERMINISTAS` como constante de clase y `parte_determinista()` los
excluye, de modo que los tests y el harness de evaluación usen exactamente la
misma definición en vez de dos listas que se desincronizan (SC-010 / SC-105).

## Consecuencias

- El bucle emite un evento por paso sin que su lógica de decisión cambie.
- La razón de parada (FR-113) queda explícita y enumerada, no inferida del texto.
- Habilita ADR-008: las métricas se calculan sobre lo que el agente **hizo**.
- Coste cuando nadie la pide: una asignación de dataclass vacía por evento.
