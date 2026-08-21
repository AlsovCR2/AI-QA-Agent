# ADR-009: Registro declarativo de ecosistemas (T223–T225)

- Status: Accepted
- Date: 2026-08-21
- Related: `specs/002-production-readiness/spec.md` (FR-122–124),
  `src/qa_agent/tools/runner_registry.py`,
  `src/qa_agent/agent/runner_detection.py`,
  `tests/unit/test_runner_registry.py`
- Principios: IV (mínimo privilegio / allowlist), VI (determinismo),
  X (extender por datos, no por ramas), FR-019 (no inventar lo que no se sabe)

## Contexto

La detección de runner vivía en `agent/runner_detection.py` como una cadena de
`if`, con un bloque por ecosistema y funciones casi gemelas para pruebas y
cobertura. Añadir JS/TS, Go y Rust habría triplicado esa cadena y obligado a
tocar dos funciones paralelas por cada ecosistema nuevo — la forma más fiable de
que ambas acaben discrepando.

## Decisión

Un ecosistema pasa a ser **una fila de datos**: `Ecosistema(id, nombre,
marcadores, pruebas, cobertura)`. La tupla `ECOSISTEMAS` es el registro
completo; `runner_detection.py` queda cableado a él.

## Ruling: detección por manifiesto, nunca por extensión de archivo

Un ecosistema se reconoce porque existe su archivo de proyecto en disco
(`pom.xml`, `go.mod`, `Cargo.toml`, …), no por qué extensiones abundan.

Contar extensiones es una heurística que falla justo en los repos donde más
importa acertar: un proyecto Maven con un script `.py` de utilidades, un
proyecto Go con más YAML que Go. El manifiesto es una declaración explícita del
autor del proyecto; el recuento de archivos es una inferencia sobre ella.

## Ruling: el orden de la tupla ES la política de desempate

Se ordena de más específico a más genérico, y Python va el último. En un
repositorio políglota, un `pom.xml` gana a un `requirements.txt` porque un
proyecto Java con scripts auxiliares es más común que lo contrario. Python
cierra la lista porque es el ecosistema por defecto del agente y sus marcadores
aparecen dentro de proyectos de otros lenguajes con frecuencia.

Hacer el orden significativo (en vez de un `dict` más un mapa de prioridades
aparte) mantiene la política en un solo sitio legible. El coste es que reordenar
la tupla cambia comportamiento: por eso está dicho en el docstring del módulo y
cubierto por tests de desempate.

## Ruling: `cobertura=None` en vez de un comando plausible

Gradle y Rust tienen `cobertura=None`. Gradle expone JaCoCo pero el comando
depende de cómo esté configurado el build; en Rust, `tarpaulin` y `llvm-cov` son
plugins externos que pueden no estar instalados.

Inventar un comando que probablemente falle produce el peor resultado posible:
un fallo de ejecución que parece un fallo del proyecto del usuario. Reportar la
ausencia es información correcta (FR-019). Con ADR-006 en su sitio, esa ausencia
además llega tipada como `causa_no_ejecutado` en vez de un "no ejecutado" mudo.

## Ruling: el registro elige el comando, no lo ejecuta

Este módulo no ejecuta nada ni toca la red: solo mira si hay archivos. La
validación contra la allowlist y la ejecución siguen siendo de
`run_tests`/`analyze_coverage` (principio IV).

Un comando presente aquí y ausente de la allowlist es un error de programación,
no una decisión de configuración — y `test_todo_comando_esta_en_allowlist` lo
convierte en un fallo de test en vez de un rechazo en tiempo de ejecución
delante del usuario.

## Ruling: profundidad máxima de búsqueda 3

Los manifiestos viven en la raíz o a uno o dos niveles (monorepos con
`packages/*`). Buscar en todo el árbol dejaría que un fixture de prueba
enterrado decidiera el ecosistema del repositorio entero. La búsqueda además
respeta `es_directorio_excluido` (ADR-004), así que no entra en `node_modules`
ni en `.venv`, donde hay manifiestos ajenos a puñados.

## Consecuencias

- Ecosistemas cubiertos: Python, .NET, Maven, Gradle, JS/TS, Go y Rust.
- Añadir uno es añadir una fila y su entrada en la allowlist; no hay ramas nuevas.
- `runner_detection.py` deja de ser una cadena de `if` paralela.
- La allowlist crece (T224) manteniendo `shell=False` en todos los casos.
