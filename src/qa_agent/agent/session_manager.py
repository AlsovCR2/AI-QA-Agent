"""`SesionManager`: persistencia de conversaciones (Phase 13 / T086).

Guarda/carga `Conversacion` a JSON (archivo por sesión) con opción de BD SQLite.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from qa_agent.agent.reasoning import (
    Conversacion,
    EstadoTarea,
    Memoria,
    TareaAgente,
    Turno,
)


class SesionManager:
    """Gestiona la persistencia de conversaciones (JSON o SQLite)."""

    def __init__(self, base_dir: str | Path | None = None, usar_sqlite: bool = False):
        self.base_dir = Path(base_dir or os.getenv("QA_AGENT_SESSIONS", "./.qa_sessions"))
        self.usar_sqlite = usar_sqlite
        if usar_sqlite:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()

    def _ruta_archivo(self, sesion_id: str) -> Path:
        return self.base_dir / f"{sesion_id}.json"

    def _init_sqlite(self) -> None:
        import sqlite3

        self._db_path = self.base_dir / "sessions.db"
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sesiones (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                actualizada_en TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    # -- API pública ---------------------------------------------------------

    def guardar(self, conversacion: Conversacion) -> None:
        """Persiste la conversación (JSON o SQLite)."""
        conversacion.actualizada_en = datetime.now()
        data = self._serializar(conversacion)
        if self.usar_sqlite:
            import sqlite3

            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO sesiones (id, data, actualizada_en) VALUES (?, ?, ?)",
                (conversacion.id, json.dumps(data), conversacion.actualizada_en.isoformat()),
            )
            conn.commit()
            conn.close()
        else:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            ruta = self._ruta_archivo(conversacion.id)
            ruta.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def cargar(self, sesion_id: str) -> Conversacion | None:
        """Carga una conversación por ID (JSON o SQLite)."""
        if self.usar_sqlite:
            import sqlite3

            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT data FROM sesiones WHERE id = ?", (sesion_id,)
            ).fetchone()
            conn.close()
            if row is None:
                return None
            data = json.loads(row[0])
        else:
            ruta = self._ruta_archivo(sesion_id)
            if not ruta.exists():
                return None
            data = json.loads(ruta.read_text(encoding="utf-8"))
        return self._deserializar(data)

    def listar(self) -> list[dict[str, Any]]:
        """Lista sesiones disponibles con metadatos básicos."""
        sesiones = []
        if self.usar_sqlite:
            import sqlite3

            conn = sqlite3.connect(self._db_path)
            rows = conn.execute(
                "SELECT id, actualizada_en FROM sesiones ORDER BY actualizada_en DESC"
            ).fetchall()
            conn.close()
            for row in rows:
                sesiones.append({"id": row[0], "actualizada_en": row[1]})
        else:
            for ruta in sorted(self.base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    data = json.loads(ruta.read_text(encoding="utf-8"))
                    sesiones.append(
                        {"id": data["id"], "actualizada_en": data.get("actualizada_en", "")}
                    )
                except Exception:
                    pass
        return sesiones

    def borrar(self, sesion_id: str) -> bool:
        """Elimina una sesión."""
        if self.usar_sqlite:
            import sqlite3

            conn = sqlite3.connect(self._db_path)
            cur = conn.execute("DELETE FROM sesiones WHERE id = ?", (sesion_id,))
            conn.commit()
            conn.close()
            return cur.rowcount > 0
        else:
            ruta = self._ruta_archivo(sesion_id)
            if ruta.exists():
                ruta.unlink()
                return True
            return False

    # -- serialización -------------------------------------------------------

    def _serializar(self, conv: Conversacion) -> dict[str, Any]:
        return {
            "id": conv.id,
            "turnos": [self._turno_a_dict(t) for t in conv.turnos],
            "resumen": conv.resumen,
            "hechos": conv.hechos,
            "tareas": [self._tarea_a_dict(t) for t in conv.tareas],
            "creada_en": conv.creada_en.isoformat(),
            "actualizada_en": conv.actualizada_en.isoformat(),
        }

    def _deserializar(self, data: dict[str, Any]) -> Conversacion:
        conv = Conversacion(
            id=data["id"],
            resumen=data.get("resumen", ""),
            hechos=data.get("hechos", {}),
            creada_en=datetime.fromisoformat(data["creada_en"]),
            actualizada_en=datetime.fromisoformat(data["actualizada_en"]),
        )
        conv.turnos = [self._dict_a_turno(t) for t in data.get("turnos", [])]
        conv.tareas = [self._dict_a_tarea(t) for t in data.get("tareas", [])]
        return conv

    @staticmethod
    def _turno_a_dict(t: Turno) -> dict[str, Any]:
        return {
            "numero": t.numero,
            "usuario": t.usuario,
            "agente": t.agente,
            "timestamp": t.timestamp.isoformat(),
            "herramientas_usadas": t.herramientas_usadas,
            # razonamiento_ref no se serializa (referencias a objetos)
        }

    @staticmethod
    def _dict_a_turno(d: dict[str, Any]) -> Turno:
        return Turno(
            numero=d["numero"],
            usuario=d["usuario"],
            agente=d["agente"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            herramientas_usadas=d.get("herramientas_usadas", []),
        )

    @staticmethod
    def _tarea_a_dict(t: TareaAgente) -> dict[str, Any]:
        return {
            "id": t.id,
            "titulo": t.titulo,
            "descripcion": t.descripcion,
            "estado": t.estado.value,
            "prioridad": t.prioridad,
            "etiquetas": t.etiquetas,
            "dependencias": t.dependencias,
            "asignado_a": t.asignado_a,
            "resultado": t.resultado,
            "creada_en": t.creada_en.isoformat(),
            "actualizada_en": t.actualizada_en.isoformat(),
        }

    @staticmethod
    def _dict_a_tarea(d: dict[str, Any]) -> TareaAgente:
        return TareaAgente(
            id=d["id"],
            titulo=d["titulo"],
            descripcion=d["descripcion"],
            estado=EstadoTarea(d["estado"]),
            prioridad=d.get("prioridad", 0),
            etiquetas=d.get("etiquetas", []),
            dependencias=d.get("dependencias", []),
            asignado_a=d.get("asignado_a", ""),
            resultado=d.get("resultado", ""),
            creada_en=datetime.fromisoformat(d["creada_en"]),
            actualizada_en=datetime.fromisoformat(d["actualizada_en"]),
        )
