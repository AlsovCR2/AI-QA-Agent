# Contratos de Herramientas — Core AI QA & Software Engineering Agent

Producción del `/speckit-plan` (Phase 1). Define el contrato general de
herramienta y el contrato específico de cada herramienta del MVP. Estos
contratos materializan el principio VII (Validación y contratos), la
testabilidad sin LLM (III / SC-006) y el determinismo (VI / SC-010).

## Contrato general de herramienta

Toda herramienta **debe** exponer una interfaz con los siguientes elementos:

- `id` (`str`): identificador único.
- `descripcion` (`str`): cuándo usar la herramienta y qué hace (para selección).
- `esquema_entrada`: esquema JSON validable de los parámetros.
- `esquema_salida`: esquema JSON validable del resultado.
- `requiere_autorizacion` (`bool`): si la ejecución es una acción sensible.
- `ejecutar(parametros) -> ResultadoDeHerramienta`: función pura determinística
  sobre el filesystem permitido.

**Reglas (FR-005, VII, SC-006)**
1. La herramienta **no** contiene lógica del agente ni selecciona otras
   herramientas (principio I).
2. El resultado se valida contra `esquema_salida` antes de usarse.
3. La herramienta opera únicamente sobre rutas dentro de su allowlist
   (FR-025, IV, SC-011).
4. La herramienta no debe depender del LLM (III, VI, SC-006).
5. Los secretos en las salidas se detectan/redactan (FR-021).

## Contrato: `explore`

**Propósito**: explorar la estructura del proyecto (UC-002).

**Entrada**
```json
{
  "ruta": {"type": "string", "description": "Raíz del proyecto a explorar"},
  "profundidad_max": {"type": "integer", "minimum": 1, "maximum": 8}
}
```

**Salida**
```json
{
  "ruta": {"type": "string"},
  "existe": {"type": "boolean"},
  "accesible": {"type": "boolean"},
  "elementos": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "nombre": {"type": "string"},
        "tipo": {"type": "string", "enum": ["archivo", "directorio"]},
        "ruta_relativa": {"type": "string"}
      }
    }
  }
}
```

**Reglas**
- Reporta únicamente información real de la estructura existente (FR-008,
  SC-003).
- Si `existe == false` o `accesible == false`, el agente informa que no puede
  acceder en lugar de inventar contenido (UC-002 flujo alternativo).
- Error explícito si la `ruta` está fuera de la allowlist.

## Contrato: `locate`

**Propósito**: localizar archivos, clases, funciones o componentes (UC-003).

**Entrada**
```json
{
  "patron": {"type": "string"},
  "ruta": {"type": "string"},
  "tipo": {"type": "string", "enum": ["archivo", "clase", "funcion", "componente", "cualquiera"]}
}
```

**Salida**
```json
{
  "coincidencias": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "ruta_relativa": {"type": "string"},
        "linea": {"type": "integer"},
        "tipo": {"type": "string"},
        "nombre": {"type": "string"}
      }
    }
  }
}
```

**Reglas**
- Devuelve **solo** coincidencias reales existentes (FR-008, SC-003).
- Si no hay coincidencias (`coincidencias == []`), el agente informa la
  ausencia sin fabricar concordancias (FR-008, UC-007, SC-002).

## Contrato: `search`

**Propósito**: revisar y buscar patrones en el código, presentando el contenido
fiel al proyecto (UC-004).

**Entrada**
```json
{
  "patron_regex": {"type": "string"},
  "ruta": {"type": "string"},
  "contexto_lineas": {"type": "integer", "minimum": 0, "maximum": 20},
  "max_ocurrencias": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 200}
}
```

**Salida**
```json
{
  "ocurrencias": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "ruta_relativa": {"type": "string"},
        "linea": {"type": "integer"},
        "contexto": {"type": "string"}
      }
    }
  },
  "nota": {"type": "string", "description": "Aviso de truncado al alcanzar max_ocurrencias"}
}
```

**Reglas**
- Presenta el contenido de código tal como existe, sin alterarlo (FR-011,
  SC-002).
- La búsqueda es determinística (VI, SC-010).
- Si no hay ocurrencias, se informa la ausencia sin inventar contenido
  (FR-008, UC-007).
- `max_ocurrencias` acota el volcado (evita saturar la observación del LLM con
  coincidencias masivas) y, al alcanzarse, la salida incluye `nota` con el
  aviso de truncado (FR-019, honestidad).

## Contrato: `run_tests`

