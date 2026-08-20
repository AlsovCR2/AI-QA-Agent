<!--
Sync Impact Report
- Version change: N/A (el archivo anterior contenía únicamente la plantilla sin completar) → 1.0.0
- Principios completados: I. Separación de responsabilidades, II. Modularidad y extensibilidad,
  III. Testabilidad, IV. Seguridad y mínimo privilegio, V. Human-in-the-loop, VI. Determinismo,
  VII. Validación y contratos, VIII. Observabilidad y trazabilidad, IX. Manejo seguro de errores,
  X. Calidad del código, XI. Seguridad de información y credenciales, XII. Evolución incremental,
  XIII. Documentación, XIV. Spec-Driven Development
- Secciones agregadas: Core Principles, Restricciones de Diseño y Alcance,
  Workflow de Desarrollo (Fases del Ciclo de Vida), Governance
- Secciones eliminadas: ninguna
- TODOs diferidos: ninguno
-->

# AI QA & Software Engineering Agent Constitution

## Core Principles

### I. Separación de Responsabilidades

El núcleo del agente, las herramientas, la lógica de negocio y las interfaces
deben mantener responsabilidades claramente separadas.

- Las herramientas ejecutan operaciones concretas y devuelven resultados; no
  contienen lógica propia del agente, no deciden la continuación de la
  conversación ni seleccionan otras herramientas.
- El agente no debe depender directamente de detalles concretos de
  infraestructura cuando pueda evitarse; cualquier dependencia de proveedores,
  frameworks o infraestructura debe quedar aislada tras interfaces estables.
- Cada componente cumple una única responsabilidad bien definida.

*Racional: permite sustituir o evolucionar cada capa (núcleo, herramientas,
infraestructura, LLM) sin reescribir las demás.*

### II. Modularidad y Extensibilidad

El diseño debe permitir agregar, reemplazar o eliminar herramientas sin realizar
cambios importantes en el núcleo del agente.

- Las nuevas capacidades se incorporan como componentes independientes con un
  contrato claro de entrada y salida.
- La adición de una herramienta no debe afectar la estabilidad ni el contrato de
  las herramientas existentes.
- El agente debe poder evolucionar progresivamente, extendiendo sus capacidades
  de forma incremental.

*Racional: garantiza que las capacidades del agente crezcan sin acoplar su
núcleo a cada nueva funcionalidad.*

### III. Testabilidad

Los componentes críticos deben poder probarse de forma independiente.

- Las herramientas deben poder probarse sin depender obligatoriamente de un
  modelo de lenguaje real.
- El comportamiento del agente debe poder validarse mediante pruebas
  automatizadas cuando sea posible; cuando una validación automatizada no sea
  posible, la razón debe quedar documentada.
- Los contratos de entrada y salida deben permitir verificación automatizada.

*Racional: la confiabilidad del agente se demuestra mediante pruebas, no
mediante suposiciones.*

### IV. Seguridad y Mínimo Privilegio

El agente solo debe acceder a los recursos explícitamente autorizados y nunca
debe asumir permisos ilimitados sobre el sistema.

- Cada operación se ejecuta bajo el mínimo privilegio necesario para completarla.
- Las operaciones potencialmente destructivas o irreversibles deben estar
  restringidas y sujetas a protección adicional.
- No se permite la ejecución arbitraria de comandos peligrosos; todo comando que
  pueda afectar el sistema debe estar acotado y justificado.

*Racional: limita el impacto de errores o intenciones maliciosas al mínimo
perímetro posible.*

### V. Human-in-the-loop

Las acciones que puedan modificar, eliminar o afectar información del proyecto
deben requerir autorización explícita cuando corresponda.

- La autonomía del agente nunca debe estar por encima de las políticas de
  seguridad del sistema.
- Las operaciones de escritura o destrucción se suspenden hasta recibir
  confirmación cuando el contexto así lo exija.

*Racional: preserva el control humano sobre las consecuencias irreversibles de
las acciones del agente.*

### VI. Determinismo

Las operaciones que no requieren inteligencia artificial deben resolverse
mediante lógica determinística.

