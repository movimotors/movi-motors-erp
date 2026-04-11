"""Pestaña Reportes: ventas."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import Client

from movi.modules.reportes.deps import ReportesModuleDeps


def render_reportes_tab_ventas(
    sb: Client,
    *,
    deps: ReportesModuleDeps,
    have_t: bool,
    t_bs: float,
    t_usdt: float,
) -> None:
    d = deps
    st.markdown("#### Ventas")
    st.caption(
        "**Paso 1:** fechas. **Paso 2:** revisá el **resumen por venta** y el gráfico. **Paso 3 (opcional):** abrí *Más detalle* para ganancias por producto, cada línea facturada y descargas."
    )
    d1, d2 = st.columns(2)
    a = d1.date_input("Desde", value=date.today() - timedelta(days=30), key="rep_ven_desde")
    b = d2.date_input("Hasta", value=date.today(), key="rep_ven_hasta")

    ventas = (
        sb.table("ventas")
        .select("id, numero, cliente, fecha, total_usd, forma_pago, usuario_id")
        .gte("fecha", str(a))
        .lte("fecha", f"{b}T23:59:59")
        .order("fecha", desc=True)
        .execute()
    )
    umap_v = {
        str(u["id"]): (u.get("nombre") or u.get("username") or "—")
        for u in (sb.table("erp_users").select("id,nombre,username").execute().data or [])
    }

    st.markdown("##### Resumen por venta")
    if ventas.data:
        dfv = pd.DataFrame(ventas.data)
        if have_t:
            dfv["Equiv. aprox. en Bs (según tasa de hoy)"] = (
                dfv["total_usd"].astype(float) * t_bs
            ).round(0).astype("Int64")
        dfv["Fecha"] = pd.to_datetime(dfv["fecha"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
        dfv["Quién la registró"] = dfv["usuario_id"].map(lambda x: umap_v.get(str(x), "—"))
        _rv = {
            "numero": "Nº interno",
            "cliente": "Cliente",
            "total_usd": "Total USD",
            "forma_pago": "Forma de pago",
        }
        dfv2 = dfv.rename(columns=_rv)
        _cols_v = ["Nº interno", "Fecha", "Cliente", "Forma de pago", "Total USD"]
        if have_t:
            _cols_v.append("Equiv. aprox. en Bs (según tasa de hoy)")
        _cols_v.append("Quién la registró")
        dfv_disp = dfv2[_cols_v]
        dfv_disp["Total USD"] = d.rep_series_montos_enteros(dfv_disp["Total USD"])
        st.dataframe(dfv_disp, use_container_width=True, hide_index=True)
        dfv["fecha_d"] = pd.to_datetime(dfv["fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
        agg = dfv.groupby("fecha_d", as_index=False)["total_usd"].sum()
        fig = px.bar(
            agg,
            x="fecha_d",
            y="total_usd",
            labels={"fecha_d": "Día", "total_usd": "Dólares (USD)"},
            title="Vendido en dólares por día (total del día)",
        )
        fig.update_layout(yaxis=dict(tickformat=",d"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay ventas registradas entre esas fechas.")

    vids = [str(x["id"]) for x in (ventas.data or [])]
    det_rows: list[dict[str, Any]] = []
    if vids:
        det = (
            sb.table("ventas_detalles")
            .select("venta_id, producto_id, cantidad, precio_unitario_usd, subtotal_usd")
            .in_("venta_id", vids)
            .execute()
        )
        det_rows = det.data or []

    with st.expander("Más detalle: ganancias por producto y cada línea de venta (con descargas)", expanded=False):
        st.markdown("##### Cuánto ganaste aproximado por producto (mismo período)")
        st.caption(
            "**Ganancia bruta** simple: precio de venta menos costo del producto × cantidades. No incluye gastos fijos."
        )
        if det_rows:
            pmap = {
                str(p["id"]): p
                for p in (sb.table("productos").select("id,descripcion,codigo,costo_usd").execute().data or [])
            }
            rows_m = []
            for row in det_rows:
                pid = str(row["producto_id"])
                pr = pmap.get(pid, {})
                desc = pr.get("descripcion", pid)
                costo = float(pr.get("costo_usd") or 0)
                cant = float(row["cantidad"])
                pu = float(row["precio_unitario_usd"])
                margin = (pu - costo) * cant
                rows_m.append({"producto": desc, "utilidad_bruta_usd": margin})
            dfm = pd.DataFrame(rows_m).groupby("producto", as_index=False)["utilidad_bruta_usd"].sum()
            dfm = dfm.rename(columns={"producto": "Producto", "utilidad_bruta_usd": "Ganancia bruta USD (aprox.)"})
            dfm["Ganancia bruta USD (aprox.)"] = d.rep_series_montos_enteros(dfm["Ganancia bruta USD (aprox.)"])
            st.dataframe(dfm, use_container_width=True, hide_index=True)
            if have_t:
                st.caption(d.fmt_tri(float(dfm["Ganancia bruta USD (aprox.)"].sum()), t_bs, t_usdt))
        else:
            st.info("No hay líneas de venta en ese período.")

        st.markdown("##### Cada artículo en cada venta")
        st.caption("Una fila por línea facturada (para buscar un repuesto o exportar).")
        filas_det: list[dict[str, Any]] = []
        if det_rows and ventas.data:
            pmap2 = {
                str(p["id"]): p
                for p in (sb.table("productos").select("id,descripcion,codigo").execute().data or [])
            }
            vhead = {str(v["id"]): v for v in ventas.data}
            for row in det_rows:
                vid = str(row.get("venta_id"))
                vh = vhead.get(vid, {})
                pid = str(row["producto_id"])
                pr = pmap2.get(pid, {})
                filas_det.append(
                    {
                        "Nº venta": vh.get("numero", ""),
                        "Fecha venta": str(vh.get("fecha", ""))[:19],
                        "Cliente": vh.get("cliente", ""),
                        "Forma de pago": vh.get("forma_pago", ""),
                        "Quién registró": umap_v.get(str(vh.get("usuario_id")), "—"),
                        "Código": d.export_cell_txt(pr.get("codigo")) or "—",
                        "Descripción": d.export_cell_txt(pr.get("descripcion")) or pid,
                        "Cantidad": float(row.get("cantidad") or 0),
                        "Precio unitario USD": int(round(float(row.get("precio_unitario_usd") or 0))),
                        "Subtotal USD": int(round(float(row.get("subtotal_usd") or 0))),
                    }
                )
        df_det = pd.DataFrame(filas_det)
        if df_det.empty:
            st.info("No hay detalle para mostrar en esas fechas.")
        else:
            st.dataframe(df_det, use_container_width=True, hide_index=True)
        ts_v = d.backup_file_timestamp()
        vx, vc = st.columns(2)
        with vx:
            try:
                st.download_button(
                    label=f"Excel — detalle_ventas_{ts_v}.xlsx",
                    data=d.reporte_tabla_a_excel(df_det, nombre_hoja="Ventas detalle"),
                    file_name=f"detalle_ventas_{ts_v}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="rep_dl_ven_det_xlsx",
                    use_container_width=True,
                )
            except ImportError:
                pass
        with vc:
            st.download_button(
                label=f"CSV — detalle_ventas_{ts_v}.csv",
                data=d.reporte_tabla_a_csv(df_det),
                file_name=f"detalle_ventas_{ts_v}.csv",
                mime="text/csv",
                key="rep_dl_ven_det_csv",
                use_container_width=True,
            )
