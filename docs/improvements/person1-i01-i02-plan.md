# Person 1 — I01/I02 Refactor Plan

Estado: PROPUESTO (Stage 1, solo diseño). Este documento no modifica la
Constitución, el Spec, el Plan, los contratos ni las tareas canónicas.
I01/I02 son deuda técnica asesora (`docs/improvements/qa-agent-improvement-
backlog.md`); ningún cambio propuesto aquí altera comportamiento observable.

## Baseline

Registrado en `main`, árbol limpio:

| Métrica | Valor |
|---|---|
| HEAD | `a69d3150b8854670067230b12b6ee4b76ede5688` |
| Commits recientes | `a69d315` docs: divide improvement backlog; `9b2070d` fix: complete QA agent SDD remediation |
| Suite completa | **354 passed** (`python -m pytest -q`) — coincide con el cierre T131 |
| `src/qa_agent/agent/loop.py` | **1947** líneas físicas |
| `src/qa_agent/agent/router.py` | **284** líneas físicas |

Notas de entorno (no afectan al repositorio):

- El paquete no estaba instalado en el Python local; se instaló
  `pip install -e ".[dev]"` (solo entorno, sin cambios en el repo).
- pytest fallaba al crear su raíz temporal por permisos de Windows
  (`PermissionError` en `...\Temp\pytest-of-mriverab`); las 155 primeras
  "errors" eran todas ese problema de entorno. Con
  `--basetemp=%TEMP%\opencode\pytest-tmp` la suite completa da 354 passed.
- Existe un directorio `.qa_sessions/` preexistente en la raíz del repo,
  anterior a esta tarea y ajeno a ella. Los tests T127
  (`test_remediation_security.py -k t127`) siguen en verde: la construcción del
  gestor de sesiones sigue sin crear persistencia activa.

Confirmación T125–T131: completados según `docs/remediation/qa-agent-
remediation-log.md` (todos FIXED, cierre T131 con 354 passed) y verificados en
la suite actual.

## I02 Inventory

Matriz de reglas de intención/frases/regex. Categorías distinguidas: (1)
enrutamiento de herramientas, (2) extracción de parámetros, (3) intención de
análisis global, (4) intención de análisis de pruebas, (5) detección de
análisis de capa, (6) enriquecimiento de plan. NO se trata todo como una sola
responsabilidad por ser regex.

### router.py (ya cohesivo)

| Regla/constante | Archivo | Responsabilidad | Tests que la protegen | Dueño propuesto |
|---|---|---|---|---|
| `_PATRONES_HERRAMIENTAS` (11 entradas ordenadas) | router.py | (1) Enrutamiento determinista con prioridad explícita | `tests/unit/test_router.py` (36 tests), incl. colisiones documentadas: analyze_coverage > analyze_test_results (`test_frases_qa_no_se_contaminan_entre_si`), leer_archivo > explore (`test_leer_archivo_gana_a_explore_cuando_pide_contenido`), crear_archivo > generate_test_cases (`test_crear_archivo_gana_a_generate_test_cases`); no-match → None (`test_sin_coincidencia_devuelve_none_para_delegar_al_llm`) | **Permanece en router.py** |
| `_normalizar` | router.py | Normalización compartida (minúsculas, sin acentos) | Indirecta: todos los tests de router | Permanece |
| `enrutar_solicitud` / `obtener_palabras_clave` / `listar_herramientas_enrutables` | router.py | API de enrutamiento | test_router.py (`test_herramientas_qa_estan_enrutables`, `test_obtener_palabras_clave_devuelve_frases`, `test_herramientas_destructivas_enrutables`) | Permanece |
| `_ARTICULOS`, `_TIPOS_OBJETIVO`, `_limpiar_objetivo`, `_inferir_cripticidad`, `extraer_objetivo_cripticidad` | router.py | (2) Extracción de parámetros para generate_test_cases | test_router.py: 5 tests de objetivo/cripticidad | Permanece |
| `extraer_patron_busqueda` | router.py | (2) Extracción para search/locate | test_router.py: 4 tests (`tras_patron_en_el_codigo`, `tras_expresion`, `nombre_tras_funcion_o_clase`, `sin_patron_extraible_devuelve_vacio`) | Permanece |
| `extraer_nombre_archivo` | router.py | (2) Extracción para leer_archivo y escrituras Phase 14 | test_router.py: 3 tests; `tests/unit/test_phase14_react.py:207` | Permanece |
| `extraer_contenido` | router.py | (2) Extracción de contenido para crear/editar_archivo | test_router.py: 3 tests; `tests/unit/test_phase14_react.py:208` | Permanece |

