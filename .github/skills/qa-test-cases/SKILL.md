---
name: qa-test-cases
description: Metodología para generar casos de prueba usando la herramienta generate_test_cases
metadata:
  version: "1.0"
  tool: generate_test_cases
  applicable_scenarios:
    - "usuario pide generar tests para una función"
    - "usuario pide generar tests para un componente"
    - "usuario pide casos de prueba para cubrir escenarios faltantes"
  cripticidad_options:
    - happy_path
    - edge_cases
    - usuarios_no_validos
---

# Skill: Generación de Casos de Prueba (QA Test Cases)

## Propósito
Esta skill define la metodología para generar casos de prueba sugeridos usando la herramienta `generate_test_cases`. El objetivo es producir casos de prueba útiles, basados en código real del proyecto, que cubran diferentes tipos de escenarios según la cripticidad solicitada.

## Cuándo Activar
Activa esta skill cuando el usuario:
- Pida explícitamente "genera tests para X" o "genera casos de prueba para X"
- Solicite "casos de prueba para la función Y"
- Pida "cubre edge cases para Z"
- Solicite "tests de validación para entrada inválida"

## Secuencia de Uso
1. **Identificar objetivo**: Extraer del mensaje del usuario la función, componente o escenario a cubrir
2. **Determinar cripticidad**: Mapear la intención del usuario a uno de los tres tipos:
   - `happy_path`: Casos de uso normal/esperado (por defecto)
   - `edge_cases`: Casos límite, bordes, valores extremos
   - `usuarios_no_validos`: Entradas inválidas, errores esperados
3. **Ejecutar herramienta**: Llamar a `generate_test_cases` con ruta, objetivo y cripticidad
4. **Presentar resultados**: Mostrar los casos propuestos citando las fuentes reales consultadas

## Criterios de Entrada
- **Objetivo requerido**: Debe especificarse una función, clase, componente o escenario claro
- **Ruta del proyecto**: Debe estar dentro de la Allowlist autorizada
- **Cripticiad válida**: Debe ser uno de: `happy_path`, `edge_cases`, `usuarios_no_validos`

## Criterios de Aceptación de los Casos Generados
Cada caso propuesto DEBE cumplir:
1. **Cita fuente real**: Referenciar al menos un archivo real del proyecto (`fuentes`)
2. **Estructura válida**: Tener `descripcion`, `entrada_esperada`, `resultado_esperado`, `tipo`
3. **Tipo coherente**: El `tipo` debe coincidir con la cripticidad solicitada
4. **Basado en evidencia**: No inventar código ni comportamientos no existentes
5. **Ejecutable conceptualmente**: La `entrada_esperada` debe ser código sintácticamente válido

## Manejo de Casos Especiales

### Sin Código Relevante Encontrado
Si la herramienta retorna `fuentes: []` y `casos_propuestos: []`:
- Informar al usuario: "No se encontró código relevante para [objetivo] en el proyecto"
- Sugerir: "Verifica que la función/componente exista en la ruta especificada"
- NO inventar casos de prueba

### Error de LLM Backend
Si la generación falla por error de LLM:
- La herramienta retorna casos básicos deterministas (fallback) si hay fuentes
- Informar: "Se generaron casos básicos basados en el código real (LLM no disponible)"

### Objetivo Ambiguo
Si el usuario no especifica claramente qué testear:
- Preguntar: "¿Para qué función o componente específico deseas generar casos?"
- Listar funciones/componentes encontrados si hay coincidencias parciales

## Ejemplos de Uso

### Usuario: "Genera tests para la función sumar"
```json
{
  "ruta": "/proyecto",
  "objetivo": "función sumar",
  "cripticidad": "happy_path"
}
```

### Usuario: "Crea edge cases para validar_email"
```json
{
  "ruta": "/proyecto",
  "objetivo": "validar_email",
  "cripticidad": "edge_cases"
}
```

### Usuario: "Tests de entrada inválida para el login"
```json
{
  "ruta": "/proyecto",
  "objetivo": "login",
  "cripticidad": "usuarios_no_validos"
}
```

## Integración con Otras Skills
- **Precede a**: `qa-test-analysis` (los casos generados pueden usarse para analizar cobertura)
- **Relacionada con**: `qa-coverage` (verificar cobertura de los casos generados)
- **Fuente de**: `run_tests` (los casos generados pueden ejecutarse)

## Notas de Implementación (Solo Referencia)
- La herramienta `generate_test_cases` identifica fuentes determinísticamente (sin LLM)
- La redacción en lenguaje natural se delega a `LLMBackend`
- Los casos son **sugerencias**, no tests ejecutables directos
- Respeta Alwayslist (FR-025) - no accede fuera del perímetro autorizado