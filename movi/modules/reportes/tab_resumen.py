"""Pestaña Reportes: Resumen ejecutivo."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import streamlit as st
from supabase import Client

from movi.modules.reportes.deps import ReportesModuleDeps


def render_reportes_tab_resumen_ejecutivo(sb: Client, t: dict[str, Any] | None, *, deps: ReportesModuleDeps) -> None:
    d = deps
    st.markdown("#### Resumen ejecutivo")
    st.caption(
        "KPIs, PDF imprimible, cuentas, flujo multimoneda y gráficos del período. "
        "Las fechas de abajo son **solo** para este reporte (independientes del Dashboard)."
    )
    rc1, rc2 = st.columns(2)
    with rc1:
        d_re_a = st.date_input(
            "Desde",
            value=date.today() - timedelta(days=30),
            key="rep_res_ej_desde",
        )
    with rc2:
        d_re_b = st.date_input("Hasta", value=date.today(), key="rep_res_ej_hasta")
    if d_re_b < d_re_a:
        st.error("La fecha *Hasta* debe ser ≥ *Desde*.")
    else:
        k_rep = d.dashboard_kpis_periodo(sb, d_re_a, d_re_b)
        d.panel_resumen_ejecutivo_periodo_ui(
            sb,
            t,
            d_re_a,
            d_re_b,
            k_rep,
            pdf_download_key="rep_resumen_ejecutivo_pdf_dl",
        )
