"""Punto de entrada CLI de `qa-agent` (REPL completo, T024).

Interfaz definida en `contracts/agent-interface-contract.md`. Modos:
- Interactivo (REPL) leyendo solicitudes de stdin en bucle.
- `--pregunta "<texto>"`: consulta puntual y termina.
- `--ruta <dir>`: raíz del proyecto a analizar (default `cwd`).
- `--demo`: fuerza FakeLLM sin API key.

Renderiza la respuesta y el historial visible con `rich` (FR-020).
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from qa_agent import __version__
from qa_agent.agent.conversational import AgentConversacional
from qa_agent.agent.loop import Agent
from qa_agent.agent.reasoning import EstadoTarea
from qa_agent.agent.response import EstadoAccion
from qa_agent.config import (
    construir_allowlist,
    construir_backend,
    construir_herramientas,
)
from qa_agent.logging_config import get_logger
from qa_agent.security.redactor import Redactor

app = typer.Typer(
    name="qa-agent",
    help="AI QA & Software Engineering Agent: asistente de análisis, "
    "exploración y validación de proyectos de software.",
    add_completion=False,
)

_console = Console()


def _acotar_render(texto: str, max_chars: int = 1000) -> str:
    """Recorta una salida para el render, conservando cabecera y cola (T094).

    Evita que el historial de acciones y el razonamiento vuelquen cientos de
    líneas de `explore`/`search` (UC-002), manteniendo legible el panel.
    """
    if len(texto) <= max_chars:
        return texto
    marca = f"… [+{len(texto) - max_chars} chars] …"
    resto = max_chars - len(marca)
    mitad = resto // 2
    return texto[:mitad] + marca + texto[-mitad:]


# Presupuesto de render para lecturas de archivos (T123): un archivo típico
# debe verse completo en el panel "Razonamiento" (igual que el presupuesto del
# contexto LLM), sin el marcador engañoso "[+N chars]" que hacía creer que la
# lectura de la clase falló por truncamiento.
_RENDER_MAX_CHARS_LEER_ARCHIVO = 6000


def _version_callback(value: bool) -> None:
    """Imprime la versión instalada y termina (--version)."""
    if value:
        typer.echo(f"qa-agent {__version__}")
        raise typer.Exit()


def _construir_agente(ruta: str, demo: bool) -> Agent:
    """Construye el `Agent` con backend, herramientas, allowlist y redactor."""
    backend = construir_backend(demo=demo)
    allowlist = construir_allowlist(ruta)
    herramientas = construir_herramientas(ruta, backend=backend)
    redactor = Redactor()
    return Agent(
        backend=backend,
        herramientas=herramientas,
        allowlist=allowlist,
        redactor=redactor,
    )


def _construir_conversacional(
    ruta: str, demo: bool, base_dir: str | None = None
) -> AgentConversacional:
    """Construye el `AgentConversacional` (chat) con su sesión y herramientas."""
    backend = construir_backend(demo=demo)
    allowlist = construir_allowlist(ruta)
    herramientas = construir_herramientas(ruta, backend=backend)
    redactor = Redactor()
    return AgentConversacional(
        backend=backend,
        herramientas=herramientas,
        allowlist=allowlist,
        redactor=redactor,
        base_dir=base_dir,
    )


def _pedir_autorizacion(herramienta_id: str) -> bool:
    """Captura la decisión del usuario (sí/no) ante una acción sensible.

    Defecto seguro: sin confirmación positiva (`True`) la acción NO se ejecuta
    (SC-004 / FR-016). Ante EOF/teclado (stdin no interactivo), se deniega.
    """
    try:
        decision = _console.input(
            f"[yellow]La herramienta '{herramienta_id}' requiere autorización. "
            "¿La autorizas? (sí/no) [no]: [/yellow]"
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return decision in {"si", "sí", "s", "y", "yes"}


def _procesar_solicitud(agente: Agent, texto: str):
    """Procesa una solicitud; si es sensible, captura la decisión del usuario."""
    respuesta = agente.atender(texto)
    pendientes = [
        a
        for a in respuesta.acciones
        if a.estado == EstadoAccion.PENDIENTE_AUTORIZACION
    ]
    if not pendientes:
        return respuesta
    decision = _pedir_autorizacion(pendientes[0].herramienta_id)
    return agente.atender(texto, autorizacion=decision)


_AYUDA_CHAT = """\
Comandos del chat:
  /ayuda             Muestra esta ayuda.
  /tarea add <tit>   Crea una tarea (opcional: --desc="..." --prioridad=N).
  /tarea list        Lista las tareas (opcional: --estado=pendiente).
  /tarea run <id>    Ejecuta la tarea con el agente ReAct (QA) y guarda el resultado.
  /tarea done <id>   Marca una tarea como completada.
  /tarea next <id>   Marca una tarea como en progreso.
  /tarea bloqueada <id>  Marca una tarea como bloqueada.
  /sesion save       Guarda la conversación y muestra su id.
  /sesion list       Lista sesiones guardadas.
  /sesion load <id>  Carga una sesión previa.
  /memoria           Muestra hechos, preferencias y proyectos conocidos.
  /salir             Termina el chat.

