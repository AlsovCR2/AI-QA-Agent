---
name: qa-coverage
description: Metodología para analizar cobertura de código usando la herramienta analyze_coverage
metadata:
  version: "1.0"
  tool: analyze_coverage
  applicable_scenarios:
    - "usuario pide analizar cobertura"
    - "usuario pide ver cobertura de tests"
    - "usuario pregunta qué líneas no están cubiertas"
  allowed_commands:
    - pytest --cov=src
    - pytest --cov=src --cov-report=term
    - pytest --cov=src --cov-report=term-missing
    - pytest --cov=. --cov-report=term
    - python -m pytest --cov=src
    - python -m pytest --cov=src --cov-report=term
    - python -m pytest --cov=src --cov-report=term-missing
    - python -m pytest --cov=. --cov-report=term
    - coverage run -m pytest
    - coverage run -m pytest && coverage report
    - coverage run -m pytest && coverage report -m
---

# Skill: Análisis de Cobertura (QA Coverage)

## Propósito
Esta skill define la metodología para analizar la cobertura de código de las pruebas usando la herramienta `analyze_coverage`. El objetivo es reportar cobertura real (global y por archivo) e identificar líneas faltantes, usando solo comandos autorizados.

## Cuándo Activar
Activa esta skill cuando el usuario:
- Pida "analiza la cobertura" o "analiza cobertura"
- Pregunte "qué líneas no están cubiertas"
- Solicite "cobertura de tests" o "reporte de cobertura"
- Quiera saber "porcentaje de cobertura" de un módulo/archivo

## Secuencia de Uso
1. **Verificar autorización**: Confirmar que el conjunto de pruebas está autorizado
2. **Seleccionar comando**: Usar comando de la allowlist predefinida (ver metadatos)
3. **Ejecutar herramienta**: Llamar a `analyze_coverage` con ruta y comando_cobertura
4. **Interpretar resultados**: Presentar cobertura global, por archivo y líneas faltantes
5. **Recomendar acciones**: Sugerir dónde agregar tests según líneas faltantes

## Criterios de Entrada
- **Ruta del proyecto**: Debe estar dentro de la Allowlist autorizada
- **Comando autorizado**: Debe ser uno de los comandos en la allowlist (ver metadatos)
- **Proyecto con tests**: Debe existir al menos un archivo de test ejecutable

## Interpretación de Resultados

### Cobertura Global
- **≥ 90%**: Excelente - Cobertura robusta
- **70-89%**: Buena - Áreas menores sin cubrir
- **50-69%**: Moderada - Faltan tests significativos
- **< 50%**: Baja - Cobertura insuficiente

### Por Archivo
Para cada archivo en `por_archivo`:
- Reportar `cobertura` (%)
- Listar `lineas_faltantes` si están disponibles (formato term-missing)
- Identificar archivos críticos con cobertura < 70%

### Líneas Faltantes
Cuando estén disponibles (comando con `--cov-report=term-missing`):
- Presentar rangos de líneas no cubiertas
- Sugerir casos de prueba específicos para esas líneas
- Priorizar líneas en lógica de negocio vs. código boilerplate

## Umbrales de Alerta (Configurables)
| Métrica | Umbral Warning | Umbral Critical |
|---------|----------------|-----------------|
| Cobertura global | < 80% | < 60% |
| Cobertura por archivo | < 70% | < 50% |
| Archivos sin cobertura | > 0 | > 3 |

## Manejo de Casos Especiales

### Comando No Autorizado
Si el usuario solicita un comando fuera de la allowlist:
- Informar: "Comando no permitido. Comandos autorizados: [lista]"
- Ofrecer alternativas de la allowlist

### Error de Ejecución
Si `estado == "error"` o `"no_ejecutado"`:
- Reportar error explícitamente: "No se pudo ejecutar análisis de cobertura: [error]"
- NO inventar datos de cobertura
- Sugerir: "Verifica que pytest y coverage estén instalados y los tests pasen"

### Sin Tests Ejecutables
Si `cobertura_global == 0` y `por_archivo == []`:
- Informar: "No se encontraron tests ejecutables o no hay código para cubrir"
- Sugerir: "Ejecuta primero `run_tests` para verificar que los tests funcionan"

## Ejemplos de Uso

### Usuario: "Analiza la cobertura del proyecto"
```json
{
  "ruta": "/proyecto",
  "comando_cobertura": "pytest --cov=src --cov-report=term-missing"
}
```

### Usuario: "Qué líneas no están cubiertas en src/auth"
```json
{
  "ruta": "/proyecto",
  "comando_cobertura": "pytest --cov=src/auth --cov-report=term-missing"
}
```

## Integración con Otras Skills
- **Precede a**: `qa-test-cases` (identificar gaps → generar tests para cubrirlos)
- **Sigue a**: `run_tests` (ejecutar tests → analizar cobertura)
- **Relacionada con**: `qa-test-analysis` (analizar resultados + cobertura = imagen completa)

## Notas de Implementación (Solo Referencia)
- La herramienta `analyze_coverage` solo ejecuta comandos de la allowlist (SC-011)
- Reporta cobertura **real** (FR-019, SC-002) - nunca inventa porcentajes
- Determinística (VI / SC-010) - misma entrada = mismo resultado
- Si falla → `estado == "error"` o `"no_ejecutado"` explícito (FR-017/018)
- Respeta Allowlist de rutas (FR-025)