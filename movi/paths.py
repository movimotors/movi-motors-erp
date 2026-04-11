"""Rutas de la aplicación (directorio raíz del proyecto)."""

from __future__ import annotations

from pathlib import Path

# Paquete en <root>/movi/ → raíz del repo es parent
APP_DIR: Path = Path(__file__).resolve().parent.parent
BRAND_LOGO_PATH: Path = APP_DIR / "assets" / "logo_movimotors.jpg"