**Propósito**: ejecutar y analizar pruebas automatizadas sobre un conjunto
autorizado (UC-005).

**Entrada**
```json
{
  "ruta": {"type": "string"},
  "conjunto_autorizado": {"type": "boolean"},
  "comando_pruebas": {"type": "string", "description": "Comando autorizado y acotado (p. ej. 'pytest')"}
}
```

**Salida**
```json
{
  "pasadas": {"type": "integer"},
  "falladas": {"type": "integer"},
  "errores": {"type": "integer"},
  "total": {"type": "integer"},
  "estado_global": {"type": "string", "enum": ["exito", "fallo", "no_ejecutado"]},
  "detalle_fallos": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "nombre": {"type": "string"},
        "mensaje_error": {"type": "string"},
        "ruta_relativa": {"type": "string"}
      }
    }
  }
}
```

**Reglas**
- Solo ejecuta sobre **conjuntos autorizados** (FR-012, FR-025, SC-011).
- Ejecutar pruebas es una acción sensible porque ejecuta código objetivo. El
  agente debe obtener autorización explícita antes de invocar esta herramienta,
  incluso cuando la invocación se origine desde una ruta de análisis
  (`analyze_test_results`) (FR-015/016, SC-004).
- Reporta el **estado real** de la ejecución (FR-013, SC-002).
- Los fallos se reportan explícitamente y las causas se delimitan a lo que la
  evidencia sustenta (FR-014). No se atribuyen causas no respaldadas (UC-007).
- Si no puede ejecutarse (`estado_global == no_ejecutado`), se informa
  explícitamente (FR-017/018).
- El `comando_pruebas` se valida contra una allowlist de comandos seguros;
  nunca es un comando arbitrario del usuario (IV, SC-011).

---

## Contrato: `analyze_test_results`

**Propósito**: analizar los resultados de una ejecución de pruebas y resumir
fallos, errores y tendencias, delimitando causas a lo que la evidencia sustenta
(UC-005; amplía el análisis de `run_tests`).

**Entrada**
```json
{
  "ruta": {"type": "string"},
  "resultado_tests": {
    "type": "object",
    "properties": {
      "pasadas": {"type": "integer"},
      "falladas": {"type": "integer"},
      "errores": {"type": "integer"},
      "detalle_fallos": {"type": "array"}
    }
  }
}
```

**Salida**
```json
{
  "resumen": {"type": "string", "description": "Resumen cuantitativo del estado real"},
  "fallos_agrupados": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "ruta_relativa": {"type": "string"},
        "error_comun": {"type": "string"},
        "posible_causa": {"type": "string", "description": "Causa respaldada por evidencia o 'sin evidencia suficiente'"}
      }
    }
  }
}
```

**Reglas**
- El análisis cuantitativo (resumen, agrupación por ruta) es **determinista**
  (VI / SC-010).
- Las `posible_causa` se limitan a lo que la evidencia sustenta; si no hay
  evidencia, se indica "sin evidencia suficiente" (FR-014, UC-007).
- Solo usa resultados y rutas reales; nunca inventa fallos ni causas (FR-019).
- Si esta capacidad necesita obtener resultados ejecutando `run_tests`, la
  autorización de ejecución sigue siendo obligatoria; el análisis no puede
  omitir ni heredar implícitamente una autorización inexistente (FR-015/016).

---

## Contrato: `generate_test_cases`

**Propósito**: generar casos de prueba sugeridos para una función/componente o
para cubrir escenarios faltantes (FR-014 ampliado; oportunidad del README).

**Entrada**
```json
{
  "ruta": {"type": "string"},
  "objetivo": {"type": "string", "description": "Función/componente o escenario a cubrir"},
  "cripticidad": {"type": "string", "enum": ["happy_path", "edge_cases", "usuarios_no_validos"]}
}
```

**Salida**
```json
{
  "casos_propuestos": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "descripcion": {"type": "string"},
        "entrada_esperada": {"type": "string"},
        "resultado_esperado": {"type": "string"},
        "tipo": {"type": "string", "enum": ["happy_path", "edge_case", "negativo"]}
      }
    }
  },
  "fuentes": {"type": "array", "items": {"type": "string"}, "description": "Código real del proyecto consultado como evidencia"}
}
```

**Reglas**
- **Separación de responsabilidades**: la herramienta identifica el código
  real relevante (`fuentes`) de forma determinista; la **generación de los
  casos en lenguaje natural es la única parte que puede delegarse al LLM**
  vía `LLMBackend` (VI).
