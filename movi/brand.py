"""Logo y marca en UI / exportaciones."""

from __future__ import annotations

import base64

import streamlit as st

from movi.paths import BRAND_LOGO_PATH


def brand_logo_file() -> str | None:
    return str(BRAND_LOGO_PATH) if BRAND_LOGO_PATH.is_file() else None


def brand_logo_data_uri() -> str | None:
    """PNG/JPEG del logo para incrustar en HTML de impresión."""
    p = BRAND_LOGO_PATH
    if not p.is_file():
        return None
    try:
        raw = p.read_bytes()
        if not raw:
            return None
        if raw.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        else:
            suf = p.suffix.lower()
            mime = "image/jpeg" if suf in (".jpg", ".jpeg") else "image/png"
        b64 = base64.standard_b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except OSError:
        return None


def render_brand_logo(*, use_column_width: bool = True) -> None:
    p = brand_logo_file()
    if p:
        st.image(p, use_container_width=use_column_width)