### loop.py (reglas de intención mezcladas con orquestación)

| Regla/constante | Archivo | Responsabilidad | Tests que la protegen | Dueño propuesto |
|---|---|---|---|---|
| `_FRASES_ANALISIS_GLOBAL` + `_es_analisis_global` | loop.py:77-122, 280-288 | (3) Detección de intención de análisis global | `tests/unit/test_profundidad_analisis.py:125-148` (por muestras, NO exhaustiva sobre las ~44 frases) | **Mover a nuevo módulo de política de intenciones** (S2) |
| `_PRESUPUESTO_ANALISIS_GLOBAL = 18` | loop.py:76 | (3)/(4)/(5) Presupuesto asociado a intención exhaustiva | `test_profundidad_analisis.py:151-161` (`presupuesto_global_amplia_pasos_max`, `sin_intencion_global_respeta_pasos_max`); nota de cobertura en :360-378 | Mover junto a las frases (par intención-presupuesto) |
| `_FRASES_INTENCION_PRUEBAS` + `_es_intencion_pruebas`, `_es_analisis_exhaustivo` | loop.py:129-187, 357-373 | (4) Detección de intención de pruebas | `tests/unit/test_intencion_pruebas.py:111-139` (por muestras) | **Mover** (S2) |
| `_PATRON_CAPA_O_CARPETA`, `_CONECTORES_CAPA`, `_VERBOS_ANALISIS_CAPA`, `_extraer_capa_solicitada`, `_es_analisis_capa` | loop.py:220-260, 291-326 | (5) Detección de análisis de capa/carpeta | `tests/unit/test_profundidad_capa.py:127-167, 619-628` (incl. salto de conectores T124) | **Mover** (S2) |
| `_resolver_capa_real` | loop.py:329-354 | Resolución filesystem de capa (única consumidora: enriquecimiento de capa) | `test_profundidad_capa.py:162-167` | Mover en S4 con el enriquecimiento (no es clasificación de texto) |
| `_EXTENSIONES_CODIGO`, `_es_archivo_codigo` | loop.py:188-193, 376-378 | (6) Soporte de enriquecimiento (clasificación de código) | Indirecta vía tests de profundidad | Mover en S4 con el enriquecimiento |
| `_NOTAS_COBERTURA_GLOBAL` | loop.py:199-205 | Política de respuesta/nota de cobertura (IX / FR-019) | `test_profundidad_analisis.py:360-378` | Permanece (futura extracción de política de respuesta, I01) |
| `_HERRAMIENTAS_ESCRITURA`, `_HERRAMIENTAS_EVIDENCIA` | loop.py:265-277 | Rails de re-planificación de escritura (T123) | `tests/unit/test_phase14_react.py:442` (`escritura_se_replanifica_anclada_en_evidencia_real`) | Permanece (rail de ejecución/orquestación) |
| `_MARCADORES_*`, `_COMANDO_PRUEBAS_*`, `_COMANDO_COBERTURA_*`, `_encontrar_marcador`, `_detectar_comando_pruebas`, `_detectar_comando_cobertura` | loop.py:55-66, 381-406 | Preparación de parámetros (detección de runner T073) — NO es regla de intención | `tests/unit/test_deteccion_runner.py` (8 tests) | Permanece en loop.py en esta oleada |
| `_afirmaciones_no_ancladas`, `_al_inicio_de_frase` | loop.py:1887-1947 | Política de anclaje de respuesta (SC-017) | `tests/unit/test_honesty.py` (flujo), robustez | Permanece (futura extracción de política de respuesta, I01) |

Conclusión I02: las únicas reglas fuera de lugar son los tres grupos de
intención de `loop.py` (filas marcadas **Mover**). `router.py` ya ES el módulo
enfocado y declarativo que el backlog pide para enrutamiento+extracción; no se
rediseña.

## Behavior Lock

Comportamiento observable que DEBE permanecer idéntico (contrato primario:
tests existentes):

1. `enrutar_solicitud`: mismo resultado por entrada, mismo orden de prioridad
   (analyze_coverage antes que analyze_test_results; destructivas antes que
   generate_test_cases; leer_archivo antes que explore), `None` si no hay
   coincidencia — test_router.py completo.
2. Extracciones de parámetros: mismos valores exactos para objetivo,
   cripticidad, patrón, nombre de archivo y contenido — test_router.py +
   test_phase14_react.py:207-208.
