# Skills de QA/Testing - Catálogo

Este directorio contiene las Skills (metodologías, criterios y procedimientos)
que orientan al agente sobre cómo usar sus herramientas QA/Testing.

## Separación Herramienta vs. Skill

- **Herramienta** (ejecución): Implementada en `src/qa_agent/tools/`. Contiene
  la lógica determinista de ejecución, validación de contratos y manejo de
  Allowlist. No contiene metodología ni criterios de uso.
- **Skill** (procedimiento): Documentada en `.github/skills/` como archivos
  `SKILL.md`. Contiene cuándo activar, cómo secuenciar, criterios de
  aceptación y manejo de casos especiales. No contiene implementación.

Esta separación sigue el principio I (separación de responsabilidades) y la
decisión D9 (`research.md`): las Skills son cargadas por el cliente de IA
(opencode/copilot), no por el código del agente.

## Skills Disponibles

| Skill | Herramienta(s) | Propósito | Archivo |
|-------|----------------|-----------|---------|
| **qa-test-cases** | `generate_test_cases` | Generar casos de prueba sugeridos basados en código real | [SKILL.md](./qa-test-cases/SKILL.md) |
| **qa-coverage** | `analyze_coverage` | Analizar cobertura de código (global y por archivo) | [SKILL.md](./qa-coverage/SKILL.md) |
| **qa-test-analysis** | `run_tests` + `analyze_test_results` | Ejecutar tests y analizar resultados con causas limitadas a evidencia | [SKILL.md](./qa-test-analysis/SKILL.md) |

## Reglas Transversales

1. **Desacople**: Ningún módulo de `src/qa_agent/tools/` importa desde
   `.github/skills/`. Las Skills son cargadas por el cliente de IA, no por
   el código del agente (D9, principio I).
2. **Honestidad**: Las Skills enfatizan no inventar datos, causas ni
   resultados (FR-019, SC-002).
3. **Seguridad**: Todas las herramientas referenciadas respetan la Allowlist
   de rutas (FR-025) y la allowlist de comandos seguros (SC-011).
4. **Determinismo**: Las operaciones determinísticas (identificación de
   fuentes, resumen cuantitativo, ejecución de comandos) no usan LLM (VI,
   SC-010). Solo la redacción en lenguaje natural puede delegarse al LLM.