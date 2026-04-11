"""Módulo Cajas y bancos: listado, alta y movimiento manual."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client


@dataclass(frozen=True)
class CajasModuleDeps:
    modulo_titulo_info: Callable[..., None]
    latest_tasas: Callable[[Client], dict[str, Any] | None]
    caja_saldo_cuenta_y_equiv: Callable[..., tuple[str, str]]
    movi_bump_form_nonce: Callable[[str], None]
    cajas_fetch_rows: Callable[..., Any]
    caja_select_options: Callable[[list[dict[str, Any]]], tuple[list[str], Any]]
    movi_ss_pop_keys: Callable[..., None]


def render_module_cajas(sb: Client, erp_uid: str, *, deps: CajasModuleDeps) -> None:
    d = deps
    d.modulo_titulo_info(
        "Cajas y bancos",
        key="cajas",
        ayuda_md=(
            "Cada fila es una **cuenta concreta**: banco o entidad (Banesco, Bancamiga…), alias interno, moneda de la cuenta (VES/USD/USDT), número y titular. "
            "**Saldo en cuenta** en **Bs** en cuentas VES, **USD** o **USDT** según la moneda; el valor interno en BD sigue siendo equiv. USD para el motor. "
            "Los **gastos operativos** (alquiler, servicios, nómina…) podés registrarlos en el módulo **Gastos operativos**."
        ),
    )
    rows = sb.table("cajas_bancos").select("*").order("nombre").execute()
    if rows.data:
        df_c = pd.DataFrame(rows.data)
        _t_cajas = d.latest_tasas(sb) or {}
        _sc: list[str] = []
        _eq: list[str] = []
        for _, _r in df_c.iterrows():
            _a, _b = d.caja_saldo_cuenta_y_equiv(_r.get("moneda_cuenta"), _r.get("saldo_actual_usd"), _t_cajas)
            _sc.append(_a)
            _eq.append(_b)
        df_c["Saldo en cuenta"] = _sc
        df_c["Equiv. USD (sistema)"] = _eq
        pref = [
            "entidad",
            "nombre",
            "tipo",
            "moneda_cuenta",
            "numero_cuenta",
            "titular",
            "Saldo en cuenta",
            "Equiv. USD (sistema)",
            "activo",
        ]
        cols_show = [c for c in pref if c in df_c.columns] + [
            c for c in df_c.columns if c not in pref and c != "saldo_actual_usd"
        ]
        st.dataframe(df_c[cols_show], use_container_width=True, hide_index=True)

    with st.expander("Nueva caja / cuenta"):
        st.caption("Si falla al guardar, ejecutá en Supabase `supabase/patch_015_cajas_detalle.sql`.")
        with st.form(f"f_caja_{int(st.session_state.get('caja_alta_form_nonce', 0))}"):
            entidad = st.text_input("Banco / entidad (ej. Banesco, Bancamiga)", placeholder="Opcional si es efectivo")
            nombre = st.text_input("Nombre o alias en el ERP", help="Ej. Corriente USD proveedores")
            tipo = st.selectbox("Tipo", ["Banco", "Wallet", "Efectivo"])
            moneda_cuenta = st.selectbox("Moneda de la cuenta", ["USD", "VES", "USDT"], index=0)
            numero_cuenta = st.text_input("Número de cuenta (últimos dígitos o completo)", placeholder="Opcional")
            titular = st.text_input("Titular", placeholder="Opcional")
            if st.form_submit_button("Crear"):
                if not nombre or not str(nombre).strip():
                    st.error("El nombre es obligatorio.")
                else:
                    try:
                        sb.table("cajas_bancos").insert(
                            {
                                "nombre": nombre.strip(),
                                "tipo": tipo,
                                "saldo_actual_usd": 0,
                                "entidad": entidad.strip() or None,
                                "numero_cuenta": numero_cuenta.strip() or None,
                                "titular": titular.strip() or None,
                                "moneda_cuenta": moneda_cuenta,
                            }
                        ).execute()
                        st.success("Caja creada.")
                        d.movi_bump_form_nonce("caja_alta_form_nonce")
                        st.rerun()
                    except Exception as e:
                        st.error(
                            f"{e} · Si falta columna en BD, aplicá el parche **patch_015_cajas_detalle** en Supabase."
                        )

    caja_rows_mov = d.cajas_fetch_rows(sb, solo_activas=True)
    caja_ids_mov, caja_fmt_mov = d.caja_select_options(caja_rows_mov) if caja_rows_mov else ([], lambda x: str(x))
    if not caja_ids_mov:
        st.info("No hay cajas activas: creá al menos una para movimientos manuales.")
        st.stop()

    st.caption("Movimiento manual (ajuste de caja)")
    with st.form(f"f_mov_{int(st.session_state.get('caja_mov_form_nonce', 0))}"):
        cid_mov = st.selectbox("Caja", options=caja_ids_mov, format_func=caja_fmt_mov)
        tipo_m = st.selectbox("Tipo movimiento", ["Ingreso", "Egreso"])
        monto = st.number_input("Monto USD", min_value=0.01, format="%.2f")
        concepto = st.text_input("Concepto")
        ref = st.text_input("Referencia")
        nota_mov = st.text_input(
            "Nota de tesorería (opcional)",
            placeholder="Ej.: Cambio Bs→USD, traspaso entre cuentas…",
            key="caja_mov_nota_op",
        )
        if st.form_submit_button("Registrar"):
            try:
                _rpc_mov: dict[str, Any] = {
                    "p_usuario_id": erp_uid,
                    "p_caja_id": str(cid_mov),
                    "p_tipo": tipo_m,
                    "p_monto_usd": float(monto),
                    "p_concepto": concepto,
                    "p_referencia": ref,
                }
                if (nota_mov or "").strip():
                    _rpc_mov["p_nota_operacion"] = (nota_mov or "").strip()
                sb.rpc("registrar_movimiento_caja_erp", _rpc_mov).execute()
                st.success("Movimiento registrado.")
                d.movi_ss_pop_keys("caja_mov_nota_op")
                d.movi_bump_form_nonce("caja_mov_form_nonce")
                st.rerun()
            except Exception as e:
                st.error(str(e))