3. Conjuntos de verdad de `_es_analisis_global`, `_es_intencion_pruebas`,
   `_es_analisis_capa`, `_extraer_capa_solicitada` — tests de profundidad e
   intención existentes, más los barridos exhaustivos S1 (ver abajo).
4. Presupuesto: 12 por defecto, max(pasos_max, 18) para intención exhaustiva o
   de capa; nota de cobertura solo cuando aplica — test_profundidad_analisis.py.
5. Orden de enriquecimiento del plan ReAct: global → pruebas → capa, con pasos
   deduplicados contra el plan del LLM — test_profundidad_*.py,
   test_intencion_pruebas.py.
6. Comportamiento ReAct: rails T111/T112/T114/T123/T124 intactos (saneo de
   lectura, dedup de pasos repetidos, parámetros visibles = ejecutados,
   re-planificación de escritura con evidencia real, rail de explore).
7. Decisiones de autorización pending/denied/approved y frontera indirecta
   run_tests→analyze_test_results (T126) — test_remediation_security.py.
8. Redacción previa al LLM (T125) en todos los argumentos externos —
   test_remediation_security.py, test_agent_autorizacion_redaccion.py,
   test_redactor.py.
9. Sin persistencia `.qa_sessions` activa (T127); contrato GenerateTestCases
   (T128); CLI top-level (T129); semántica de subprocess (T130).
10. Contratos públicos de herramientas y esquemas — tests/contract/.

### Parity tests faltantes que deben añadirse ANTES de mover reglas (S1)

Los tests actuales cubren por muestras; para mover tablas enteras con
confianza se añadirán pruebas de caracterización (contra el código VIEJO):

1. Barrido exhaustivo: CADA frase de `_FRASES_ANALISIS_GLOBAL` dispara
   `_es_analisis_global`; CADA frase de `_FRASES_INTENCION_PRUEBAS` dispara
   `_es_intencion_pruebas`.
2. Barrido negativo cruzado: frases representativas de un grupo NO disparan el
   otro detector (global vs pruebas vs capa).
3. Cada verbo relevante de `_VERBOS_ANALISIS_CAPA` combinado con "capa X"
   dispara `_es_analisis_capa`; conectores de `_CONECTORES_CAPA` nunca se
   devuelven como capa.
4. Matriz parametrizada de no-match de `enrutar_solicitud` (además de
   `"hola"`/`""`): solicitudes ambiguas reales → None.
5. Aserción directa del presupuesto: intención puntual → pasos_max;
   exhaustiva/capa → max(pasos_max, 18).

## I02 Design Options

| Criterio | A. Solo centralizar constantes | B. Un módulo interno enfocado de política de intenciones | C. Fusionar también router en ese módulo |
|---|---|---|---|
| Riesgo conductual | Mínimo | Bajo (movimiento literal de tablas+predicados) | Medio (toca tabla de prioridad sensible) |
| Acoplamiento | loop.py sigue conteniendo la lógica de matching | loop.py consume predicados puros; dirección única | Un mega-módulo vuelve a concentrar responsabilidades |
| Testabilidad | Igual (todo privado en loop) | Predicados importables y auditables en un punto | Igual que B pero superficie mayor |
| Dirección de imports | — | intents ← loop; intents NO importa loop/tools/router | Igual, con churn extra |
| Código movido | ~120 líneas de datos | ~200 líneas (tablas + 5 funciones puras) | +284 de router |
| Mantenibilidad futura | Baja: el problema (mezcla en loop) persiste | Alta: cobertura de intenciones auditable en un archivo | Media: mezcla enrutamiento con heurísticas de intención |

**Recomendación: Opción B (mínimo viable).** Crear
`src/qa_agent/agent/intents.py` con los tres grupos de intención (frases,
patrones, conectores, verbos, presupuesto) y sus predicados puros
(`es_analisis_global`, `es_intencion_pruebas`, `es_analisis_capa`,
`extraer_capa_solicitada`). `router.py` no cambia (ya es dueño correcto de
enrutamiento y extracción de parámetros). No se rediseña el enrutamiento ni se
altera ninguna frase, prioridad ni fallback. Sin cambios semánticos → no
requiere revisión de producto (backlog: "Plan/ADR DEPENDS" solo si cambia
semántica; aquí no cambia).

## I01 Responsibility Map

Mapa de responsabilidades reales presentes hoy en `loop.py` (1947 líneas):

