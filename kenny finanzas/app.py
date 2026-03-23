"""
Kenny Finanzas — ingresos y egresos (cuenta BofA u otras).
Supabase: proyecto NUEVO, solo este esquema (supabase/schema.sql).
No usar patches/SQL del ERP de la empresa en la misma base.
Secretos: .streamlit/secrets.toml (ver secrets.toml.example).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client


def get_supabase() -> Client:
    from supabase import create_client

    u = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
    k = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
    return create_client(str(u), str(k))


def _dec(x: Any) -> Decimal:
    if x is None:
        return Decimal("0")
    return Decimal(str(x))


def load_accounts(sb: Client) -> list[dict[str, Any]]:
    r = sb.table("kf_account").select("*").order("created_at").execute()
    return list(r.data or [])


def load_transactions(sb: Client, account_id: str) -> list[dict[str, Any]]:
    r = (
        sb.table("kf_transaction")
        .select("*")
        .eq("account_id", account_id)
        .order("tx_date", desc=True)
        .order("created_at", desc=True)
        .limit(2000)
        .execute()
    )
    return list(r.data or [])


def compute_balance(account: dict[str, Any], txs: list[dict[str, Any]]) -> Decimal:
    base = _dec(account.get("opening_balance"))
    for t in txs:
        amt = _dec(t.get("amount"))
        if t.get("tx_type") == "ingreso":
            base += amt
        else:
            base -= amt
    return base


def main() -> None:
    st.set_page_config(page_title="Kenny Finanzas", layout="wide")
    st.title("Kenny Finanzas")
    st.caption("Ingresos y egresos · Supabase")

    try:
        sb = get_supabase()
    except Exception as e:
        st.error("No se pudo conectar a Supabase. Revisa `.streamlit/secrets.toml`.")
        st.code(str(e))
        st.stop()

    accounts = load_accounts(sb)

    if not accounts:
        st.subheader("Primera vez: crear tu cuenta (ej. BofA)")
        with st.form("new_account"):
            label = st.text_input("Nombre de la cuenta", value="BofA — Orlando Linares")
            bank = st.text_input("Banco", value="Bank of America")
            holder = st.text_input("Titular", value="Orlando Linares")
            opening = st.number_input(
                "Saldo inicial (desde tu Excel)",
                min_value=-1e12,
                value=0.0,
                step=0.01,
                format="%.2f",
            )
            ob_date = st.date_input("Fecha de ese saldo", value=date.today())
            notes = st.text_area("Notas (opcional)", height=68)
            if st.form_submit_button("Crear cuenta"):
                row = {
                    "label": label.strip() or "Cuenta",
                    "bank_name": bank.strip() or None,
                    "holder_name": holder.strip() or None,
                    "currency": "USD",
                    "opening_balance": float(opening),
                    "opening_balance_date": ob_date.isoformat(),
                    "notes": notes.strip() or None,
                }
                sb.table("kf_account").insert(row).execute()
                st.success("Cuenta creada. Recarga la página o continúa.")
                st.rerun()
        st.info("Ejecutá `supabase/schema.sql` en tu proyecto Supabase si aún no existe la tabla.")
        return

    opts = {a["id"]: f'{a.get("label")} ({a.get("currency", "USD")})' for a in accounts}
    if len(accounts) == 1:
        account_id = accounts[0]["id"]
        st.session_state["kf_account_id"] = account_id
    else:
        account_id = st.selectbox(
            "Cuenta",
            options=list(opts.keys()),
            format_func=lambda i: opts[i],
            key="kf_account_pick",
        )

    acc = next(a for a in accounts if a["id"] == account_id)
    txs = load_transactions(sb, account_id)
    balance = compute_balance(acc, txs)

    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo calculado", f"{balance:,.2f} {acc.get('currency', 'USD')}")
    c2.metric("Saldo inicial (Excel)", f'{_dec(acc.get("opening_balance")):,.2f}')
    c3.metric("Movimientos", len(txs))

    st.divider()
    t1, t2 = st.tabs(["Registrar movimiento", "Ajustar saldo inicial"])

    with t1:
        with st.form("tx"):
            col_a, col_b = st.columns(2)
            with col_a:
                tx_type = st.radio("Tipo", ["ingreso", "egreso"], horizontal=True)
            with col_b:
                tx_date = st.date_input("Fecha", value=date.today())
            amount = st.number_input("Monto", min_value=0.01, value=10.0, step=0.01, format="%.2f")
            description = st.text_input("Descripción", placeholder="Ej. Nómina, supermercado…")
            category = st.text_input("Categoría (opcional)")
            if st.form_submit_button("Guardar"):
                sb.table("kf_transaction").insert(
                    {
                        "account_id": account_id,
                        "tx_type": tx_type,
                        "amount": float(amount),
                        "tx_date": tx_date.isoformat(),
                        "description": description.strip() or "(sin descripción)",
                        "category": category.strip() or None,
                    }
                ).execute()
                st.success("Movimiento guardado.")
                st.rerun()

    with t2:
        st.write(
            "Actualiza el saldo de corte si corregiste el Excel o empezás de otra fecha. "
            "Los movimientos ya cargados se siguen sumando sobre este valor."
        )
        with st.form("adj_opening"):
            new_open = st.number_input(
                "Nuevo saldo inicial",
                min_value=-1e12,
                value=float(_dec(acc.get("opening_balance"))),
                step=0.01,
                format="%.2f",
            )
            _obd = acc.get("opening_balance_date")
            _obd_val = (
                date.fromisoformat(str(_obd)[:10]) if _obd else date.today()
            )
            new_date = st.date_input("Fecha de referencia del saldo", value=_obd_val)
            if st.form_submit_button("Actualizar saldo inicial"):
                sb.table("kf_account").update(
                    {
                        "opening_balance": float(new_open),
                        "opening_balance_date": new_date.isoformat(),
                    }
                ).eq("id", account_id).execute()
                st.success("Saldo inicial actualizado.")
                st.rerun()

    st.divider()
    st.subheader("Últimos movimientos")
    if not txs:
        st.write("Todavía no hay movimientos.")
    else:
        df = pd.DataFrame(txs)
        show = df[
            ["tx_date", "tx_type", "amount", "description", "category", "id"]
        ].copy()
        show["amount"] = show["amount"].apply(lambda x: f"{float(x):,.2f}")
        st.dataframe(show, use_container_width=True, hide_index=True)

        del_id = st.text_input("Eliminar movimiento (pegar ID)", placeholder="uuid…")
        if st.button("Eliminar por ID") and del_id.strip():
            sb.table("kf_transaction").delete().eq("id", del_id.strip()).execute()
            st.success("Eliminado.")
            st.rerun()


if __name__ == "__main__":
    main()
