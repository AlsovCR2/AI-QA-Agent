# AI QA & Software Engineering Agent

## Contexto

El desarrollo de software y el aseguramiento de la calidad requieren realizar constantemente tareas de análisis, exploración y validación sobre los proyectos.

Un desarrollador o profesional de QA puede necesitar comprender rápidamente la estructura de un proyecto, localizar archivos y componentes específicos, revisar código, buscar patrones, ejecutar pruebas automatizadas, analizar errores y generar casos de prueba.

Muchas de estas actividades requieren recorrer manualmente diferentes archivos, ejecutar comandos, interpretar resultados y relacionar información proveniente de distintas partes del proyecto.

Con la incorporación de modelos de inteligencia artificial capaces de razonar sobre información y utilizar herramientas, es posible construir agentes que colaboren con los profesionales durante estas actividades.

El proyecto **AI QA & Software Engineering Agent** nace con el propósito de explorar cómo un agente de inteligencia artificial puede utilizar herramientas de software para asistir de manera controlada en tareas relacionadas con **Software Engineering y Quality Assurance**.

El agente no pretende reemplazar al desarrollador ni al profesional de QA. Su propósito es actuar como un asistente capaz de analizar información del proyecto, ejecutar determinadas tareas y presentar sus resultados de forma comprensible para el usuario.

---

## Problema

Actualmente, muchas tareas relacionadas con el análisis y validación de software requieren una intervención manual repetitiva.

Entre estas actividades se encuentran:

- Explorar la estructura de un proyecto.
- Localizar archivos, clases, funciones o componentes.
- Buscar patrones específicos dentro del código.
- Revisar diferentes partes de una implementación para comprender su funcionamiento.
- Ejecutar pruebas automatizadas.
- Revisar resultados de pruebas.
- Investigar errores y sus posibles causas.
- Identificar escenarios de prueba que podrían estar faltando.
- Generar casos de prueba.
- Recopilar información para elaborar reportes técnicos.

El problema no consiste únicamente en la cantidad de trabajo manual, sino también en que la información necesaria para realizar estas tareas suele encontrarse distribuida en múltiples archivos, directorios, pruebas y resultados de ejecución.

Esto obliga al profesional a cambiar constantemente entre diferentes herramientas y fuentes de información.

Por ejemplo, ante una prueba automatizada que falla, un profesional puede tener que:

```text
Identificar la prueba fallida
        ↓
Revisar el mensaje de error
        ↓
Analizar el stack trace
        ↓
Localizar el código involucrado
        ↓
Revisar dependencias relacionadas
        ↓
Comprender el comportamiento esperado
        ↓
Determinar una posible causa
        ↓
Proponer escenarios adicionales de prueba
```

Este proceso puede ser repetitivo y consumir tiempo, especialmente en proyectos grandes.

---

## Oportunidad

Los agentes de inteligencia artificial permiten combinar un modelo de lenguaje con herramientas capaces de interactuar con un entorno de software.

En lugar de limitarse a responder preguntas basándose únicamente en el conocimiento del modelo, un agente puede utilizar herramientas para obtener información actual del proyecto y posteriormente utilizar esos resultados para generar una respuesta.

Por ejemplo:

```text
Usuario
   ↓
"¿Por qué está fallando este test?"
   ↓
Agente
   ↓
Analiza el proyecto
   ↓
Localiza la prueba
   ↓
Consulta el código relacionado
   ↓
Ejecuta la prueba
   ↓
Analiza el resultado
   ↓
Explica una posible causa
```

Esto plantea la posibilidad de desarrollar un asistente especializado que ayude a los profesionales de desarrollo y QA a realizar tareas de análisis y validación de manera más eficiente.

---

## Propósito del proyecto

**AI QA & Software Engineering Agent** busca explorar y demostrar cómo puede construirse un agente de inteligencia artificial especializado en tareas de Software Engineering y Quality Assurance utilizando Python.

El proyecto se enfocará inicialmente en un agente sencillo, controlado y orientado a herramientas, que pueda interactuar con un proyecto de software y ayudar al usuario a comprender, analizar y validar diferentes aspectos del mismo.

La primera versión estará enfocada en demostrar el funcionamiento fundamental de un agente:

```text
Usuario
   ↓
Solicitud
   ↓
Agente
   ↓
Selección de herramienta
   ↓
Ejecución
   ↓
Resultado
   ↓
Análisis
   ↓
Respuesta
```

El proyecto también servirá como base para estudiar posteriormente conceptos más avanzados de **Agentic AI**, incluyendo memoria, MCP, RAG, observabilidad, human-in-the-loop y sistemas multi-agente.

---

## Instalación y uso

El agente se instala como paquete Python (`qa-agent`) y se invoca desde cualquier
proyecto de software que se quiera analizar, sin añadir código ni dependencias al
destino.

```bash
# Desde la raíz del repositorio del agente
pip install .            # o: pipx install .

# Desde el directorio del proyecto que se quiere analizar
qa-agent --ruta .                        # REPL interactivo sobre el proyecto
qa-agent --ruta . --demo                 # modo demo con FakeLLM (sin API key)
qa-agent --ruta . --pregunta "¿cuál es la estructura?"   # consulta puntual
qa-agent --version                       # versión instalada
```

### Argumentos

| Flag | Descripción |
|------|-------------|
| `--ruta <dir>` | Raíz del proyecto a analizar (por defecto, el directorio de trabajo actual). |
| `--pregunta "<texto>"` | Consulta puntual; omite el REPL y responde directamente (útil en scripts/CI). |
| `--demo` | Fuerza `FakeLLM` (validación sin LLM real ni API key). |
| `--version` | Muestra la versión instalada. |

### Credenciales

El agente lee sus credenciales de sus propias variables de entorno (nunca del
proyecto destino), usando `python-dotenv` sobre `.env`:

```bash
# Proveedor por defecto (DeepSeek)
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_API_KEY=sk-tu_llave_deepseek
```

Sin `LLM_API_KEY` (o con `--demo`) el agente arranca con `FakeLLM`, un backend
determinista sin red que permite validar todo el flujo y los tests sin depender
de un proveedor real (SC-006).

### Validación rápida

Con un proyecto de ejemplo en `tests/fixtures/proyecto_ejemplo`:

```bash
qa-agent --ruta tests/fixtures/proyecto_ejemplo --demo --pregunta "¿cuál es la estructura del proyecto?"
qa-agent --ruta tests/fixtures/proyecto_ejemplo --demo --pregunta "ejecuta las pruebas del proyecto"
```

La guía completa de validación de extremo a extremo está en
`specs/001-core-ai-qa-agent/quickstart.md` (validaciones UC-001..UC-010).