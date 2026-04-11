"""KPIs de período para dashboard / resumen ejecutivo (solo datos, sin Streamlit)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pandas as pd
from supabase import Client

from movi.net_retry import run_transient_http_retry

_ID_CHUNK = 200


def _productos_costo_por_ids(sb: Client, producto_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Solo costos de los IDs pedidos (evita descargar toda la tabla `productos` en cada KPI)."""
    out: dict[str, dict[str, Any]] = {}
    ids = sorted(producto_ids)
    if not ids:
        return out
    for i in range(0, len(ids), _ID_CHUNK):
        chunk = ids[i : i + _ID_CHUNK]
        r = run_transient_http_retry(
            lambda c=chunk: sb.table("productos").select("id, costo_usd").in_("id", c).execute()
        )
        for p in r.data or []:
            out[str(p["id"])] = p
    return out


def compute_dashboard_kpis_periodo(
    sb: Client,
    d_a: date,
    d_b: date,
    *,
    cambios_tesoreria_en_rango: Callable[[Client, date, str], list[dict[str, Any]]],
    caja_map_por_id: Callable[[Client], dict[str, dict[str, Any]]],
    gastos_op_totales_solo_cargado: Callable[
        [Client, str, str, dict[str, dict[str, Any]]],
        tuple[dict[str, float], int, int],
    ],
    fmt_linea_gastos_solo_cargados: Callable[[dict[str, float]], str],
) -> dict[str, Any]:
    """Ventas, margen, stock, liquidez, compras, gastos op. y bitácora en [d_a, d_b]."""
    n_days = max(1, (d_b - d_a).days + 1)
    d_prev_b = d_a - timedelta(days=1)
    d_prev_a = d_prev_b - timedelta(days=n_days - 1)
    r_fut = f"{d_b.isoformat()}T23:59:59"
    rows_cambios_bitacora = cambios_tesoreria_en_rango(sb, d_a, r_fut)
    v_cur = run_transient_http_retry(
        lambda: (
            sb.table("ventas")
            .select("id, total_usd, fecha")
            .gte("fecha", str(d_a))
            .lte("fecha", r_fut)
            .execute()
        )
    )
    v_prev = run_transient_http_retry(
        lambda: (
            sb.table("ventas")
            .select("total_usd")
            .gte("fecha", str(d_prev_a))
            .lte("fecha", f"{d_prev_b.isoformat()}T23:59:59")
            .execute()
        )
    )
    df_vc = pd.DataFrame(v_cur.data or [])
    ventas_usd = float(pd.to_numeric(df_vc["total_usd"], errors="coerce").fillna(0).sum()) if not df_vc.empty else 0.0
    ventas_prev = float(
        pd.to_numeric(pd.DataFrame(v_prev.data or [])["total_usd"], errors="coerce").fillna(0).sum()
    ) if (v_prev.data or []) else 0.0
    vids = [str(x["id"]) for x in (v_cur.data or [])]
    margen_usd = 0.0
    if vids:
        det = run_transient_http_retry(
            lambda: (
                sb.table("ventas_detalles")
                .select("producto_id, cantidad, precio_unitario_usd")
                .in_("venta_id", vids)
                .execute()
            )
        )
        det_rows = det.data or []
        pmap = _productos_costo_por_ids(
            sb,
            {str(row["producto_id"]) for row in det_rows if row.get("producto_id") is not None},
        )
        for row in det_rows:
            pid = str(row["producto_id"])
            costo = float(pmap.get(pid, {}).get("costo_usd") or 0)
            cant = float(row["cantidad"])
            pu = float(row["precio_unitario_usd"])
            margen_usd += (pu - costo) * cant
    vids_prev = [
        str(x["id"])
        for x in (
            run_transient_http_retry(
                lambda: (
                    sb.table("ventas")
                    .select("id")
                    .gte("fecha", str(d_prev_a))
                    .lte("fecha", f"{d_prev_b.isoformat()}T23:59:59")
                    .execute()
                )
            ).data
            or []
        )
    ]
    margen_prev = 0.0
    if vids_prev:
        detp = run_transient_http_retry(
            lambda: (
                sb.table("ventas_detalles")
                .select("producto_id, cantidad, precio_unitario_usd")
                .in_("venta_id", vids_prev)
                .execute()
            )
        )
        detp_rows = detp.data or []
        pmap2 = _productos_costo_por_ids(
            sb,
            {str(row["producto_id"]) for row in detp_rows if row.get("producto_id") is not None},
        )
        for row in detp_rows:
            pid = str(row["producto_id"])
            costo = float(pmap2.get(pid, {}).get("costo_usd") or 0)
            cant = float(row["cantidad"])
            pu = float(row["precio_unitario_usd"])
            margen_prev += (pu - costo) * cant
    prods = run_transient_http_retry(
        lambda: sb.table("productos").select("stock_actual, activo").eq("activo", True).execute()
    )
    unidades_stock = float(sum(float(p.get("stock_actual") or 0) for p in (prods.data or [])))
    n_sku = len(prods.data or [])
    try:
        bal = run_transient_http_retry(
            lambda: sb.table("v_balance_consolidado_usd").select("total_usd").execute()
        )
        liquidez = float((bal.data or [{}])[0].get("total_usd") or 0)
    except Exception:
        liquidez = 0.0
    dsl_mov = f"{d_a.isoformat()}T00:00:00"
    try:
        cr_p = run_transient_http_retry(
            lambda: sb.table("compras")
            .select("total_usd")
            .gte("fecha", str(d_a))
            .lte("fecha", r_fut)
            .execute()
        )
        compras_period_usd = sum(float(x.get("total_usd") or 0) for x in (cr_p.data or []))
    except Exception:
        compras_period_usd = 0.0
    gastos_op_period_usd = 0.0
    n_gastos_op_movs = 0
    try:
        mr_go = run_transient_http_retry(
            lambda: (
                sb.table("movimientos_caja")
                .select("monto_usd,categoria_gasto")
                .gte("created_at", dsl_mov)
                .lte("created_at", r_fut)
                .eq("tipo", "Egreso")
                .execute()
            )
        )
        for row in mr_go.data or []:
            cg = row.get("categoria_gasto")
            if cg is not None and str(cg).strip():
                gastos_op_period_usd += float(row.get("monto_usd") or 0)
                n_gastos_op_movs += 1
    except Exception:
        gastos_op_period_usd = 0.0
        n_gastos_op_movs = 0
    total_salidas_op_usd = compras_period_usd + gastos_op_period_usd
    _cmap_kpi = caja_map_por_id(sb)
    go_tot_carg, n_go_moneda, n_go_sin_moneda = gastos_op_totales_solo_cargado(sb, dsl_mov, r_fut, _cmap_kpi)
    go_kpi_main = fmt_linea_gastos_solo_cargados(go_tot_carg) or "—"
    _go_kpi_sub_bits: list[str] = []
    if n_gastos_op_movs:
        _go_kpi_sub_bits.append(f"{n_gastos_op_movs} gasto(s) con categoría en el período")
    if n_go_moneda:
        _go_kpi_sub_bits.append(f"{n_go_moneda} con monto en moneda guardado (suma arriba)")
    if n_go_sin_moneda and n_gastos_op_movs:
        _go_kpi_sub_bits.append(f"{n_go_sin_moneda} sin monto en moneda en BD (no sumados)")
    if not n_gastos_op_movs:
        _go_kpi_sub_bits.append("Registrá en Gastos operativos")
    go_kpi_sub = " · ".join(_go_kpi_sub_bits) if _go_kpi_sub_bits else None
    return {
        "r_fut": r_fut,
        "dsl_mov": dsl_mov,
        "rows_cambios_bitacora": rows_cambios_bitacora,
        "ventas_usd": ventas_usd,
        "ventas_prev": ventas_prev,
        "margen_usd": margen_usd,
        "margen_prev": margen_prev,
        "vids": vids,
        "unidades_stock": unidades_stock,
        "n_sku": n_sku,
        "liquidez": liquidez,
        "compras_period_usd": compras_period_usd,
        "gastos_op_period_usd": gastos_op_period_usd,
        "total_salidas_op_usd": total_salidas_op_usd,
        "n_gastos_op_movs": n_gastos_op_movs,
        "go_tot_carg": go_tot_carg,
        "n_go_moneda": n_go_moneda,
        "n_go_sin_moneda": n_go_sin_moneda,
        "go_kpi_main": go_kpi_main,
        "go_kpi_sub": go_kpi_sub,
    }