- El modelo de lenguaje debe utilizarse principalmente para interpretación,
  razonamiento, selección de herramientas y generación de respuestas.
- Una misma entrada y estado debe producir el mismo resultado para todas las
  operaciones que no dependen del LLM.
- El LLM no debe usarse para decisiones o cálculos que la lógica determinística
  pueda resolver de forma correcta y verificable.

*Racional: separa lo no determinístico (razonamiento del LLM) de lo que debe ser
predecible y reproducible.*

### VII. Validación y Contratos

Las entradas y salidas de las herramientas deben utilizar estructuras claramente
definidas y validables.

- Los errores deben manejarse explícitamente.
- El agente no debe asumir que una herramienta siempre devuelve información
  válida; cualquier resultado debe validarse antes de ser usado en el
  razonamiento o en la respuesta.

*Racional: los contratos explícitos hacen que las fallas se detecten en el punto
de origen y no se propaguen silenciosamente.*

### VIII. Observabilidad y Trazabilidad

Las acciones relevantes realizadas por el agente deben poder identificarse y
registrarse.

- Debe ser posible conocer qué herramientas utilizó el agente y qué resultados
  obtuvo para facilitar el debugging y la auditoría.
- Los registros deben permitir reconstruir la secuencia de decisiones y llamadas
  que produjeron una respuesta.

*Racional: sin trazabilidad no es posible depurar, auditar ni justificar el
comportamiento del agente.*

### IX. Manejo Seguro de Errores

Un error de una herramienta no debe provocar silenciosamente un comportamiento
incorrecto.

- El agente debe informar cuando no posee suficiente información para responder
  con confianza.
- Está prohibido inventar o fabricar resultados de herramientas, archivos,
  pruebas o información del proyecto que no provengan de una fuente real y
  verificada.

*Racional: la honestidad sobre los límites de lo conocido es un requisito de
confianza del agente.*

### X. Calidad del Código

El código debe mantener una calidad alta y sostenible.

- Aplicar principios SOLID cuando sean apropiados.
- Mantener el código simple y comprensible; evitar abstracciones innecesarias.
- Favorecer composición sobre acoplamiento excesivo.
- Mantener responsabilidades pequeñas y claramente definidas.

*Racional: un código comprensible es más fácil de revisar, probar y ampliar.*

### XI. Seguridad de Información y Credenciales

Las credenciales, API keys, tokens y secretos nunca deben almacenarse
directamente en el código fuente.

- La configuración sensible se gestiona mediante mecanismos apropiados de
  configuración y variables de entorno.
- Los secretos nunca deben aparecer en logs ni en las respuestas del agente.

*Racional: protege la infraestructura y los datos ante cualquier filtración de
artefactos o registros.*

### XII. Evolución Incremental

El MVP debe mantenerse pequeño y enfocado en el problema inicial.

- No se incorporan prematuramente conceptos como multi-agente, RAG, bases
  vectoriales, memoria de largo plazo o MCP si no existe una necesidad concreta
  que los justifique.
- Las nuevas capacidades se incorporan únicamente cuando existe una necesidad
  funcional o técnica justificada.

*Racional: evita complejidad y deuda técnica especulativa en las primeras
iteraciones.*

### XIII. Documentación

Las decisiones arquitectónicas y técnicas importantes deben quedar documentadas.

- La documentación debe mantenerse alineada con la implementación; cualquier
  divergencia debe corregirse.
- La documentación se considera parte de la entrega, no un accesorio opcional.

*Racional: la documentación preserva el conocimiento y reduce el costo de
mantener y ampliar el proyecto.*

### XIV. Spec-Driven Development

La implementación debe estar guiada por las especificaciones del proyecto.

- Las decisiones técnicas deben estar justificadas por los requisitos y
  restricciones definidos en las especificaciones.
- El código no debe introducir funcionalidades fuera del alcance definido sin
  contar con una especificación correspondiente.

*Racional: la especificación es la fuente de verdad para el alcance; el código
debe traducirla, no reemplazarla.*

## Restricciones de Diseño y Alcance

