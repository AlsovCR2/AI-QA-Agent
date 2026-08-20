---
name: qa-test-analysis
description: Metodología para analizar resultados de pruebas usando analyze_test_results y run_tests
metadata:
  version: "1.0"
  tools:
    - run_tests
    - analyze_test_results
  applicable_scenarios:
    - "usuario pide analizar resultados de pruebas"
    - "usuario pide ejecutar tests y ver resumen"
    - "usuario pregunta por qué fallan los tests"
    - "usuario quiere agrupar fallos por archivo"
  sequence:
    - step: 1
      tool: run_tests
      action: "Ejecutar conjunto autorizado de pruebas"
    - step: 2
      tool: analyze_test_results
      action: "Analizar salida real de run_tests (resumen + agrupación)"
---

# Skill: Análisis de Resultados de Pruebas (QA Test Analysis)

## Propósito
Esta skill define la metodología para analizar resultados de pruebas usando las herramientas `run_tests` y `analyze_test_results` en secuencia. El objetivo es ejecutar pruebas, reportar el estado real (pasadas/falladas/errores) y delimitar las posibles causas de fallos a lo que la evidencia sustenta, sin inventar causas.

## Cuándo Activar
Activa esta skill cuando el usuario:
- Pida "analiza estos resultados de prueba"
- Pida "ejecuta los tests y analiza los resultados"
- Pregunte "por qué fallan los tests" o "qué pasó con los tests"
- Solicite "agrupa los fallos por archivo"
- Quiera "resumen de los tests ejecutados"

## Secuencia Esperada

### Paso 1: Ejecutar Pruebas (`run_tests`)
1. Verificar que el conjunto de pruebas esté autorizado (`conjunto_autorizado: true`)
2. Seleccionar comando de la allowlist segura (p. ej. `pytest -v`, `pytest --tb=short`)
3. Ejecutar `run_tests` con:
   ```json
   {
     "ruta": "/proyecto",
     "conjunto_autorizado": true,
     "comando_pruebas": "pytest -v"
   }
   ```
4. Capturar el resultado: `pasadas`, `falladas`, `errores`, `total`, `estado_global`, `detalle_fallos`

### Paso 2: Analizar Resultados (`analyze_test_results`)
1. Pasar el resultado de `run_tests` como entrada a `analyze_test_results`
2. Ejecutar con:
   ```json
   {
     "ruta": "/proyecto",
     "resultado_tests": {
       "pasadas": <valor_de_run_tests>,
       "falladas": <valor_de_run_tests>,
       "errores": <valor_de_run_tests>,
       "total": <valor_de_run_tests>,
       "estado_global": "<valor_de_run_tests>",
       "detalle_fallos": <valor_de_run_tests>
     }
   }
   ```
3. Obtener: `resumen` (cuantitativo determinista) y `fallos_agrupados` (por archivo)

## Criterios de Entrada
- **Conjunto autorizado**: `run_tests` requiere `conjunto_autorizado: true` (FR-012)
- **Comando seguro**: Debe ser de la allowlist de comandos seguros (SC-011)
- **Ruta válida**: Dentro de la Allowlist de rutas (FR-025)

## Delimitación de Causas a la Evidencia (FR-014, UC-007)

### Regla Fundamental
Las `posible_causa` en `fallos_agrupados` DEBEN limitarse a:
1. **Evidencia directa**: Mensaje de error explícito (AssertionError, TimeoutError, etc.)
2. **"sin evidencia suficiente"**: Cuando no hay patrón reconocido

### Patrones Reconocidos con Causa Evidente
| Tipo de Error | Causa Asignada | Evidencia |
|---------------|----------------|-----------|
| AssertionError + comparación | Valor inesperado en aserción | Mensaje con `!=` o `==` |
| TimeoutError | Tiempo de espera excedido | TimeoutError |
| ValueError | Valor inválido proporcionado | ValueError |
| KeyError | Clave no encontrada | KeyError |
| AttributeError | Atributo inexistente | AttributeError |
| ImportError/ModuleNotFoundError | Módulo faltante | ImportError |
| TypeError | Tipo incorrecto | TypeError |
| FileNotFoundError | Archivo no encontrado | FileNotFoundError |
| PermissionError | Permisos insuficientes | PermissionError |
| ConnectionError | Error de conexión | ConnectionError |

### Lo que NUNCA se debe hacer
- **NO inventar causas** no respaldadas por el mensaje de error (FR-019)
- **NO atribuir a hipótesis** sin evidencia directa (UC-007)
- **NO especular** sobre causas root si solo hay un AssertionError simple
- **NO fabricar fallos** que no aparecen en `detalle_fallos` (FR-019, SC-002)

## Presentación de Resultados

### Resumen Cuantitativo (Determinista)
Presentar el `resumen` de `analyze_test_results` directamente:
- "X pasadas, Y falladas, Z errores de N total. Estado global: [exito/fallo]."

### Fallos Agrupados por Archivo
Para cada grupo en `fallos_agrupados`:
1. Mostrar `ruta_relativa` del archivo
2. Mostrar `error_comun` (mensaje representativo)
3. Mostrar `posible_causa` (limitada a evidencia o "sin evidencia suficiente")
4. Contar número de fallos por archivo (si hay múltiples en mismo archivo)

## Manejo de Casos Especiales

### Sin Fallos (`falladas == 0`)
- Reportar: "Todos los tests pasaron. X pasadas de N total."
- No invocar análisis de causas (no hay fallos que analizar)

### Todos Fallan (`pasadas == 0`)
- Reportar el resumen
- Para cada fallo, mostrar error y causa
- Sugerir: "Revisa si hay un problema común (importación, configuración, etc.)"

### Error de Ejecución (`estado_global == "no_ejecutado"`)
- Informar: "No se pudieron ejecutar las pruebas: [error]"
- NO inventar resultados
- Sugerir: "Verifica la configuración del proyecto o el comando de pruebas"

## Ejemplos de Uso

### Usuario: "Ejecuta los tests y analiza los resultados"
```json
// Paso 1: run_tests
{
  "ruta": "/proyecto",
  "conjunto_autorizado": true,
  "comando_pruebas": "pytest -v"
}

// Paso 2: analyze_test_results (con salida de paso 1)
{
  "ruta": "/proyecto",
  "resultado_tests": "<resultado_de_run_tests>"
}
```

### Usuario: "Agrupa los fallos por archivo"
- Si ya se ejecutaron tests, usar el resultado existente
- Si no, ejecutar `run_tests` primero, luego `analyze_test_results`

## Integración con Otras Skills
- **Sigue a**: `run_tests` (paso 1 de la secuencia)
- **Relacionada con**: `qa-coverage` (análisis + cobertura = imagen completa)
- **Precede a**: `qa-test-cases` (fallos identificados → generar tests para cubrirlos)

## Notas de Implementación (Solo Referencia)
- `run_tests` es determinístico en ejecución; el análisis de causa puede ser asistido por LLM (VI)
- `analyze_test_results` es determinista en resumen y agrupación (SC-010)
- Las causas se limitan a evidencia (FR-014) o "sin evidencia suficiente"
- No inventa fallos ni causas (FR-019, SC-002)
- Ambas herramientas respetan Allowlist (FR-025)