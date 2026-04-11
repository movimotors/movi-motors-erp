"""Pestaña Reportes: cartera (cobrar / pagar)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client

from movi.modules.reportes.deps import ReportesModuleDeps


def render_reportes_tab_cartera(
    sb: Client,
    *,
    deps: ReportesModuleDeps,
    have_t: bool,
    t_bs: float,
    t_usdt: float,
) -> None:
    d = deps
    st.markdown("#### Clientes que deben y proveedores a los que debes")
    st.caption(
        "**Paso 1:** revisá totales y **resumen por plazo**. **Paso 2:** abrí *Listado completo* si necesitás todas las filas. **Paso 3:** descargá Excel/CSV abajo. "
        "*¿Qué tan al día está?* indica si la fecha límite ya pasó."
    )

    ventas_all = {str(v["id"]): v for v in (sb.table("ventas").select("id, numero, cliente").execute().data or [])}
    compras_all = {str(c["id"]): c for c in (sb.table("compras").select("id, numero, proveedor").execute().data or [])}

    df_dl_cob = pd.DataFrame()
    df_dl_pag = pd.DataFrame()

    cxc = sb.table("cuentas_por_cobrar").select("*").execute()
    if cxc.data:
        st.markdown("##### Te deben (clientes)")
        rows_cxc: list[dict[str, Any]] = []
        for r in cxc.data:
            vid = str(r.get("venta_id") or "")
            vh = ventas_all.get(vid, {})
            rows_cxc.append(
                {
                    "Cliente": vh.get("cliente", "—"),
                    "Nº venta": vh.get("numero", "—"),
                    "Estado del crédito": r.get("estado", ""),
                    "Fecha límite de cobro": str(r.get("fecha_vencimiento") or "")[:10],
                    "¿Qué tan al día está?": d.rep_texto_plazo_vencimiento(r.get("fecha_vencimiento")),
                    "Grupo (para totales)": d.rep_bucket_antiguedad(r.get("fecha_vencimiento")),
                    "Adeudado USD": int(round(float(r.get("monto_pendiente_usd") or 0))),
                }
            )
        df_cxc = pd.DataFrame(rows_cxc)
        df_dl_cob = df_cxc
        pend_c = df_cxc[df_cxc["Estado del crédito"].isin(["Pendiente", "Parcial"])]["Adeudado USD"].sum()
        st.metric("Total que te deben (pendiente, USD)", f"{int(round(pend_c)):,d}")
        if have_t:
            st.caption(d.fmt_tri(pend_c, t_bs, t_usdt))

        res_c = (
            df_cxc[df_cxc["Estado del crédito"].isin(["Pendiente", "Parcial"])]
            .groupby("Grupo (para totales)", as_index=False)["Adeudado USD"]
            .sum()
            .sort_values("Adeudado USD", ascending=False)
        )
        res_c["Adeudado USD"] = d.rep_series_montos_enteros(res_c["Adeudado USD"])
        st.markdown("**Resumen: te deben — agrupado por plazo**")
        st.dataframe(res_c, use_container_width=True, hide_index=True)
        with st.expander("Listado completo — clientes que te deben (todas las filas)", expanded=False):
            st.dataframe(df_cxc, use_container_width=True, hide_index=True)
    else:
        st.info("No hay cuentas por cobrar.")

    st.divider()
    cxp2 = sb.table("cuentas_por_pagar").select("*").execute()
    if cxp2.data:
        st.markdown("##### Debes a proveedores")
        rows_cxp: list[dict[str, Any]] = []
        for r in cxp2.data:
            cid = str(r.get("compra_id") or "")
            ch = compras_all.get(cid, {})
            rows_cxp.append(
                {
                    "Proveedor": ch.get("proveedor", "—"),
                    "Nº compra": ch.get("numero", "—"),
                    "Estado": r.get("estado", ""),
                    "Fecha límite de pago": str(r.get("fecha_vencimiento") or "")[:10],
                    "¿Qué tan al día está?": d.rep_texto_plazo_vencimiento(r.get("fecha_vencimiento")),
                    "Grupo (para totales)": d.rep_bucket_antiguedad(r.get("fecha_vencimiento")),
                    "Debes USD": int(round(float(r.get("monto_pendiente_usd") or 0))),
                }
            )
        df_cxp = pd.DataFrame(rows_cxp)
        df_dl_pag = df_cxp
        pend_x = df_cxp[df_cxp["Estado"].isin(["Pendiente", "Parcial"])]["Debes USD"].sum()
        st.metric("Total que debes pagar (pendiente, USD)", f"{int(round(pend_x)):,d}")
        if have_t:
            st.caption(d.fmt_tri(pend_x, t_bs, t_usdt))
        res_x = (
            df_cxp[df_cxp["Estado"].isin(["Pendiente", "Parcial"])]
            .groupby("Grupo (para totales)", as_index=False)["Debes USD"]
            .sum()
            .sort_values("Debes USD", ascending=False)
        )
        res_x["Debes USD"] = d.rep_series_montos_enteros(res_x["Debes USD"])
        st.markdown("**Resumen: debes — agrupado por plazo**")
        st.dataframe(res_x, use_container_width=True, hide_index=True)
        with st.expander("Listado completo — proveedores a pagar (todas las filas)", expanded=False):
            st.dataframe(df_cxp, use_container_width=True, hide_index=True)
    else:
        st.info("No hay cuentas por pagar.")

    st.markdown("##### Bajar estos listados a tu computadora")
    ts_car = d.backup_file_timestamp()
    _parts_dl = []
    if not df_dl_cob.empty:
        _parts_dl.append(df_dl_cob.assign(**{"Listado": "Clientes que te deben"}))
    if not df_dl_pag.empty:
        _parts_dl.append(df_dl_pag.assign(**{"Listado": "Proveedores a pagar"}))
    df_car_csv = pd.concat(_parts_dl, ignore_index=True) if _parts_dl else pd.DataFrame()

    ca1, ca2, ca3 = st.columns(3)
    with ca1:
        try:
            st.download_button(
                label=f"Excel — clientes_que_deben_{ts_car}.xlsx",
                data=d.reporte_tabla_a_excel(df_dl_cob, nombre_hoja="Te deben"),
                file_name=f"clientes_que_deben_{ts_car}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="rep_dl_car_cxc_xlsx",
                use_container_width=True,
                disabled=df_dl_cob.empty,
            )
        except ImportError:
            st.caption("Instalá **openpyxl** para generar Excel.")
    with ca2:
        try:
            st.download_button(
                label=f"Excel — proveedores_a_pagar_{ts_car}.xlsx",
                data=d.reporte_tabla_a_excel(df_dl_pag, nombre_hoja="Debes pagar"),
                file_name=f"proveedores_a_pagar_{ts_car}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="rep_dl_car_cxp_xlsx",
                use_container_width=True,
                disabled=df_dl_pag.empty,
            )
        except ImportError:
            pass
    with ca3:
        st.download_button(
            label=f"CSV — todo_junto_{ts_car}.csv",
            data=d.reporte_tabla_a_csv(df_car_csv),
            file_name=f"cartera_cobrar_y_pagar_{ts_car}.csv",
            mime="text/csv",
            key="rep_dl_car_csv",
            use_container_width=True,
            disabled=df_car_csv.empty,
        )
