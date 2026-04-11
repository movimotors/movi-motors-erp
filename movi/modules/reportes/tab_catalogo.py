"""Pestaña Reportes: catálogo y fotos."""

from __future__ import annotations

import streamlit as st
from supabase import Client

from movi.modules.reportes.deps import ReportesModuleDeps


def render_reportes_tab_catalogo(sb: Client, erp_uid: str, *, deps: ReportesModuleDeps) -> None:
    deps.panel_reportes_catalogo_fotos(sb, erp_uid)
