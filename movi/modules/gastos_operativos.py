"""Módulo Gastos operativos: registro, corrección de egresos y tabla reciente."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client


@dataclass(frozen=True)
class GastosOperativosModuleDeps:
    modulo_titulo_info: Callable[..., None]
    cajas_fetch_rows: Callable[..., Any]
    caja_select_options: Callable[[list[dict[str, Any]]], tuple[list[str], Any]]
    caja_etiqueta_lista: Callable[[dict[str, Any]], str]
    gasto_operativo_categorias: tuple[str, ...]
    gasto_operativo_otro: str
    tasa_bs_para_documento: Callable[..., float]
    nf: Callable[..., Any]
    round_money_2: Callable[..., float]
    error_msg_from_supabase_exc: Callable[[BaseException], str]
    movi_ss_pop_keys: Callable[..., None]
    movi_bump_form_nonce: Callable[[str], None]
    movi_fetch_egresos_caja_recientes: Callable[..., tuple[list[dict[str, Any]], bool]]
    gasto_op_fmt_monto_tabla: Callable[[dict[str, Any], dict[str, dict[str, Any]]], str]


def render_module_gastos_operativos(
    sb: Client, erp_uid: str, t: dict[str, Any] | None, *, deps: GastosOperativosModuleDeps
) -> None:
    d = deps
    d.modulo_titulo_info(
        "Gastos operativos",
        key="gastos_op",
        ayuda_md=(
            "Salidas de efectivo que **no** son compra de mercancía para inventario (eso va en **Compras / CXP**). "
            "El **monto** se ingresa en la **moneda de la cuenta** (Bs, US$ o USDT); el sistema guarda también el **equivalente USD** para el saldo. "
            "Podés **corregir** egresos **manuales** (sin venta/compra ligada) en el expander. "
            "Ejecutá **`patch_025`** (categoría), **`patch_028`** (moneda nativa + corrección) y **`patch_030`** (columnas Bs / USDT / USD de cuenta en movimientos) en Supabase cuando corresponda."
        ),
    )

    caja_rows = d.cajas_fetch_rows(sb, solo_activas=True)
    caja_ids, caja_fmt = d.caja_select_options(caja_rows) if caja_rows else ([], lambda x: str(x))
    if not caja_ids:
        st.warning("No hay cajas activas. Creá una en **Cajas y bancos**.")
        st.stop()

    cmap_full = {str(c["id"]): c for c in d.cajas_fetch_rows(sb, solo_activas=False)}
    cmap_lab = {str(c["id"]): d.caja_etiqueta_lista(c) for c in caja_rows}

    cat_opts = d.gasto_operativo_categorias + (d.gasto_operativo_otro,)

    with st.form(f"f_gasto_op_{int(st.session_state.get('gasto_op_form_nonce', 0))}"):
        cat = st.selectbox("Categoría", options=cat_opts, key="gasto_op_cat")
        cat_custom = ""
        if cat == d.gasto_operativo_otro:
            cat_custom = st.text_input("Nombre de la categoría", key="gasto_op_cat_custom", placeholder="Ej.: Suscripción software")
        desc = st.text_input("Descripción / detalle", key="gasto_op_desc", placeholder="Ej.: Alquiler enero local principal")
        cid = st.selectbox("Caja de donde sale el dinero", options=caja_ids, format_func=caja_fmt, key="gasto_op_caja")
        acc = cmap_full.get(str(cid), {}) or {}
        _mc_raw = acc.get("moneda_cuenta")
        if _mc_raw is None or not str(_mc_raw).strip():
            st.warning(
                "Esta caja **no tiene moneda de cuenta** definida en **Cajas y bancos**. "
                "El formulario tratará la cuenta como **USD** y **no** guardará el monto en **bolívares** en el movimiento. "
                "Editá la caja y elegí **VES**, **USD** o **USDT**."
            )
        mon_cuenta = str(_mc_raw or "USD").strip().upper()
        if mon_cuenta not in ("VES", "USD", "USDT"):
            st.warning(
                f"Moneda de cuenta **{mon_cuenta}** no estándar; usá **VES**, **USD** o **USDT** en la ficha de la caja para cobros y gastos coherentes."
            )
        monto_usd_calc = 0.01
        p_mon: str | None = None
        p_mm: float | None = None
        if mon_cuenta == "VES":
            m_bs = st.number_input("Monto en bolívares (Bs)", min_value=0.01, format="%.2f", key="gasto_op_m_bs")
            try:
                _tb0 = float(d.tasa_bs_para_documento(t, usar_bcv=False)) if t else 0.0
            except (ValueError, TypeError):
                _tb0 = 0.0
            tasa_bs = st.number_input(
                "Tasa Bs por 1 USD (para equivalente en sistema)",
                min_value=0.01,
                value=float(_tb0) if _tb0 > 0 else 300.0,
                format="%.4f",
                key="gasto_op_tasa_bs",
                help="Solo para convertir a USD interno; el gasto se muestra en Bs en reportes.",
            )
            monto_usd_calc = float(m_bs) / float(tasa_bs) if tasa_bs > 0 else 0.0
            p_mon, p_mm = "VES", float(m_bs)
            st.caption(f"Equiv. en sistema: **US$ {d.round_money_2(monto_usd_calc):,.2f}** (Bs ÷ tasa).")
        elif mon_cuenta == "USDT":
            m_ut = st.number_input("Monto en USDT", min_value=0.0001, format="%.4f", key="gasto_op_m_ut")
            t_ut = float(d.nf(t.get("tasa_usdt")) or 1.0) if t else 1.0
            if t_ut <= 0:
                t_ut = 1.0
            monto_usd_calc = float(m_ut) / t_ut
            p_mon, p_mm = "USDT", float(m_ut)
            st.caption(
                f"Equiv. en sistema: **US$ {d.round_money_2(monto_usd_calc):,.2f}** (USDT ÷ tasa USDT/USD **{t_ut:,.6f}** del día en BD)."
            )
        else:
            m_us = st.number_input("Monto en USD", min_value=0.01, format="%.2f", key="gasto_op_m_usd")
            monto_usd_calc = float(m_us)
            p_mon, p_mm = "USD", float(m_us)
        ref = st.text_input("Referencia (Nº factura, recibo…)", key="gasto_op_ref")
        nota = st.text_input(
            "Nota de tesorería (opcional)",
            key="gasto_op_nota",
            placeholder="Ej.: Pago Banesco / efectivo",
        )
        submitted = st.form_submit_button("Registrar gasto operativo")
        if submitted:
            cat_final = (cat_custom or "").strip() if cat == d.gasto_operativo_otro else cat
            if cat == d.gasto_operativo_otro and not cat_final:
                st.error("Completá el nombre de la categoría.")
            elif not (desc or "").strip():
                st.error("La descripción es obligatoria.")
            elif monto_usd_calc <= 0:
                st.error("El equivalente USD calculado debe ser mayor que cero (revisá monto y tasa).")
            else:
                payload: dict[str, Any] = {
                    "p_usuario_id": erp_uid,
                    "p_caja_id": str(cid),
                    "p_tipo": "Egreso",
                    "p_monto_usd": float(monto_usd_calc),
                    "p_concepto": (desc or "").strip(),
                    "p_referencia": (ref or "").strip(),
                }
                if (nota or "").strip():
                    payload["p_nota_operacion"] = (nota or "").strip()
                payload_cat = cat_final if cat_final else None
                if payload_cat:
                    payload["p_categoria_gasto"] = payload_cat
                if p_mon and p_mm is not None and p_mm > 0:
                    payload["p_moneda"] = p_mon
                    payload["p_monto_moneda"] = float(p_mm)

                def _try_reg(pl: dict[str, Any]) -> Exception | None:
                    try:
                        sb.rpc("registrar_movimiento_caja_erp", pl).execute()
                        return None
                    except Exception as ex:
                        return ex

                err = _try_reg(payload)
                if err is not None:
                    err_s = d.error_msg_from_supabase_exc(err)
                    low = err_s.lower()
                    if "p_moneda" in low or "p_monto_moneda" in low:
                        payload.pop("p_moneda", None)
                        payload.pop("p_monto_moneda", None)
                        err = _try_reg(payload)
                        if err is None:
                            st.warning(
                                "Gasto guardado **sin** moneda nativa en BD. Ejecutá **`supabase/patch_028_mov_caja_moneda_nativa_y_correccion.sql`** "
                                "o revisá que la firma del RPC en Supabase incluya `p_moneda` y `p_monto_moneda`."
                            )
                    if err is not None:
                        err_s = d.error_msg_from_supabase_exc(err)
                        low = err_s.lower()
                        if payload_cat and any(
                            x in low for x in ("categoria_gasto", "p_categoria", "could not find", "42883", "42725")
                        ):
                            payload.pop("p_categoria_gasto", None)
                            payload["p_concepto"] = f"[{cat_final}] {(desc or '').strip()}"
                            err = _try_reg(payload)
                            if err is None:
                                st.warning(
                                    "Se guardó **sin** columna de categoría. Ejecutá **`patch_025`** en Supabase."
                                )
                        if err is not None:
                            st.error(d.error_msg_from_supabase_exc(err))
                if err is None:
                    st.success("Gasto registrado.")
                    d.movi_ss_pop_keys(
                        "gasto_op_cat",
                        "gasto_op_cat_custom",
                        "gasto_op_desc",
                        "gasto_op_m_bs",
                        "gasto_op_tasa_bs",
                        "gasto_op_m_ut",
                        "gasto_op_m_usd",
                        "gasto_op_caja",
                        "gasto_op_ref",
                        "gasto_op_nota",
                    )
                    d.movi_bump_form_nonce("gasto_op_form_nonce")
                    st.rerun()

    rows_eg, tiene_cat = d.movi_fetch_egresos_caja_recientes(sb, limit=200)
    editable = [
        r
        for r in rows_eg
        if not r.get("venta_id") and not r.get("compra_id") and r.get("id")
    ]
    with st.expander("✏️ Corregir un egreso manual (monto o texto)", expanded=False):
        _flash_corr = st.session_state.pop("flash_gasto_op_correccion", None)
        if isinstance(_flash_corr, dict) and _flash_corr.get("ok"):
            st.success(str(_flash_corr.get("msg") or "Cambios guardados."))
        elif isinstance(_flash_corr, dict) and not _flash_corr.get("ok"):
            st.error(str(_flash_corr.get("msg") or "No se pudo guardar."))
        st.caption(
            "Solo movimientos **sin** venta ni compra ligada. "
            "En cuentas **VES** / **USDT** cargás el **monto en la moneda del banco**; el ERP calcula el **equiv. USD** (`monto_usd`) que usa el **motor de saldos** (igual que al dar de alta un gasto). "
            "En cuenta **USD** el monto es directamente en dólares. Requiere **`patch_028`** en Supabase; si falla *schema cache*, ejecutá **`patch_029_corregir_movimiento_fn_recreate.sql`**."
        )
        if not editable:
            st.info("No hay egresos editables en los últimos registros, o falta columna **id** en la consulta.")
        else:
            id_opts = [str(r["id"]) for r in editable]

            def _fmt_ed(mid: str) -> str:
                rr = next(x for x in editable if str(x.get("id")) == mid)
                ts = str(rr.get("created_at") or "")[:19].replace("T", " ")
                co = (rr.get("concepto") or "")[:42]
                return f"{ts} — {co}"

            pick = st.selectbox("Elegí el movimiento", options=id_opts, format_func=_fmt_ed, key="gasto_op_edit_pick")
            er = next(x for x in editable if str(x.get("id")) == pick)
            _fk = str(pick).replace("-", "")[:32]
            ecaja = cmap_full.get(str(er.get("caja_id") or ""), {})
            emon_raw = str(ecaja.get("moneda_cuenta") or "USD").strip().upper()
            emon = "VES" if emon_raw in ("VES", "BS") else emon_raw
            _musd_er = float(er.get("monto_usd") or 0.01)
            _mm_er = er.get("monto_moneda")
            _mm_f = float(_mm_er) if _mm_er is not None and str(_mm_er).strip() != "" else 0.0
            with st.form(f"f_gasto_op_corregir_{_fk}"):
                st.markdown(f"**Cuenta:** {emon} · {d.caja_etiqueta_lista(ecaja) if ecaja else '—'}")
                if emon == "VES" and _mm_f <= 0:
                    st.warning(
                        "Este movimiento **no tiene Bs guardados** en BD (`monto_moneda` vacío). "
                        "Cargá abajo el **monto real en bolívares** que salió del banco y la **tasa** con la que querés valorar en el sistema."
                    )

                nu: float
                p_mon_e: str | None = None
                p_mm_e: float | None = None
                upd_nat: bool

                if emon == "VES":
                    try:
                        _tb0 = float(d.tasa_bs_para_documento(t, usar_bcv=False)) if t else 0.0
                    except (ValueError, TypeError):
                        _tb0 = float(d.nf(t.get("tasa_bs")) or 0) if t else 0.0
                    if _tb0 <= 0:
                        _tb0 = 300.0
                    _sug_bs = _mm_f if _mm_f > 0 else max(0.01, _musd_er * _tb0)
                    m_bs_in = st.number_input(
                        "Monto en bolívares (Bs) — lo que salió de la cuenta",
                        min_value=0.01,
                        value=float(d.round_money_2(_sug_bs)),
                        format="%.2f",
                        key=f"gasto_op_edit_bs_{_fk}",
                    )
                    tasa_bs_in = st.number_input(
                        "Tasa Bs por 1 USD (para calcular el equiv. interno `monto_usd`)",
                        min_value=0.01,
                        value=float(_tb0),
                        format="%.4f",
                        key=f"gasto_op_edit_tasa_bs_{_fk}",
                        help="Mismo criterio que al registrar un gasto en Bs: Bs ÷ esta tasa = valor que guarda el motor de saldos en USD.",
                    )
                    if float(tasa_bs_in) <= 0:
                        nu = _musd_er
                    else:
                        nu = float(m_bs_in) / float(tasa_bs_in)
                    st.caption(
                        f"En base se guardará: **moneda** = VES, **monto_moneda** = {d.round_money_2(m_bs_in):,.2f} Bs, "
                        f"**monto_usd** = US$ {d.round_money_2(nu):,.2f} (equiv. para saldos)."
                    )
                    upd_nat = True
                    p_mon_e, p_mm_e = "VES", float(m_bs_in)
                elif emon == "USDT":
                    t_ut0 = float(d.nf(t.get("tasa_usdt")) or 1.0) if t else 1.0
                    if t_ut0 <= 0:
                        t_ut0 = 1.0
                    _sug_ut = _mm_f if _mm_f > 0 else max(0.0001, _musd_er * t_ut0)
                    m_ut_in = st.number_input(
                        "Monto en USDT",
                        min_value=0.0001,
                        value=float(d.round_money_2(_sug_ut)),
                        format="%.4f",
                        key=f"gasto_op_edit_ut_{_fk}",
                    )
                    t_ut_in = st.number_input(
                        "Tasa USDT por 1 USD",
                        min_value=0.0000001,
                        value=float(t_ut0),
                        format="%.6f",
                        key=f"gasto_op_edit_tasa_ut_{_fk}",
                    )
                    if float(t_ut_in) <= 0:
                        nu = _musd_er
                    else:
                        nu = float(m_ut_in) / float(t_ut_in)
                    st.caption(
                        f"En base: **moneda** = USDT, **monto_moneda** = {d.round_money_2(m_ut_in):,.4f} USDT, "
                        f"**monto_usd** = US$ {d.round_money_2(nu):,.2f}."
                    )
                    upd_nat = True
                    p_mon_e, p_mm_e = "USDT", float(m_ut_in)
                else:
                    nu = st.number_input(
                        "Monto en USD (cuenta en dólares)",
                        min_value=0.01,
                        value=float(d.round_money_2(_musd_er)),
                        format="%.2f",
                        key=f"gasto_op_edit_usd_{_fk}",
                    )
                    upd_nat = st.checkbox(
                        "Guardar también en columnas moneda / monto_moneda (USD)",
                        value=True,
                        key=f"gasto_op_edit_upd_nat_{_fk}",
                    )
                    if upd_nat:
                        p_mon_e, p_mm_e = "USD", float(nu)
                nc = st.text_input("Concepto", value=str(er.get("concepto") or ""), key=f"gasto_op_edit_conc_{_fk}")
                nr = st.text_input("Referencia", value=str(er.get("referencia") or ""), key=f"gasto_op_edit_ref_{_fk}")
                ncat = st.text_input(
                    "Categoría (vacío = quitar categoría)",
                    value=str(er.get("categoria_gasto") or ""),
                    key=f"gasto_op_edit_cat_{_fk}",
                )
                if st.form_submit_button("Guardar corrección"):
                    if not (erp_uid or "").strip():
                        st.error("Sesión sin usuario ERP; no se puede guardar.")
                    elif not (nc or "").strip():
                        st.error("El **concepto** no puede quedar vacío (lo exige la base de datos).")
                    elif nu <= 0:
                        st.error("El equivalente USD calculado debe ser mayor que cero (revisá monto y tasa).")
                    else:
                        _rpc_mon = (p_mon_e or None) if upd_nat else None
                        _rpc_mm = float(p_mm_e) if upd_nat and p_mm_e is not None else None
                        pl_e: dict[str, Any] = {
                            "p_usuario_id": erp_uid,
                            "p_movimiento_id": pick,
                            "p_monto_usd": float(nu),
                            "p_concepto": (nc or "").strip(),
                            "p_referencia": (nr or "").strip(),
                            "p_categoria_gasto": (ncat or "").strip() or None,
                            "p_actualizar_moneda_nativa": bool(upd_nat),
                            "p_moneda": _rpc_mon,
                            "p_monto_moneda": _rpc_mm,
                        }
                        try:
                            sb.rpc("corregir_movimiento_caja_manual_erp", pl_e).execute()
                            st.session_state["flash_gasto_op_correccion"] = {
                                "ok": True,
                                "msg": "Movimiento actualizado y guardado en base de datos.",
                            }
                            st.rerun()
                        except Exception as ex:
                            _em = d.error_msg_from_supabase_exc(ex)
                            st.session_state["flash_gasto_op_correccion"] = {
                                "ok": False,
                                "msg": f"{_em} · Si falta el RPC: **`patch_029_corregir_movimiento_fn_recreate.sql`** en Supabase y **Reload schema** (API).",
                            }
                            st.rerun()

    if not tiene_cat:
        st.caption(
            "Para ver la columna **Categoría** en la tabla de abajo, aplicá **`patch_025_gastos_operativos.sql`** en Supabase."
        )
    if rows_eg:
        disp: list[dict[str, Any]] = []
        for r in rows_eg:
            cid_s = str(r.get("caja_id") or "")
            row_d: dict[str, Any] = {
                "Fecha": str(r.get("created_at") or "")[:19].replace("T", " "),
                "Caja": cmap_lab.get(cid_s, cid_s[:8] + "…"),
                "Monto": d.gasto_op_fmt_monto_tabla(r, cmap_full),
                "Concepto": r.get("concepto") or "",
            }
            if tiene_cat:
                row_d["Categoría"] = r.get("categoria_gasto") or "—"
            if r.get("referencia"):
                row_d["Ref."] = r.get("referencia")
            disp.append(row_d)
        st.markdown("##### Últimos egresos de caja (incluye compras al contado y otros pagos)")
        st.dataframe(pd.DataFrame(disp), use_container_width=True, hide_index=True)
        st.caption(
            "Si necesitás filtrar **solo** gastos operativos, usá la columna **Categoría** tras el patch, o revisá **Reportes → movimientos de caja**."
        )
    else:
        st.info("Aún no hay egresos registrados en caja.")
