"""Pestaña Reportes: inventario / exportaciones."""

from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import Client

from movi.modules.reportes.deps import ReportesModuleDeps


def render_reportes_tab_inventario(sb: Client, t: dict[str, Any] | None, *, deps: ReportesModuleDeps) -> None:
    st.markdown("#### Listado de repuestos y productos")
    st.caption(
        "**Paso 1:** usá los filtros del panel de abajo. **Paso 2:** revisá la vista previa. **Paso 3:** descargá **Excel**, **PDF** o **HTML** (imprimible desde el navegador)."
    )
    deps.panel_reportes_inventario_export(sb, t)
