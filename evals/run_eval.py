#!/usr/bin/env python3
"""Ejecuta el harness de evaluación sin pasar por la CLI del agente.

Útil en CI y para comparar proveedores:

    python evals/run_eval.py                 # modo demo (determinista)
    python evals/run_eval.py --proveedor     # usa el backend configurado
    python evals/run_eval.py --json          # salida machine-readable

El motor vive en `qa_agent.evaluacion`; este script solo es la envoltura de
línea de comandos para quien no tenga el paquete instalado como `qa-agent`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from qa_agent.evaluacion.harness import ejecutar_evaluacion  # noqa: E402

#: Mismo umbral que usa `qa-agent --eval`, para que ambos caminos coincidan.
UMBRAL_APROBACION = 0.75


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluación del agente QA")
    parser.add_argument(
        "--proveedor",
        action="store_true",
        help="Usa el backend real en vez de FakeLLM (no determinista).",
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument(
        "--umbral",
        type=float,
        default=UMBRAL_APROBACION,
        help=f"Puntuación mínima para salir con código 0 (def. {UMBRAL_APROBACION}).",
    )
    args = parser.parse_args()

    informe = ejecutar_evaluacion(base=RAIZ, demo=not args.proveedor)

    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        for tarea in informe["tareas"]:
            print(
                f"{tarea['id']:<24} {tarea['ecosistema']:<8} "
                f"total={tarea['puntuacion']:.2f}  "
                f"herram={tarea['acierto_herramienta']:.2f} "
                f"anclaje={tarea['anclaje_evidencia']:.2f} "
                f"seguridad={tarea['seguridad']:.2f} "
                f"pasos={tarea['eficiencia_pasos']:.2f}"
            )
            for nota in tarea["notas"]:
                print(f"{'':<24} ! {nota}")
        resumen = informe["resumen"]
        print(
            f"\n{resumen['tareas']} tareas · "
            f"puntuación global {resumen['puntuacion_global']:.2f}"
        )

    return 0 if informe["resumen"]["puntuacion_global"] >= args.umbral else 1


if __name__ == "__main__":
    raise SystemExit(main())