Cualquier otra línea se trata como un mensaje de conversación: las intenciones
de análisis QA se delegan al agente ReAct (Phase 12) y la conversación general
se responde directamente con el LLM.
"""


def _ayuda_tareas() -> str:
    return """\
  /tarea add <titulo> [--desc="..."] [--prioridad=N]  Crea una tarea.
  /tarea list [--estado=pendiente|en_progreso|completada|bloqueada]
  /tarea run <id>   Ejecuta la tarea con el agente ReAct y guarda el resultado.
  /tarea done <id>   /tarea next <id>   /tarea bloqueada <id>
"""


def _mostrar_memoria(conversacional: AgentConversacional) -> None:
    memoria = conversacional.memoria
    lineas = [
        f"Hechos: {memoria.hechos or '(vacío)'}",
        f"Preferencias: {memoria.preferencias or '(vacío)'}",
        f"Proyectos conocidos: {memoria.proyectos_conocidos or '(ninguno)'}",
    ]
    _console.print(Panel("\n".join(lineas), title="Memoria", border_style="magenta"))


def _mostrar_tareas(conversacional: AgentConversacional, estado: str | None) -> None:
    tareas = conversacional.listar_tareas(filtro_estado=estado)
    if not tareas:
        _console.print("[yellow]No hay tareas.[/yellow]")
        return
    tabla = Table(title=f"Tareas ({estado or 'todas'})")
    tabla.add_column("id")
    tabla.add_column("titulo")
    tabla.add_column("estado")
    tabla.add_column("prioridad")
    tabla.add_column("etiquetas")
    for t in tareas:
        tabla.add_row(
            t.id,
            t.titulo,
            t.estado.value,
            str(t.prioridad),
            ", ".join(t.etiquetas),
        )
    _console.print(tabla)


def _ejecutar_comando(conversacional: AgentConversacional, texto: str) -> None:
    """Procesa los comandos `/...` del chat (T089)."""
    partes = texto.split()
    comando = partes[0]
    argumentos = partes[1:]
    if comando == "/ayuda":
        _console.print(Panel(_AYUDA_CHAT, title="Ayuda", border_style="cyan"))
    elif comando == "/memoria":
        _mostrar_memoria(conversacional)
    elif comando == "/tarea":
        _comando_tarea(conversacional, argumentos)
    elif comando == "/sesion":
        _comando_sesion(conversacional, argumentos)
    else:
        _console.print(f"[yellow]Comando desconocido: {comando} (usa /ayuda).[/yellow]")


def _comando_tarea(conversacional: AgentConversacional, argumentos: list[str]) -> None:
    if not argumentos:
        _console.print(_ayuda_tareas())
        return
    accion = argumentos[0]
    resto = argumentos[1:]
    if accion == "add":
        desc = ""
        prioridad = 0
        palabras_titulo = []
        for arg in resto:
            if arg.startswith("--desc="):
                desc = arg.split("=", 1)[1]
            elif arg.startswith("--prioridad="):
                try:
                    prioridad = int(arg.split("=", 1)[1])
                except ValueError:
                    prioridad = 0
            else:
                palabras_titulo.append(arg)
        titulo = " ".join(palabras_titulo).strip() or "Tarea sin título"
        tid = conversacional.crear_tarea(
            titulo=titulo, descripcion=desc, prioridad=prioridad
        )
        _console.print(f"[green]Tarea creada: {tid}[/green] — {titulo}")
    elif accion == "list":
        estado = None
        for arg in resto:
            if arg.startswith("--estado="):
                estado = arg.split("=", 1)[1]
        _mostrar_tareas(conversacional, estado)
    elif accion == "run":
        if not resto:
            _console.print("[yellow]Indica el id de la tarea a ejecutar.[/yellow]")
            return
        tid = resto[0]
        _console.print(f"[cyan]Ejecutando tarea {tid}...[/cyan]")
        ok = conversacional.ejecutar_tarea(tid)
        if not ok:
            _console.print(f"[red]No se pudo ejecutar la tarea {tid} (no existe o ya está completada).[/red]")
            return
        tarea = conversacional.tareas.obtener(tid)
        if tarea is None:
            return
        if tarea.estado == EstadoTarea.COMPLETADA:
            _console.print(f"[green]Tarea {tid} completada.[/green]")
        else:
            _console.print(f"[yellow]Tarea {tid} bloqueada: sin evidencia real suficiente.[/yellow]")
        _console.print(Panel(tarea.resultado or "(sin resultado)", title=f"Resultado de {tid}", border_style="green"))
    elif accion in {"done", "next", "bloqueada"}:
        mapa = {"done": "completada", "next": "en_progreso", "bloqueada": "bloqueada"}
        if not resto:
            _console.print("[yellow]Indica el id de la tarea.[/yellow]")
            return
        tid = resto[0]
        ok = conversacional.cambiar_estado_tarea(tid, mapa[accion])
        if ok:
            _console.print(f"[green]Tarea {tid} → {mapa[accion]}.[/green]")
        else:
            _console.print(f"[red]No existe la tarea {tid}.[/red]")
    else:
        _console.print(_ayuda_tareas())


def _comando_sesion(conversacional: AgentConversacional, argumentos: list[str]) -> None:
    if not argumentos:
        _console.print(
            "Uso: /sesion save | /sesion list | /sesion load <id>"
        )
        return
    accion = argumentos[0]
    if accion == "save":
        sid = conversacional.guardar()
        _console.print(f"[green]Sesión guardada: {sid}[/green]")
    elif accion == "list":
        sesiones = conversacional.listar_sesiones()
        if not sesiones:
            _console.print("[yellow]No hay sesiones guardadas.[/yellow]")
            return
        tabla = Table(title="Sesiones")
        tabla.add_column("id")
        tabla.add_column("actualizada")
        for s in sesiones:
            tabla.add_row(s["id"], s.get("actualizada_en", ""))
        _console.print(tabla)
    elif accion == "load":
        if len(argumentos) < 2:
            _console.print("[yellow]Indica el id de la sesión.[/yellow]")
            return
        sid = argumentos[1]
        ok = conversacional.cargar(sid)
        if ok:
            _console.print(f"[green]Sesión {sid} cargada.[/green]")
        else:
            _console.print(f"[red]No existe la sesión {sid}.[/red]")
    else:
        _console.print("Uso: /sesion save | /sesion list | /sesion load <id>")


def _procesar_mensaje_chat(
    conversacional: AgentConversacional, texto: str, mostrar_historial: bool = False
) -> None:
    """Renderiza el turno del chat: comandos o conversación/QA normal.

    Si el turno requiere autorización (Phase 14 / FR-046, SC-004), se captura
    la decisión del usuario y se re-invoca con ella antes de renderizar.
    """
    if texto.startswith("/"):
        _ejecutar_comando(conversacional, texto)
        return
    respuesta = conversacional.atender(texto)
    pendientes = [
        a
        for a in respuesta.acciones
        if a.estado == EstadoAccion.PENDIENTE_AUTORIZACION
    ]
    if pendientes:
        decision = _pedir_autorizacion(pendientes[0].herramienta_id)
        respuesta = conversacional.atender(texto, autorizacion=decision)
    _renderizar_respuesta(
        respuesta, mostrar_historial=mostrar_historial
    )


def _renderizar_respuesta(respuesta, mostrar_historial: bool = False) -> None:
    """Imprime el razonamiento, la respuesta, las recomendaciones y el historial.

    El historial de acciones (tabla) está OCULTO por defecto (T109 / FR-020):
    la trazabilidad completa sigue disponible en el panel "Razonamiento" (cada
    paso muestra razón, herramienta, parámetros y observación real, FR-035) y
    el historial puede mostrarse con `--mostrar-historial`.
    """
    if getattr(respuesta, "razonamiento", None):
        lineas = []
        for observacion in respuesta.razonamiento:
            paso = observacion.paso
            resultado = getattr(observacion, "resultado", None)
            salida = getattr(resultado, "datos", resultado) if resultado else ""
            max_chars = (
                _RENDER_MAX_CHARS_LEER_ARCHIVO
                if paso.herramienta == "leer_archivo"
                else 1000
            )
            lineas.append(
                f"{paso.orden}. {paso.razon or paso.herramienta} "
                f"-> {paso.herramienta} {str(paso.parametros)}\n"
                f"   observación: {_acotar_render(str(salida), max_chars)}"
            )
        _console.print(
            Panel("\n".join(lineas), title="Razonamiento", border_style="cyan")
        )
    _console.print(
        Panel(respuesta.texto, title="Respuesta", border_style="green")
    )
    if getattr(respuesta, "recomendaciones", None):
        recomendaciones = "\n".join(
            f"• {rec}" for rec in respuesta.recomendaciones
        )
        _console.print(
            Panel(
                recomendaciones,
                title="Recomendaciones",
                border_style="yellow",
            )
        )
    if mostrar_historial and respuesta.acciones:
        tabla = Table(title="Historial de acciones")
        tabla.add_column("orden", justify="right")
        tabla.add_column("herramienta")
        tabla.add_column("estado")
        tabla.add_column("salida")
        for accion in respuesta.acciones:
            max_chars = (
                _RENDER_MAX_CHARS_LEER_ARCHIVO
                if accion.herramienta_id == "leer_archivo"
                else 1000
            )
            tabla.add_row(
                str(accion.orden),
                accion.herramienta_id,
                accion.estado.value,
                _acotar_render(str(accion.salida), max_chars),
            )
        _console.print(tabla)


@app.command()
def main(
    ruta: str = typer.Option(
        ".", "--ruta", help="Raíz del proyecto a analizar (default: cwd)."
    ),
    pregunta: Optional[str] = typer.Option(
        None, "--pregunta", help="Consulta puntual; omite el REPL."
    ),
    demo: bool = typer.Option(
        False, "--demo", help="Fuerza FakeLLM sin API key (validación sin LLM real)."
    ),
    mostrar_historial: bool = typer.Option(
        False,
        "--mostrar-historial",
        help="Muestra la tabla del historial de acciones (por defecto oculta; "
        "el razonamiento ya traza cada paso, FR-020/035).",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Muestra la versión instalada.",
    ),
) -> None:
    """Inicia el agente REPL interactivo o procesa `--pregunta`."""
    logger = get_logger()
    agente = _construir_agente(ruta, demo)
    logger.info("qa-agent iniciado (ruta=%s, demo=%s)", ruta, demo)

    if pregunta is not None:
        _renderizar_respuesta(
            _procesar_solicitud(agente, pregunta),
            mostrar_historial=mostrar_historial,
        )
        return

    _console.print(
        Panel(
            "AI QA & Software Engineering Agent — asistente orientado a "
            "herramientas.\nEscribe una consulta (o 'salir').",
            border_style="cyan",
        )
    )
    while True:
        try:
            texto = _console.input("[cyan]> [/cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            _console.print("\nFin de la sesión.")
            return
        if not texto:
            continue
        if texto.lower() in {"salir", "exit", "quit"}:
            _console.print("Fin de la sesión.")
            return
        _renderizar_respuesta(
            _procesar_solicitud(agente, texto),
            mostrar_historial=mostrar_historial,
        )


def _chat_diferido(
    ruta: str = typer.Option(
        ".", "--ruta", help="Raíz del proyecto a analizar (default: cwd)."
    ),
    demo: bool = typer.Option(
        False, "--demo", help="Fuerza FakeLLM sin API key (validación sin LLM real)."
    ),
    sesion_dir: str = typer.Option(
        None, "--sesion-dir", help="Directorio donde persistir las sesiones."
    ),
    mostrar_historial: bool = typer.Option(
        False,
        "--mostrar-historial",
        help="Muestra la tabla del historial de acciones (por defecto oculta; "
        "el razonamiento ya traza cada paso, FR-020/035).",
    ),
) -> None:
    """Código histórico diferido; no es un punto de entrada del MVP."""
    logger = get_logger()
    conversacional = _construir_conversacional(ruta, demo, sesion_dir)
    logger.info("qa-agent chat iniciado (ruta=%s, demo=%s)", ruta, demo)

    _console.print(
        Panel(
            "AI QA & Software Engineering Agent — chat conversacional.\n"
            "Análisis QA se delega al agente ReAct; conversación general "
            "se responde directo.\nEscribe /ayuda para ver los comandos.",
            border_style="cyan",
        )
    )
    while True:
        try:
            texto = _console.input("[cyan]> [/cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            _console.print("\nFin de la sesión.")
            return
        if not texto:
            continue
        if texto.lower() in {"salir", "exit", "quit", "/salir"}:
            _console.print("Fin de la sesión.")
            return
        _procesar_mensaje_chat(conversacional, texto, mostrar_historial)


if __name__ == "__main__":
    app()
