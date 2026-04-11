"""Pestaña Reportes: compras y CXP."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import Client

from movi.modules.reportes.deps import ReportesModuleDeps


def render_reportes_tab_compras(
    sb: Client,
    *,
    deps: ReportesModuleDeps,
    have_t: bool,
    t_bs: float,
    t_usdt: float,
) -> None:
    d = deps
    st.markdown("#### Compras a proveedores")
    st.caption(
        "**Paso 1:** fechas. **Paso 2:** tabla y gráfico del período. **Paso 3 (opcional):** *Más detalle* por artículo y descargas. **Paso 4:** más abajo, **pendientes de pagar** al proveedor."
    )
    d1c, d2c = st.columns(2)
    ac = d1c.date_input("Desde", value=date.today() - timedelta(days=30), key="rep_comp_desde")
    bc = d2c.date_input("Hasta", value=date.today(), key="rep_comp_hasta")

    compras_r = (
        sb.table("compras")
        .select("id, numero, proveedor, fecha, total_usd, forma_pago, usuario_id")
        .gte("fecha", str(ac))
        .lte("fecha", f"{bc}T23:59:59")
        .order("fecha", desc=True)
        .execute()
    )
    umap_c = {
        str(u["id"]): (u.get("nombre") or u.get("username") or "—")
        for u in (sb.table("erp_users").select("id,nombre,username").execute().data or [])
    }

    st.markdown("##### Compras en el rango")
    if compras_r.data:
        dfcmp = pd.DataFrame(compras_r.data)
        if have_t:
            dfcmp["Equiv. aprox. en Bs (tasa de hoy)"] = (
                dfcmp["total_usd"].astype(float) * t_bs
            ).round(0).astype("Int64")
        dfcmp["Fecha"] = pd.to_datetime(dfcmp["fecha"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
        dfcmp["Quién la registró"] = dfcmp["usuario_id"].map(lambda x: umap_c.get(str(x), "—"))
        _rc = {
            "numero": "Nº interno",
            "proveedor": "Proveedor",
            "total_usd": "Total USD",
            "forma_pago": "Forma de pago",
        }
        dfc2 = dfcmp.rename(columns=_rc)
        _cols_c = ["Nº interno", "Fecha", "Proveedor", "Forma de pago", "Total USD"]
        if have_t:
            _cols_c.append("Equiv. aprox. en Bs (tasa de hoy)")
        _cols_c.append("Quién la registró")
        dfc_disp = dfc2[_cols_c]
        dfc_disp["Total USD"] = d.rep_series_montos_enteros(dfc_disp["Total USD"])
        st.dataframe(dfc_disp, use_container_width=True, hide_index=True)
        dfcmp["fecha_d"] = pd.to_datetime(dfcmp["fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
        aggc = dfcmp.groupby("fecha_d", as_index=False)["total_usd"].sum()
        figc = px.bar(
            aggc,
            x="fecha_d",
            y="total_usd",
            labels={"fecha_d": "Día", "total_usd": "Dólares (USD)"},
            title="Compras en dólares por día",
        )
        figc.update_layout(yaxis=dict(tickformat=",d"))
        st.plotly_chart(figc, use_container_width=True)
    else:
        st.info("No hay compras entre esas fechas.")

    cids = [str(x["id"]) for x in (compras_r.data or [])]
    det_c: list[dict[str, Any]] = []
    if cids:
        dc = (
            sb.table("compras_detalles")
            .select("compra_id, producto_id, cantidad, costo_unitario_usd, subtotal_usd")
            .in_("compra_id", cids)
            .execute()
        )
        det_c = dc.data or []

    with st.expander("Más detalle: cada artículo comprado (con descargas)", expanded=False):
        st.markdown("##### Detalle por artículo comprado")
        filas_cd: list[dict[str, Any]] = []
        if det_c and compras_r.data:
            pmap_c = {
                str(p["id"]): p
                for p in (sb.table("productos").select("id,descripcion,codigo").execute().data or [])
            }
            head_c = {str(v["id"]): v for v in compras_r.data}
            for row in det_c:
                cid = str(row.get("compra_id"))
                ch = head_c.get(cid, {})
                pid = str(row["producto_id"])
                pr = pmap_c.get(pid, {})
                filas_cd.append(
                    {
                        "Nº compra": ch.get("numero", ""),
                        "Fecha": str(ch.get("fecha", ""))[:19],
                        "Proveedor": ch.get("proveedor", ""),
                        "Código": d.export_cell_txt(pr.get("codigo")) or "—",
                        "Descripción": d.export_cell_txt(pr.get("descripcion")) or pid,
                        "Cantidad": float(row.get("cantidad") or 0),
                        "Costo unit. USD": int(round(float(row.get("costo_unitario_usd") or 0))),
                        "Subtotal USD": int(round(float(row.get("subtotal_usd") or 0))),
                    }
                )
        df_cd = pd.DataFrame(filas_cd)
        if df_cd.empty:
            st.info("No hay líneas de compra en ese período.")
        else:
            st.dataframe(df_cd, use_container_width=True, hide_index=True)
        ts_cp = d.backup_file_timestamp()
        cpx, cpc = st.columns(2)
        with cpx:
            try:
                st.download_button(
                    label=f"Excel — detalle_compras_{ts_cp}.xlsx",
                    data=d.reporte_tabla_a_excel(df_cd, nombre_hoja="Compras detalle"),
                    file_name=f"detalle_compras_{ts_cp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="rep_dl_comp_det_xlsx",
                    use_container_width=True,
                )
            except ImportError:
                pass
        with cpc:
            st.download_button(
                label=f"CSV — detalle_compras_{ts_cp}.csv",
                data=d.reporte_tabla_a_csv(df_cd),
                file_name=f"detalle_compras_{ts_cp}.csv",
                mime="text/csv",
                key="rep_dl_comp_det_csv",
                use_container_width=True,
            )

    st.divider()
    st.markdown("##### Facturas o deudas pendientes de pagar al proveedor")
    cxp = sb.table("cuentas_por_pagar").select("*").execute()
    if cxp.data:
        dfp = pd.DataFrame(cxp.data)
        st.dataframe(dfp, use_container_width=True, hide_index=True)
        pend_p = dfp[dfp["estado"].isin(["Pendiente", "Parcial"])]["monto_pendiente_usd"].astype(float).sum()
        st.metric("Total aún por pagar (USD)", f"{int(round(pend_p)):,d}")
        if have_t:
            st.caption(d.fmt_tri(pend_p, t_bs, t_usdt))
    else:
        st.info("No hay cuentas por pagar cargadas.")
