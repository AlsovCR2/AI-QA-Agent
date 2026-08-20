"""`Allowlist`: restricción de rutas autorizadas (mínimo privilegio, FR-025).

Permite comprobar si una ruta solicitada pertenece al perímetro autorizado.
Normaliza rutas (resolución de `..` y symlinks) para evitar escapes del
perímetro. Usa `pathspec` (D10) para soportar patrones gitignore-like.
"""

from __future__ import annotations

from pathlib import Path

import pathspec

# Patrones de exclusión por defecto: directorios habituales a ignorar.
_EXCLUSIONES_DEFECTO = (
    ".git/",
    "__pycache__/",
    "*.pyc",
    ".venv/",
    "node_modules/",
    "dist/",
    "build/",
    ".pytest_cache/",
    ".env",
)


class Allowlist:
    """Permite rutas dentro de uno o varios perímetros autorizados.

    Una ruta se considera permitida si, tras normalizarla (`Path.resolve`),
    cae dentro de al menos uno de los perímetros y no coincide con ningún
    patrón de exclusión.
    """

    def __init__(
        self,
        rutas_permitidas: list[Path | str],
        exclusiones: list[str] | None = None,
    ) -> None:
        self._perimetros: list[Path] = [
            Path(ruta).resolve() for ruta in rutas_permitidas
        ]
        patrones = list(exclusiones) if exclusiones is not None else list(_EXCLUSIONES_DEFECTO)
        self._spec = pathspec.PathSpec.from_lines(
            "gitwildmatch", patrones
        )

    @property
    def perimetros(self) -> list[Path]:
        """Perímetros autorizados (normalizados)."""
        return self._perimetros

    def _normalizar(self, ruta: Path | str) -> Path:
        return Path(ruta).expanduser().resolve()

    def _dentro_de_perimetro(self, ruta_normalizada: Path) -> bool:
        for perimetro in self._perimetros:
            try:
                ruta_normalizada.relative_to(perimetro)
                return True
            except ValueError:
                continue
        return False

    def __contains__(self, ruta: Path | str) -> bool:
        """True si `ruta` está autorizada dentro del perímetro (FR-025)."""
        normalizada = self._normalizar(ruta)
        if not self._dentro_de_perimetro(normalizada):
            return False
        relativa = normalizada.relative_to(
            self._perimetros[0] if self._perimetros else Path.cwd()
        )
        return not self._spec.match_file(str(relativa))

    def contiene(self, ruta: Path | str) -> bool:
        """Forma explícita de `__contains__`."""
        return ruta in self

    def ruta_permitida(self, ruta: Path | str) -> bool:
        """Alias legible de `__contains__`."""
        return self.contiene(ruta)