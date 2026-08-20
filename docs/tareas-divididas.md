# Tareas divididas para seis personas

## Propósito y alcance

Este documento distribuye los ítems I01–I16 de
`docs/improvements/qa-agent-improvement-backlog.md` entre seis responsables.
Es una guía de coordinación derivada: no modifica la Constitución, el Spec, el
Plan, los contratos ni `tasks.md`, y tampoco autoriza por sí sola la
implementación de una mejora.

La asignación busca que las seis personas puedan iniciar trabajo útil en
paralelo sin editar las mismas áreas. No todos los ítems pueden implementarse
simultáneamente: los ítems post-MVP y las funcionalidades futuras deben pasar
primero por su aprobación de producto y por los cambios SDD indicados en el
backlog.

## Reglas de ejecución

1. Cada ítem conserva su identificador, alcance y clasificación del backlog.
2. Antes de implementar, cada responsable debe confirmar la aprobación exigida
   por las columnas **Spec** y **Plan/ADR** de la matriz de dependencias.
3. Las limpiezas de deuda técnica deben conservar el comportamiento y los
   contratos públicos existentes.
4. Cada ítem debe desarrollarse en un cambio pequeño e independiente, con sus
   propias pruebas y revisión. La asignación a una persona no implica agrupar
   todos sus ítems en un solo commit o pull request.
5. Ningún trabajo puede debilitar la autorización, la redacción previa al LLM,
   la clasificación de evidencia ni la limitación del MVP a repositorios de
   confianza.
6. I15 no puede producir evidencia verificada ni controlar el veredicto. I16 es
   una evaluación diferida, no una migración aprobada.

## Mapa de dependencias

| Ítem | Responsable | Puede iniciar sin otro ítem | Dependencia previa | Puerta SDD |
|---|---:|---|---|---|
| I01 | 1 | Sí, con plan aprobado | Coordinar primero la extracción de I02 | Plan/ADR |
| I02 | 1 | Sí | Ninguna | Plan/ADR si cambia semántica |
| I03 | 2 | Sí | Ninguna | Plan/ADR |
| I04 | 3 | Sí | Ninguna | Plan/ADR |
| I05 | 3 | Sí | Ninguna; integrar en CI después de I04 | Plan/ADR |
| I06 | 3 | Solo diseño | Ninguna para diseñar; contrato aprobado para implementar | Spec + Plan/ADR |
| I07 | 4 | Sí | Ninguna | Plan/ADR según impacto |
| I08 | 5 | Sí | Casos concretos de secretos y falsos positivos | Plan/ADR según impacto |
| I09 | 5 | Solo diseño | Puede consumir metadatos aprobados de I06 | Spec según alcance + Plan/ADR |
| I10 | 2 | Solo diseño | Ninguna para diseñar | Spec + Plan/ADR |
| I11 | 4 | Solo diseño | Conviene estabilizar I07 primero | Spec + Plan/ADR |
| I12 | 5 | Solo diseño | Contrato de procedencia aprobado | Spec + Plan/ADR |
| I13 | 4 | Solo diseño | Interfaces de descubrimiento de I11 | Spec + Plan/ADR |
| I14 | 6 | Solo diseño | `qa-agent eval` depende del diseño de I10 | Spec + Plan/ADR |
| I15 | 6 | Solo evaluación | Criterios de I10 y procedencia de I12 | Spec + Plan/ADR |
| I16 | 6 | No se implementa ahora | Métricas de I10 y dolor de orquestación medido | Spec + Plan/ADR |

## Primera oleada: seis frentes independientes

Los siguientes entregables pueden prepararse simultáneamente. La palabra
“implementar” presupone que la aprobación SDD indicada en el backlog ya fue
obtenida.