**Independencia del proveedor y del framework.** La constitución y los principios
arquitectónicos deben seguir siendo válidos aunque cambien el modelo de lenguaje,
el framework de agentes o la infraestructura. Las decisiones concretas sobre
tecnología se documentan en las especificaciones y los planes, no en esta
constitución.

**Esta constitución no es un documento de implementación.** No define clases,
módulos, nombres de archivos, APIs concretas ni detalles específicos de
librerías. Esas decisiones pertenecen a las fases de Specification y Plan
respectivas.

**Alcance del proyecto.** El agente es un asistente controlado orientado a
herramientas, enfocado en tareas de análisis, exploración y validación de
proyectos de software en el dominio de Software Engineering y Quality Assurance.
Su propósito es asistir al desarrollador o profesional de QA, no reemplazarlo.

**Fuente de verdad de los resultados.** El agente se apoya en información real
del proyecto obtenida a través de sus herramientas; nunca en conocimiento
inventado sobre el estado del proyecto.

## Workflow de Desarrollo: Fases del Ciclo de Vida

La constitución condiciona cada fase del ciclo de desarrollo, sin reemplazar los
artefactos que cada fase genera.

**Specification**
- Las especificaciones deben describir el comportamiento sin fijar decisiones
  de implementación que queden a criterio posterior.
- Cada requisito debe mapearse explícitamente a los principios de esta
  constitución (seguridad, mínimo privilegio, contratos, alcance).
- El alcance del MVP se limita conforme al principio XII; cualquier capacidad
  fuera del alcance debe justificarse con su necesidad concreta.

**Planning**
- El plan descompone el trabajo preservando la separación de responsabilidades
  (principio I) y la modularidad (principio II).
- La ruta de implementación debe considerar la testabilidad (principio III)
  desde el inicio, indicando cómo se verificará cada componente.
- Las decisiones técnicas se justifican en términos de requisitos y de esta
  constitución, no por preferencia arbitraria.

**Tasks**
- Cada tarea debe ser la unidad mínima con una responsabilidad claramente
  definida.
- Las tareas que tocan seguridad, credenciales, human-in-the-loop o contratos
  deben marcar explícitamente sus restricciones y requisitos de validación.
- Ninguna tarea debe introducir funcionalidad nueva sin especificación.

**Implementation**
- La implementación traduce la especificación; no introduce funcionalidades
  fuera de alcance (principio XIV).
- Los secretos se mantienen fuera del código (principio XI); las acciones
  destructivas requieren autorización (principio V).
- La lógica determinística se implementa sin depender del LLM (principio VI), y
  el código cumple con los principios de calidad (principio X).

**Verification**
- La verificación verifica el comportamiento documentado y esperado, incluyendo
  manejo de errores (principio IX) y validación de contratos (principio VII).
- Los componentes críticos se prueban de forma independiente; las herramientas
  sin un LLM real (principio III).
- La revisión verifica cumplimiento de seguridad, mínimo privilegio y
  observabilidad (principios IV, VIII).

## Governance

Esta constitución prevalece sobre cualquier otra práctica, patrón o preferencia
del equipo. Toda especificación, plan, tarea, implementación y verificación debe
ser evaluada contra los principios aquí definidos.

**Procedimiento de enmienda.** Toda modificación de esta constitución requiere
una propuesta por escrito, revisión y aprobación explícita. Las enmiendas deben
documentar el impacto sobre las fases afectadas.

**Política de versionado.** La versión se incrementa siguiendo versionado
semántico:
- **MAJOR**: eliminación o redefinición de principios.
- **MINOR**: adición de principios o ampliación de guías.
- **PATCH**: aclaraciones o refinamientos sin cambio de significado.

**Revisión de cumplimiento.** Los PRs, revisiones y verificaciones deben
confirmar conformidad con la constitución. La complejidad no justificada por los
requisitos es motivo de rechazo. Las violaciones se corrigen antes de aceptar el
cambio.

**Version**: 1.0.0 | **Ratified**: 2026-08-11 | **Last Amended**: 2026-08-11