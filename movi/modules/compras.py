"""Módulo Compras / CXP: líneas múltiples, CSV, registro atómico."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import streamlit as st
from supabase import Client

from movi.producto_busqueda import filtrar_productos_por_busqueda


@dataclass(frozen=True)
class ComprasModuleDeps:
    modulo_titulo_info: Callable[..., None]
    cajas_fetch_rows: Callable[..., Any]
    caja_select_options: Callable[[list[dict[str, Any]]], tuple[list[str], Any]]
    doc_tasa_bs_opts: tuple[str, ...]
    infer_tasa_bs_oper_index: Callable[[dict[str, Any]], int]
    compra_parse_lineas_csv: Callable[[bytes, dict[str, str]], tuple[list[dict[str, Any]] | None, str | None]]
    movi_reset_compra_form_fields: Callable[[], None]
    movi_bump_form_nonce: Callable[[str], None]
    line_qty_int: Callable[..., int]
    tasa_bs_para_documento: Callable[..., float]


def render_module_compras(sb: Client, erp_uid: str, t: dict[str, Any] | None, *, deps: ComprasModuleDeps) -> None:
    d = deps
    d.modulo_titulo_info(
        "Compras y CXP",
        key="compras",
        ayuda_md=(
            "Podés cargar **varias líneas** (botón abajo o **CSV**). Montos en **USD** (1:1). "
            "Para equivalente en **bolívares**, elegí **BCV** o **P2P Binance**.\n\n"
            "**Líneas de la compra:** **Añadir línea** agrega una fila más. Para facturas con muchos ítems, usá **importar CSV** "
            "(exportá desde Excel con las columnas indicadas en el expander de importación)."
        ),
    )
    if not t:
        st.stop()

    t_usdt = float(t["tasa_usdt"])

    prods = (
        sb.table("productos")
        .select(
            "id,descripcion,costo_usd,codigo,sku_oem,marca_producto,categorias(nombre),compatibilidad"
        )
        .eq("activo", True)
        .order("descripcion")
        .execute()
    )
    plist = prods.data or []
    if not plist:
        st.warning("No hay productos.")
        st.stop()

    id_to_label = {str(p["id"]): p["descripcion"] for p in plist}
    id_to_cost = {str(p["id"]): float(p["costo_usd"]) for p in plist}

    caja_rows_act_c = d.cajas_fetch_rows(sb, solo_activas=True)
    caja_ids_c, caja_fmt_c = d.caja_select_options(caja_rows_act_c) if caja_rows_act_c else ([], lambda x: str(x))

    if "compra_lines" not in st.session_state:
        st.session_state["compra_lines"] = [
            {"producto_id": str(plist[0]["id"]), "cantidad": 1, "costo_unitario_usd": id_to_cost[str(plist[0]["id"])]}
        ]

    st.markdown("#### Datos del documento")
    prov = st.text_input("Proveedor", key="compra_prov", autocomplete="off")
    c_fp, c_caja = st.columns([1, 1])
    with c_fp:
        forma = st.selectbox("Forma de pago compra", ["contado", "credito"], key="forma_compra")
    with c_caja:
        caja_id_compra = (
            st.selectbox("Caja (solo contado)", options=caja_ids_c, format_func=caja_fmt_c, key="caja_compra")
            if caja_ids_c
            else None
        )
    fv = st.date_input("Vencimiento (crédito compra)", value=date.today() + timedelta(days=30), key="fv_compra")
    notas = st.text_area("Notas compra", key="compra_notas")

    doc_tasa_c = st.radio(
        "Tasa Bs/USD para esta compra:",
        options=d.doc_tasa_bs_opts,
        index=d.infer_tasa_bs_oper_index(t),
        horizontal=True,
        key="compra_doc_tasa_bs",
        help="Montos de línea en USD sin cambio; la tasa queda en el registro de compra.",
    )

    st.markdown("#### Líneas de la compra")
    _ba, _bb, _bc = st.columns([1, 1, 2])
    with _ba:
        if st.button("➕ Añadir línea", key="compra_btn_add_line"):
            st.session_state["compra_lines"].append(
                {
                    "producto_id": str(plist[0]["id"]),
                    "cantidad": 1,
                    "costo_unitario_usd": id_to_cost[str(plist[0]["id"])],
                }
            )
            st.rerun()
    with _bb:
        if len(st.session_state["compra_lines"]) > 1 and st.button(
            "➖ Quitar última línea", key="compra_btn_drop_line"
        ):
            st.session_state["compra_lines"].pop()
            st.rerun()

    with st.expander("Importar líneas desde CSV (facturas largas)", expanded=False):
        st.markdown(
            "Columnas requeridas: **`cantidad`**, **`costo_unitario_usd`**, y además **`producto_id`** "
            "(UUID) **o** **`descripcion`** (texto **idéntico** al producto en inventario, sin importar mayúsculas)."
        )
        sample = (
            "descripcion,cantidad,costo_unitario_usd\n"
            f'"{plist[0]["descripcion"]}",2,10.50\n'
        )
        st.download_button(
            "Descargar ejemplo CSV",
            data=sample.encode("utf-8"),
            file_name="ejemplo_compra_lineas.csv",
            mime="text/csv",
            key="compra_dl_sample_csv",
        )
        up = st.file_uploader("Archivo .csv", type=["csv"], key="compra_csv_up")
        if st.button("Importar líneas del archivo", key="compra_csv_apply"):
            if up is None:
                st.error("Elegí un archivo CSV primero.")
            else:
                raw = up.getvalue()
                parsed, err = d.compra_parse_lineas_csv(raw, id_to_label)
                if err:
                    st.error(err)
                elif parsed:
                    st.session_state["compra_lines"] = parsed
                    d.movi_reset_compra_form_fields()
                    d.movi_bump_form_nonce("compra_form_nonce")
                    st.success(f"Se cargaron **{len(parsed)}** líneas. Revisalas abajo y pulsá **Registrar compra**.")
                    st.rerun()

    new_lines: list[dict[str, Any]] = []
    for i, line in enumerate(st.session_state["compra_lines"]):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            _cq = st.text_input(
                f"Buscar producto (línea {i + 1})",
                key=f"cp_q_{i}",
                placeholder="Código, OEM, descripción, marca…",
                label_visibility="collapsed",
            )
            _plf = filtrar_productos_por_busqueda(
                plist, _cq, siempre_incluir_id=str(line.get("producto_id") or "")
            )
            _opt_c = [str(p["id"]) for p in _plf]
            if not _opt_c:
                _opt_c = [str(plist[0]["id"])]
                st.caption("Sin coincidencias; mostrando un ítem. Vacía el filtro o probá otras palabras.")
            _ix_c = _opt_c.index(str(line["producto_id"])) if str(line["producto_id"]) in _opt_c else 0
            pid = st.selectbox(
                f"Producto {i+1}",
                options=_opt_c,
                format_func=lambda x, _m=id_to_label: _m.get(str(x), str(x)),
                key=f"cp_{i}",
                index=_ix_c,
            )
        qty = c2.number_input(
            "Cant.",
            min_value=1,
            value=d.line_qty_int(line.get("cantidad"), default=1),
            step=1,
            format="%d",
            key=f"cq_{i}",
        )
        cu = c3.number_input(
            "Costo u. USD", min_value=0.0, value=float(line.get("costo_unitario_usd", id_to_cost.get(pid, 0))), format="%.2f", key=f"ccu_{i}"
        )
        new_lines.append({"producto_id": pid, "cantidad": int(qty), "costo_unitario_usd": float(cu)})

    n_lin = len(new_lines)
    tot_usd = sum(float(x["cantidad"]) * float(x["costo_unitario_usd"]) for x in new_lines)
    st.metric("Líneas en esta compra", f"{n_lin} · Total USD {tot_usd:,.2f}")

    with st.form(f"f_compra_{int(st.session_state.get('compra_form_nonce', 0))}"):
        st.caption("Un solo **registro atómico** en base: stock, costos, caja o CXP.")
        if st.form_submit_button("Registrar compra (atómica)"):
            try:
                t_bs_doc = d.tasa_bs_para_documento(t, usar_bcv=(doc_tasa_c == d.doc_tasa_bs_opts[0]))
            except ValueError as e:
                st.error(str(e))
            else:
                payload = {
                    "p_usuario_id": erp_uid,
                    "p_proveedor": prov,
                    "p_forma_pago": forma,
                    "p_caja_id": str(caja_id_compra) if forma == "contado" and caja_id_compra else None,
                    "p_tasa_bs": t_bs_doc,
                    "p_tasa_usdt": t_usdt,
                    "p_fecha_vencimiento": str(fv) if forma == "credito" else None,
                    "p_notas": notas,
                    "p_lineas": new_lines,
                }
                if forma == "contado" and not caja_id_compra:
                    st.error("Elegí una caja activa para compra al contado (o creá una en Cajas).")
                else:
                    try:
                        sb.rpc("crear_compra_erp", payload).execute()
                        st.success("Compra registrada.")
                        st.session_state["compra_lines"] = [
                            {
                                "producto_id": str(plist[0]["id"]),
                                "cantidad": 1,
                                "costo_unitario_usd": id_to_cost[str(plist[0]["id"])],
                            }
                        ]
                        d.movi_reset_compra_form_fields()
                        d.movi_bump_form_nonce("compra_form_nonce")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo registrar: {e}")