| Persona | Frente inicial | Entregable independiente |
|---:|---|---|
| 1 | I02 y primer corte de I01 | Mapa de responsabilidades de `loop.py` y extracción conservadora de reglas de intención, con pruebas de paridad |
| 2 | I03 | Decisión del validador y suite de compatibilidad para todos los esquemas utilizados actualmente |
| 3 | I04 e I05 | CI base con las verificaciones existentes y propuesta separada de herramientas de calidad |
| 4 | I07 | Política central de exclusiones con pruebas de paridad para descubrimiento y búsqueda |
| 5 | I08 | Ampliación basada en casos de la política de redacción, con pruebas de secretos y falsos positivos |
| 6 | I14, I15 e I16, solo diseño/evaluación | Propuestas de producto separadas y criterios medibles; no se agrega código ni dependencias todavía |

## Persona 1 — Núcleo y enrutamiento

**Ítems asignados:** I01 e I02.

**Objetivo:** reducir el tamaño y las responsabilidades mezcladas de
`agent/loop.py` sin cambiar la conducta observable del agente.

**Orden interno:**

1. Inventariar frases, expresiones regulares y reglas de intención de
   `agent/loop.py` y `agent/router.py`.
2. Resolver I02 mediante una política o tabla enfocada, manteniendo exactamente
   la cobertura actual.
3. Definir un ADR para I01 con extracciones incrementales y límites claros.
4. Extraer una responsabilidad de `loop.py` por cambio: planificación,
   autorización/ejecución, normalización de observaciones o política de
   respuesta.
5. Ejecutar la suite completa después de cada extracción.

**Archivos probables:**

- `src/qa_agent/agent/loop.py`
- `src/qa_agent/agent/router.py`
- nuevos módulos enfocados bajo `src/qa_agent/agent/`, solo si los aprueba el ADR
- `tests/unit/test_router.py`
- pruebas de intención, profundidad, razonamiento y ReAct bajo `tests/unit/`

**Criterios de aceptación:**

- Las entradas existentes producen la misma selección de herramienta, plan,
  autorización y respuesta.
- No cambia ningún contrato público ni requisito SDD.
- Cada extracción reduce una responsabilidad concreta de `loop.py` y tiene una
  prueba de regresión asociada.
- La suite completa permanece en verde.

**No depende de:** CI nueva, metadatos de runner, procedencia de evidencia ni
frameworks externos.

**Zona reservada:** durante su oleada, esta persona es la propietaria de
`agent/loop.py`. Las personas 4 y 5 deben entregar interfaces o cambios en sus
módulos y posponer el cableado en `loop.py` a una ventana de integración.

## Persona 2 — Validación y evaluación reproducible

**Ítems asignados:** I03 e I10.

**Objetivo:** fortalecer la validación determinista actual y diseñar, por
separado, una futura evaluación reproducible de calidad.

**Orden interno:**

1. Enumerar todos los esquemas realmente usados por las herramientas.
2. Crear pruebas de compatibilidad para valores válidos, inválidos, anidados y
   errores legibles.
3. Comparar mantener el validador parcial, usar Pydantic o adoptar un validador
   JSON Schema; registrar la decisión en un ADR.
4. Implementar I03 únicamente si la decisión fue aprobada y conserva los
   contratos actuales.
5. Para I10, producir primero una propuesta de Spec con corpus, golden files,
   métricas, tolerancias y control de variabilidad; no construir el harness sin
   esa aprobación.

**Archivos probables:**

- `src/qa_agent/tools/base.py`
- `tests/contract/test_tool_contracts.py`
- pruebas unitarias de herramientas
- para I10, nuevos artefactos de diseño y, solo después de aprobación, un área
  de fixtures/evaluación separada de las pruebas funcionales

**Criterios de aceptación:**

- I03 valida todos los esquemas usados actualmente sin ampliar silenciosamente
  el contrato.
- Los mensajes de error son deterministas y están probados.
- I10 define cómo comparar resultados sin convertir variaciones del proveedor
  en falsos fallos.
- El diseño de I10 expone una interfaz consumible por I14 e I15.

