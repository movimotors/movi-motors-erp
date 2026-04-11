"""Pestaña Reportes: movimientos de caja."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client

from movi.modules.reportes.deps import ReportesModuleDeps


def render_reportes_tab_caja(sb: Client, *, deps: ReportesModuleDeps) -> None:
    d = deps
    st.markdown("#### Dinero que entró y salió de cada cuenta")
    st.caption(
        "**Paso 1:** fechas y tipo (todo / solo entradas / solo salidas). **Paso 2:** cuenta o *Todas*. **Paso 3:** revisá la tabla y los totales. **Paso 4:** descargá Excel o CSV."
    )
    c1, c2, c3 = st.columns(3)
    d_caja_a = c1.date_input("Desde", value=date.today() - timedelta(days=30), key="rep_caja_desde")
    d_caja_b = c2.date_input("Hasta", value=date.today(), key="rep_caja_hasta")
    tipo_sel = c3.selectbox(
        "Qué mostrar",
        options=["Todo", "Solo entradas de dinero", "Solo salidas de dinero"],
        key="rep_caja_tipo",
        help="Entrada = cobraste o ingresó dinero a la cuenta. Salida = pagaste o retiraste.",
    )
    tipo_f = None
    if tipo_sel == "Solo entradas de dinero":
        tipo_f = "Ingreso"
    elif tipo_sel == "Solo salidas de dinero":
        tipo_f = "Egreso"

    cajas_r = d.cajas_fetch_rows(sb, solo_activas=False)
    caja_ids_all, caja_fmt_all = d.caja_select_options(cajas_r) if cajas_r else ([], lambda x: str(x))
    cuenta_opciones = ["(Todas las cuentas)"] + caja_ids_all

    def _fmt_cuenta_opt(x: str) -> str:
        if x == "(Todas las cuentas)":
            return "Todas las cuentas"
        return caja_fmt_all(x)

    caja_pick = st.selectbox(
        "Cuenta o caja",
        options=cuenta_opciones,
        format_func=_fmt_cuenta_opt,
        key="rep_caja_cuenta",
        help="Elegí una cuenta suelta (por ejemplo un banco en bolívares) o dejá **Todas** para ver todo junto.",
    )
    caja_f = None if caja_pick == "(Todas las cuentas)" else str(caja_pick)

    movs = d.rep_movimientos_caja_filtrados(sb, desde=d_caja_a, hasta=d_caja_b, caja_id=caja_f, tipo_mov=tipo_f)
    umap = {
        str(u["id"]): (u.get("nombre") or u.get("username") or "")
        for u in (sb.table("erp_users").select("id,nombre,username").execute().data or [])
    }
    cmap = {str(c["id"]): d.caja_etiqueta_lista(c) for c in cajas_r}

    filas_mc: list[dict[str, Any]] = []
    for m in movs:
        mon = (m.get("moneda") or "USD") or "USD"
        mm = m.get("monto_moneda")
        _musd = d.round_money_2(m.get("monto_usd"))
        mon_u = str(mon).upper()
        ex_bk, ex_amt = d.movimiento_monto_explicito_columnas(m)
        if ex_bk is not None and ex_amt is not None:
            mon_orig = "ZELLE" if mon_u == "ZELLE" and ex_bk == "USD" else ex_bk
            _mm_orig = d.round_money_2(ex_amt)
        else:
            mon_orig = mon_u
            _mm_orig = d.round_money_2(mm) if mm is not None and str(mm).strip() != "" else None
        filas_mc.append(
            {
                "Fecha y hora": str(m.get("created_at", ""))[:19],
                "Cuenta": cmap.get(str(m.get("caja_id")), "—"),
                "Entrada o salida": "Entrada (cobro / ingreso)" if m.get("tipo") == "Ingreso" else "Salida (pago / egreso)",
                "Monto en USD (sistema)": _musd,
                "Moneda original": mon_orig,
                "Monto en moneda original": _mm_orig,
                "Concepto": (m.get("concepto") or "")[:120],
                "Referencia": (m.get("referencia") or "")[:80],
                "Nota tesorería": str(m.get("nota_operacion") or "")[:200],
                "Registrado por": umap.get(str(m.get("usuario_id")), "—"),
            }
        )
    df_mc = pd.DataFrame(filas_mc)
    if df_mc.empty:
        st.info("No hay movimientos en esas fechas y filtros. Probá ampliar el rango o elegir **Todas las cuentas**.")
    else:
        st.dataframe(
            df_mc,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Monto en USD (sistema)": st.column_config.NumberColumn(format="%.2f"),
                "Monto en moneda original": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        tot_in = d.round_money_2(
            df_mc[df_mc["Entrada o salida"].str.startswith("Entrada")]["Monto en USD (sistema)"].sum()
        )
        tot_out = d.round_money_2(
            df_mc[df_mc["Entrada o salida"].str.startswith("Salida")]["Monto en USD (sistema)"].sum()
        )
        m1, m2 = st.columns(2)
        with m1:
            st.metric("Total entradas (USD en el sistema)", f"{tot_in:,.2f}")
        with m2:
            st.metric("Total salidas (USD en el sistema)", f"{tot_out:,.2f}")
        st.caption(
            "Los **USD** son el equivalente que guardó el sistema al momento del movimiento (bolívares y USDT convertidos con la tasa de entonces)."
        )

    ts_c = d.backup_file_timestamp()
    colx, colc = st.columns(2)
    with colx:
        try:
            st.download_button(
                label=f"Descargar Excel — movimientos_caja_{ts_c}.xlsx",
                data=d.reporte_tabla_a_excel(df_mc if not df_mc.empty else pd.DataFrame(), nombre_hoja="Movimientos"),
                file_name=f"movimientos_caja_{ts_c}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="rep_dl_caja_xlsx",
                use_container_width=True,
            )
        except ImportError:
            st.caption("Para Excel hace falta instalar **openpyxl** (ya viene en los requisitos del programa).")
    with colc:
        st.download_button(
            label=f"Descargar CSV — movimientos_caja_{ts_c}.csv",
            data=d.reporte_tabla_a_csv(df_mc if not df_mc.empty else pd.DataFrame()),
            file_name=f"movimientos_caja_{ts_c}.csv",
            mime="text/csv",
            key="rep_dl_caja_csv",
            use_container_width=True,
        )
