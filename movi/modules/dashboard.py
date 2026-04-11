"""Panel ejecutivo (Dashboard): Bento, tabs mercado / inventario / caja."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import Client

from movi.rbac import role_can


@dataclass(frozen=True)
class DashboardModuleDeps:
    cajas_fetch_rows: Callable[..., Any]
    nf: Callable[..., Any]
    dashboard_kpis_periodo: Callable[[Client, date, date], dict[str, Any]]
    render_dashboard_mercado_live_tarjetas: Callable[[dict[str, Any] | None], None]
    dash_semaforo: Callable[..., str]
    plotly_apply_dash_theme: Callable[..., Any]
    dashboard_seccion_cambios_tesoreria: Callable[..., None]
    dashboard_resumen_cobros_por_moneda: Callable[..., None]
    render_tasas_tiempo_real: Callable[..., Any]
    render_tabla_tasas_ui: Callable[[pd.DataFrame], None]
    build_tasas_tabla_detalle: Callable[[dict[str, Any]], pd.DataFrame]
    run_tasas_embedded: Callable[[Client], None]
    caja_etiqueta_lista: Callable[[dict[str, Any]], str]


def render_module_dashboard(sb: Client, t: dict[str, Any] | None, *, deps: DashboardModuleDeps) -> None:
    """Panel ejecutivo estilo Bento (dark + acentos cian/naranja). Streamlit + Plotly."""
    d = deps
    h1, h2, h3 = st.columns([2.2, 2.2, 1.6])
    with h1:
        st.markdown('<p class="dash-header-title">Panel Movi Motors</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="dash-header-sub">ERP automotriz · multimoneda · vista ejecutiva</p>',
            unsafe_allow_html=True,
        )
    with h2:
        d_a = st.date_input("Desde", value=date.today() - timedelta(days=30), key="dash_d0")
        d_b = st.date_input("Hasta", value=date.today(), key="dash_d1")
    with h3:
        q_search = st.text_input(
            "Buscar", placeholder="Producto, código…", key="dash_global_search", label_visibility="visible"
        )

    if d_b < d_a:
        st.error("La fecha *Hasta* debe ser ≥ *Desde*.")
        st.stop()

    _bit_flash = st.session_state.pop("dash_bitacora_flash", None)
    if isinstance(_bit_flash, dict):
        if _bit_flash.get("aplicar_mov"):
            _dm_f = str(_bit_flash.get("dest_moneda") or "").strip().upper()
            if _dm_f == "USDT":
                _dest_txt = "El equivalente quedó en **USDT** (moneda estable en la caja destino)."
            elif _dm_f == "USD":
                _dest_txt = (
                    "El equivalente quedó en **USD** en la cuenta destino (banco, efectivo en dólares o **Zelle**, según cómo tengas nombrada esa caja)."
                )
            else:
                _dest_txt = "El equivalente quedó en la **cuenta destino** en moneda estable."
            st.success(
                f"**Bitácora guardada con movimientos en caja:** salieron **{_bit_flash.get('monto_bs', 0):,.2f} Bs** del saldo en bolívares; "
                f"ingresó **~US$ {float(_bit_flash.get('monto_usd') or 0):,.2f}** de equivalente en destino. {_dest_txt} "
                "Ese monto en **VES** ya no debería figurar como bolívares en caja; si algo no cuadra, revisá **Caja, cobros y tasas**."
            )
        else:
            st.info(
                "**Bitácora guardada solo como anotación:** no se movieron saldos entre cajas. "
                "Para que los Bs **salgan** de la cuenta VES y el equivalente **entre** a USD/USDT/efectivo dólar, "
                "marcá **Aplicar movimientos en caja**, elegí origen y destino, y guardá de nuevo."
            )

    if st.session_state.get("dash_open_cambio_tesoreria"):
        st.info("Abriendo formulario de cambio (bitácora)…")

    _caj_ves_alert = d.cajas_fetch_rows(sb, solo_activas=True)
    sum_ves_equiv_usd = sum(
        float(c.get("saldo_actual_usd") or 0)
        for c in _caj_ves_alert
        if str(c.get("moneda_cuenta") or "").strip().upper() == "VES"
    )
    # Aviso solo si el remanente VES (equiv. USD) supera este monto (evita ruido por centavos / ~US$ 1).
    _ves_remanente_alerta_min_usd = 20.0
    if sum_ves_equiv_usd > _ves_remanente_alerta_min_usd:
        _ves_cajas = [
            c
            for c in _caj_ves_alert
            if str(c.get("moneda_cuenta") or "").strip().upper() == "VES" and float(c.get("saldo_actual_usd") or 0) > 0.00001
        ]
        _ves_cajas.sort(key=lambda x: -float(x.get("saldo_actual_usd") or 0))
        _ves_top = _ves_cajas[0] if _ves_cajas else None

        st.warning(
            f"**Todavía hay equivalente en cuentas en bolívares (VES):** suman ~**US$ {sum_ves_equiv_usd:,.2f}** en el sistema — es lo que **aún está** en caja/banco en Bs. "
            "Si **registraste un cambio con movimientos de caja**, lo que cambiaste **ya salió** de ahí: el valor pasó a la cuenta destino en **USD**, **USDT** o **efectivo en dólares** "
            "(**Zelle** suele registrarse en una caja en **USD**). Este aviso solo refleja **lo que sigue** en VES, no lo ya convertido."
        )
        c1, c2 = st.columns([1.4, 2.6])
        with c1:
            if st.button("Registrar cambio ahora", use_container_width=True, key="dash_cta_registrar_cambio"):
                _tasa_pref = 1.0
                if t:
                    _tasa_pref = float(d.nf(t.get("bcv_bs_por_usd")) or 0) or float(d.nf(t.get("tasa_bs")) or 0) or float(
                        d.nf(t.get("paralelo_bs_por_usd")) or 0
                    ) or 1.0
                if _ves_top is not None:
                    # Prefill para ambas instancias del formulario (Resumen y Caja).
                    for _ks in ("_res", "_caja"):
                        st.session_state[f"dash_ct_orig{_ks}"] = str(_ves_top.get("id"))
                        st.session_state[f"dash_ct_musd{_ks}"] = float(_ves_top.get("saldo_actual_usd") or 0.0)
                        st.session_state[f"dash_ct_mves{_ks}"] = float(_ves_top.get("saldo_actual_usd") or 0.0) * float(
                            _tasa_pref
                        )
                    # Nota: no conocemos Bs exactos; sugerimos Bs ref. usando la tasa del panel.
                st.session_state["dash_open_cambio_tesoreria"] = True
                st.session_state["dash_cta_ack"] = (st.session_state.get("dash_cta_ack") or 0) + 1
                st.rerun()
        with c2:
            st.caption(
                "Recomendación operativa: convertí el remanente en VES a una cuenta estable (USD/USDT/Zelle) y registralo en la bitácora para que los saldos del panel reflejen la realidad."
            )

    k_dash = d.dashboard_kpis_periodo(sb, d_a, d_b)
    r_fut = k_dash["r_fut"]
    dsl_mov = k_dash["dsl_mov"]
    rows_cambios_bitacora = k_dash["rows_cambios_bitacora"]
    ventas_usd = k_dash["ventas_usd"]
    ventas_prev = k_dash["ventas_prev"]
    margen_usd = k_dash["margen_usd"]
    margen_prev = k_dash["margen_prev"]
    vids = k_dash["vids"]
    unidades_stock = k_dash["unidades_stock"]
    n_sku = k_dash["n_sku"]
    liquidez = k_dash["liquidez"]
    compras_period_usd = k_dash["compras_period_usd"]
    gastos_op_period_usd = k_dash["gastos_op_period_usd"]
    total_salidas_op_usd = k_dash["total_salidas_op_usd"]
    n_gastos_op_movs = k_dash["n_gastos_op_movs"]
    go_tot_carg = k_dash["go_tot_carg"]
    n_go_moneda = k_dash["n_go_moneda"]
    n_go_sin_moneda = k_dash["n_go_sin_moneda"]
    go_kpi_main = k_dash["go_kpi_main"]
    go_kpi_sub = k_dash["go_kpi_sub"]

    with st.expander("Información del panel", expanded=False, key="modinfo_exp_dashboard"):
        st.markdown(
            "**Cómo recorrer el dashboard:** 1) Elegí **Desde / Hasta** arriba. 2) Pestaña **Mercado en vivo** → cotizaciones. "
            "El **resumen ejecutivo completo** (KPIs, PDF, cuentas, gráficos) está en **Reportes → Resumen ejecutivo**. "
            "3) **Inventario y stock** → semáforo y valor (el **Buscar** de arriba filtra la tabla). 4) **Caja, cobros y tasas** → flujo, cobros por moneda, bitácora, tasas y últimos movimientos. "
            "**Usuarios** del ERP están en **Mantenimiento** (superusuario)."
        )
    tab_d_mercado, tab_d_inv, tab_d_caja = st.tabs(
        [
            "Mercado en vivo",
            "Inventario y stock",
            "Caja, cobros y tasas",
        ]
    )

    with tab_d_mercado:
        d.render_dashboard_mercado_live_tarjetas(t)
        st.info(
            "**Resumen ejecutivo** (KPIs, PDF imprimible, cuentas, flujo y gráficos del período): abrí el módulo **Reportes** "
            "y la pestaña **Resumen ejecutivo**. Allí elegís **Desde / Hasta** propios del reporte."
        )

    pinv = (
        sb.table("productos")
        .select("id, codigo, descripcion, stock_actual, stock_minimo, costo_usd, precio_v_usd, categorias(nombre)")
        .eq("activo", True)
        .execute()
        .data
        or []
    )

    def _dash_inv_sem_prio(s: str) -> int:
        if str(s).startswith("🔴"):
            return 0
        if str(s).startswith("🟡"):
            return 1
        return 2

    ventas_qty_dash: dict[str, float] = {}
    if vids:
        dq_dash = (
            sb.table("ventas_detalles")
            .select("producto_id, cantidad")
            .in_("venta_id", vids)
            .execute()
            .data
            or []
        )
        for r in dq_dash:
            pid = str(r["producto_id"])
            ventas_qty_dash[pid] = ventas_qty_dash.get(pid, 0) + float(r.get("cantidad") or 0)
    rows_inv_dash: list[dict[str, Any]] = []
    for p in pinv:
        pid = str(p["id"])
        st_a = float(p.get("stock_actual") or 0)
        st_m = float(p.get("stock_minimo") or 0)
        if st_a <= 0:
            continue
        vq = ventas_qty_dash.get(pid, 0.0)
        cat = p.get("categorias")
        if isinstance(cat, list) and cat:
            cat = cat[0]
        cat_n = cat.get("nombre") if isinstance(cat, dict) else "—"
        rows_inv_dash.append(
            {
                "Semáforo": d.dash_semaforo(stock=st_a, minimo=st_m, vendido_periodo=vq),
                "Producto": str(p.get("descripcion", ""))[:80],
                "Código": str(p.get("codigo") or "—"),
                "Categoría": str(cat_n or "—")[:40],
                "Stock": st_a,
                "Mín.": st_m,
                "Vendido (período)": vq,
                "Valor inv. USD": round(st_a * float(p.get("costo_usd") or 0), 2),
            }
        )
    dfi_inv = pd.DataFrame(rows_inv_dash)
    if not dfi_inv.empty:
        dfi_inv["_prio"] = dfi_inv["Semáforo"].map(_dash_inv_sem_prio)
        dfi_inv = dfi_inv.sort_values(["_prio", "Valor inv. USD"], ascending=[True, False]).drop(columns=["_prio"])

    with tab_d_inv:
        st.caption(
            "El campo **Buscar** del encabezado filtra la tabla de la izquierda. La columna *Vendido (período)* usa las mismas fechas **Desde/Hasta** que arriba."
        )
        row3a, row3b = st.columns([1.2, 1])
        with row3a:
            st.markdown('<div class="dash-bento">', unsafe_allow_html=True)
            st.markdown("**Productos con baja rotación** · semáforo de inventario")
            st.caption("🟢 OK · 🟡 revisar · 🔴 bajo mínimo")
            if dfi_inv.empty:
                st.info("No hay stock positivo para analizar.")
            else:
                dfi_show = dfi_inv.copy()
                if q_search and q_search.strip():
                    qs = q_search.strip().lower()
                    mask = dfi_show["Producto"].str.lower().str.contains(qs, na=False) | dfi_show[
                        "Código"
                    ].str.lower().str.contains(qs, na=False)
                    dfi_show = dfi_show[mask]
                if dfi_show.empty:
                    st.info("Ningún producto coincide con la búsqueda. Probá otro texto o vaciá el buscador.")
                else:
                    st.dataframe(dfi_show, use_container_width=True, hide_index=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with row3b:
            st.markdown('<div class="dash-bento">', unsafe_allow_html=True)
            st.markdown("**Valor de inventario por categoría** (costo × stock)")
            if not pinv:
                st.caption("Sin productos.")
            else:
                rows_cat: list[dict[str, Any]] = []
                for p in pinv:
                    cat = p.get("categorias")
                    if isinstance(cat, list) and cat:
                        cat = cat[0]
                    cn = str(cat.get("nombre")) if isinstance(cat, dict) and cat.get("nombre") else "Sin categoría"
                    rows_cat.append(
                        {
                            "categoria": cn,
                            "valor_usd": float(p.get("stock_actual") or 0) * float(p.get("costo_usd") or 0),
                        }
                    )
                dfc2 = pd.DataFrame(rows_cat).groupby("categoria", as_index=False)["valor_usd"].sum()
                dfc2 = dfc2[dfc2["valor_usd"] > 0]
                if dfc2.empty:
                    st.caption("Sin valor de inventario (costos en cero o sin stock).")
                else:
                    fig_iv = px.bar(
                        dfc2.sort_values("valor_usd", ascending=True),
                        x="valor_usd",
                        y="categoria",
                        orientation="h",
                        labels={"valor_usd": "USD", "categoria": ""},
                    )
                    fig_iv.update_traces(marker_color="#00e5ff", hovertemplate="%{y}: %{x:,.2f} USD<extra></extra>")
                    d.plotly_apply_dash_theme(fig_iv, title="Inventario por categoría")
                    st.plotly_chart(fig_iv, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_d_caja:
        st.caption("Movimientos del período, cobros por moneda, comparación ventas/compras y **tasas** (expandibles abajo).")
        st.divider()
        st.markdown("##### Flujo de caja y ventas (detalle)")
        dsl = d_a.isoformat()
        mh = (
            sb.table("movimientos_caja")
            .select("created_at, tipo, monto_usd")
            .gte("created_at", dsl)
            .execute()
        )
        dfm = pd.DataFrame(mh.data or [])
        if dfm.empty:
            st.caption("Sin movimientos de caja en el rango seleccionado.")
        else:
            ts = pd.to_datetime(dfm["created_at"], errors="coerce")
            dfm["dia"] = ts.dt.strftime("%Y-%m-%d")
            dfm["monto_usd"] = pd.to_numeric(dfm["monto_usd"], errors="coerce").fillna(0)
            ing = dfm[dfm["tipo"] == "Ingreso"].groupby("dia", as_index=False)["monto_usd"].sum().rename(columns={"monto_usd": "Ingreso"})
            egr = dfm[dfm["tipo"] == "Egreso"].groupby("dia", as_index=False)["monto_usd"].sum().rename(columns={"monto_usd": "Egreso"})
            merged_ie = pd.merge(
                pd.DataFrame({"dia": sorted(dfm["dia"].unique())}),
                ing,
                on="dia",
                how="left",
            )
            merged_ie = pd.merge(merged_ie, egr, on="dia", how="left").fillna(0)
            merged_ie["Ingreso"] = pd.to_numeric(merged_ie["Ingreso"], errors="coerce").fillna(0).round(2)
            merged_ie["Egreso"] = pd.to_numeric(merged_ie["Egreso"], errors="coerce").fillna(0).round(2)
            fig_ie = px.bar(
                merged_ie,
                x="dia",
                y=["Ingreso", "Egreso"],
                barmode="group",
                labels={"value": "USD", "dia": "Día", "variable": ""},
            )
            fig_ie.update_traces(
                marker_line_width=0,
                hovertemplate="<b>%{data.name}</b><br>%{x}<br>%{y:,.2f} USD<extra></extra>",
            )
            d.plotly_apply_dash_theme(fig_ie, title="Ingresos y egresos por día")
            st.plotly_chart(fig_ie, use_container_width=True)

        d.dashboard_seccion_cambios_tesoreria(
            sb, t=t, d_a=d_a, d_b=d_b, r_fut=r_fut, rows_raw=rows_cambios_bitacora, key_suffix="caja"
        )

        st.markdown("##### Resumen: qué entró en Bs, USD y USDT (y en qué cuenta)")
        d.dashboard_resumen_cobros_por_moneda(sb, d_a=d_a, r_fut=r_fut)

        vrows = sb.table("ventas").select("fecha, total_usd").gte("fecha", str(d_a)).lte("fecha", r_fut).execute()
        crows = sb.table("compras").select("fecha, total_usd").gte("fecha", str(d_a)).lte("fecha", r_fut).execute()
        dfv = pd.DataFrame(vrows.data or [])
        dfc_v = pd.DataFrame(crows.data or [])
        if dfv.empty and dfc_v.empty:
            st.caption("Sin ventas ni compras en el rango.")
        else:
            vsum = (
                dfv.assign(
                    dia=pd.to_datetime(dfv["fecha"], errors="coerce").dt.strftime("%Y-%m-%d"),
                    total_usd=pd.to_numeric(dfv["total_usd"], errors="coerce").fillna(0),
                )
                .groupby("dia", as_index=False)["total_usd"]
                .sum()
                .rename(columns={"total_usd": "Ventas USD"})
                if not dfv.empty
                else pd.DataFrame(columns=["dia", "Ventas USD"])
            )
            csum = (
                dfc_v.assign(
                    dia=pd.to_datetime(dfc_v["fecha"], errors="coerce").dt.strftime("%Y-%m-%d"),
                    total_usd=pd.to_numeric(dfc_v["total_usd"], errors="coerce").fillna(0),
                )
                .groupby("dia", as_index=False)["total_usd"]
                .sum()
                .rename(columns={"total_usd": "Compras USD"})
                if not dfc_v.empty
                else pd.DataFrame(columns=["dia", "Compras USD"])
            )
            dias = sorted(
                set(vsum["dia"].tolist() if not vsum.empty else []) | set(csum["dia"].tolist() if not csum.empty else [])
            )
            out_vc = pd.DataFrame({"dia": dias})
            out_vc = out_vc.merge(vsum, on="dia", how="left").merge(csum, on="dia", how="left").fillna(0)
            for _col in ("Ventas USD", "Compras USD"):
                if _col in out_vc.columns:
                    out_vc[_col] = pd.to_numeric(out_vc[_col], errors="coerce").fillna(0.0)

            out_vc_long = out_vc.melt(
                id_vars=["dia"],
                value_vars=[c for c in ("Ventas USD", "Compras USD") if c in out_vc.columns],
                var_name="serie",
                value_name="value",
            )
            fig_vc = px.line(
                out_vc_long,
                x="dia",
                y="value",
                color="serie",
                markers=True,
                labels={"value": "USD", "dia": "Día", "serie": ""},
            )
            fig_vc.update_traces(line=dict(width=2))
            d.plotly_apply_dash_theme(fig_vc, title="Ventas vs compras (USD)")
            st.plotly_chart(fig_vc, use_container_width=True)

        with st.expander("Tasas en vivo y tabla guardada (BCV · ref. mercado / P2P Binance)", expanded=False):
            d.render_tasas_tiempo_real(key_suffix="dash", t_guardado=t)
            if t:
                st.caption(f"Registro tasas **{t.get('fecha', '—')}**")
                d.render_tabla_tasas_ui(d.build_tasas_tabla_detalle(t))
            else:
                st.warning("Sin tasas del día en base de datos.")

        rol_dash = str(st.session_state.get("erp_rol", ""))
        if role_can(rol_dash, "tasas"):
            with st.expander("Cargar / editar tasas (BCV, ref. P2P Binance Bs/USD, USDT P2P)", expanded=False):
                d.run_tasas_embedded(sb)

        st.divider()
        st.markdown("##### Últimos movimientos de caja")
        try:
            mov = (
                sb.table("movimientos_caja")
                .select("created_at, tipo, monto_usd, concepto, caja_id, moneda, nota_operacion")
                .order("created_at", desc=True)
                .limit(15)
                .execute()
            )
        except Exception:
            mov = (
                sb.table("movimientos_caja")
                .select("created_at, tipo, monto_usd, concepto, caja_id")
                .order("created_at", desc=True)
                .limit(15)
                .execute()
            )
        if mov.data:
            _mc_cajas = d.cajas_fetch_rows(sb, solo_activas=False)
            _mc_map = {str(c["id"]): d.caja_etiqueta_lista(c) for c in _mc_cajas}
            df_mc = pd.DataFrame(mov.data)
            df_mc["caja"] = df_mc["caja_id"].map(lambda x: _mc_map.get(str(x), str(x)[:8] + "…"))
            df_mc = df_mc.drop(columns=["caja_id"], errors="ignore")
            cols = ["created_at", "tipo", "monto_usd", "moneda", "caja", "concepto", "nota_operacion"]
            df_mc = df_mc[[c for c in cols if c in df_mc.columns]]
            if "monto_usd" in df_mc.columns:
                df_mc["monto_usd"] = pd.to_numeric(df_mc["monto_usd"], errors="coerce").fillna(0).round(2)
            st.dataframe(
                df_mc,
                use_container_width=True,
                hide_index=True,
                column_config=(
                    {"monto_usd": st.column_config.NumberColumn(format="%.2f")}
                    if "monto_usd" in df_mc.columns
                    else {}
                ),
            )
        else:
            st.caption("Sin movimientos.")
