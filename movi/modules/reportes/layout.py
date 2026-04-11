"""Orquestación del módulo Reportes: permisos, título y pestañas."""

from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import Client

from movi.rbac import role_can

from movi.modules.reportes.deps import ReportesModuleDeps
from movi.modules.reportes.tab_caja import render_reportes_tab_caja
from movi.modules.reportes.tab_cartera import render_reportes_tab_cartera
from movi.modules.reportes.tab_catalogo import render_reportes_tab_catalogo
from movi.modules.reportes.tab_compras import render_reportes_tab_compras
from movi.modules.reportes.tab_inventario import render_reportes_tab_inventario
from movi.modules.reportes.tab_resumen import render_reportes_tab_resumen_ejecutivo
from movi.modules.reportes.tab_ventas import render_reportes_tab_ventas


def render_module_reportes(
    sb: Client,
    erp_uid: str,
    t: dict[str, Any] | None,
    rol: str,
    *,
    deps: ReportesModuleDeps,
) -> None:
    d = deps
    can_fin = role_can(rol, "reportes")
    can_cat = role_can(rol, "catalogo")
    if not can_fin and not can_cat:
        st.error("Tu rol no tiene acceso a reportes ni al catálogo.")
        return

    have_t = bool(t) if can_fin else True
    t_bs = float(t["tasa_bs"]) if t else 0.0
    t_usdt = float(t["tasa_usdt"]) if t else 0.0

    if can_fin:
        _rep_info_parts = [
            "**Cómo usar reportes:** 1) Elegí la **pestaña** del tema. 2) Ajustá **fechas** y filtros en esa pestaña. "
            "3) Revisá la **tabla o gráfico** principal. 4) Si necesitás profundizar, abrí **Más detalle** al final de la pestaña. "
            "5) **Descargá** Excel o CSV para otra PC o WhatsApp.",
            "Los totales en **USD** son los del sistema; las columnas en **bolívares** son referencia según la tasa del día (cuando esté cargada).",
        ]
        if have_t:
            _rep_info_parts.append(
                f"Referencia: 1 USD equivale a **Bs** {int(round(t_bs)):,d} · **USDT** {int(round(t_usdt)):,d}"
            )
        if can_cat:
            _rep_info_parts.append(
                "**Catálogo y etiquetas:** página HTML para imprimir listados y fichas. "
                "La subida de fotos a la nube es opcional y se puede apagar en `secrets` → `[catalogo]` → `storage_fotos`."
            )
        d.modulo_titulo_info("Reportes", key="reportes", ayuda_md="\n\n".join(_rep_info_parts))
        if not have_t:
            st.warning(
                "Aún no hay **tasas del día** cargadas en el Dashboard: los reportes en bolívares no se muestran hasta que las registres. "
                "La pestaña **Catálogo y etiquetas** funciona igual."
            )
    else:
        d.modulo_titulo_info(
            "Reportes",
            key="reportes_cat",
            ayuda_md=(
                "**Catálogo y etiquetas:** página HTML para imprimir listados y fichas. "
                "La subida de fotos a la nube es opcional y se puede apagar en `secrets` → `[catalogo]` → `storage_fotos`."
            ),
        )

    if can_fin:
        tab_re, tab_inv, tab_caja, tab_ven, tab_comp, tab_cartera, tab_cat = st.tabs(
            [
                "Resumen ejecutivo",
                "Inventario",
                "Caja",
                "Ventas",
                "Compras",
                "Cartera",
                "Catálogo",
            ]
        )
    else:
        tab_cat = st.tabs(["Catálogo"])[0]

    if can_fin:
        with tab_re:
            render_reportes_tab_resumen_ejecutivo(sb, t, deps=d)
        with tab_inv:
            render_reportes_tab_inventario(sb, t, deps=d)
        with tab_caja:
            render_reportes_tab_caja(sb, deps=d)
        with tab_ven:
            render_reportes_tab_ventas(sb, deps=d, have_t=have_t, t_bs=t_bs, t_usdt=t_usdt)
        with tab_comp:
            render_reportes_tab_compras(sb, deps=d, have_t=have_t, t_bs=t_bs, t_usdt=t_usdt)
        with tab_cartera:
            render_reportes_tab_cartera(sb, deps=d, have_t=have_t, t_bs=t_bs, t_usdt=t_usdt)

    with tab_cat:
        render_reportes_tab_catalogo(sb, erp_uid, deps=d)