- Los `casos_propuestos` son **sugerencias** que deben basarse en el código real
  citado (FR-019, IX); el agente nunca inventa código inexistente como fuente.
- Respeta la `Allowlist` (FR-025). La generación de casos es una acción no
  destructiva (no requiere autorización).

---

## Contrato: `analyze_coverage`

**Propósito**: analizar la cobertura de código de las pruebas del proyecto,
reportando cobertura real por archivo/módulo (SC-006/SC-003 transversales).

**Entrada**
```json
{
  "ruta": {"type": "string"},
  "comando_cobertura": {"type": "string", "description": "Comando autorizado y acotado (p. ej. 'pytest --cov=src')"}
}
```

**Salida**
```json
{
  "cobertura_global": {"type": "number", "description": "Porcentaje 0-100"},
  "por_archivo": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "ruta_relativa": {"type": "string"},
        "cobertura": {"type": "number"},
        "lineas_faltantes": {"type": "array", "items": {"type": "integer"}}
      }
    }
  },
  "estado": {"type": "string", "enum": ["exito", "error", "no_ejecutado"]}
}
```

**Reglas**
- Solo ejecuta comandos autorizados y acotados (`comando_cobertura`) dentro de
  una allowlist de comandos seguros (FR-025, SC-011, IV).
- Ejecutar cobertura es una acción sensible porque ejecuta código objetivo; la
  herramienta requiere autorización explícita previa (FR-015/016, SC-004).
- Reporta cobertura **real** (FR-019, SC-002); si no puede ejecutarse
  (`estado == no_ejecutado`), se informa explícitamente (FR-017/018).
- Determinística (VI / SC-010).
- `run_tests` y `analyze_coverage` operan sobre repositorios de confianza y
  ejecutan en el host. Este contrato no ofrece aislamiento de proceso, red,
  credenciales ni filesystem.

---

## Contrato: `leer_archivo`

**Propósito**: leer el contenido real de un archivo del proyecto (US-14 /
FR-048 / SC-025). Es la base de las respuestas **profundas** al explicar o
entender el código (qué hace una capa, qué pruebas cubre un módulo), junto con
`search` y `locate`.

**Entrada**
```json
{
  "ruta": {"type": "string", "description": "Raíz del proyecto a autorizar (allowlist)"},
  "archivo_relativo": {"type": "string", "description": "Ruta del archivo relativa a la raíz"},
  "max_lineas": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200}
}
```

**Salida**
```json
{
  "archivo": {"type": "string", "description": "Ruta relativa normalizada"},
  "existe": {"type": "boolean"},
  "contenido": {"type": "string", "description": "Contenido real del archivo ('' si no existe)"},
  "total_lineas": {"type": "integer"},
  "truncado": {"type": "boolean", "description": "True si se limitó a max_lineas"}
}
```

**Reglas**
- Devuelve el contenido **real** tal como existe, sin alterarlo (FR-011 /
  SC-003). El contenido puede truncarse por `max_lineas`; el truncado SIEMPRE
  se indica (`truncado=true` + `"\n… [N líneas más] …\n"`) y nunca se presenta
  como el archivo completo (FR-019).
- Archivo inexistente → `existe=false` y `contenido=""` (informa ausencia, no
  inventa contenido, FR-008 / UC-007). Sin `archivo_relativo` → error explícito.
- Opera SOLO dentro de la allowlist (FR-025 / SC-011): valida tanto la raíz como
  el archivo resuelto (rechaza `..`, symlinks y rutas fuera del perímetro).
- Herramienta de **solo lectura**: `requiere_autorizacion=False` (no modifica
  nada; no aplica human-in-the-loop).
- Determinística (VI / SC-010). Testable sin LLM (SC-006).
- El contenido leído puede incluir secretos (p. ej. un `.env`); se excluyen por
  defecto los directorios/archivos sensibles de la allowlist y la redacción
  sigue aplicándose en respuestas/historial (FR-021 / SC-008).

---

## Contrato: `crear_archivo`

**Propósito**: crear un archivo nuevo dentro del proyecto con el contenido
indicado (Phase 14, US-13 / FR-042 / SC-021). Acción **destructiva** que
modifica el estado del proyecto → **requiere autorización explícita**
(FR-046 / SC-004 / UC-006).

**Entrada**
```json
{
  "ruta": {"type": "string", "description": "Raíz del proyecto a autorizar (allowlist)"},
  "archivo_relativo": {"type": "string", "description": "Ruta del archivo a crear, relativa a la raíz"},
  "contenido": {"type": "string", "description": "Contenido a escribir en el archivo"}
}
```