**No depende de:** la modularización de `loop.py` ni la política de exclusiones.

**Entrega a otros:** la definición aprobada de I10 habilita `qa-agent eval` en
I14 y proporciona métricas para valorar I15 e I16.

## Persona 3 — Plataforma de ingeniería y ejecución

**Ítems asignados:** I04, I05 e I06.

**Objetivo:** automatizar la verificación existente, acordar herramientas de
calidad y diseñar metadatos deterministas del runner.

**Orden interno:**

1. Implementar I04 con el baseline ya verificado: suite completa y
   `python -m pip check`.
2. Proponer para I05 versiones, reglas y política de adopción de Ruff, análisis
   de tipos y cobertura.
3. Incorporar a CI solamente las herramientas de I05 que hayan sido aprobadas;
   no imponer umbrales arbitrarios.
4. Diseñar I06 como cambio versionado de contrato: campos, límites de salida,
   estados y compatibilidad.
5. Implementar I06 solo después de aprobar Spec, contrato y Plan/ADR.

**Archivos probables:**

- `.github/workflows/`
- `pyproject.toml`
- archivos de dependencias/desarrollo existentes
- `src/qa_agent/tools/run_tests.py`
- `src/qa_agent/tools/analyze_coverage.py`
- `specs/001-core-ai-qa-agent/contracts/tool-contracts.md`, solo tras aprobación
- pruebas unitarias e integración de runner

**Criterios de aceptación:**

- CI reproduce comandos locales documentados y distingue PASS, FAIL, SKIPPED y
  UNAVAILABLE cuando corresponda.
- I05 no introduce miles de cambios de formato mezclados con lógica.
- I06 conserva los estados corregidos por T130 y prueba límites para
  `stdout`/`stderr`, código de salida, runner y duración que finalmente apruebe
  el contrato.

**No depende de:** I01, I02, I07 o I08.

**Entrega a otros:** I06 puede alimentar I09, pero I09 no debe acoplarse a
campos que todavía no estén aprobados.

## Persona 4 — Descubrimiento y ecosistemas

**Ítems asignados:** I07, I11 e I13.

**Objetivo:** unificar las exclusiones antes de profundizar el descubrimiento
semántico o agregar nuevos ecosistemas.

**Orden interno:**

1. Inventariar exclusiones duplicadas en `allowlist.py`, `explore.py`,
   `generate_test_cases.py` y `loop.py`.
2. Implementar I07 con fixtures que demuestren paridad de rutas incluidas y
   excluidas.
3. Diseñar I11 por adaptadores de lenguaje, con fallback explícito cuando no
   exista AST, LSP o índice estructurado.
4. Implementar I11 únicamente después de aprobar su Spec y Plan/ADR.
5. Seleccionar un solo ecosistema para el primer incremento de I13 y definir
   comandos permitidos, parsers, fixtures y límites de confianza antes de
   programarlo.

**Archivos probables:**

- `src/qa_agent/tools/allowlist.py`
- `src/qa_agent/tools/explore.py`
- `src/qa_agent/tools/locate.py`
- `src/qa_agent/tools/search.py`
- `src/qa_agent/tools/generate_test_cases.py`
- detectores de lenguaje/runner que se aprueben
- fixtures y pruebas de descubrimiento

**Criterios de aceptación:**

- I07 ofrece una fuente única sin cambiar silenciosamente resultados actuales.
- I11 declara precisión, fallback y errores por lenguaje.
- Cada incremento de I13 agrega un ecosistema completo y probado; no una lista
  de extensiones sin ejecución ni parser compatibles.

**Dependencias:** I11 debe partir de la política estable de I07; I13 debe partir
de las interfaces aprobadas de I11.

**Zona compartida:** cualquier cambio requerido en `agent/loop.py` se integra
después de la oleada de la persona 1.

## Persona 5 — Seguridad, observabilidad y procedencia

**Ítems asignados:** I08, I09 e I12.