### 1. Orquestación de flujos

- Código: `atender`, `_atender_una_pasada`, `_atender_react` (~330 líneas).
- Dependencias: backend, herramientas, autorizaciones, redactor, sesión.
- Sensibilidad seguridad: ALTA (fronteras de autorización y redacción viven en
  estos flujos).
- Tests: test_agent_loop.py, test_agent_qa_integration.py,
  test_phase14_react.py, test_remediation_security.py.
- Candidato de extracción: NO (es el núcleo que debe permanecer).
- Riesgo de tocarlo: alto.

### 2. Soporte de intención

- Código: constantes y predicados module-level (~320 líneas, filas del
  inventario I02).
- Dependencias: ninguna fuera de stdlib (`re`, `pathlib` para
  `_resolver_capa_real`).
- Sensibilidad: baja (clasificación de texto; sin efectos).
- Tests: test_profundidad_analisis.py, test_profundidad_capa.py,
  test_intencion_pruebas.py.
- Candidato: SÍ — resuelto por I02 (S2).

### 3. Enriquecimiento de plan

- Código: `_presupuesto_pasos`, `_enriquecer_plan_analisis_global`,
  `_enriquecer_plan_pruebas`, `_enriquecer_plan_analisis_capa`,
  `_archivos_codigo_de_capa`, `_plan_ya_explora_capa`, `_plan_ya_lee_archivo`,
  `_capas_reales`, `_encolar_explore_capas_reales`, `_resolver_capa_real`,
  `_EXTENSIONES_CODIGO`/`_es_archivo_codigo` (~430 líneas, FR-049 /
  T116..T124).
- Dependencias: catálogo de herramientas (solo lectura vía `explore.ejecutar`
  sobre la ruta autorizada), tipos `Plan`/`PasoDePlan`/`EstadoDelAgente`,
  predicados de intención.
- Sensibilidad seguridad: BAJA-MEDIA: solo AÑADE pasos de herramientas de
  lectura/sugerencia (explore, locate, leer_archivo, generate_test_cases);
  nunca añade herramientas con `requiere_autorizacion`; la ejecución sigue
  pasando íntegra por los rails de `_ejecutar_siguiente_paso` (esquema →
  allowlist → autorización → ejecutar).
- Tests: test_profundidad_analisis.py (≈380 líneas),
  test_profundidad_capa.py (≈630 líneas), test_intencion_pruebas.py,
  test_deteccion_runner.py (adyacente).
- Candidato: **SÍ — primera extracción (S4)**.
- Riesgo: bajo-medio; responsabilidad cohesiva con tests fuertes y sin
  superficie de autorización.

### 4. Preparación de parámetros

- Código: `_parametros_para`, `_resultado_de_pruebas`, detectores de runner
  (~130 líneas).
- Sensibilidad: MEDIA-ALTA: `_resultado_de_pruebas` EJECUTA run_tests
  (frontera T126 heredada por analyze_test_results en una pasada).
- Tests: test_deteccion_runner.py, test_agent_loop.py.
- Candidato: NO en esta oleada (roza la frontera T126).
- Riesgo: medio.

### 5. Autorización/ejecución

- Código: bloques de autorización en ambos flujos, `_ejecutar_herramienta`,
  `_validar_y_usar`, núcleo de `_ejecutar_siguiente_paso` (validación de
  esquema, allowlist, autorización, ejecución, registro).
- Sensibilidad: CRÍTICA (T125/T126).
- Tests: test_remediation_security.py, test_authorization.py,
  test_agent_autorizacion_redaccion.py.
- Candidato: NO (excluido explícitamente como primera extracción).
- Riesgo: alto.

### 6. Resolución de rutas reales (rails T123/T124)

- Código: `_resolver_archivo_real`, `_corregir_escritura`,
  `_buscar_archivo_por_nombre`, `_buscar_directorio_por_nombre`,
  `_resolver_directorio_real` (~140 líneas).
- Dependencias: pathlib + perímetro (`_ruta_base`).
- Sensibilidad: MEDIA: garantizan que nunca se ejecute fuera del perímetro
  (FR-025) y que crear sobre existente se mapee a editar (FR-042).
- Tests: test_phase14_react.py (varios), integración QA.
- Candidato: posible segunda extracción futura; no la primera.
- Riesgo: medio.

### 7. Observación/evidencia

- Código: deduplicación de pasos dentro de `_ejecutar_siguiente_paso`
  (T112/T114), `_tiene_evidencia_real` (~80 líneas).