**Salida**
```json
{
  "archivo": {"type": "string", "description": "Ruta relativa normalizada"},
  "creado": {"type": "boolean"},
  "existia": {"type": "boolean"}
}
```

**Reglas**
- Crea el archivo con su contenido **real** (FR-042). Si el archivo **ya
  existe**, se rechaza SIN modificar nada (FR-042 / SC-024).
- Opera SOLO dentro de la allowlist (FR-025 / SC-022): valida la raíz y el
  archivo resuelto (rechaza `..`, symlinks y path traversal).
- `requiere_autorizacion=True` (FR-046 / SC-004). Sin contenido o sin archivo →
  error explícito sin ejecutar (FR-019 / SC-002).
- Determinística (VI / SC-010). Testable sin LLM (SC-006).

---

## Contrato: `editar_archivo`

**Propósito**: modificar el contenido de un archivo existente (Phase 14,
US-13 / FR-043 / SC-021). Acción **destructiva** → **requiere autorización
explícita** (FR-046 / SC-004 / UC-006) y **respalda el estado previo** en
`.qa-backup/` antes de modificar (FR-045 / SC-023).

**Entrada**
```json
{
  "ruta": {"type": "string", "description": "Raíz del proyecto a autorizar (allowlist)"},
  "archivo_relativo": {"type": "string", "description": "Ruta del archivo a editar, relativa a la raíz"},
  "contenido": {"type": "string", "description": "Contenido nuevo a escribir"}
}
```

**Salida**
```json
{
  "archivo": {"type": "string", "description": "Ruta relativa normalizada"},
  "editado": {"type": "boolean"},
  "existia": {"type": "boolean"},
  "backup": {"type": "string", "description": "Ruta del respaldo en .qa-backup/ (restaurable)"}
}
```

**Reglas**
- Edita el archivo con el contenido nuevo **real** (FR-043). Si el archivo **no
  existe**, se rechaza SIN modificar nada (FR-043 / SC-024).
- **Backup** del contenido original en `.qa-backup/` antes de modificar
  (FR-045 / SC-023); ante fallo a mitad de camino se reporta y el backup queda
  disponible para restaurar (FR-047).
- Opera SOLO dentro de la allowlist (FR-025 / SC-022): rechaza `..`, symlinks y
  rutas fuera del perímetro.
- `requiere_autorizacion=True` (FR-046 / SC-004). Sin contenido nuevo → error
  explícito sin ejecutar (FR-019 / SC-002).
- Determinística (VI / SC-010). Testable sin LLM (SC-006).

---

## Contrato: `eliminar_archivo`

**Propósito**: eliminar un archivo existente del proyecto (Phase 14, US-13 /
FR-044 / SC-021). Acción **destructiva** → **requiere autorización explícita**
(FR-046 / SC-004 / UC-006) y **respalda el estado previo** en `.qa-backup/`
antes de eliminar (FR-045 / SC-023).

**Entrada**
```json
{
  "ruta": {"type": "string", "description": "Raíz del proyecto a autorizar (allowlist)"},
  "archivo_relativo": {"type": "string", "description": "Ruta del archivo a eliminar, relativa a la raíz"}
}
```

**Salida**
```json
{
  "archivo": {"type": "string", "description": "Ruta relativa normalizada"},
  "eliminado": {"type": "boolean"},
  "backup": {"type": "string", "description": "Ruta del respaldo en .qa-backup/ (restaurable)"}
}
```

**Reglas**
- Elimina el archivo real (FR-044). Si el archivo **no existe** (o es un
  directorio), se rechaza SIN modificar nada (FR-044 / SC-024).
- **Backup** del contenido original en `.qa-backup/` antes de eliminar
  (FR-045 / SC-023); ante fallo se reporta y el backup queda disponible
  (FR-047).
- Opera SOLO dentro de la allowlist (FR-025 / SC-022): rechaza `..`, symlinks y
  rutas fuera del perímetro.
- `requiere_autorizacion=True` (FR-046 / SC-004). Sin archivo → error explícito
  sin ejecutar (FR-019 / SC-002).
- Determinística (VI / SC-010). Testable sin LLM (SC-006).

---

## Nota de alcance

Estas herramientas amplían el `run_tests` del MVP hacia capacidades QA/Testing
de generación de casos, análisis de resultados y cobertura. Se incorporan como
componentes modulares (principio II): no alteran el contrato ni la estabilidad de
las herramientas existentes (`explore`, `locate`, `search`, `run_tests`).
