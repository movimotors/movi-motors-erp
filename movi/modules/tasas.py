"""Módulo Tasas del día (formulario, tiempo real embebido opcional)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client


@dataclass(frozen=True)
class TasasModuleDeps:
    modulo_titulo_info: Callable[..., None]
    auto_tasa_abs_min_bs: float
    auto_tasa_sync_rel_min: float
    auto_tasa_sync_min_seconds: float
    latest_tasas: Callable[[Client], dict[str, Any] | None]
    nf: Callable[..., Any]
    render_tasas_tiempo_real: Callable[..., Any]
    get_live_exchange_rates: Callable[[], dict[str, Any]]
    render_tabla_tasas_ui: Callable[[pd.DataFrame], None]
    build_tasas_tabla_detalle: Callable[[dict[str, Any]], pd.DataFrame]
    infer_tasa_bs_oper_index: Callable[[dict[str, Any]], int]
    refresh_productos_bs_equiv_note: Callable[[Client, float], str]
    movi_bump_form_nonce: Callable[[str], None]


def render_module_tasas(sb: Client, *, embedded: bool, deps: TasasModuleDeps) -> None:
    """
    Guarda tasas en `tasas_dia`. Si `embedded=True`, no muestra el panel duplicado de tiempo real
    (se usa desde el Dashboard, donde ya existe el expander de tasas en vivo).
    """
    d = deps
    if not embedded:
        d.modulo_titulo_info(
            "Tasas del día",
            key="tasas",
            ayuda_md=(
                "Guardás **BCV oficial** (referencia legal), **ref. Bs/USD mercado** (la que usás desde **Binance P2P** u otra fuente, campo 2), "
                "**EUR** (vía *USD por 1 EUR*), **USDT×VES (P2P Binance)** y **USDT por USD**. "
                "En **Operativo** elegís si ventas/compras usan **BCV** o **esa ref. P2P/mercado** para `tasa_bs`. "
                "**Auto-sync web:** actualiza la ref. mercado Bs/USD; **no cambia el BCV** que cargaste; "
                "`tasa_bs` sigue en BCV si venías operando con BCV. "
                f"Dispara si esa ref. web se mueve ≥ **{d.auto_tasa_abs_min_bs}** Bs/USD"
                + (f" o **≥{d.auto_tasa_sync_rel_min*100:.1f} %**" if d.auto_tasa_sync_rel_min > 0 else "")
                + ".\n\n"
                "Si al guardar ves error de columna inexistente, ejecutá en Supabase el archivo "
                "`supabase/patch_005_tasas_dashboard.sql`."
            ),
        )
    else:
        with st.expander("Información (tasas en este panel)", expanded=False, key="modinfo_exp_tasas_embed"):
            st.markdown(
                f"Elegís **BCV** o **ref. P2P/mercado (campo 2)** para `tasa_bs`. Auto-sync (~cada {int(d.auto_tasa_sync_min_seconds)}s, "
                f"≥{d.auto_tasa_abs_min_bs} Bs/USD) actualiza esa ref.; **no pisa BCV**; respeta si operabas con BCV.\n\n"
                "¿Error de columna al guardar? Ejecutá en Supabase `supabase/patch_005_tasas_dashboard.sql`."
            )

    lt = d.latest_tasas(sb) or {}
    _applied_live = st.session_state.pop("_live_apply", None)

    def dv(key: str, fallback: float) -> float:
        v = d.nf(lt.get(key))
        return float(v) if v is not None else float(fallback)

    if not embedded:
        d.render_tasas_tiempo_real(key_suffix="tasas_mod", t_guardado=lt or None)
        if st.button(
            "Aplicar tasas web al formulario (ref. Bs/USD, EUR, P2P y USDT)",
            key="apply_live_to_form",
            help="Rellena **ref. Bs/USD mercado** (campo 2) y P2P Binance donde aplique. El **BCV oficial** lo cargás vos a mano.",
        ):
            snap = d.get_live_exchange_rates()
            if snap.get("ok"):
                st.session_state["_live_apply"] = snap
                st.rerun()
            else:
                st.warning("No hay datos web listos. Revisa la conexión o pulsa **Refrescar ahora** arriba.")
        st.divider()
    else:
        if st.button(
            "Rellenar formulario con tasas web (ref. Bs/USD, EUR, P2P, USDT)",
            key="apply_live_to_form_embed",
            help="Ref. mercado Bs/USD + P2P; el **BCV oficial** no se toca.",
        ):
            snap = d.get_live_exchange_rates()
            if snap.get("ok"):
                st.session_state["_live_apply"] = snap
                st.rerun()
            else:
                st.warning("No hay datos web listos. Usa **Actualizar cotización web** en la barra lateral.")

    if lt:
        with st.expander("Ver tasas guardadas en BD (detalle)", expanded=False):
            st.caption(f"Último registro — fecha **{lt.get('fecha', '—')}**.")
            d.render_tabla_tasas_ui(d.build_tasas_tabla_detalle(lt))
    else:
        st.warning("Aún no hay tasas en base de datos. Completa el formulario y guarda.")

    par_def = (
        float(_applied_live["ves_bs_por_usd"])
        if (_applied_live and _applied_live.get("ves_bs_por_usd"))
        else dv("paralelo_bs_por_usd", dv("tasa_bs", 36.5))
    )
    p2p_def = (
        float(_applied_live["p2p_bs_por_usdt_aprox"])
        if (_applied_live and _applied_live.get("p2p_bs_por_usdt_aprox"))
        else dv("p2p_bs_por_usdt", dv("tasa_bs", 36.5))
    )
    eur_def = (
        float(_applied_live["usd_por_eur"])
        if (_applied_live and _applied_live.get("usd_por_eur"))
        else dv("usd_por_eur", 1.08)
    )
    usdt_def = (
        float(_applied_live["usdt_por_usd"])
        if (_applied_live and _applied_live.get("usdt_por_usd"))
        else dv("tasa_usdt", 1.0)
    )

    _tasa_fn = int(st.session_state.get("tasa_form_nonce", 0))
    _form_id = (f"f_tasa_embed_{_tasa_fn}" if embedded else f"f_tasa_{_tasa_fn}")
    _oper_opts = ("BCV oficial (campo 1)", "Mercado P2P Binance — Bs/USD (campo 2)")
    with st.form(_form_id):
        f = st.date_input("Fecha", value=date.today())
        st.markdown("**1 · Tasa oficial BCV**")
        st.caption(
            "Tipo de cambio **legal** del **Banco Central de Venezuela**. "
            "La referencia **Binance P2P** va en el bloque siguiente, no aquí."
        )
        bcv = st.number_input(
            "Bs por 1 USD — oficial BCV",
            min_value=0.00000001,
            value=dv("bcv_bs_por_usd", dv("tasa_bs", 36.5)),
            format="%.8f",
        )
        st.markdown("**2 · Mercado P2P (Binance) — Bs por 1 USD**")
        st.caption(
            "Referencia de **mercado** que usás operativamente (p. ej. la que ves en **Binance P2P** "
            "u otra fuente P2P). **No es la tasa oficial BCV.** Si solo facturás con BCV, podés repetir el valor del campo 1."
        )
        par = st.number_input(
            "Bs por 1 USD — ref. mercado / Binance P2P",
            min_value=0.00000001,
            value=par_def,
            format="%.8f",
            help="Valor Bs por cada USD según tu referencia P2P (Binance) o la que cargues a mano.",
        )
        st.markdown("**3 · Otros cruces (tablas y dashboard)**")
        usd_eur = st.number_input(
            "USD por 1 EUR (referencia para EUR×VES en el detalle)",
            min_value=0.00000001,
            value=eur_def,
            format="%.8f",
            help="En el detalle verás EUR×VES con BCV y con la ref. mercado (campo 2), según estos valores.",
        )
        p2p = st.number_input(
            "USDT × VES — P2P (Bs por 1 USDT)",
            min_value=0.00000001,
            value=p2p_def,
            format="%.8f",
        )
        st.markdown("**4 · Operativo (facturación / sistema)**")
        t_usdt = st.number_input(
            "USDT por 1 USD (referencia)",
            min_value=0.00000001,
            value=usdt_def,
            format="%.8f",
            help="Para USD↔USDT en pantallas y el equivalente USD×Bs vía P2P.",
        )
        oper_sel = st.radio(
            "Para ventas, compras y campo `tasa_bs` en base de datos, usar:",
            options=_oper_opts,
            index=d.infer_tasa_bs_oper_index(lt),
            horizontal=True,
            help="BCV legal (campo 1) o la ref. Bs/USD que cargás como mercado P2P Binance (campo 2).",
        )
        t_oper = float(bcv) if oper_sel == _oper_opts[0] else float(par)
        _lbl = "BCV oficial" if oper_sel == _oper_opts[0] else "mercado P2P Binance (campo 2)"
        st.caption(f"Se guardará **tasa_bs** = **{t_oper:,.4f}** Bs/USD (**{_lbl}**).")
        if st.form_submit_button("Guardar / actualizar"):
            if bcv <= 0 or par <= 0 or t_usdt <= 0 or usd_eur <= 0 or p2p <= 0:
                st.error("Todos los valores deben ser mayores que cero.")
            else:
                row = {
                    "fecha": str(f),
                    "tasa_bs": float(t_oper),
                    "tasa_usdt": float(t_usdt),
                    "bcv_bs_por_usd": float(bcv),
                    "paralelo_bs_por_usd": float(par),
                    "usd_por_eur": float(usd_eur),
                    "p2p_bs_por_usdt": float(p2p),
                }
                try:
                    sb.table("tasas_dia").upsert(row, on_conflict="fecha").execute()
                    st.success("Tasas guardadas." + d.refresh_productos_bs_equiv_note(sb, float(t_oper)))
                    d.movi_bump_form_nonce("tasa_form_nonce")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    r = sb.table("tasas_dia").select("*").order("fecha", desc=True).limit(30).execute()
    if r.data:
        st.dataframe(pd.DataFrame(r.data), use_container_width=True, hide_index=True)