- Sensibilidad: MEDIA (trazabilidad FR-034/035).
- Tests: test_phase14_react.py.
- Candidato: futuro; acoplada al flujo de ejecución.
- Riesgo: medio.

### 8. Política de respuesta/anclaje

- Código: `_respuesta_react`, `_afirmaciones_no_ancladas`,
  `_al_inicio_de_frase`, `_recomendaciones_redactadas`,
  `_NOTAS_COBERTURA_GLOBAL` (~190 líneas).
- Sensibilidad: ALTA: aquí ocurre la redacción previa a `responder` (T125) y
  la honestidad de confianza (SC-017).
- Tests: test_honesty.py, test_responder_robustez.py, profundidad (nota).
- Candidato: NO como primera extracción (roza T125).
- Riesgo: alto.

## First I01 Extraction

**Responsabilidad elegida: enriquecimiento determinista de plan (mapa §3).**

Es la opción de menor riesgo coherente que I02 deja clara: es la mayor
responsibilidad no-orquestadora, no toca autorización/ejecución ni la frontera
T125/T126, tiene la cobertura de tests más fuerte del módulo, y tras I02 sus
dependencias de intención quedan en un módulo propio.

Interfaz interna mínima (sin dependencias nuevas, sin cambio de Spec):

```python
# src/qa_agent/agent/enriquecimiento.py
class EnriquecedorDePlan:
    """Enriquece planes con pasos deterministas de cobertura (FR-049)."""
    def __init__(self, herramientas, ruta_base): ...
    def enriquecer(self, plan, texto): ...
    # aplica EN ORDEN: análisis global → intención de pruebas → capa
    def encolar_explore_capas_reales(self, estado): ...
```

- `loop.py` conserva `_presupuesto_pasos` (política de presupuesto del bucle,
  SC-016) y delega la construcción/enriquecimiento del plan en
  `EnriquecedorDePlan`; el `Agent` sigue siendo el orquestador.
- Nombres de dominio (sin Manager/Service/Engine/Handler genéricos).
- La llamada `_encolar_explore_capas_reales` desde el rail de `explore` pasa a
  delegar en el mismo colaborador (misma firma semántica).
- Comportamiento público idéntico: mismas decisiones, mismos pasos añadidos,
  mismo orden, mismos textos de razón.

## Implementation Slices

| Slice | Contenido | Verificación independiente |
|---|---|---|
| S1 | Pruebas de caracterización/parity sobre el código VIEJO: barridos exhaustivos de frases (global/pruebas/capa), negativos cruzados, matriz no-match de router, aserción de presupuesto | Suite nueva en verde SIN cambiar src/ |
| S2 | I02: crear `agent/intents.py` con tablas+predicados; `loop.py` importa; cero duplicación post-transición; actualizar SOLO rutas de import en tests existentes | Focused: router + profundidad ×2 + intencion_pruebas |
| S3 | Verificación I02: subsets relevantes + suite completa + `pip check` + `git diff --check` | 354+N passed; STOP si cambia comportamiento |
| S4 | Primera extracción I01: `agent/enriquecimiento.py` (`EnriquecedorDePlan`); loop.py delega; sin cambio de contrato | Focused: profundidad ×2, intencion_pruebas, reasoning, phase14_react, remediation_security, autorizacion_redaccion, qa_integration |
| S5 | Verificación final: suite completa + gate de seguridad (T125-T130) + pip check + git diff --check + log de ejecución | Informe final Person 1 |

Cada slice es revisable de forma independiente; S1 debe estar fusionado/verde
antes de S2; S3 antes de S4.

## Riesgos y mitigaciones

1. Import circular `intents ↔ loop`: mitigado porque `intents.py` solo usa
   stdlib; loop importa a intents, nunca al revés.
2. Tests existentes importan símbolos privados desde `loop`
   (`_es_analisis_global`, etc.): se actualizan las líneas de import hacia
   `intents` sin tocar aserciones (cambio mecánico, revisable en diff).
3. Movimiento accidental de semántica (p. ej. normalización distinta):
   mitigado por barridos S1 ejecutados contra el código viejo primero.
4. `.qa_sessions` preexistente en la raíz del repo: artefacto histórico ajeno;
   los tests T127 siguen siendo la guarda; no se toca.
5. Entorno Windows: usar siempre `--basetemp` para pytest en esta máquina
   (permisos de `%TEMP%`); registrado para reproducibilidad.
