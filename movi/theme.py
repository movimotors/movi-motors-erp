"""Tema visual Movi (tokens + CSS inyectado)."""
from __future__ import annotations

import streamlit as st

# --- Temas de interfaz (fondos y acentos; texto siempre legible) ---
MOVI_UI_THEME_DEFAULT: str = "aurora"

MOVI_UI_THEME_ORDER: list[str] = [
    "aurora",
    "origen",
    "laguna",
    "calido",
    "lavanda",
    "jade",
    "horizonte",
]

# Cada tema: label + tokens para la plantilla CSS (contraste orientado a WCAG sobre fondos oscuros).
MOVI_UI_THEMES: dict[str, dict[str, str]] = {
    "origen": {
        "label": "Origen · morado y ámbar",
        "app_bg": "#0e1117",
        "app_fg": "#f0f3f6",
        "fg_muted": "#a8b4c0",
        "sb_g1": "#2a1f45",
        "sb_g2": "#1a1228",
        "sb_g3": "#14101c",
        "sb_br": "rgba(255, 152, 0, 0.14)",
        "sb_md_strong": "#ffb74d",
        "dec1": "#5c2d91",
        "dec2": "#ff9800",
        "lbl": "#c9d1d9",
        "met_lbl": "#8b949e",
        "btn_bg": "#e65100",
        "btn_bd": "#ff9800",
        "btn_h_bg": "#ff9800",
        "btn_h_bd": "#ffb74d",
        "sw_g1": "rgba(255, 152, 0, 0.14)",
        "sw_g2": "rgba(92, 45, 145, 0.22)",
        "sw_bd": "rgba(255, 183, 77, 0.35)",
        "sw_title": "#ffb74d",
        "sw_sub": "#e0c8ff",
        "sw_user": "#e6edf3",
        "sw_role": "#ffcc80",
        "sbt": "#ffcc80",
        "sexp_bg": "rgba(255, 255, 255, 0.04)",
        "sexp_bd": "rgba(255, 183, 77, 0.28)",
        "sexp_sum": "#ffe0b2",
        "smet_bg": "rgba(0, 0, 0, 0.15)",
        "smet_bd": "rgba(255, 255, 255, 0.08)",
        "smet_lbl": "#b8c4d0",
        "smet_val": "#fff8e1",
        "db_g1": "rgba(28, 33, 40, 0.95)",
        "db_g2": "rgba(18, 22, 28, 0.98)",
        "db_bd": "rgba(0, 229, 255, 0.14)",
        "db_sh": "rgba(0, 0, 0, 0.45)",
        "db_in": "rgba(255, 145, 0, 0.07)",
        "dbh_bd": "rgba(0, 229, 255, 0.3)",
        "dbh_sh": "rgba(0, 229, 255, 0.1)",
        "dbh_in": "rgba(255, 145, 0, 0.12)",
        "dk_lbl": "#8b949e",
        "dk_val": "#f0f6fc",
        "dk_sub": "#7d8590",
        "dt_up": "#26c6da",
        "dt_dn": "#ff8a80",
        "dt_fl": "#8b949e",
        "dh_g1": "#26c6da",
        "dh_g2": "#ffa726",
        "dh_sub": "#8b949e",
        "dl_bg": "rgba(0, 229, 255, 0.1)",
        "dl_bd": "rgba(0, 229, 255, 0.35)",
        "dl_txt": "#b3f0ff",
        "link": "#79c0ff",
    },
    "aurora": {
        "label": "Aurora · teal y melocotón",
        "app_bg": "#132c38",
        "app_fg": "#eef8fb",
        "fg_muted": "#a8c4d0",
        "sb_g1": "#1a4556",
        "sb_g2": "#0f3242",
        "sb_g3": "#0a2433",
        "sb_br": "rgba(244, 168, 150, 0.2)",
        "sb_md_strong": "#f5c4b8",
        "dec1": "#2dd4bf",
        "dec2": "#f0a090",
        "lbl": "#c5dce4",
        "met_lbl": "#8eb8c8",
        "btn_bg": "#c75d4d",
        "btn_bd": "#e89588",
        "btn_h_bg": "#e07868",
        "btn_h_bd": "#f5b5aa",
        "sw_g1": "rgba(45, 212, 191, 0.12)",
        "sw_g2": "rgba(240, 160, 144, 0.15)",
        "sw_bd": "rgba(125, 211, 232, 0.35)",
        "sw_title": "#fde8e4",
        "sw_sub": "#a5e8df",
        "sw_user": "#e8f4f8",
        "sw_role": "#f5c4b8",
        "sbt": "#a5e8df",
        "sexp_bg": "rgba(255, 255, 255, 0.05)",
        "sexp_bd": "rgba(125, 211, 232, 0.3)",
        "sexp_sum": "#d4f5f0",
        "smet_bg": "rgba(0, 0, 0, 0.12)",
        "smet_bd": "rgba(255, 255, 255, 0.1)",
        "smet_lbl": "#9ec9d6",
        "smet_val": "#ffffff",
        "db_g1": "rgba(24, 52, 64, 0.96)",
        "db_g2": "rgba(12, 38, 50, 0.98)",
        "db_bd": "rgba(45, 212, 191, 0.22)",
        "db_sh": "rgba(0, 0, 0, 0.4)",
        "db_in": "rgba(240, 160, 144, 0.08)",
        "dbh_bd": "rgba(45, 212, 191, 0.38)",
        "dbh_sh": "rgba(45, 212, 191, 0.12)",
        "dbh_in": "rgba(240, 160, 144, 0.12)",
        "dk_lbl": "#8eb8c8",
        "dk_val": "#ffffff",
        "dk_sub": "#7aa8b8",
        "dt_up": "#5eead4",
        "dt_dn": "#fca5a5",
        "dt_fl": "#8eb8c8",
        "dh_g1": "#5eead4",
        "dh_g2": "#fdba74",
        "dh_sub": "#8eb8c8",
        "dl_bg": "rgba(45, 212, 191, 0.12)",
        "dl_bd": "rgba(94, 234, 212, 0.4)",
        "dl_txt": "#ccfbf1",
        "link": "#7dd3fc",
    },
    "laguna": {
        "label": "Laguna · azul marino y cielo",
        "app_bg": "#102a40",
        "app_fg": "#f0f9ff",
        "fg_muted": "#a3c4de",
        "sb_g1": "#1e4976",
        "sb_g2": "#153a5c",
        "sb_g3": "#0f2f4d",
        "sb_br": "rgba(56, 189, 248, 0.22)",
        "sb_md_strong": "#7dd3fc",
        "dec1": "#0ea5e9",
        "dec2": "#38bdf8",
        "lbl": "#c9e2f5",
        "met_lbl": "#8fb8d9",
        "btn_bg": "#0284c7",
        "btn_bd": "#38bdf8",
        "btn_h_bg": "#0ea5e9",
        "btn_h_bd": "#7dd3fc",
        "sw_g1": "rgba(14, 165, 233, 0.14)",
        "sw_g2": "rgba(56, 189, 248, 0.12)",
        "sw_bd": "rgba(125, 211, 252, 0.35)",
        "sw_title": "#e0f2fe",
        "sw_sub": "#93c5fd",
        "sw_user": "#f0f9ff",
        "sw_role": "#bae6fd",
        "sbt": "#93c5fd",
        "sexp_bg": "rgba(255, 255, 255, 0.04)",
        "sexp_bd": "rgba(56, 189, 248, 0.28)",
        "sexp_sum": "#e0f2fe",
        "smet_bg": "rgba(0, 0, 0, 0.12)",
        "smet_bd": "rgba(255, 255, 255, 0.08)",
        "smet_lbl": "#9ec9e8",
        "smet_val": "#ffffff",
        "db_g1": "rgba(22, 50, 78, 0.96)",
        "db_g2": "rgba(14, 40, 66, 0.98)",
        "db_bd": "rgba(56, 189, 248, 0.22)",
        "db_sh": "rgba(0, 0, 0, 0.42)",
        "db_in": "rgba(125, 211, 252, 0.06)",
        "dbh_bd": "rgba(56, 189, 248, 0.35)",
        "dbh_sh": "rgba(14, 165, 233, 0.12)",
        "dbh_in": "rgba(125, 211, 252, 0.1)",
        "dk_lbl": "#8fb8d9",
        "dk_val": "#ffffff",
        "dk_sub": "#7aa3c8",
        "dt_up": "#38bdf8",
        "dt_dn": "#f87171",
        "dt_fl": "#8fb8d9",
        "dh_g1": "#38bdf8",
        "dh_g2": "#a78bfa",
        "dh_sub": "#8fb8d9",
        "dl_bg": "rgba(14, 165, 233, 0.12)",
        "dl_bd": "rgba(56, 189, 248, 0.4)",
        "dl_txt": "#e0f2fe",
        "link": "#7dd3fc",
    },
    "calido": {
        "label": "Cálido · café y ámbar",
        "app_bg": "#261e18",
        "app_fg": "#faf6f0",
        "fg_muted": "#c4b8a8",
        "sb_g1": "#3d3028",
        "sb_g2": "#2a221c",
        "sb_g3": "#1f1814",
        "sb_br": "rgba(212, 160, 52, 0.2)",
        "sb_md_strong": "#e8c468",
        "dec1": "#b45309",
        "dec2": "#d4a034",
        "lbl": "#ddd4c8",
        "met_lbl": "#a89888",
        "btn_bg": "#b45309",
        "btn_bd": "#d4a034",
        "btn_h_bg": "#ca8a04",
        "btn_h_bd": "#e8c468",
        "sw_g1": "rgba(212, 160, 52, 0.12)",
        "sw_g2": "rgba(180, 83, 9, 0.15)",
        "sw_bd": "rgba(232, 196, 104, 0.3)",
        "sw_title": "#fde68a",
        "sw_sub": "#d6c4a8",
        "sw_user": "#faf6f0",
        "sw_role": "#fcd34d",
        "sbt": "#e8c468",
        "sexp_bg": "rgba(255, 255, 255, 0.04)",
        "sexp_bd": "rgba(212, 160, 52, 0.25)",
        "sexp_sum": "#fde68a",
        "smet_bg": "rgba(0, 0, 0, 0.15)",
        "smet_bd": "rgba(255, 255, 255, 0.06)",
        "smet_lbl": "#c4b8a8",
        "smet_val": "#fffbeb",
        "db_g1": "rgba(48, 38, 30, 0.96)",
        "db_g2": "rgba(32, 26, 20, 0.98)",
        "db_bd": "rgba(212, 160, 52, 0.2)",
        "db_sh": "rgba(0, 0, 0, 0.45)",
        "db_in": "rgba(252, 211, 77, 0.06)",
        "dbh_bd": "rgba(212, 160, 52, 0.35)",
        "dbh_sh": "rgba(252, 211, 77, 0.1)",
        "dbh_in": "rgba(212, 160, 52, 0.1)",
        "dk_lbl": "#a89888",
        "dk_val": "#fffbeb",
        "dk_sub": "#9a8a7a",
        "dt_up": "#fcd34d",
        "dt_dn": "#fca5a5",
        "dt_fl": "#a89888",
        "dh_g1": "#fcd34d",
        "dh_g2": "#fb923c",
        "dh_sub": "#a89888",
        "dl_bg": "rgba(212, 160, 52, 0.12)",
        "dl_bd": "rgba(252, 211, 77, 0.35)",
        "dl_txt": "#fff7d6",
        "link": "#93c5fd",
    },
    "lavanda": {
        "label": "Lavanda · violeta suave y rosa",
        "app_bg": "#1e1b2e",
        "app_fg": "#f5f3ff",
        "fg_muted": "#b8b0d4",
        "sb_g1": "#2e2654",
        "sb_g2": "#221c3d",
        "sb_g3": "#1a162e",
        "sb_br": "rgba(196, 181, 253, 0.2)",
        "sb_md_strong": "#ddd6fe",
        "dec1": "#8b5cf6",
        "dec2": "#f0abbd",
        "lbl": "#d8d4ec",
        "met_lbl": "#a8a0c8",
        "btn_bg": "#7c3aed",
        "btn_bd": "#a78bfa",
        "btn_h_bg": "#8b5cf6",
        "btn_h_bd": "#c4b5fd",
        "sw_g1": "rgba(139, 92, 246, 0.14)",
        "sw_g2": "rgba(240, 171, 189, 0.12)",
        "sw_bd": "rgba(196, 181, 253, 0.35)",
        "sw_title": "#fce7f3",
        "sw_sub": "#c4b5fd",
        "sw_user": "#f5f3ff",
        "sw_role": "#fbcfe8",
        "sbt": "#ddd6fe",
        "sexp_bg": "rgba(255, 255, 255, 0.04)",
        "sexp_bd": "rgba(196, 181, 253, 0.28)",
        "sexp_sum": "#ede9fe",
        "smet_bg": "rgba(0, 0, 0, 0.12)",
        "smet_bd": "rgba(255, 255, 255, 0.08)",
        "smet_lbl": "#b8b0d4",
        "smet_val": "#ffffff",
        "db_g1": "rgba(40, 34, 62, 0.96)",
        "db_g2": "rgba(28, 24, 48, 0.98)",
        "db_bd": "rgba(167, 139, 250, 0.22)",
        "db_sh": "rgba(0, 0, 0, 0.42)",
        "db_in": "rgba(240, 171, 189, 0.07)",
        "dbh_bd": "rgba(167, 139, 250, 0.35)",
        "dbh_sh": "rgba(196, 181, 253, 0.12)",
        "dbh_in": "rgba(244, 114, 182, 0.1)",
        "dk_lbl": "#a8a0c8",
        "dk_val": "#ffffff",
        "dk_sub": "#948bb8",
        "dt_up": "#a5f3fc",
        "dt_dn": "#fda4af",
        "dt_fl": "#a8a0c8",
        "dh_g1": "#c4b5fd",
        "dh_g2": "#fbcfe8",
        "dh_sub": "#a8a0c8",
        "dl_bg": "rgba(139, 92, 246, 0.12)",
        "dl_bd": "rgba(196, 181, 253, 0.4)",
        "dl_txt": "#ede9fe",
        "link": "#93c5fd",
    },
    "jade": {
        "label": "Jade · bosque y oro suave",
        "app_bg": "#152520",
        "app_fg": "#f0fdf4",
        "fg_muted": "#a8c4b0",
        "sb_g1": "#1f3d32",
        "sb_g2": "#152e28",
        "sb_g3": "#0f241f",
        "sb_br": "rgba(52, 211, 153, 0.2)",
        "sb_md_strong": "#6ee7b7",
        "dec1": "#059669",
        "dec2": "#d4a574",
        "lbl": "#cce8d4",
        "met_lbl": "#8fb89a",
        "btn_bg": "#047857",
        "btn_bd": "#34d399",
        "btn_h_bg": "#059669",
        "btn_h_bd": "#6ee7b7",
        "sw_g1": "rgba(52, 211, 153, 0.12)",
        "sw_g2": "rgba(212, 165, 116, 0.1)",
        "sw_bd": "rgba(110, 231, 183, 0.3)",
        "sw_title": "#d1fae5",
        "sw_sub": "#a7f3d0",
        "sw_user": "#f0fdf4",
        "sw_role": "#fcd34d",
        "sbt": "#6ee7b7",
        "sexp_bg": "rgba(255, 255, 255, 0.04)",
        "sexp_bd": "rgba(52, 211, 153, 0.25)",
        "sexp_sum": "#d1fae5",
        "smet_bg": "rgba(0, 0, 0, 0.12)",
        "smet_bd": "rgba(255, 255, 255, 0.06)",
        "smet_lbl": "#9cc9a8",
        "smet_val": "#ffffff",
        "db_g1": "rgba(26, 48, 40, 0.96)",
        "db_g2": "rgba(18, 36, 30, 0.98)",
        "db_bd": "rgba(52, 211, 153, 0.2)",
        "db_sh": "rgba(0, 0, 0, 0.42)",
        "db_in": "rgba(212, 165, 116, 0.06)",
        "dbh_bd": "rgba(52, 211, 153, 0.35)",
        "dbh_sh": "rgba(16, 185, 129, 0.12)",
        "dbh_in": "rgba(212, 165, 116, 0.1)",
        "dk_lbl": "#8fb89a",
        "dk_val": "#ffffff",
        "dk_sub": "#7aa88a",
        "dt_up": "#34d399",
        "dt_dn": "#fb923c",
        "dt_fl": "#8fb89a",
        "dh_g1": "#34d399",
        "dh_g2": "#fcd34d",
        "dh_sub": "#8fb89a",
        "dl_bg": "rgba(16, 185, 129, 0.12)",
        "dl_bd": "rgba(52, 211, 153, 0.38)",
        "dl_txt": "#d1fae5",
        "link": "#7dd3fc",
    },
    "horizonte": {
        "label": "Horizonte · índigo y coral elegante",
        "app_bg": "#1a2235",
        "app_fg": "#f1f5ff",
        "fg_muted": "#a4b0cc",
        "sb_g1": "#2d3a5c",
        "sb_g2": "#222c45",
        "sb_g3": "#1a2238",
        "sb_br": "rgba(139, 156, 244, 0.22)",
        "sb_md_strong": "#c7d2fe",
        "dec1": "#6366f1",
        "dec2": "#f0a090",
        "lbl": "#d0d8ec",
        "met_lbl": "#94a3c8",
        "btn_bg": "#4f46e5",
        "btn_bd": "#818cf8",
        "btn_h_bg": "#6366f1",
        "btn_h_bd": "#a5b4fc",
        "sw_g1": "rgba(99, 102, 241, 0.14)",
        "sw_g2": "rgba(240, 160, 144, 0.1)",
        "sw_bd": "rgba(165, 180, 252, 0.32)",
        "sw_title": "#e0e7ff",
        "sw_sub": "#a5b4fc",
        "sw_user": "#f1f5ff",
        "sw_role": "#fecdd3",
        "sbt": "#c7d2fe",
        "sexp_bg": "rgba(255, 255, 255, 0.04)",
        "sexp_bd": "rgba(129, 140, 248, 0.28)",
        "sexp_sum": "#e0e7ff",
        "smet_bg": "rgba(0, 0, 0, 0.12)",
        "smet_bd": "rgba(255, 255, 255, 0.07)",
        "smet_lbl": "#a4b0cc",
        "smet_val": "#ffffff",
        "db_g1": "rgba(32, 40, 62, 0.96)",
        "db_g2": "rgba(22, 28, 48, 0.98)",
        "db_bd": "rgba(129, 140, 248, 0.22)",
        "db_sh": "rgba(0, 0, 0, 0.42)",
        "db_in": "rgba(240, 160, 144, 0.06)",
        "dbh_bd": "rgba(129, 140, 248, 0.35)",
        "dbh_sh": "rgba(99, 102, 241, 0.12)",
        "dbh_in": "rgba(251, 113, 133, 0.1)",
        "dk_lbl": "#94a3c8",
        "dk_val": "#ffffff",
        "dk_sub": "#7c8aad",
        "dt_up": "#7dd3fc",
        "dt_dn": "#fb923c",
        "dt_fl": "#94a3c8",
        "dh_g1": "#818cf8",
        "dh_g2": "#fda4af",
        "dh_sub": "#94a3c8",
        "dl_bg": "rgba(99, 102, 241, 0.12)",
        "dl_bd": "rgba(165, 180, 252, 0.38)",
        "dl_txt": "#e0e7ff",
        "link": "#93c5fd",
    },
}


