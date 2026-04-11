"""Barra horizontal de módulos (Streamlit)."""

from __future__ import annotations

import streamlit as st

from movi.rbac import MOVI_MOD_ICONS


def nav_column_weights(opts: list[str]) -> list[int]:
    """Pesos para st.columns: más ancho en etiquetas largas → una sola línea."""
    return [max(12, len(opt) + 10) for opt in opts]


def render_movi_main_module_nav(opts: list[str]) -> None:
    """Píldoras con icono; activo en gradiente (CSS en theme)."""
    if len(opts) <= 1:
        return
    st.session_state.setdefault("movi_mod", opts[0])
    if st.session_state.get("movi_mod") not in opts:
        st.session_state["movi_mod"] = opts[0]
    st.markdown('<div class="movi-mod-nav-outer">', unsafe_allow_html=True)
    cols = st.columns(nav_column_weights(opts))
    for i, opt in enumerate(opts):
        ic = MOVI_MOD_ICONS.get(opt, "▪")
        active = st.session_state["movi_mod"] == opt
        key = f"movi_nav_{i}_{abs(hash(opt)) % 10_000_000}"
        with cols[i]:
            if st.button(
                f"{ic} {opt}",
                key=key,
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                if st.session_state["movi_mod"] != opt:
                    st.session_state["movi_mod"] = opt
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
