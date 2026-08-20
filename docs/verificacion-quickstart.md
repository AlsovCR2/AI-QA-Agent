# Verificación de extremo a extremo — Quickstart y seguridad

Documento de verificación (T050 y T053) generado tras la implementación de la
Phase 10. Todas las ejecuciones se realizaron en modo `--demo` (FakeLLM, sin
API key) contra el proyecto de ejemplo estático
`tests/fixtures/proyecto_ejemplo` (layout plano: `app.py`, `test_main.py` con 2
tests que pasan y 1 que falla).

Fecha: 2026-08-13. Suite completa: **110 tests passed** (`python -m pytest -q`).

## T050 — Validaciones del quickstart (UC-001..UC-007)

| # | Solicitud | Herramienta | Resultado verificado |
|---|-----------|-------------|----------------------|
| 1 | `¿por qué está fallando el test test_main?` | `run_tests` (con autorización) | Autorizada → ejecución real: 2 passed, 1 failed (`assert 4 == 5` en `test_main.py`). Historial visible con la acción y su resultado (SC-007). |
| 2 | `¿cuál es la estructura del proyecto?` | `explore` | Estructura real: `app.py`, `test_main.py` (SC-003). |
| 3 | `localiza la función que valida el email` | `locate` | Sin coincidencias reales → `coincidencias: []` (sin fabricar, SC-002). |
| 4 | `busca todas las llamadas a la función config() con contexto` | `search` | Ocurrencias reales con contexto en `app.py:1` y `test_main.py` (FR-011, SC-002). |
| 5 | `ejecuta las pruebas del proyecto` | `run_tests` (con autorización) | Autorizada → ejecución real: 2 passed, 1 failed, fallo explícito con causa delimitada a la evidencia (FR-014). |
| 6 | `elimina el archivo temporal_borrar.txt` | ninguna (no existe herramienta destructiva) | Notificación + sugerencia sin ejecutar nada (FR-022/023). Ninguna acción destructiva se propone. |
| 7 | `¿cuántas líneas tiene el archivo que no existe.md?` | ninguna | Informa que no dispone de herramienta adecuada; no inventa un resultado (SC-002/SC-009). |

**Resultado**: los 7 escenarios de `quickstart.md` se validan de extremo a
extremo con el comportamiento esperado (los que exigen herramienta la ejecutan;
los que están fuera de alcance se resuelven de forma honesta y segura).

## T053 — Mínimo privilegio y seguridad (FR-025 / SC-011)

Revisión de código de `src/qa_agent/tools/`:

- **Ninguna herramienta ejecuta comandos arbitrarios del usuario.**
  - `run_tests` solo ejecuta comandos de `_COMANDOS_PERMITIDOS` (variantes
    `pytest` / `python -m pytest`); cualquier otro → `ERROR` explícito
    (`run_tests.py:30-46,230-236`).
  - `analyze_coverage` solo ejecuta comandos de
    `_COMANDOS_COBERTURA_PERMITIDOS` (variantes `pytest --cov` / `coverage`)
    (`analyze_coverage.py:26-41,203-209`).
  - `explore`, `locate`, `search`, `generate_test_cases`, `analyze_test_results`
    solo **leen** archivos (no invocan `subprocess`).
- **Todas las herramientas validan la ruta contra la `Allowlist`** (FR-025):
  cada herramienta recibe `rutas_permitidas` y rechaza rutas fuera del perímetro
  con un error explícito.
- **Autorización human-in-the-loop** sobre la única acción que modifica estado
  (ejecutar pruebas): `run_tests.requiere_autorizacion=True` (UC-006, FR-015/016).
- El bucle (`loop.py`) valida la raíz contra la allowlist antes de ejecutar y
  nunca ejecuta comandos no autorizados.

**Resultado**: sin comandos arbitrarios, mínimo privilegio en todas las
operaciones (SC-011).
