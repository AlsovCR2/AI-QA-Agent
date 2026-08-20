# Contrato: LLM Backend — Core AI QA & Software Engineering Agent

Producción del `/speckit-plan` (Phase 1). Define la interfaz que aísla al
proveedor del modelo de lenguaje del núcleo del agente, garantizando la
independencia del proveedor (constitución) y la testabilidad sin LLM real (III /
FR-003 / SC-006).

## Interfaz `LLMBackend` (Strategy)

```
interface LLMBackend:
    nombre: str                      # identificador del backend (p. ej. "openai", "fake")
    requiere_api_key: bool           # si necesita credenciales externas
    proveedor_requerido: bool        # false para FakeLLM (pruebas)

    # Interpreta la solicitud del usuario en una acción de agente
    interpretar(solicitud: Solicitud) -> Intencion

    # Selecciona la herramienta adecuada entre las disponibles
    seleccionar_herramienta(solicitud: Solicitud, herramientas: list[Herramienta]) -> Seleccion

    # Genera la respuesta final basada en resultados reales
    generar_respuesta(solicitud: Solicitud, resultados: list[Resultado]) -> RespuestaDelAgente
```

## Reglas del contrato

1. **El núcleo depende solo de la interfaz**, nunca de una implementación
   concreta del proveedor (principio de independencia del proveedor/framework).
2. **El LLM solo interviene en interpretación, selección y generación de
   respuesta** (principio VI). Nunca en operaciones determinísticas (explorar,
   localizar, buscar, ejecutar pruebas).
3. **Sin LLM real en pruebas**: las herramientas y el ciclo determinista se
   prueban con `FakeLLM` (III / SC-006).
4. La selección de herramienta devuelve un `id` de herramienta existente o una
   señal de "ninguna herramienta adecuada" (FR-022/023, SC-009).
5. La generación de respuesta recibe solo resultados **validados**; el backend
   no puede presentar contenido inventado como real (IX).

## Implementaciones

### `FakeLLM` (pruebas)

- `requiere_proveedor = false`.
- Devuelve selecciones configurables (scripted) para testear el bucle, el
  historial visible, la autorización y la honestidad de forma determinista.

### `OpenAICompatibleBackend` (producción — backend por defecto)

Proveedor real vía API de **Chat Completions**, compatible con cualquier
servicio que exponga una API OpenAI-compatible. El **proveedor por defecto es
DeepSeek**; NVIDIA NIM y OpenAI se soportan como alternativas cambiando solo la
configuración de entorno.

- `requiere_proveedor = true`, `requiere_api_key = true`.
- Usa la API de Chat Completions para las tres operaciones (interpretar,
  seleccionar, generar respuesta).
- Se configura íntegramente por variables de entorno (`.env`, vía
  `python-dotenv`), **nunca** por valores en código (XI):

| Variable | Descripción | Defecto |
|----------|-------------|---------|
| `LLM_BASE_URL` | URL base del proveedor compatible OpenAI | `https://api.deepseek.com` (DeepSeek) |
| `LLM_API_KEY` | Clave de API del proveedor | requerida |
| `LLM_MODEL` | Identificador del modelo | `deepseek-v4-flash` |

**Proveedores soportados (misma implementación, distinta configuración):**

| Proveedor | `LLM_BASE_URL` | `LLM_MODEL` ejemplo | Notas |
|-----------|----------------|---------------------|-------|
| **DeepSeek** (defecto) | `https://api.deepseek.com` (o `/v1`) | `deepseek-v4-flash` o `deepseek-v4-pro` | Proveedor principal. |
| **NVIDIA NIM** (opcional, gratis) | `https://integrate.api.nvidia.com/v1` | `deepseek-ai/deepseek-v4-flash`, `deepseek-ai/deepseek-v4-pro`, `mistralai/mistral-medium-3.5-128b` | Free tier con créditos iniciales; deepseek disponible gratis vía NIM. |
| **OpenAI** (opcional) | `https://api.openai.com/v1` | `gpt-4o-mini`, `gpt-4o`, `gpt-5-mini` | Alternativa de pago por tokens. |

- Los prompt y respuestas pasan por el `Redactor` (XI / FR-021).
- Si `LLM_API_KEY` falta, se falla con error explícito en producción (no
  silencioso); en modo `--demo` se usa `FakeLLM`.

## Transversal: contextos seguros

Toda entrada booleana a los métodos (p. ej. historial para debugging) pasa por
el `Redactor` antes de enviarse o guardarse (XI / FR-021). El backend no debe
emitir secretos de vuelta.