def _movi_ui_theme_tokens() -> dict[str, str]:
    tid = st.session_state.get("movi_ui_theme", MOVI_UI_THEME_DEFAULT)
    if tid not in MOVI_UI_THEMES:
        tid = MOVI_UI_THEME_DEFAULT
    row = dict(MOVI_UI_THEMES[tid])
    row.pop("label", None)
    return row


def _movi_ui_theme_css_block() -> str:
    t = _movi_ui_theme_tokens()
    return """
<style>
  .stApp {{ background-color: {app_bg}; color: {app_fg}; }}
  .stApp .stMarkdown, .stApp .stMarkdown p, .stApp [data-testid="stMarkdownContainer"] p {{
    color: {app_fg};
  }}
  .stApp .stCaption {{ color: {fg_muted} !important; }}
  [data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {sb_g1} 0%, {sb_g2} 55%, {sb_g3} 100%);
    border-right: 1px solid {sb_br};
  }}
  [data-testid="stSidebar"] .stMarkdown strong {{ color: {sb_md_strong} !important; }}
  div[data-testid="stDecoration"] {{ background: linear-gradient(90deg, {dec1}, {dec2}); }}
  div[data-baseweb="block-label"] {{ color: {lbl} !important; }}
  .stMetric label {{ color: {met_lbl} !important; }}
  button[kind="primary"] {{
    background-color: {btn_bg} !important;
    border-color: {btn_bd} !important;
  }}
  button[kind="primary"]:hover {{
    background-color: {btn_h_bg} !important;
    border-color: {btn_h_bd} !important;
  }}
  [data-testid="stSidebar"] .sb-welcome {{
    background: linear-gradient(135deg, {sw_g1} 0%, {sw_g2} 100%);
    border: 1px solid {sw_bd};
    border-radius: 14px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.75rem;
  }}
  [data-testid="stSidebar"] .sb-welcome-title {{
    font-size: 0.95rem;
    font-weight: 800;
    color: {sw_title};
    letter-spacing: 0.03em;
    line-height: 1.2;
  }}
  [data-testid="stSidebar"] .sb-welcome-sub {{
    font-size: 0.72rem;
    color: {sw_sub};
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-top: 0.15rem;
    margin-bottom: 0.5rem;
  }}
  [data-testid="stSidebar"] .sb-welcome-user {{
    font-size: 0.8rem;
    color: {sw_user};
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    padding-top: 0.5rem;
  }}
  [data-testid="stSidebar"] .sb-role {{
    color: {sw_role};
    font-weight: 600;
  }}
  [data-testid="stSidebar"] .sb-block-title {{
    font-size: 0.72rem;
    font-weight: 700;
    color: {sbt};
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 0.5rem 0 0.35rem 0;
    opacity: 0.95;
  }}
  [data-testid="stSidebar"] [data-testid="stExpander"] {{
    background: {sexp_bg};
    border: 1px solid {sexp_bd};
    border-radius: 12px;
    margin-bottom: 0.45rem;
    overflow: hidden;
  }}
  [data-testid="stSidebar"] [data-testid="stExpander"] details {{ border: none; }}
  [data-testid="stSidebar"] [data-testid="stExpander"] summary {{
    font-weight: 700 !important;
    color: {sexp_sum} !important;
    font-size: 0.88rem !important;
  }}
  [data-testid="stSidebar"] [data-testid="stExpander"] summary span {{ color: {sexp_sum} !important; }}
  [data-testid="stSidebar"] div[data-testid="stMetric"] {{
    background: {smet_bg};
    border-radius: 10px;
    padding: 0.35rem 0.5rem;
    border: 1px solid {smet_bd};
  }}
  [data-testid="stSidebar"] div[data-testid="stMetric"] label {{
    color: {smet_lbl} !important;
    font-size: 0.72rem !important;
  }}
  [data-testid="stSidebar"] div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    color: {smet_val} !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
  }}
  .dash-bento {{
    background: linear-gradient(145deg, {db_g1} 0%, {db_g2} 100%);
    border: 1px solid {db_bd};
    border-radius: 16px;
    padding: 1rem 1.2rem;
    box-shadow: 0 10px 40px {db_sh}, 0 0 0 1px {db_in} inset;
    margin-bottom: 0.65rem;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }}
  .dash-bento:hover {{
    border-color: {dbh_bd};
    box-shadow: 0 12px 48px {dbh_sh}, 0 0 0 1px {dbh_in} inset;
  }}
  .dash-kpi-label {{
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: {dk_lbl};
    margin-bottom: 0.35rem;
  }}
  .dash-kpi-value {{
    font-size: 1.55rem;
    font-weight: 800;
    color: {dk_val};
    line-height: 1.15;
  }}
  .dash-kpi-sub {{
    font-size: 0.78rem;
    color: {dk_sub};
    margin-top: 0.4rem;
  }}
  .dash-kpi-trend-up {{ color: {dt_up} !important; font-weight: 700; font-size: 0.85rem; }}
  .dash-kpi-trend-down {{ color: {dt_dn} !important; font-weight: 700; font-size: 0.85rem; }}
  .dash-kpi-trend-flat {{ color: {dt_fl} !important; font-size: 0.85rem; }}
  .dash-header-title {{
    font-size: 1.65rem;
    font-weight: 800;
    background: linear-gradient(90deg, {dh_g1}, {dh_g2});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.25rem 0;
    letter-spacing: -0.02em;
  }}
  .dash-header-sub {{ color: {dh_sub}; font-size: 0.85rem; margin-bottom: 0.5rem; }}
  .dash-live-chip {{
    display: inline-block;
    background: {dl_bg};
    border: 1px solid {dl_bd};
    border-radius: 12px;
    padding: 0.45rem 0.75rem;
    font-size: 0.78rem;
    color: {dl_txt};
    margin-top: 0.25rem;
  }}
  .stApp a {{ color: {link}; }}
  .stApp [data-testid="stHeader"] {{ background-color: transparent; }}
  .main .block-container div[data-testid="stWidgetLabel"] p,
  .main .block-container [data-baseweb="form-heading"] label {{
    font-size: 1.08rem !important;
    font-weight: 700 !important;
    color: {dec1} !important;
    letter-spacing: 0.03em;
  }}
  .main .block-container .stTabs [data-baseweb="tab"] {{
    font-size: 1.06rem !important;
    font-weight: 600 !important;
  }}
  div.movi-mod-nav-outer {{
    position: sticky;
    top: 0.35rem;
    z-index: 50;
    border: 1px solid rgba(94, 234, 212, 0.38);
    border-radius: 16px;
    padding: 10px 12px 14px 12px;
    margin-bottom: 0.85rem;
    background: rgba(15, 23, 42, 0.92);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
  }}
  div.movi-mod-nav-outer [data-testid="stHorizontalBlock"] {{
    flex-wrap: nowrap !important;
    align-items: stretch !important;
    overflow-x: auto !important;
    gap: 0.35rem !important;
    padding-bottom: 2px;
    scrollbar-width: thin;
  }}
  div.movi-mod-nav-outer [data-testid="column"] {{
    flex-shrink: 0 !important;
    min-width: 0 !important;
  }}
  div.movi-mod-nav-outer [data-testid="column"] button {{
    width: 100%;
    min-height: 2.75rem !important;
  }}
  div.movi-mod-nav-outer button[kind="primary"],
  div.movi-mod-nav-outer button[kind="secondary"] {{
    white-space: nowrap !important;
    line-height: 1.2 !important;
    font-size: 0.88rem !important;
  }}
  div.movi-mod-nav-outer button[kind="primary"] p,
  div.movi-mod-nav-outer button[kind="secondary"] p {{
    white-space: nowrap !important;
  }}
  div.movi-mod-nav-outer button[kind="secondary"] {{
    background: rgba(15, 23, 42, 0.55) !important;
    border: 1px solid rgba(94, 234, 212, 0.45) !important;
    color: {lbl} !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    padding-left: 0.65rem !important;
    padding-right: 0.65rem !important;
    padding-top: 0.5rem !important;
    padding-bottom: 0.5rem !important;
  }}
  div.movi-mod-nav-outer button[kind="secondary"]:hover {{
    border-color: rgba(34, 211, 238, 0.8) !important;
    background: rgba(30, 41, 59, 0.9) !important;
  }}
  div.movi-mod-nav-outer button[kind="primary"] {{
    background: linear-gradient(135deg, #5eead4 0%, #22d3ee 52%, #38bdf8 100%) !important;
    color: #0f172a !important;
    border: none !important;
    font-weight: 800 !important;
    border-radius: 12px !important;
    padding-left: 0.65rem !important;
    padding-right: 0.65rem !important;
    padding-top: 0.5rem !important;
    padding-bottom: 0.5rem !important;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.12) inset;
  }}
  div.movi-mod-nav-outer button[kind="primary"]:hover {{
    filter: brightness(1.06);
  }}
</style>
""".format(
        **t
    )


def render_movi_ui_theme_styles() -> None:
    st.markdown(_movi_ui_theme_css_block(), unsafe_allow_html=True)


def render_movi_theme_picker(*, key_suffix: str) -> None:
    opts = MOVI_UI_THEME_ORDER
    cur = st.session_state.get("movi_ui_theme", MOVI_UI_THEME_DEFAULT)
    if cur not in opts:
        cur = MOVI_UI_THEME_DEFAULT
    sel = st.selectbox(
        "Tema visual",
        options=opts,
        format_func=lambda x: MOVI_UI_THEMES[x]["label"],
        index=opts.index(cur),
        key=f"movi_theme_pick_{key_suffix}",
        help="Colores de fondo y acentos; el texto se mantiene legible. Se aplica al refrescar la vista.",
    )
    if sel != cur:
        st.session_state["movi_ui_theme"] = sel
        st.rerun()
