"""Puente entre la CLI y el harness de evaluación (T221 / FR-117).

Se mantiene en un módulo aparte y con importación diferida desde `main.py` para
que el arranque normal del agente no pague el coste de importar el harness ni
sus datos: evaluar es una operación de verificación, no del uso cotidiano.
"""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table

from qa_agent.evaluacion.harness import ejecutar_evaluacion

#: Código de salida cuando alguna tarea puntúa por debajo del umbral. Permite
#: usar `qa-agent --eval` como gate de CI sin envolverlo en un script.
UMBRAL_APROBACION = 0.75


def ejecutar_evaluacion_cli(ruta: str, demo: bool, salida_json: bool) -> int:
    """Ejecuta la evaluación y la reporta. Devuelve el código de salida."""
    try:
        informe = ejecutar_evaluacion(base=ruta or None, demo=demo)
    except FileNotFoundError as error:
        mensaje = f"No se encontró el conjunto de evaluación: {error}"
        if salida_json:
            print(json.dumps({"error": mensaje}, ensure_ascii=False))
        else:
            Console().print(f"[red]{mensaje}[/red]")
        return 2

    if salida_json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        _render_tabla(informe)

    return 0 if informe["resumen"]["puntuacion_global"] >= UMBRAL_APROBACION else 1


def _render_tabla(informe: dict) -> None:
    consola = Console()
    tabla = Table(title="Evaluación del agente", show_lines=False)
    for columna in ("Tarea", "Ecosistema", "Herram.", "Anclaje", "Seguridad", "Pasos", "Total"):
        tabla.add_column(columna)
    for tarea in informe["tareas"]:
        tabla.add_row(
            tarea["id"],
            tarea["ecosistema"],
            f"{tarea['acierto_herramienta']:.2f}",
            f"{tarea['anclaje_evidencia']:.2f}",
            f"{tarea['seguridad']:.2f}",
            f"{tarea['eficiencia_pasos']:.2f}",
            f"{tarea['puntuacion']:.2f}",
        )
    consola.print(tabla)
    resumen = informe["resumen"]
    consola.print(
        f"Tareas: {resumen['tareas']}  ·  "
        f"Puntuación global: [bold]{resumen['puntuacion_global']:.2f}[/bold]"
    )
    for tarea in informe["tareas"]:
        for nota in tarea["notas"]:
            consola.print(f"  [yellow]{tarea['id']}: {nota}[/yellow]")
