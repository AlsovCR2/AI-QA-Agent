# ADR-006: Metadatos de ejecución y taxonomía de causas (T206–T209)

- Status: Accepted
- Date: 2026-08-21
- Related: `specs/002-production-readiness/spec.md` (FR-105–109),
  `src/qa_agent/tools/ejecucion.py`, `docs/proposals/I06-runner-metadata.md`
- Principios: VI (determinismo), VII (contratos), IX (errores), XI (credenciales)

## Contexto

`run_tests` y `analyze_coverage` emitían `estado_global = "no_ejecutado"` en
tres situaciones distintas e indistinguibles: el proyecto no tiene pruebas, el
runner no está instalado, o la colección falló. Para un agente de QA es el modo
de fallo más frecuente y el menos diagnosticable — y la auditoría del
2026-08-21 encontró un caso real: en macOS el intérprete `python` no existe, la
ejecución fallaba con `FileNotFoundError` y el usuario solo veía "no ejecutado".

## Decisión

Un módulo compartido (`tools/ejecucion.py`) que:

1. ejecuta el subproceso de forma portable y siempre con `shell=False`;
2. devuelve `MetadatosDeEjecucion` (`exit_code`, `runner_detectado`,
   `duracion_ms`, `stdout_tail`, `stderr_tail`, `causa_no_ejecutado`);
3. define la taxonomía de causas como constantes de módulo.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Ampliar cada herramienta por separado | Reproduce la duplicación que ya existía y garantiza que las dos taxonomías diverjan. |
| Excepciones tipadas en vez de un campo de causa | El contrato de herramienta es "devolver un resultado, nunca lanzar" (IX). Una excepción obligaría a cada llamador a traducirla de vuelta. |
| `causa_no_ejecutado` como `enum` de Python | El valor viaja dentro de un `dict` que se serializa a JSON y se valida contra un esquema; un `str` con `enum` declarado en el esquema es el mismo contrato sin la conversión. |

## Ruling: campos aditivos, no `required`

Los seis campos nuevos se añaden a `properties` pero **no** a `required`.

Motivo: `required` invalidaría los resultados que ya construyen consumidores
existentes y los 92 casos de la suite de compatibilidad de ADR-002 (FR-109).
Que la herramienta los emita SIEMPRE se garantiza con un test explícito
(`test_run_tests_siempre_emite_los_metadatos`), que es un contrato más fuerte
que el esquema para este caso concreto: comprueba el comportamiento de todos
los caminos de retorno, no la forma de un diccionario de ejemplo.

## Ruling: los rechazos previos a la ejecución sí emiten causa

Antes, un comando fuera de allowlist devolvía `datos = {}`. Ahora devuelve solo
los metadatos, sin ningún contador de pruebas. Es un cambio de contrato
deliberado: el consumidor obtiene un motivo legible por máquina
(`comando_no_permitido`) en vez de tener que interpretar el texto del error, y
sigue siendo imposible confundir la respuesta con un resultado real porque los
campos de resultado no están presentes. Tres tests se actualizaron en
consecuencia.

## Consecuencias

- `run_tests`/`analyze_coverage` dejan de duplicar el bloque de subproceso.
- La cola de salida pasa por el `Redactor` antes de salir del módulo (XI): es
  el único punto por el que puede escapar contenido del proyecto.
- Habilita la observabilidad (ADR-007) y la evaluación (ADR-008), que necesitan
  una señal de éxito fiable.
