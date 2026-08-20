# Diagrama General de Casos de Uso

Diagrama a nivel de sistema de los casos de uso del **AI QA & Software
Engineering Agent**, mostrando los actores y sus interacciones con el sistema.

```mermaid
flowchart LR
    U[Usuario<br/>Desarrollador / QA]

    subgraph S["AI QA & Software Engineering Agent"]
        direction LR
        UC1(UC-001<br/>Recibir solicitud y responder<br/>usando herramientas)
        UC2(UC-002<br/>Explorar la estructura<br/>del proyecto)
        UC3(UC-003<br/>Localizar archivos<br/>y componentes)
        UC4(UC-004<br/>Revisar y buscar<br/>patrones en el código)
        UC5(UC-005<br/>Ejecutar y analizar<br/>pruebas automatizadas)
        UC6(UC-006<br/>Gestionar operaciones<br/>con autorización)
        UC7(UC-007<br/>Informar límites y evitar<br/>inventar información)
        UC12(UC-012<br/>Acciones destructivas<br/>crear/editar/eliminar)
    end

    U --> UC1
    U --> UC2
    U --> UC3
    U --> UC4
    U --> UC5
    U --> UC6
    U --> UC7
    U --> UC12

    UC1 -.incluye.-> UC2
    UC1 -.incluye.-> UC3
    UC1 -.incluye.-> UC4
    UC1 -.incluye.-> UC5
    UC2 -.base para.-> UC3
    UC4 -.habilita.-> UC5

    UC6 -.restricción.-> UC1
    UC6 -.restricción.-> UC5
    UC6 -.restricción.-> UC12
    UC7 -.restricción.-> UC1
    UC7 -.restricción.-> UC2
    UC7 -.restricción.-> UC3
    UC7 -.restricción.-> UC4
    UC7 -.restricción.-> UC5
    UC7 -.restricción.-> UC6
    UC7 -.restricción.-> UC12
```

## Leyenda

- **Actor**: `U` — el usuario (desarrollador o profesional de QA) que inicia la
  interacción con el sistema.
- **Caso de uso**: nodos `UC-XXX` agrupados dentro del límite del sistema.
- **`includes`** (línea punteada): el caso de uso de destino forma parte del
  procesamiento del caso de uso origen como parte de su flujo.
- **`restricción`** (línea punteada): casos de uso transversales cuyas reglas
  condicionan al resto.