**Objetivo:** ampliar de forma verificable la protección de secretos y diseñar
telemetría/evidencia estructurada sin crear persistencia no aprobada.

**Orden interno:**

1. Reunir ejemplos concretos para I08: tokens de proveedores, asignaciones de
   contraseña/secreto, claves privadas y casos que no deben redactarse.
2. Implementar patrones uno por uno con pruebas de detección y falsos positivos.
3. Diseñar I09 con clasificación de datos, redacción, retención y apagado; no
   asumir almacenamiento persistente.
4. Diseñar I12 como contrato de procedencia acotado: tipo de fuente, ruta,
   rango, hash y extracto limitado.
5. Implementar I09 o I12 solo después de aprobar sus requisitos y contratos.

**Archivos probables:**

- `src/qa_agent/security/redactor.py`
- `src/qa_agent/logging_config.py`
- modelos de observaciones/evidencia que apruebe el futuro Spec
- contratos afectados, solo después de aprobación
- `tests/unit/test_redactor.py`
- pruebas de seguridad, observabilidad y procedencia

**Criterios de aceptación:**

- Cada patrón de I08 tiene un caso positivo y uno de falso positivo.
- Ningún secreto protegido llega sin redactar a logs o al backend externo.
- I09 no restaura `.qa_sessions` ni memoria persistente diferida.
- I12 permite comprobar que la evidencia cambió sin convertir una sugerencia
  semántica en evidencia verificada.

**No depende de:** I01 para desarrollar y probar el `Redactor`.

**Entregas a otros:** I09 puede consumir I06; I12 debe estar aprobado antes de
integrar resultados semánticos de I15.

## Persona 6 — CLI y evaluación de capacidades futuras

**Ítems asignados:** I14, I15 e I16.

**Objetivo:** preparar decisiones de producto para automatización CLI y QA
semántico sin introducir frameworks antes de contar con evidencia.

**Orden interno:**

1. Dividir I14 en propuestas independientes: salida automatizable, control de
   ejecución y comando de evaluación.
2. Mantener `qa-agent eval` bloqueado hasta que I10 defina el harness y sus
   métricas.
3. Para I15, definir casos semánticos concretos, salida estructurada y frontera
   HYPOTHESIS; comparar una solución mínima sin framework contra LangChain.
4. Evaluar I16 solo si I10 demuestra un problema medible de orquestación que el
   loop actual no resuelve de forma razonable.
5. No agregar LangChain, LangGraph o LlamaIndex como dependencia durante el
   análisis.

**Archivos probables:**

- documentos futuros de Spec/Plan/ADR
- `src/qa_agent/cli/main.py`, solo después de aprobar I14
- contratos CLI y LLM afectados, solo después de aprobación
- pruebas E2E del entry point instalado

**Criterios de aceptación:**

- Cada bandera de I14 tiene combinaciones válidas, errores y compatibilidad
  definidos antes de programarse.
- I15 produce únicamente candidatos/hipótesis y nunca controla autorización,
  evidencia determinista, integridad, seguridad o veredicto final.
- I16 termina en KEEP, REASSESS o REPLACE con métricas y coste de migración; no
  en una migración por popularidad del framework.

**Dependencias:** I14 (`qa-agent eval`) e I15 dependen de I10; I15 depende del
contrato de I12 para procedencia; I16 depende de dolor medido y no debe iniciar
como implementación.

## Oleadas de integración

### Oleada A — Deuda técnica paralela

- Persona 1: I02 y un primer corte aprobado de I01.
- Persona 2: I03.
- Persona 3: I04 e I05.
- Persona 4: I07.
- Persona 5: I08.
- Persona 6: diseño de I14–I16, sin cambios de código o dependencias.

Estos frentes no dependen funcionalmente entre sí. Los cambios deben revisarse
y fusionarse por ítem para mantener una superficie pequeña.

### Oleada B — Decisiones post-MVP

