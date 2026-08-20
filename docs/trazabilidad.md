# Trazabilidad de requerimientos aprobados

Documento de trazabilidad (T052) que mapea requisitos aprobados a implementación
y tests. Un mapeo identifica evidencia candidata; no implica conformidad cuando
la tabla de remediación registra una desviación abierta.

## Requerimientos funcionales (FR-001..FR-036, FR-042..FR-050)

| FR | Requisito | Implementación | Tests |
|----|-----------|----------------|-------|
| FR-001 | Aceptar solicitud en lenguaje natural | `Agent.atender` (`src/qa_agent/agent/loop.py`) | `test_agent_loop.py`, `test_router.py` |
| FR-002 | Respuesta relacionada con la solicitud | `Agent.atender` → `_backend.generar_respuesta` | `test_agent_loop.py` |
| FR-003 | Seleccionar y ejecutar herramienta | `_seleccionar_herramienta` + `_ejecutar_herramienta` (`loop.py`) | `test_agent_loop.py`, `test_agent_qa_integration.py` |
| FR-004 | Respuesta basada en resultados reales | `loop.py` (valida y usa `resultado.datos`) | `test_agent_qa_integration.py` |
| FR-005 | Validar resultados antes de usarlos | `validar_resultado` (`tools/base.py`) | `test_tool_contracts.py`, `test_honesty.py` |
| FR-006 | Explorar estructura del proyecto | `tools/explore.py` | `test_tools_explore.py` |
| FR-007 | Localizar archivos/clases/funciones | `tools/locate.py` | `test_tools_locate.py` |
| FR-008 | Reportar solo coincidencias/datos reales | `locate.py`, `search.py` (T114: `ruta_relativa` relativa a la raíz de la búsqueda); rail de `explore` (T124): ruta inexistente → corrección a directorio real del mismo nombre (`_resolver_directorio_real`) y, si no existe, enriquecimiento determinista con las capas reales de primer nivel (`_encolar_explore_capas_reales`, FR-024/VI) para no dejar la respuesta anclada solo en `existe=False` | `test_tools_locate.py` (incl. `test_locate_ruta_relativa_incluye_el_directorio`), `test_tools_search.py`, `test_profundidad_capa.py::test_explore_capa_inexistente_enriquece_capas_reales`, `test_profundidad_capa.py::test_explore_ruta_con_mismo_nombre_se_corrige_sin_fallback` |
| FR-009 | Revisar partes del código | `search.py` (contexto real) | `test_tools_search.py` |
| FR-010 | Buscar patrones específicos | `search.py` + `extraer_patron_busqueda` (`agent/router.py`) | `test_tools_search.py`, `test_router.py`, `test_honesty.py` (smoke) |
| FR-011 | Presentar código tal como existe | `search.py` (`_obtener_contexto`) | `test_tools_search.py` |
| FR-012 | Ejecutar operaciones sobre conjuntos autorizados | `tools/run_tests.py` (allowlist comandos) | `test_tools_run_tests.py` |
| FR-013 | Reportar estado real de pruebas | `run_tests.py` (parsing salida real) | `test_tools_run_tests.py`, `test_determinism.py` |
| FR-014 | Fallos explícitos con causas basadas en evidencia | `tools/analyze_test_results.py` | `test_tools_analyze_results.py`, `test_agent_qa_integration.py` |
| FR-015 | Solicitar autorización antes de acciones que modifican | `loop.py` rail + `security/authorization.py` | `test_authorization.py`, `test_agent_autorizacion_redaccion.py` |
| FR-016 | Abstenerse y notificar denegación/pendiente | `loop.py` (autorización `False`/`None`) | `test_authorization.py`, `test_agent_autorizacion_redaccion.py` |
| FR-017 | Informar falta de información/confianza | `loop.py` (Confianza.SIN_INFORMACION) | `test_honesty.py` |
| FR-018 | Manejo explícito de errores/inválidos | `loop.py` (estados ERROR/INVALIDO) | `test_honesty.py`, `test_tools_search.py` |
| FR-019 | No inventar resultados/archivos/pruebas | todas las herramientas + loop (revisión transversal; T119: `loop._respuesta_react` expone el error real del proveedor LLM en vez de un fallback genérico) | `test_honesty.py` (smoke), `test_tools_*`, `test_responder_robustez.py::test_respuesta_expone_error_real_del_backend` |
| FR-019+ | Recomendaciones etiquetadas (sin afirmar hechos inventados) | `loop.py` (`_recomendaciones_redactadas`) + prompt `generar_respuesta` (`openai_compatible_backend.py`) | `test_recomendaciones.py` |
| FR-020 | Historial visible de herramientas ejecutadas | `agent/session.py` | `test_session.py`, `test_agent_loop.py` |
| FR-021 | Filtrar/ocultar secretos antes de exponer | `security/redactor.py` (respuesta/historial/logs) | `test_redactor.py`, `test_session.py` |
| FR-022 | Informar cuando ninguna herramienta es adecuada + sugerir | `loop.py` (notificación FR-022) | `test_honesty.py`, `test_agent_loop.py` |
| FR-023 | Abstenerse de herramientas cuando ninguna es adecuada | `loop.py` (sin forzar ejecución) | `test_honesty.py` |
| FR-024 | Determinismo de operaciones sin IA | `agent/router.py` + herramientas | `test_determinism.py`, `test_router.py` |
| FR-025 | Mínimo privilegio y comandos autorizados | `tools/allowlist.py` + allowlists de comandos | `test_tools_run_tests.py`, `test_tools_coverage.py`, `test_determinism.py` |
| FR-025+ | Multi-lenguaje: runner detectado por marcador (dotnet/mvn/gradle) | `agent/loop.py` (`_detectar_comando_pruebas`/`_detectar_comando_cobertura`) + allowlists | `test_deteccion_runner.py`, `test_tools_run_tests.py` (parsers dotnet/mvn/gradle), `test_tools_coverage.py` (Cobertura XML/JaCoCo) |
| FR-026 | Análisis determinista de resultados de pruebas | `tools/analyze_test_results.py` | `test_tools_analyze_results.py` |
| FR-027 | Marcar "sin evidencia suficiente" | `analyze_test_results.py` | `test_tools_analyze_results.py` |
| FR-028 | Generar casos de prueba citando código real | `tools/generate_test_cases.py` (identificación determinista de `fuentes` sobre todas las extensiones de código reconocidas — no solo `*.py`, T123: soporta C#/`.cs`; ignora `bin`/`obj`/`.git`/dependencias; relevancia por contenido y por nombre de archivo) + redacción en lenguaje natural delegada al LLM (VI) | `test_tools_generate_cases.py` (fuentes reales Python y C#, casos según cripticidad), `test_agent_qa_integration.py` |
| FR-029 | No inventar casos/fuentes sin código relevante | `generate_test_cases.py` (objetivo sin palabras clave o sin archivos de código relevantes → `fuentes`/`casos_propuestos` vacíos, honesto FR-019) | `test_tools_generate_cases.py` |
| FR-030 | Analizar cobertura real (global y por archivo) | `tools/analyze_coverage.py` | `test_tools_coverage.py` |
| FR-031 | Reportar explícitamente fallo de cobertura | `analyze_coverage.py` (estado `no_ejecutado`) | `test_tools_coverage.py` |
| FR-032 | Plan multi-paso explícito antes de ejecutar | `loop.py` (`_atender_react` → `backend.planificar`) + `agent/reasoning.py` (`Plan`) (T115: el prompt instruye explorar por capa para la estructura completa; T117: `_enriquecer_plan_analisis_global` añade pasos deterministas por capa real en análisis global) | `test_reasoning.py` (T076-T078), `test_profundidad_analisis.py::test_enriquecimiento_anade_explore_y_lectura_por_capa` |
| FR-033 | Elegir herramienta y parámetros por razonamiento, validados | `loop.py` (`_ejecutar_siguiente_paso`: esquema + allowlist) + `backend.razonar` | `test_reasoning.py::test_parametros_fuera_del_esquema_no_se_ejecutan` |
| FR-034 | Iterar hasta satisfacer criterio de éxito o agotar límite | `loop.py` (`_atender_react`: while + `evaluar`) + dedup de pasos idénticos en `_ejecutar_siguiente_paso` (`paso_repetido`, T112; ruta normalizada T117) + presupuesto dinámico para análisis global (T116, `_presupuesto_pasos`) y de capa/carpeta concreta (T122, `_presupuesto_pasos` + `_es_analisis_capa`) | `test_reasoning.py` (T078, T081), `test_reasoning.py::test_react_no_repite_pasos_identicos_ya_ejecutados`, `test_profundidad_analisis.py::test_presupuesto_global_amplia_pasos_max`, `test_profundidad_analisis.py::test_sin_intencion_global_respeta_pasos_max`, `test_profundidad_capa.py::test_presupuesto_capa_amplia_pasos_max` |
| FR-035 | Mostrar el razonamiento de cada paso (razón+herramienta+parámetros+observación) | `loop.py` (`_respuesta_react`, `razonamiento`; T114: la observación guarda los parámetros realmente ejecutados, empareja solo pasos pendientes) + `cli/main.py` (`_renderizar_respuesta`) | `test_reasoning.py::test_historial_incluye_la_razon_de_cada_paso`, `test_reasoning.py::test_respuesta_expone_el_razonamiento_completo`, `test_reasoning.py::test_react_observacion_guarda_parametros_realmente_ejecutados` |
| FR-036 | Re-planificar ante autorización denegada (paso alternativo no sensible) | `loop.py` (`_atender_react` + `_ejecutar_siguiente_paso`: omite y continúa) | `test_reasoning.py::test_denegacion_no_aborta_y_replanifica_con_paso_no_sensible` |
| FR-042 | Crear archivos nuevos solo dentro del perímetro, rechazando existentes/fuera | `tools/crear_archivo.py` + helper `resolver_archivo_en_perimetro` (`tools/base.py`, T095) + `agent/router.py` (`crear_archivo` pattern + `extraer_contenido`, T100) + rail `_corregir_escritura` en `_ejecutar_siguiente_paso` (T123): si el destino ya existe (path propuesto o mismo nombre en otro subárbol del perímetro), se mapea a `editar_archivo` sobre la ruta real, sin duplicar ni rechazar por un nombre mal resuelto | `test_tools_crear_archivo.py` (crea, existente→INVALIDO, fuera-de-perímetro, `..`, sin archivo/contenido), `test_router.py::test_enruta_crear_archivo`, `test_router.py::test_crear_archivo_gana_a_generate_test_cases`, `test_phase14_react.py::test_autorizada_ejecuta_y_crea_el_archivo`, `test_phase14_react.py::test_crear_archivo_en_ruta_erronea_se_corrige_a_editar`, `test_phase14_react.py::test_crear_archivo_ya_existente_se_corrige_a_editar` |
| FR-043 | Modificar contenido de archivos existentes dentro del perímetro | `tools/editar_archivo.py` + `resolver_archivo_en_perimetro` (T095) + router (`editar_archivo`, T100) + rail `_corregir_escritura` en `_ejecutar_siguiente_paso` (T123): `editar_archivo` sobre un destino inexistente se mantiene y la herramienta lo rechaza honestamente (no se invierte a `crear_archivo` por sorpresa); además, el paso de escritura del plan se re-planifica con `razonar` cuando ya hay evidencia real acumulada (lecturas/exploraciones previas) para que el contenido se ancle en lo observado (FR-019) | `test_tools_editar_archivo.py` (edita, inexistente→INVALIDO, fuera-de-perímetro, sin contenido), `test_router.py::test_enruta_editar_archivo`, `test_phase14_react.py::test_pasada_unica_con_parametros_extraidos`, `test_phase14_react.py::test_editar_archivo_inexistente_no_se_invierte_a_crear`, `test_phase14_react.py::test_escritura_se_replanifica_anclada_en_evidencia_real` |
| FR-044 | Eliminar archivos existentes dentro del perímetro | `tools/eliminar_archivo.py` + `resolver_archivo_en_perimetro` (T095) + router (`eliminar_archivo`, T100) | `test_tools_eliminar_archivo.py` (elimina, inexistente/directorio→INVALIDO, fuera-de-perímetro), `test_router.py::test_enruta_eliminar_archivo` |
| FR-045 | Respaldo (backup) del estado previo antes de modificar/eliminar | `agent/backup.py` (`BackupManager`: `.qa-backup/<marca>/<ruta>` + `restaurar()`, T099), usado por `editar_archivo`/`eliminar_archivo` (T097/T098) | `test_backup.py` (respaldar/restaurar/ajenos), `test_tools_editar_archivo.py::test_editar_archivo_respalda_estado_previo_y_restaura`, `test_tools_eliminar_archivo.py::test_eliminar_archivo_borra_con_backup_restaurable` |
| FR-046 | Autorización explícita antes de crear/editar/eliminar; abstenerse si denegada/pendiente | `requiere_autorizacion=True` en las tres herramientas (T096-T098) + rail `loop._ejecutar_siguiente_paso`/`_atender_una_pasada` + `cli/main.py` (`_procesar_solicitud` re-invoca con la decisión, T101) | `test_tools_*_archivo.py::test_*_requiere_autorizacion`, `test_phase14_react.py::test_pendiente_autorizacion_suspende_sin_modificar`, `test_phase14_react.py::test_denegada_replanifica_y_no_aborta` |
| FR-047 | Verificar el estado real tras la operación y reportar con evidencia | las herramientas reportan el resultado real (creado/editado/eliminado + backup); la respuesta ReAct queda anclada en observaciones reales (T101/T102) | `test_phase14_react.py::test_autorizada_ejecuta_y_crea_el_archivo` (verifica el archivo real), `test_phase14_react.py::test_paso_fuera_de_perimetro_se_rechaza_sin_crear` (no afirma cambios) |
| FR-048 | Leer contenido real de un archivo dentro del perímetro (límite de líneas + aviso de truncado) | `tools/leer_archivo.py` (`LeerArchivoHerramienta`, `requiere_autorizacion=False`) + saneo ReAct (`loop._ejecutar_siguiente_paso` deriva/rechaza placeholders, T111) + corrección de ruta real (T123): si el LLM propone una lectura inexistente pero hay un archivo real con el mismo nombre dentro del perímetro (regresión: leía 'Datos/ClienteDAL.cs' cuando la carpeta real es 'DAL'), se corrige a la ruta real para no perder la evidencia; sin archivo real se reporta ausencia (FR-019). La evidencia de la lectura entra íntegra en el contexto del LLM (T123): `OpenAICompatibleBackend._contexto_observacion` amplía el presupuesto de `leer_archivo` a `_MAX_CHARS_EVIDENCIA_LEER_ARCHIVO` y añade `_resumen_firmas` (firmas deterministas `L{n}: firma` que sobreviven al recorte); `cli/main.py` renderiza lecturas con presupuesto ampliado (sin el marcador `[+N chars]` engañoso) | `test_tools_leer_archivo.py` (contenido real, inexistente, fuera-de-perímetro, `..`, truncado), `test_reasoning.py::test_react_leer_archivo_placeholder_se_deriva_de_la_solicitud`, `test_reasoning.py::test_react_leer_archivo_placeholder_sin_archivo_se_rechaza`, `test_phase14_react.py::test_leer_archivo_en_ruta_erronea_se_corrige_a_ruta_real`, `test_phase14_react.py::test_leer_archivo_sin_archivo_real_se_mantiene_y_reporta_ausencia`, `test_profundidad_capa.py::test_contexto_leer_archivo_preserva_contenido_completo`, `test_profundidad_capa.py::test_contexto_leer_archivo_grande_incluye_firmas_deterministas`, `test_profundidad_capa.py::test_resumen_firmas_extrae_firmas_csharp_y_python` |
| FR-049 | Explicar/entender el código con profundidad (leer archivos relevantes y responder por capa/módulo citando contenido real; honestidad si falta evidencia) | `tools/leer_archivo.py` + `agent/loop.py` (`_parametros_para` inyecta `ruta`+`archivo_relativo`; T117 `_enriquecer_plan_analisis_global` lee el código principal de cada capa en análisis global; detector `_es_analisis_global` ampliado en T120; intenciones de sugerencia de pruebas como análisis exhaustivo con `_enriquecer_plan_pruebas`/`_es_intencion_pruebas`, T121; análisis de UNA capa/carpeta concreta con `_es_analisis_capa`+`_enriquecer_plan_analisis_capa`/`_resolver_capa_real`, T122; detección ampliada en T123 a intenciones de definir/escribir pruebas y cobertura de una capa concreta: `_VERBOS_ANALISIS_CAPA` y `_FRASES_INTENCION_PRUEBAS` cubren "define las pruebas", "pruebas unitarias", "porcentaje de cobertura", "procede a definir/realizar", de modo que el enriquecimiento se dispara aunque el LLM planifique rutas inventadas ("Datos"/"Negocio") + T124: `_extraer_capa_solicitada` salta conectores ("la capa de DAL" → `dal`) y rail de `explore` con corrección de ruta real (`_resolver_directorio_real`/`_buscar_directorio_por_nombre`) + fallback determinista a capas reales de primer nivel cuando la ruta explorada no existe (`_encolar_explore_capas_reales`, regresión real "Que otros archivos hay en esa capa?" planificaba 'Datos' en vez de 'DAL') + prompts `planificar`/`razonar`/`responder`/`generar_respuesta`/`evaluar` (`llm/openai_compatible_backend.py`, T118) + nota de cobertura al agotar presupuesto (T118, `_NOTAS_COBERTURA_GLOBAL`; aplica también a análisis de capa T122) + evidencia acotada en `responder` con reintento compacto (T119, `_evidencia_responder`) + listado de nombres de `explore` sin recortar el medio en el contexto del LLM (T122, `_resumen_nombres`/`_contexto_observacion`) + error real del proveedor expuesto en `loop._respuesta_react` (T119) | `test_reasoning.py::test_react_ejecuta_paso_leer_archivo_con_archivo_relativo`, `test_tools_leer_archivo.py`, `test_router.py::test_leer_archivo_*`, `test_profundidad_analisis.py::test_enriquecimiento_anade_explore_y_lectura_por_capa`, `test_profundidad_analisis.py::test_analiza_la_estructura_dispara_enriquecimiento`, `test_profundidad_analisis.py::test_respuesta_incluye_nota_de_cobertura_cuando_agota_presupuesto`, `test_intencion_pruebas.py::test_enriquecimiento_pruebas_anade_cobertura_locate_y_casos`, `test_profundidad_capa.py::test_enriquecimiento_capa_lee_todos_los_archivos`, `test_profundidad_capa.py::test_enriquecimiento_capa_no_duplica_previstos`, `test_profundidad_capa.py::test_enriquecimiento_capa_solo_si_existe`, `test_profundidad_capa.py::test_respuesta_capa_incluye_nota_cuando_agota_presupuesto`, `test_profundidad_capa.py::test_enriquecimiento_capa_con_intencion_de_definir_pruebas`, `test_profundidad_capa.py::test_contexto_explore_no_oculta_nombres_del_medio`, `test_profundidad_capa.py::test_extraer_capa_solicitada_salta_conectores`, `test_profundidad_capa.py::test_resolver_directorio_real_encuentra_directorio_por_nombre`, `test_profundidad_capa.py::test_explore_capa_inexistente_enriquece_capas_reales`, `test_profundidad_capa.py::test_explore_ruta_con_mismo_nombre_se_corrige_sin_fallback`, `test_responder_robustez.py` |
| FR-050 | Ocultar el historial visible por defecto en el CLI, mostrándolo con `--mostrar-historial` (trazabilidad por paso en Razonamiento) | `cli/main.py` (`_renderizar_respuesta(mostrar_historial=False)`, opción `--mostrar-historial` en `main`) | `test_cli_render.py::test_render_oculta_el_historial_por_defecto`, `test_cli_render.py::test_render_muestra_el_historial_con_flag` |

## Criterios de éxito (SC-001..SC-017, SC-021..SC-026)

| SC | Criterio | Test de verificación |
|----|----------|----------------------|
| SC-001 | Respuesta para el 100% de solicitudes válidas | `test_agent_loop.py::test_respuesta_no_vacia_para_solicitud_valida` |
| SC-002 | Solo información real, sin contenido inventado | `test_honesty.py::test_resultado_real_vacio_no_inventa_contenido`, `test_honesty.py::test_humo_*` |
| SC-003 | 100% de coincidencias reales pertinentes | `test_tools_locate.py`, `test_tools_search.py` |
| SC-004 | 100% de acciones que modifican requieren autorización | `test_authorization.py` |
| SC-005 | 100% de errores comunicados explícitamente | `test_honesty.py` (inválido/error/excepción) |
| SC-006 | Herramientas probables sin LLM real | `test_determinism.py`, suite con `FakeLLM` |
| SC-007 | Historial visible por solicitud | `test_session.py`, `test_agent_loop.py` |
| SC-008 | 100% de secretos ocultados | `test_redactor.py`, `test_session.py` |
| SC-009 | 100% de solicitudes sin herramienta → notificación+sugerencia | `test_honesty.py::test_sin_herramienta_adecuada_notifica_y_sugiere_sin_ejecutar` |
| SC-010 | Operaciones sin IA → deterministas | `test_determinism.py` |
| SC-011 | Mínimo privilegio, sin comandos no autorizados | `test_tools_run_tests.py`, `test_tools_coverage.py` |
| SC-012 | Análisis de resultados determinista y evidencia acotada | `test_tools_analyze_results.py` |
| SC-013 | Casos generados citan código real | `test_tools_generate_cases.py` |
| SC-014 | Cobertura real o estado explícito ante fallo | `test_tools_coverage.py` |
| SC-015 | Historial muestra pasos con razón y observaciones reales | `test_reasoning.py::test_historial_incluye_la_razon_de_cada_paso`, `test_reasoning.py::test_respuesta_expone_el_razonamiento_completo` |
| SC-016 | No supera `pasos_max` pasos por solicitud | `test_reasoning.py::test_pasos_max_corta_el_bucle_y_responde_con_confianza_limitada`, `test_profundidad_analisis.py::test_sin_intencion_global_respeta_pasos_max` (y ampliación determinista a 18 solo para análisis exhaustivo: análisis global T116 + sugerencia de pruebas T121 + análisis de capa/carpeta T122; detector de frases ampliado en T120 y en T123 para definir/escribir pruebas y cobertura de una capa concreta) |
| SC-017 | Toda afirmación final anclada en una observación real | `test_reasoning.py::test_responder_que_inventa_no_produce_afirmaciones_sin_observacion`, `test_reasoning.py::test_evidencia_real_produce_afirmacion_anclada` |
| SC-021 | 100% de operaciones crear/editar/eliminar requieren autorización explícita | `test_tools_crear_archivo.py::test_crear_archivo_requiere_autorizacion`, `test_tools_editar_archivo.py::test_editar_archivo_requiere_autorizacion`, `test_tools_eliminar_archivo.py::test_eliminar_archivo_requiere_autorizacion`, `test_phase14_react.py::test_pendiente_autorizacion_suspende_sin_modificar` |
| SC-022 | 100% de operaciones destructivas solo dentro del perímetro autorizado | `test_tools_crear_archivo.py::test_crear_archivo_fuera_de_allowlist_se_rechaza`, `test_tools_crear_archivo.py::test_crear_archivo_traversal_se_rechaza_sin_crear_nada`, `test_tools_editar_archivo.py::test_editar_archivo_fuera_de_allowlist_se_rechaza`, `test_tools_eliminar_archivo.py::test_eliminar_archivo_fuera_de_allowlist_se_rechaza`, `test_phase14_react.py::test_paso_fuera_de_perimetro_se_rechaza_sin_crear` |
| SC-023 | 100% de modificaciones/eliminaciones con backup previo y verificación posterior | `test_backup.py`, `test_tools_editar_archivo.py::test_editar_archivo_respalda_estado_previo_y_restaura`, `test_tools_eliminar_archivo.py::test_eliminar_archivo_borra_con_backup_restaurable` |
| SC-024 | 100% de resultados destructivos reportados con evidencia real | `test_tools_crear_archivo.py::test_crear_archivo_existente_rechaza_sin_modificar`, `test_tools_editar_archivo.py::test_editar_archivo_inexistente_rechaza_sin_modificar`, `test_phase14_react.py::test_autorizada_ejecuta_y_crea_el_archivo` (verificación del archivo real) |
| SC-025 | 100% de lecturas de archivos devuelven contenido real o informan ausencia/rechazo (FR-048) | `test_tools_leer_archivo.py::test_leer_archivo_devuelve_contenido_real_tal_cual`, `test_tools_leer_archivo.py::test_leer_archivo_inexistente_informa_ausencia_sin_inventar`, `test_tools_leer_archivo.py::test_leer_archivo_ruta_fuera_de_allowlist_rechaza`; evidencia íntegra en el contexto del LLM (T123): `_contexto_observacion` amplía el presupuesto de `leer_archivo` a `_MAX_CHARS_EVIDENCIA_LEER_ARCHIVO` y añade `_resumen_firmas` (firmas deterministas que no se recortan) → `test_profundidad_capa.py::test_contexto_leer_archivo_preserva_contenido_completo`, `test_profundidad_capa.py::test_contexto_leer_archivo_grande_incluye_firmas_deterministas`, `test_profundidad_capa.py::test_resumen_firmas_extrae_firmas_csharp_y_python` |
| SC-026 | 100% de solicitudes de explicar/entender el código responden con profundidad anclada en contenido real o con honestidad/confianza no alta (FR-049) | `test_reasoning.py::test_react_ejecuta_paso_leer_archivo_con_archivo_relativo`, `test_reasoning.py::test_respuesta_profunda_con_palabras_al_inicio_de_frase_no_se_degrada`, `test_reasoning.py::test_responder_que_inventa_no_produce_afirmaciones_sin_observacion` |

## Estado de remediación de conformidad

| Gap | Requisitos aprobados | Estado | Tarea |
|-----|----------------------|--------|-------|
| G1: evidencia cruda podía llegar al LLM externo | FR-021, SC-008, constitución XI, contrato LLM | CONFORME — regresión PASS | T125 |
| G2: `run_tests` podía eludir autorización por una ruta de análisis | FR-015/016, SC-004, constitución V | CONFORME — regresión PASS | T126 |
| G3: cobertura ejecutaba código sin autorización declarada | FR-015/016, SC-004, FR-030 | CONFORME — regresión PASS | T126 |
| G5: generación de casos incumplía el contrato del backend y silenciaba el error | FR-017/019/028/029, SC-013 | CONFORME — regresión PASS | T128 |
| G6/G7: persistencia y chat/tareas no aprobados estaban activos/documentados como alcance vigente | Constitución XII/XIV, `Storage: N/A` | RETIRADO DEL MVP — US-12 diferido | T127 |
| G8: sintaxis CLI instalada difería del contrato | FR-001/002/050, contrato CLI | CONFORME — E2E PASS | T129 |
| G9: resultado de proceso no distinguía de forma fiable fallo/no ejecutado | FR-013/017/018/031, SC-005/014 | CONFORME — regresión PASS | T130 |

G4 se resolvió como decisión de alcance: el MVP acepta solo repositorios de
confianza y no promete sandbox. T125-T131 están cerradas con evidencia en
`docs/remediation/qa-agent-remediation-log.md`: 354 pruebas PASS, CLI E2E,
`pip check`, análisis SDD y `git diff --check` en verde.

## Conclusión

Los requisitos aprobados están mapeados a implementación y tests. Las
desviaciones T125-T131 de la tabla anterior están cerradas. La **Phase 14
(acciones destructivas)** está implementada (FR-042..047, SC-021..024) en
`tasks.md` (T095-T103): herramientas `crear_archivo`/`editar_archivo`/
`eliminar_archivo` con autorización obligatoria, perímetro y backup, integradas
en el bucle ReAct. La **Phase 15 (profundidad de análisis)** está
especificada e implementada (`spec.md` v1.3, US-14/FR-048..050/SC-025..026,
`tasks.md` T104-T115, `docs/use-cases/UC-013.md`). La **profundidad por
capa/carpeta concreta** ("explora todas las clases de la capa X", T122) se
añadió a la Phase 15: detección determinista de la intención, enriquecimiento
del plan con lectura exhaustiva de la capa real y evidencia de `explore` sin
ocultar nombres (FR-049/FR-024, verificación con ReservaHotel). **T123**
completa la corrección de la regresión real de escritura con ReservaHotel:
(a) la detección de análisis de capa/pruebas se amplió a intenciones de
definir/escribir pruebas y cobertura ("procede a definir las pruebas unitarias
y cobertura ... de la capa DAL"), de modo que el enriquecimiento determinista
se dispara aunque el LLM planifique rutas inventadas ("Datos"/"Negocio"); y
(b) el rail `_corregir_escritura` resuelve la ruta real de un
`crear_archivo`/`editar_archivo` contra el filesystem y mapea `crear_archivo`
sobre un archivo existente a `editar_archivo` (FR-042/043/025), evitando
duplicados como el `UnitTest.md` creado en la raíz en vez de modificar
`docs/UnitTest.md`. El mismo resolutor de ruta real (`_resolver_archivo_real`)
se aplica a `leer_archivo` (FR-048): una lectura que el LLM planifica sobre
una ruta inexistente con un archivo real del mismo nombre (p. ej.
'Datos/ClienteDAL.cs' cuando la carpeta real es 'DAL') se corrige a la ruta
real, recuperando la evidencia en vez de reportar `existe=False`. Además, un
paso de escritura del plan (`crear_archivo`/`editar_archivo`) se re-planifica
(`razonar`) cuando la solicitud ya acumuló evidencia real de lecturas/
exploraciones: el `contenido` que el LLM planificó antes de ejecutar esas
lecturas se regenera anclado en lo observado (FR-019), usando el del plan solo
si el backend no produce otro paso de escritura. Y la evidencia de
`leer_archivo` entra íntegra en el contexto del LLM (T123): el presupuesto de
cada observación de lectura se amplía (`_MAX_CHARS_EVIDENCIA_LEER_ARCHIVO`) y,
si el archivo aún excede, se añaden las firmas deterministas de métodos
(`_resumen_firmas`, nombre + línea) que nunca se recortan — la regresión real
de "dime los métodos de UsuarioDAL.cs" (el recorte a 700/1500 caracteres
ocultaba el MEDIO del contenido, donde están las firmas, y el LLM respondía
"está truncado") queda resuelta; el panel del CLI también amplía el render de
lecturas para no mostrar el marcador engañoso `[+N chars]`. **T124** extiende
la corrección de rutas inventadas a la exploración de capas: (a) el detector
`_extraer_capa_solicitada` salta conectores ("la capa de DAL" → `dal`, en vez
de quedarse en "de"), de modo que "explora a profundidad la capa de DAL"
dispara el enriquecimiento determinista de la capa; y (b) se añade un rail de
`explore` análogo al de lectura: si el LLM planifica explorar una capa con
nombre inventado por convención (regresión real: 'Datos' en vez de 'DAL'), la
ruta se resuelve a un directorio real del mismo nombre dentro del perímetro y,
si no existe, se enriquecen deterministamente las capas REALES de primer nivel
(`_encolar_explore_capas_reales`) para que la respuesta se ancle en la
estructura real y no solo en un `explore` vacío (`existe=False`). Verificación
end-to-end con ReservaHotel: "Que otros archivos hay en esa capa?" ahora
explora BLL/DAL/EDL/UIL/WebPortal y responde con evidencia real. La conformidad
del alcance aprobado quedó verificada por T131; US-12 continúa diferido y no
forma parte de esa declaración.