- Persona 2: Spec/Plan de I10.
- Persona 3: Spec/contrato de I06.
- Persona 4: Spec/Plan de I11.
- Persona 5: Spec/Plan de I09 e I12.
- Persona 6: Spec de las partes aprobadas de I14 e I15.

Esta oleada es principalmente documental. La aprobación de un diseño es una
puerta explícita antes de modificar código.

### Oleada C — Capacidades futuras aprobadas

Orden recomendado de integración:

1. I06 e I10, porque producen interfaces consumidas por otros trabajos.
2. I09, I11 e I12, sobre esos contratos ya estables.
3. I14 e I15, usando I10 e I12 sin reemplazar los límites deterministas.
4. I13, un ecosistema por incremento.
5. I16, únicamente si las métricas justifican evaluarlo.

## Archivos con riesgo de conflicto

| Área | Responsables potenciales | Regla de coordinación |
|---|---|---|
| `src/qa_agent/agent/loop.py` | 1, 4 y 5 | Persona 1 realiza primero las extracciones; 4 y 5 integran después mediante interfaces aprobadas |
| `src/qa_agent/tools/generate_test_cases.py` | 4, 5 y 6 | Separar descubrimiento, redacción y semántica en cambios distintos |
| `src/qa_agent/cli/main.py` | 3 y 6 | CI solo prueba el contrato actual; Persona 6 cambia CLI únicamente tras aprobar I14 |
| `contracts/tool-contracts.md` | 2, 3 y 5 | Una sola ventana de versión de contrato; no mezclar I03, I06 e I12 |
| `pyproject.toml` | 2 y 3 | Persona 3 coordina dependencias; Persona 2 documenta la necesidad antes de agregar un validador |
| fixtures/evaluaciones | 2 y 6 | Persona 2 define el formato de I10; Persona 6 lo consume sin duplicarlo |

## Handoffs obligatorios

| Productor | Entrega | Consumidor | Condición |
|---:|---|---:|---|
| 1 | Límites internos del loop | 4 y 5 | I01 aprobado y pruebas de paridad verdes |
| 2 | Contrato del harness I10 | 6 | Métricas y fixtures aprobados |
| 3 | Metadatos aprobados de I06 | 5 | Contrato versionado y pruebas deterministas |
| 4 | Interfaces de descubrimiento I11 | 4, para I13 | Fallback y ecosistema base probados |
| 5 | Contrato de procedencia I12 | 6 | HYPOTHESIS y evidencia determinista separadas |
| 6 | Resultados comparativos I15/I16 | Producto/arquitectura | Métricas de I10, sin agregar dependencias durante la evaluación |

## Definición de terminado por ítem

Un ítem puede marcarse terminado únicamente cuando:

- tiene la aprobación SDD requerida por el backlog;
- su alcance no incluye otros ítems por conveniencia;
- cuenta con prueba de regresión o evidencia objetiva correspondiente;
- pasa las pruebas enfocadas, relacionadas y la suite completa;
- actualiza la documentación afectada sin crear FR, SC, US o Tasks de manera
  implícita;
- no deja cambios no relacionados ni dependencias de frameworks no aprobadas;
- registra limitaciones y handoffs pendientes.

## Cobertura del backlog

| Persona | Ítems | Clasificación original |
|---:|---|---|
| 1 | I01, I02 | Deuda técnica |
| 2 | I03, I10 | Deuda técnica; post-MVP |
| 3 | I04, I05, I06 | Deuda técnica; post-MVP |
| 4 | I07, I11, I13 | Deuda técnica; post-MVP; funcionalidad futura |
| 5 | I08, I09, I12 | Deuda técnica; post-MVP |
| 6 | I14, I15, I16 | Funcionalidades futuras; no recomendado actualmente |

Los dieciséis ítems aparecen exactamente una vez como responsabilidad primaria.
Las relaciones adicionales de las tablas son dependencias o revisiones, no una
segunda asignación.
