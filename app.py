"""
Movi Motors ERP — Streamlit + Supabase (USD base, multimoneda BS/USDT).

Conexión: cliente oficial `supabase` con secretos en [connections.supabase].
(Streamlit también documenta `st_supabase_connection.SupabaseConnection`; si lo
instalas, puedes sustituir `get_supabase()` por `st.connection(...)`.)

Requisitos: ejecutar supabase/schema_erp_multimoneda.sql (o patch_004 si ya tenías
BD) y configurar `.streamlit/secrets.toml` con Supabase (no subir a Git).

Acceso: cada persona entra con su **usuario** y **contraseña** (guardada hasheada
en `erp_users`). El **superusuario** crea usuarios y asigna rol: administrador,
vendedor o almacén. Tras entrar, la sesión se guarda en una **cookie firmada**
(por usuario y por cada login); al refrescar la página sigues identificado hasta
que pulses **Salir** o venza la vigencia (p. ej. 90 días).
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import html
import json
import re
import secrets
import unicodedata
import time
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import bcrypt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from supabase import Client


_APP_DIR = Path(__file__).resolve().parent
BRAND_LOGO_PATH = _APP_DIR / "assets" / "logo_movimotors.png"


def brand_logo_file() -> str | None:
    return str(BRAND_LOGO_PATH) if BRAND_LOGO_PATH.is_file() else None


def _brand_logo_data_uri() -> str | None:
    """PNG/JPEG del logo para incrustar en HTML de impresión."""
    p = BRAND_LOGO_PATH
    if not p.is_file():
        return None
    try:
        raw = p.read_bytes()
        if not raw:
            return None
        suf = p.suffix.lower()
        mime = "image/jpeg" if suf in (".jpg", ".jpeg") else "image/png"
        b64 = base64.standard_b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except OSError:
        return None


def render_brand_logo(*, use_column_width: bool = True) -> None:
    p = brand_logo_file()
    if p:
        st.image(p, use_container_width=use_column_width)


# --- Página y tema oscuro (colores alineados con logo: morado + acento naranja) ---
_PAGE_ICON: str = brand_logo_file() or "⚙️"
st.set_page_config(
    page_title="Movi Motor's Importadora · ERP",
    page_icon=_PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
  .stApp { background-color: #0e1117; color: #fafafa; }
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #2a1f45 0%, #1a1228 55%, #14101c 100%);
    border-right: 1px solid rgba(255, 152, 0, 0.12);
  }
  [data-testid="stSidebar"] .stMarkdown strong { color: #ffb74d !important; }
  div[data-testid="stDecoration"] { background: linear-gradient(90deg, #5c2d91, #ff9800); }
  div[data-baseweb="block-label"] { color: #c9d1d9 !important; }
  .stMetric label { color: #8b949e !important; }
  button[kind="primary"] {
    background-color: #e65100 !important;
    border-color: #ff9800 !important;
  }
  button[kind="primary"]:hover {
    background-color: #ff9800 !important;
    border-color: #ffb74d !important;
  }
  /* Sidebar: cabecera y cotizaciones más claras y ordenadas */
  [data-testid="stSidebar"] .sb-welcome {
    background: linear-gradient(135deg, rgba(255, 152, 0, 0.14) 0%, rgba(92, 45, 145, 0.22) 100%);
    border: 1px solid rgba(255, 183, 77, 0.35);
    border-radius: 14px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.75rem;
  }
  [data-testid="stSidebar"] .sb-welcome-title {
    font-size: 0.95rem;
    font-weight: 800;
    color: #ffb74d;
    letter-spacing: 0.03em;
    line-height: 1.2;
  }
  [data-testid="stSidebar"] .sb-welcome-sub {
    font-size: 0.72rem;
    color: #e0c8ff;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-top: 0.15rem;
    margin-bottom: 0.5rem;
  }
  [data-testid="stSidebar"] .sb-welcome-user {
    font-size: 0.8rem;
    color: #e6edf3;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    padding-top: 0.5rem;
  }
  [data-testid="stSidebar"] .sb-role {
    color: #ffcc80;
    font-weight: 600;
  }
  [data-testid="stSidebar"] .sb-block-title {
    font-size: 0.72rem;
    font-weight: 700;
    color: #ffcc80;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 0.5rem 0 0.35rem 0;
    opacity: 0.95;
  }
  [data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 183, 77, 0.28);
    border-radius: 12px;
    margin-bottom: 0.45rem;
    overflow: hidden;
  }
  [data-testid="stSidebar"] [data-testid="stExpander"] details {
    border: none;
  }
  [data-testid="stSidebar"] [data-testid="stExpander"] summary {
    font-weight: 700 !important;
    color: #ffe0b2 !important;
    font-size: 0.88rem !important;
  }
  [data-testid="stSidebar"] [data-testid="stExpander"] summary span {
    color: #ffe0b2 !important;
  }
  [data-testid="stSidebar"] div[data-testid="stMetric"] {
    background: rgba(0, 0, 0, 0.15);
    border-radius: 10px;
    padding: 0.35rem 0.5rem;
    border: 1px solid rgba(255, 255, 255, 0.06);
  }
  [data-testid="stSidebar"] div[data-testid="stMetric"] label {
    color: #b8c4d0 !important;
    font-size: 0.72rem !important;
  }
  [data-testid="stSidebar"] div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #fff8e1 !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
  }
  /* Dashboard Bento (Tesla / fintech dark) */
  .dash-bento {
    background: linear-gradient(145deg, rgba(22, 27, 34, 0.92) 0%, rgba(14, 17, 23, 0.95) 100%);
    border: 1px solid rgba(0, 229, 255, 0.12);
    border-radius: 16px;
    padding: 1rem 1.2rem;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 145, 0, 0.06) inset;
    margin-bottom: 0.65rem;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .dash-bento:hover {
    border-color: rgba(0, 229, 255, 0.28);
    box-shadow: 0 12px 48px rgba(0, 229, 255, 0.08), 0 0 0 1px rgba(255, 145, 0, 0.1) inset;
  }
  .dash-kpi-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #8b949e;
    margin-bottom: 0.35rem;
  }
  .dash-kpi-value {
    font-size: 1.55rem;
    font-weight: 800;
    color: #f0f6fc;
    line-height: 1.15;
  }
  .dash-kpi-sub {
    font-size: 0.78rem;
    color: #7d8590;
    margin-top: 0.4rem;
  }
  .dash-kpi-trend-up { color: #00e5ff !important; font-weight: 700; font-size: 0.85rem; }
  .dash-kpi-trend-down { color: #ff6b6b !important; font-weight: 700; font-size: 0.85rem; }
  .dash-kpi-trend-flat { color: #8b949e !important; font-size: 0.85rem; }
  .dash-header-title {
    font-size: 1.65rem;
    font-weight: 800;
    background: linear-gradient(90deg, #00e5ff, #ff9100);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.25rem 0;
    letter-spacing: -0.02em;
  }
  .dash-header-sub { color: #8b949e; font-size: 0.85rem; margin-bottom: 0.5rem; }
  .dash-live-chip {
    display: inline-block;
    background: rgba(0, 229, 255, 0.1);
    border: 1px solid rgba(0, 229, 255, 0.35);
    border-radius: 12px;
    padding: 0.45rem 0.75rem;
    font-size: 0.78rem;
    color: #b3f0ff;
    margin-top: 0.25rem;
  }
</style>
""",
    unsafe_allow_html=True,
)


def _secrets_ready() -> bool:
    try:
        _ = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
        _ = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
        return True
    except Exception:
        return False


ERP_SESSION_COOKIE = "movi_erp_session"
SESSION_MAX_DAYS = 90


def _session_signing_key() -> bytes:
    try:
        auth = st.secrets.get("auth")
        if isinstance(auth, dict):
            sk = auth.get("SESSION_SIGNING_KEY")
            if sk:
                return str(sk).encode("utf-8")
    except Exception:
        pass
    k = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
    return hashlib.sha256((str(k) + "|movi_erp_session_v1").encode("utf-8")).digest()


def _encode_session_token(uid: str, sid: str, exp_unix: int) -> str:
    payload = {"v": 1, "uid": str(uid), "sid": str(sid), "exp": int(exp_unix)}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_session_signing_key(), body, hashlib.sha256).hexdigest()
    wrapped = json.dumps({"p": payload, "sig": sig}, separators=(",", ":"))
    return base64.urlsafe_b64encode(wrapped.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_session_token(token: str) -> dict[str, Any] | None:
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad)
        o = json.loads(raw.decode("utf-8"))
        p = o.get("p")
        sig = o.get("sig")
        if not isinstance(p, dict) or not isinstance(sig, str):
            return None
        body = json.dumps(p, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expect = hmac.new(_session_signing_key(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            return None
        if int(p.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            return None
        return p
    except Exception:
        return None


def _erp_cookie_manager():
    from extra_streamlit_components import CookieManager

    return CookieManager(key="movi_erp_cookie_mgr")


def _persist_new_session_cookie(cm: Any | None, row: dict[str, Any]) -> None:
    """Un token nuevo en cada login (sid distinto); la cookie queda ligada a ese usuario (uid)."""
    if cm is None:
        return
    uid = str(row["id"])
    sid = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    exp_unix = int(now.timestamp()) + SESSION_MAX_DAYS * 86400
    tok = _encode_session_token(uid, sid, exp_unix)
    expires_at = now + timedelta(days=SESSION_MAX_DAYS)
    cm.set(
        ERP_SESSION_COOKIE,
        tok,
        key="erp_cookie_set_login",
        path="/",
        expires_at=expires_at,
        same_site="lax",
    )


def _try_restore_session_from_cookie(sb: Client, cm: Any | None) -> None:
    if cm is None or st.session_state.get("erp_uid"):
        return
    tok = cm.get(ERP_SESSION_COOKIE)
    if not tok or not isinstance(tok, str):
        return
    payload = _decode_session_token(tok)
    if not payload:
        try:
            cm.delete(ERP_SESSION_COOKIE, key="erp_cookie_del_bad")
        except Exception:
            pass
        return
    uid = str(payload.get("uid", "")).strip()
    if not uid:
        try:
            cm.delete(ERP_SESSION_COOKIE, key="erp_cookie_del_bad2")
        except Exception:
            pass
        return
    r = (
        sb.table("erp_users")
        .select("id,username,nombre,rol,activo")
        .eq("id", uid)
        .limit(1)
        .execute()
    )
    row = (r.data or [None])[0]
    if not row or row.get("activo") is False:
        try:
            cm.delete(ERP_SESSION_COOKIE, key="erp_cookie_del_inactive")
        except Exception:
            pass
        return
    st.session_state["erp_uid"] = str(row["id"])
    st.session_state["erp_rol"] = str(row["rol"])
    st.session_state["erp_nombre"] = str(row.get("nombre") or row["username"])
    st.session_state["erp_username"] = str(row["username"])
    st.rerun()


def _logout() -> None:
    for k in ("erp_uid", "erp_rol", "erp_nombre", "erp_username"):
        st.session_state.pop(k, None)
    try:
        cm = _erp_cookie_manager()
        cm.delete(ERP_SESSION_COOKIE, key="erp_cookie_del_logout")
    except Exception:
        pass


def _cookie_support() -> bool:
    try:
        import extra_streamlit_components  # noqa: F401

        return True
    except ImportError:
        return False


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _password_ok(plain: str, stored_hash: str) -> bool:
    h = (stored_hash or "").strip()
    if not h or not h.startswith("$2"):
        return False
    b = plain.encode("utf-8")
    try:
        if bcrypt.checkpw(b, h.encode("utf-8")):
            return True
    except Exception:
        pass
    # PostgreSQL pgcrypto suele guardar $2a$; la librería bcrypt en Python a veces falla: probamos $2b$
    if h.startswith("$2a$"):
        try:
            h2 = "$2b$" + h[4:]
            return bool(bcrypt.checkpw(b, h2.encode("utf-8")))
        except Exception:
            return False
    return False


def _fetch_erp_user_by_login(sb: Client, username_normalized: str) -> dict[str, Any] | None:
    """Coincide usuario ignorando mayúsculas (p. ej. Admin = admin)."""
    resp = sb.table("erp_users").select("id,username,nombre,rol,password_hash,activo").execute()
    u = username_normalized.strip().lower()
    for row in resp.data or []:
        if str(row.get("username", "")).strip().lower() == u:
            return row
    return None


def gate_user_login(sb: Client, cm: Any | None) -> dict[str, Any] | None:
    if st.session_state.get("erp_uid"):
        return {
            "id": st.session_state["erp_uid"],
            "rol": st.session_state["erp_rol"],
            "nombre": st.session_state["erp_nombre"],
            "username": st.session_state["erp_username"],
        }

    _, c_logo, _ = st.columns([1, 2.2, 1])
    with c_logo:
        render_brand_logo()
    st.markdown("---")
    st.subheader("Iniciar sesión")
    _persist_hint = (
        f"En este equipo la sesión se mantiene al refrescar (hasta **{SESSION_MAX_DAYS} días** o **Salir**)."
        if _cookie_support()
        else "Para recordar la sesión al refrescar, instala: `python -m pip install extra-streamlit-components`."
    )
    st.caption(
        "Usuario y contraseña los asigna el superusuario en el módulo Usuarios. "
        "El nombre de usuario no distingue mayúsculas (admin = Admin). "
        + _persist_hint
    )
    user = st.text_input("Usuario", autocomplete="username")
    pwd = st.text_input("Contraseña", type="password", autocomplete="current-password")
    if st.button("Entrar"):
        u = (user or "").strip().lower()
        if not u or not pwd:
            st.error("Complete usuario y contraseña.")
            return None
        row = _fetch_erp_user_by_login(sb, u)
        if not row:
            st.error("Usuario o contraseña incorrectos.")
            return None
        if row.get("activo") is False:
            st.error("Este usuario está desactivado.")
            return None
        ph = (row.get("password_hash") or "").strip()
        if not ph:
            st.error("Tu cuenta aún no tiene contraseña. Pide al superusuario que te la asigne.")
            return None
        if not _password_ok(pwd, ph):
            st.error("Usuario o contraseña incorrectos.")
            return None
        st.session_state["erp_uid"] = str(row["id"])
        st.session_state["erp_rol"] = str(row["rol"])
        st.session_state["erp_nombre"] = str(row.get("nombre") or row["username"])
        st.session_state["erp_username"] = str(row["username"])
        _persist_new_session_cookie(cm, row)
        st.rerun()
    return None


@st.cache_resource
def get_supabase() -> Client:
    from supabase import create_client

    u = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
    k = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
    return create_client(str(u), str(k))


def role_can(rol: str, module: str) -> bool:
    if module == "usuarios":
        return rol == "superuser"
    if rol == "superuser":
        return True
    if rol == "admin":
        return module in {
            "dashboard",
            "tasas",
            "ventas",
            "compras",
            "cajas",
            "reportes",
        }
    if rol == "vendedor":
        return module in {"ventas"}
    if rol == "almacen":
        return module in {"inventario"}
    return False


def latest_tasas(sb: Client) -> dict[str, Any] | None:
    r = (
        sb.table("tasas_dia")
        .select("*")
        .order("fecha", desc=True)
        .limit(1)
        .execute()
    )
    rows = r.data or []
    return rows[0] if rows else None


def _today_caracas() -> date:
    return datetime.now(ZoneInfo("America/Caracas")).date()


def _tasas_para_fecha(sb: Client, d: date) -> dict[str, Any] | None:
    r = sb.table("tasas_dia").select("*").eq("fecha", str(d)).limit(1).execute()
    row = (r.data or [None])[0]
    return row if isinstance(row, dict) else None


# Sincronización automática tasas web → `tasas_dia` + recálculo Bs en productos (RPC).
# Si REL = 0, solo cuenta la diferencia absoluta en Bs/USD (más “tiempo real”).
AUTO_TASA_SYNC_REL_MIN = 0.0
# Mínimo cambio en Bs por 1 USD para escribir (evita ruido de redondeo de la API).
AUTO_TASA_ABS_MIN_BS = 0.02
# Alineado con caché de `get_live_exchange_rates` (~120 s): cada refresco web puede persistirse.
AUTO_TASA_SYNC_MIN_SECONDS = 120.0


def _refresh_productos_bs_equiv_note(sb: Client, t_oper: float) -> str:
    """Tras actualizar `tasa_bs`, recalcula precio_v_bs_ref y costo_bs_ref en productos."""
    try:
        sb.rpc("refresh_productos_bs_equiv", {"p_tasa_bs": float(t_oper)}).execute()
        return " Productos: equivalentes Bs recalculados en BD."
    except Exception:
        return " (Ejecuta `supabase/patch_007_productos_bs_ref.sql` para recalcular Bs en productos.)"


def maybe_auto_sync_tasas_from_web(sb: Client) -> dict[str, Any] | None:
    """
    Si el USD×Bs web difiere del guardado (abs ≥ AUTO_TASA_ABS_MIN_BS y/o rel ≥ AUTO_TASA_SYNC_REL_MIN),
    hace upsert del día (Caracas): actualiza la **ref. Bs/USD mercado (API / alineada a P2P)**; **no pisa el BCV** que tengas guardado.
    `tasa_bs` sigue **BCV** si en el último guardado estabas operando con BCV; si operabas con mercado P2P, sigue esa cotización web.
    Tras guardar, llama `refresh_productos_bs_equiv` con esa `tasa_bs`.
    """
    t_latest = latest_tasas(sb)
    if not t_latest:
        return None

    now = time.monotonic()
    last = float(st.session_state.get("_auto_tasas_sync_mono", 0.0))
    if now - last < AUTO_TASA_SYNC_MIN_SECONDS:
        return latest_tasas(sb)

    live = get_live_exchange_rates()
    if not live.get("ok"):
        return latest_tasas(sb)

    ves = _nf(live.get("ves_bs_por_usd"))
    if ves is None or ves <= 0:
        return latest_tasas(sb)

    hoy = _today_caracas()
    t_hoy = _tasas_para_fecha(sb, hoy)
    base = t_hoy or t_latest
    saved_par = _nf(base.get("paralelo_bs_por_usd")) or _nf(base.get("tasa_bs"))
    if saved_par is None or saved_par <= 0:
        return latest_tasas(sb)

    abs_diff = abs(float(ves) - float(saved_par))
    rel_diff = abs_diff / float(saved_par) if saved_par > 0 else 0.0
    rel_ok = AUTO_TASA_SYNC_REL_MIN > 0 and rel_diff >= AUTO_TASA_SYNC_REL_MIN
    abs_ok = abs_diff >= AUTO_TASA_ABS_MIN_BS
    if not rel_ok and not abs_ok:
        return latest_tasas(sb)

    bcv = _nf(base.get("bcv_bs_por_usd"))
    if bcv is None or bcv <= 0:
        bcv = _nf(t_latest.get("bcv_bs_por_usd")) or _nf(t_latest.get("tasa_bs")) or float(saved_par)

    tusdt = _nf(base.get("tasa_usdt")) or _nf(t_latest.get("tasa_usdt")) or 1.0
    if tusdt <= 0:
        tusdt = 1.0

    usd_eur = _nf(live.get("usd_por_eur")) or _nf(base.get("usd_por_eur")) or _nf(t_latest.get("usd_por_eur")) or 1.08
    if usd_eur <= 0:
        usd_eur = 1.08

    p2p = _nf(live.get("usdt_x_ves_p2p")) or _nf(live.get("p2p_bs_por_usdt_aprox"))
    if p2p is None or p2p <= 0:
        p2p = _nf(base.get("p2p_bs_por_usdt")) or _nf(t_latest.get("p2p_bs_por_usdt")) or float(ves)

    par = float(ves)
    prev_tb = _nf(base.get("tasa_bs"))
    prev_bcv = _nf(base.get("bcv_bs_por_usd")) or prev_tb
    prev_par = _nf(base.get("paralelo_bs_por_usd")) or prev_tb
    if (
        prev_tb is not None
        and prev_bcv is not None
        and prev_par is not None
        and float(prev_bcv) > 0
        and float(prev_par) > 0
    ):
        d_b = abs(float(prev_tb) - float(prev_bcv))
        d_p = abs(float(prev_tb) - float(prev_par))
        t_oper = float(bcv) if d_b <= d_p else par
    else:
        t_oper = par
    row = {
        "fecha": str(hoy),
        "tasa_bs": float(t_oper),
        "tasa_usdt": float(tusdt),
        "bcv_bs_por_usd": float(bcv),
        "paralelo_bs_por_usd": float(par),
        "usd_por_eur": float(usd_eur),
        "p2p_bs_por_usdt": float(p2p),
    }
    try:
        sb.table("tasas_dia").upsert(row, on_conflict="fecha").execute()
        st.session_state["_auto_tasas_sync_mono"] = now
        prod_note = _refresh_productos_bs_equiv_note(sb, float(t_oper))
        modo = (
            "tasa_bs = BCV guardado"
            if abs(float(t_oper) - float(bcv)) < 1e-6
            else "tasa_bs = mercado P2P / ref. web"
        )
        st.session_state["_tasas_auto_sync_msg"] = (
            f"Tasas auto: mercado/ref. web {par:,.2f} Bs/USD (antes {saved_par:,.2f}). {modo}.{prod_note}"
        )
    except Exception:
        pass
    return latest_tasas(sb)


_INV_PRODUCTO_COLS = [
    "id",
    "codigo",
    "sku_oem",
    "descripcion",
    "marca_producto",
    "condicion",
    "ubicacion",
    "compatibilidad",
    "imagen_url",
    "stock_actual",
    "stock_minimo",
    "costo_usd",
    "precio_v_usd",
    "precio_v_bs_ref",
    "costo_bs_ref",
    "activo",
    "categoria_id",
]


def _inv_compat_as_dict(raw: Any) -> dict[str, Any]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            o = json.loads(s)
            return o if isinstance(o, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _inv_compat_marcas_str(d: dict[str, Any]) -> str:
    m = d.get("marcas_vehiculo") if "marcas_vehiculo" in d else d.get("marcas")
    if isinstance(m, list):
        return ", ".join(str(x).strip() for x in m if str(x).strip())
    if isinstance(m, str) and m.strip():
        return m.strip()
    return ""


def _inv_compat_anos_str(d: dict[str, Any]) -> str:
    a = d.get("años") if "años" in d else d.get("anos")
    if a is None or (isinstance(a, float) and pd.isna(a)):
        return ""
    return str(a).strip()


def _inv_build_compat_dict(marcas_csv: str, anos: str) -> dict[str, Any]:
    raw = (marcas_csv or "").replace(";", ",")
    marcas = [x.strip() for x in raw.split(",") if x.strip()]
    out: dict[str, Any] = {}
    if marcas:
        out["marcas_vehiculo"] = marcas
    a = (anos or "").strip()
    if a:
        out["años"] = a
    return out


def _inv_merge_marcas_catalogo_texto(seleccion: list[str], texto_extra: str) -> str:
    """Une marcas elegidas en multiselect + las que escribís a mano (coma o punto y coma)."""
    nombres: set[str] = set()
    for x in seleccion or []:
        s = str(x).strip()
        if s:
            nombres.add(s)
    raw = (texto_extra or "").replace(";", ",")
    for x in raw.split(","):
        s = x.strip()
        if s:
            nombres.add(s)
    return ", ".join(sorted(nombres, key=str.casefold))


def _codigo_interno_slug(s: str, *, max_len: int = 3) -> str:
    """Fragmento corto en mayúsculas (solo letras/números) para armar códigos tipo FIL-BOS-0001."""
    if not s or not str(s).strip():
        return "GEN"[:max_len]
    t = unicodedata.normalize("NFKD", str(s).strip())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = "".join(ch for ch in t.upper() if ch.isalnum())
    if not t:
        return "GEN"[:max_len]
    return t[:max_len]


def _siguiente_codigo_interno_producto(sb: Client, nombre_categoria: str, marca_repuesto: str) -> str:
    """
    Código automático: CATEGORÍA(3)-MARCA_REP(3)-NNNN.
    Ej.: categoría «Filtros» + marca «Bosch» → FIL-BOS-0007
    """
    cat = _codigo_interno_slug(nombre_categoria or "CAT", max_len=3)
    mar = _codigo_interno_slug(marca_repuesto or "GEN", max_len=3)
    prefix = f"{cat}-{mar}-"
    try:
        r = sb.table("productos").select("codigo").like("codigo", f"{prefix}%").execute()
    except Exception:
        r = type("R", (), {"data": []})()
    max_n = 0
    rx = re.compile(re.escape(prefix) + r"(\d{1,6})$", re.IGNORECASE)
    for row in r.data or []:
        c = (row.get("codigo") or "").strip()
        m = rx.match(c)
        if m:
            try:
                max_n = max(max_n, int(m.group(1)))
            except ValueError:
                pass
    return f"{prefix}{max_n + 1:04d}"


def _fetch_marcas_vehiculo_catalogo(sb: Client) -> list[str]:
    try:
        mr = (
            sb.table("marcas_vehiculo")
            .select("nombre")
            .eq("activo", True)
            .order("orden")
            .execute()
        )
        return [str(r["nombre"]) for r in (mr.data or []) if r.get("nombre")]
    except Exception:
        return []


def _inv_row_matches_query(row: pd.Series, q: str) -> bool:
    ql = q.lower()
    for k in ("descripcion", "codigo", "sku_oem", "marca_producto"):
        if ql in str(row.get(k) or "").lower():
            return True
    d = _inv_compat_as_dict(row.get("compatibilidad"))
    for m in d.get("marcas_vehiculo") or d.get("marcas") or []:
        if ql in str(m).lower():
            return True
    if ql in _inv_compat_anos_str(d).lower():
        return True
    return False


def _inv_stock_int(x: Any) -> int:
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return 0
        return int(round(float(x)))
    except (TypeError, ValueError):
        return 0


def _line_qty_int(x: Any, *, default: int = 1) -> int:
    """Cantidad en líneas de venta/compra: entero ≥ 1."""
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return max(1, default)
        v = int(round(float(x)))
        return max(1, v)
    except (TypeError, ValueError):
        return max(1, default)


def _inv_eliminar_producto_stock_cero(sb: Client, producto_id: str, confirmacion: str) -> tuple[bool, str]:
    if (confirmacion or "").strip().upper() != "ELIMINAR":
        return False, "Escribí **ELIMINAR** en mayúsculas para confirmar."
    r = sb.table("productos").select("id,stock_actual,codigo,descripcion").eq("id", producto_id).limit(1).execute()
    rows = r.data or []
    if not rows:
        return False, "Producto no encontrado."
    row = rows[0]
    if _inv_stock_int(row.get("stock_actual")) != 0:
        return False, "Solo se puede eliminar con **stock en cero**."
    try:
        sb.table("productos").delete().eq("id", producto_id).execute()
    except Exception as e:
        es = str(e).lower()
        if "foreign key" in es or "23503" in es or "violates" in es:
            return (
                False,
                "No se puede borrar: el producto tiene **ventas o compras** registradas. "
                "Desactivá el ítem (**Activo** = no) en la tabla de abajo para dejar de usarlo.",
            )
        return False, str(e)
    cd = _export_cell_txt(row.get("codigo")) or "—"
    ds = _export_cell_txt(row.get("descripcion"))[:80]
    return True, f"Eliminado **{cd}** · {ds}"


def _inv_aplicar_movimiento_stock(
    sb: Client,
    erp_uid: str,
    producto_id: str,
    tipo: str,
    cantidad: int,
    motivo: str,
) -> tuple[bool, str]:
    if tipo not in ("Entrada", "Salida"):
        return False, "Tipo inválido."
    if cantidad < 1:
        return False, "La cantidad debe ser al menos **1**."
    r = sb.table("productos").select("id,stock_actual,descripcion,codigo").eq("id", producto_id).limit(1).execute()
    rows = r.data or []
    if not rows:
        return False, "Producto no encontrado."
    row = rows[0]
    st_antes = _inv_stock_int(row.get("stock_actual"))
    if tipo == "Salida":
        if st_antes < cantidad:
            return False, f"Stock insuficiente para descargar (hay **{st_antes}**)."
        st_desp = st_antes - cantidad
    else:
        st_desp = st_antes + cantidad
    mot = (motivo or "").strip()
    if not mot:
        return False, "Indicá un **motivo** (ej. inventario físico, merma, hallazgo, traslado)."
    try:
        sb.table("productos").update({"stock_actual": st_desp}).eq("id", producto_id).execute()
    except Exception as e:
        return False, str(e)
    try:
        sb.table("movimientos_inventario").insert(
            {
                "producto_id": producto_id,
                "tipo": tipo,
                "cantidad": int(cantidad),
                "motivo": mot[:2000],
                "stock_antes": st_antes,
                "stock_despues": st_desp,
                "usuario_id": erp_uid,
            }
        ).execute()
    except Exception as e:
        try:
            sb.table("productos").update({"stock_actual": st_antes}).eq("id", producto_id).execute()
        except Exception:
            pass
        return (
            False,
            f"{e} · Stock revertido. Ejecutá **supabase/patch_013_movimientos_inventario.sql** si falta la tabla.",
        )
    cd = _export_cell_txt(row.get("codigo")) or "—"
    return True, f"**{cd}** · Stock **{st_antes}** → **{st_desp}** ({tipo} **{cantidad}** unidades)."


def _inv_enrich_compat_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    if "compatibilidad" not in df.columns:
        df["compatibilidad"] = pd.NA
        df["vehiculos_compat"] = ""
        df["años_compat"] = ""
        return df
    vc: list[str] = []
    va: list[str] = []
    for _, row in df.iterrows():
        d = _inv_compat_as_dict(row.get("compatibilidad"))
        vc.append(_inv_compat_marcas_str(d))
        va.append(_inv_compat_anos_str(d))
    df["vehiculos_compat"] = vc
    df["años_compat"] = va
    return df


def _fetch_productos_inventario_df(sb: Client) -> pd.DataFrame:
    cols_full = (
        "id,codigo,sku_oem,descripcion,marca_producto,condicion,ubicacion,compatibilidad,imagen_url,"
        "stock_actual,stock_minimo,costo_usd,precio_v_usd,precio_v_bs_ref,costo_bs_ref,activo,categoria_id"
    )
    cols_base = (
        "id,codigo,descripcion,stock_actual,stock_minimo,costo_usd,precio_v_usd,"
        "precio_v_bs_ref,costo_bs_ref,activo,categoria_id"
    )
    cols_min = "id,codigo,descripcion,stock_actual,stock_minimo,costo_usd,precio_v_usd,activo,categoria_id"
    try:
        r = sb.table("productos").select(cols_full).order("descripcion").execute()
    except Exception:
        try:
            r = sb.table("productos").select(cols_base).order("descripcion").execute()
        except Exception:
            r = sb.table("productos").select(cols_min).order("descripcion").execute()
    return pd.DataFrame(r.data or [])


def _normalize_productos_inventario_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Si no hay filas, Supabase devuelve [] y pandas crea un DataFrame **sin columnas**.
    Normalizamos al esquema esperado por el editor y los reportes.
    """
    if df.empty and len(df.columns) == 0:
        return pd.DataFrame(columns=_INV_PRODUCTO_COLS)
    out = df.copy()
    for c in _INV_PRODUCTO_COLS:
        if c not in out.columns:
            out[c] = pd.NA
    if "condicion" in out.columns:
        out["condicion"] = out["condicion"].apply(
            lambda x: (
                "Nuevo"
                if x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() not in ("Nuevo", "Usado")
                else str(x).strip()
            )
        )
    return out


def _categoria_maps_from_rows(
    cat_rows: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """id->nombre, nombre->id, opciones selectbox ('' = sin categoría)."""
    id_to_n: dict[str, str] = {}
    n_to_id: dict[str, str] = {}
    for c in cat_rows:
        cid = str(c.get("id") or "").strip()
        nom = str(c.get("nombre") or "").strip()
        if cid and nom:
            id_to_n[cid] = nom
            n_to_id[nom] = cid
    opts = [""] + sorted(n_to_id.keys(), key=str.casefold)
    return id_to_n, n_to_id, opts


def _resolve_categoria_id_por_nombre(nombre: str, n_to_id: dict[str, str]) -> str | None:
    s = nombre.strip()
    if not s:
        return None
    if s in n_to_id:
        return n_to_id[s]
    sl = s.lower()
    for k, vid in n_to_id.items():
        if k.lower() == sl:
            return vid
    return None


def _inv_cat_display(celda: Any) -> str:
    if celda is None or (isinstance(celda, float) and pd.isna(celda)):
        return "(Sin categoría)"
    s = str(celda).strip()
    return s if s else "(Sin categoría)"


def _df_inventario_filtrado_impresion(
    df: pd.DataFrame,
    *,
    categorias_sel: list[str],
    costo_min: float,
    costo_max: float,
    precio_min: float,
    precio_max: float,
    solo_activos: bool,
) -> pd.DataFrame:
    out = df.copy()
    if solo_activos and "activo" in out.columns:
        out = out[out["activo"] == True]  # noqa: E712
    if categorias_sel:
        disp = out["categoria"].map(_inv_cat_display)
        out = out[disp.isin(categorias_sel)]
    c_usd = pd.to_numeric(out["costo_usd"], errors="coerce").fillna(0.0)
    p_usd = pd.to_numeric(out["precio_v_usd"], errors="coerce").fillna(0.0)
    m = pd.Series(True, index=out.index)
    if costo_min > 0:
        m &= c_usd >= float(costo_min)
    if costo_max > 0:
        m &= c_usd <= float(costo_max)
    if precio_min > 0:
        m &= p_usd >= float(precio_min)
    if precio_max > 0:
        m &= p_usd <= float(precio_max)
    return out.loc[m]


def _df_inventario_orden_impresion(df: pd.DataFrame, orden_key: str, *, agrupar_categoria: bool) -> pd.DataFrame:
    keys: list[tuple[str, bool]] = []
    if orden_key == "codigo":
        keys = [("codigo", True)]
    elif orden_key == "costo_asc":
        keys = [("costo_usd", True)]
    elif orden_key == "costo_desc":
        keys = [("costo_usd", False)]
    elif orden_key == "precio_asc":
        keys = [("precio_v_usd", True)]
    elif orden_key == "precio_desc":
        keys = [("precio_v_usd", False)]
    else:
        keys = [("descripcion", True)]
    if agrupar_categoria:
        keys = [("categoria", True)] + keys
    work = df.copy()
    for col, _asc in keys:
        if col not in work.columns:
            continue
        if work[col].dtype == object or str(work[col].dtype) == "object":
            work[col] = work[col].fillna("").astype(str)
    col_names = [k[0] for k in keys if k[0] in work.columns]
    ascending = [k[1] for k in keys if k[0] in work.columns]
    if not col_names:
        return work
    return work.sort_values(by=col_names, ascending=ascending, kind="mergesort")


def _html_inventario_listado(
    df: pd.DataFrame,
    t: dict[str, Any] | None,
    *,
    agrupar_categoria: bool,
    subtitulo_filtros: str,
) -> str:
    tz = ZoneInfo("America/Caracas")
    fecha = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    work = df.copy()
    work["categoria_display"] = work["categoria"].map(_inv_cat_display)
    if "compatibilidad" in work.columns:
        work["_veh_rep"] = work["compatibilidad"].map(
            lambda x: _inv_compat_marcas_str(_inv_compat_as_dict(x))
        )
        work["_anos_rep"] = work["compatibilidad"].map(
            lambda x: _inv_compat_anos_str(_inv_compat_as_dict(x))
        )
    else:
        work["_veh_rep"] = ""
        work["_anos_rep"] = ""

    cols_print: list[tuple[str, str]] = [
        ("codigo", "Código"),
        ("sku_oem", "OEM"),
        ("descripcion", "Descripción"),
        ("marca_producto", "Marca rep."),
        ("condicion", "Cond."),
        ("_veh_rep", "Marcas carro"),
        ("_anos_rep", "Años"),
        ("categoria_display", "Categoría"),
        ("stock_actual", "Stock"),
        ("stock_minimo", "Stock mín."),
        ("costo_usd", "Costo USD"),
        ("precio_v_usd", "Precio venta USD"),
    ]
    cols_print = [(k, lab) for k, lab in cols_print if k in work.columns]
    if "precio_v_bs_ref" in work.columns:
        cols_print.append(("precio_v_bs_ref", "Precio venta Bs (ref.)"))
    if "costo_bs_ref" in work.columns:
        cols_print.append(("costo_bs_ref", "Costo Bs (ref.)"))

    ths = "".join(f"<th>{html.escape(lab)}</th>" for _k, lab in cols_print)
    body_rows: list[str] = []
    current_cat: str | None = None
    for _, row in work.iterrows():
        if agrupar_categoria:
            cd = str(row["categoria_display"])
            if cd != current_cat:
                current_cat = cd
                body_rows.append(
                    f'<tr class="catgrp"><td colspan="{len(cols_print)}">{html.escape(cd)}</td></tr>'
                )
        tds: list[str] = []
        for key, _lab in cols_print:
            val = row.get(key)
            if key in ("stock_actual", "stock_minimo"):
                try:
                    cell = f"{_inv_stock_int(val):,d}"
                except (TypeError, ValueError):
                    cell = html.escape("" if val is None else str(val))
            elif key in ("costo_usd", "precio_v_usd", "precio_v_bs_ref", "costo_bs_ref"):
                try:
                    cell = f"{float(val):,.2f}"
                except (TypeError, ValueError):
                    cell = html.escape("" if val is None else str(val))
            else:
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    cell = ""
                else:
                    cell = html.escape(str(val))
            tds.append(f"<td>{cell}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")

    n = len(work)
    tasa_note = ""
    if t and _nf(t.get("tasa_bs")) is not None:
        tasa_note = f"<p class=\"sub\">Tasa Bs/USD de referencia en sistema: <strong>{float(t['tasa_bs']):,.2f}</strong></p>"

    filt_html = f"<p class=\"sub\">{html.escape(subtitulo_filtros)}</p>" if subtitulo_filtros.strip() else ""

    _logo_uri = _brand_logo_data_uri()
    _logo_block = (
        f'<div class="logo-wrap"><img class="logo" src="{_logo_uri}" alt="Movi Motors"/></div>'
        if _logo_uri
        else '<div class="logo-wrap logo-missing">Movi Motor\'s Importadora</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>Inventario — Movi Motors</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 14mm 16mm 16mm 16mm;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: Segoe UI, Roboto, Arial, sans-serif;
    margin: 0;
    padding: 1rem 1.25rem;
    max-width: 210mm;
    margin-left: auto;
    margin-right: auto;
    color: #111;
  }}
  .logo-wrap {{
    text-align: center;
    margin: 0 0 0.6rem 0;
  }}
  .logo {{
    max-height: 22mm;
    max-width: 52mm;
    width: auto;
    height: auto;
    object-fit: contain;
  }}
  .logo-missing {{
    font-weight: 800;
    font-size: 1rem;
    color: #5c2d91;
    letter-spacing: 0.02em;
  }}
  h1 {{ font-size: 1.1rem; margin: 0 0 0.35rem 0; text-align: center; color: #2a1f45; }}
  .meta {{ color: #444; font-size: 0.82rem; margin-bottom: 0.65rem; text-align: center; }}
  .sub {{ font-size: 0.78rem; color: #333; margin: 0.3rem 0; text-align: center; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.72rem; }}
  th, td {{ border: 1px solid #bbb; padding: 0.3rem 0.4rem; text-align: left; vertical-align: top; word-break: break-word; }}
  th {{ background: #2a1f45; color: #fff; font-weight: 600; }}
  tr.catgrp td {{ background: #fff3e0; font-weight: 700; color: #e65100; border-color: #ffcc80; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
  .foot {{ margin-top: 0.85rem; font-size: 0.75rem; color: #555; text-align: center; }}
  .print-actions {{ margin-top: 0.75rem; text-align: center; }}
  @media print {{
    body {{ padding: 0; max-width: none; }}
    .print-actions {{ display: none !important; }}
    tr.catgrp td {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    th {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    table {{ font-size: 0.68rem; }}
  }}
</style>
</head>
<body>
  {_logo_block}
  <h1>Listado de inventario</h1>
  <div class="meta">Generado: {html.escape(fecha)} (America/Caracas) · <strong>{n}</strong> ítem(s)</div>
  {tasa_note}
  {filt_html}
  <table>
    <thead><tr>{ths}</tr></thead>
    <tbody>
      {''.join(body_rows)}
    </tbody>
  </table>
  <p class="foot">Precios y costos en USD son los maestros del sistema. Columnas Bs (ref.) dependen de la tasa guardada al momento del reporte.</p>
  <div class="print-actions">
    <script>function imprimir(){{ window.print(); }}</script>
    <button type="button" onclick="imprimir()" style="padding:0.5rem 1.2rem;font-size:1rem;cursor:pointer;background:#2a1f45;color:#fff;border:none;border-radius:6px;">Imprimir</button>
  </div>
</body>
</html>"""


def _export_cell_txt(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


def _df_inventario_export_flat(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    base: dict[str, Any] = {
        "Código": work["codigo"].map(_export_cell_txt),
        "Descripción": work["descripcion"].map(_export_cell_txt),
        "Categoría": work["categoria"].map(_inv_cat_display),
        "Stock": work["stock_actual"].map(_inv_stock_int),
        "Stock mín.": work["stock_minimo"].map(_inv_stock_int),
        "Costo USD": pd.to_numeric(work["costo_usd"], errors="coerce"),
        "Precio venta USD": pd.to_numeric(work["precio_v_usd"], errors="coerce"),
    }
    if "sku_oem" in work.columns:
        base["OEM"] = work["sku_oem"].map(_export_cell_txt)
    if "marca_producto" in work.columns:
        base["Marca repuesto"] = work["marca_producto"].map(_export_cell_txt)
    if "condicion" in work.columns:
        base["Condición"] = work["condicion"].map(_export_cell_txt)
    if "compatibilidad" in work.columns:
        base["Marcas carro"] = work["compatibilidad"].map(
            lambda x: _inv_compat_marcas_str(_inv_compat_as_dict(x))
        )
        base["Años"] = work["compatibilidad"].map(
            lambda x: _inv_compat_anos_str(_inv_compat_as_dict(x))
        )
    if "ubicacion" in work.columns:
        base["Ubicación"] = work["ubicacion"].map(_export_cell_txt)
    out = pd.DataFrame(base)
    if "precio_v_bs_ref" in work.columns:
        out["Precio venta Bs (ref.)"] = pd.to_numeric(work["precio_v_bs_ref"], errors="coerce")
    if "costo_bs_ref" in work.columns:
        out["Costo Bs (ref.)"] = pd.to_numeric(work["costo_bs_ref"], errors="coerce")
    if "activo" in work.columns:
        out["Activo"] = work["activo"].astype(bool)
    return out


def _xlsx_inventario_bytes(df_flat: pd.DataFrame) -> bytes:
    from openpyxl.utils import get_column_letter

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_flat.to_excel(writer, index=False, sheet_name="Inventario")
        ws = writer.sheets["Inventario"]
        for i, col in enumerate(df_flat.columns, start=1):
            lens = df_flat[col].astype(str).map(len)
            m = max(int(lens.max()) if len(lens) > 0 else 0, len(str(col)))
            ws.column_dimensions[get_column_letter(i)].width = float(min(48, max(10, m + 2)))
    return buf.getvalue()


def _pdf_short_txt(val: Any, max_len: int) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        s = ""
    else:
        s = str(val).strip()
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _pdf_inventario_col_widths(n_cols: int, total_w: float) -> list[float]:
    """Proporciones para **A4 vertical** (ancho útil ≈ 210 mm − márgenes)."""
    if n_cols == 7:
        parts = [0.09, 0.30, 0.14, 0.09, 0.09, 0.145, 0.145]
    elif n_cols == 8:
        parts = [0.08, 0.26, 0.12, 0.08, 0.08, 0.13, 0.13, 0.13]
    elif n_cols == 9:
        parts = [0.07, 0.22, 0.11, 0.07, 0.07, 0.12, 0.12, 0.12, 0.12]
    else:
        parts = [1.0 / n_cols] * n_cols
    return [total_w * p for p in parts]


def _pdf_inventario_bytes(
    df: pd.DataFrame,
    t: dict[str, Any] | None,
    *,
    agrupar_categoria: bool,
    subtitulo_filtros: str,
) -> bytes:
    from copy import deepcopy

    from xml.sax.saxutils import escape as xml_esc

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = BytesIO()
    page = A4
    lm = 18 * mm
    rm = 18 * mm
    tm = 15 * mm
    bm = 18 * mm
    doc = SimpleDocTemplate(
        buf,
        pagesize=page,
        leftMargin=lm,
        rightMargin=rm,
        topMargin=tm,
        bottomMargin=bm,
    )
    styles = getSampleStyleSheet()
    story: list[Any] = []
    tw = float(page[0] - lm - rm)

    if BRAND_LOGO_PATH.is_file():
        try:
            ir = ImageReader(str(BRAND_LOGO_PATH))
            iw, ih = ir.getSize()
            if iw > 0 and ih > 0:
                target_w = 44 * mm
                target_h = target_w * (float(ih) / float(iw))
                max_h = 22 * mm
                if target_h > max_h:
                    target_h = max_h
                    target_w = target_h * (float(iw) / float(ih))
                lg = RLImage(str(BRAND_LOGO_PATH), width=target_w, height=target_h)
                lg.hAlign = "CENTER"
                story.append(lg)
                story.append(Spacer(1, 2.5 * mm))
        except Exception:
            pass

    tz = ZoneInfo("America/Caracas")
    fecha = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    tit = deepcopy(styles["Title"])
    tit.fontSize = 13
    tit.leading = 15
    tit.textColor = colors.HexColor("#2a1f45")
    tit.alignment = TA_CENTER
    story.append(Paragraph(xml_esc("Listado de inventario"), tit))
    meta = deepcopy(styles["Normal"])
    meta.fontSize = 8.5
    meta.alignment = TA_CENTER
    story.append(
        Paragraph(
            xml_esc(f"Movi Motor's Importadora · Generado: {fecha} (America/Caracas) · {len(df)} ítem(s)"),
            meta,
        )
    )
    tbs = _nf(t.get("tasa_bs")) if t else None
    if tbs is not None:
        story.append(Paragraph(xml_esc(f"Tasa Bs/USD ref.: {tbs:,.2f}"), meta))
    if subtitulo_filtros.strip():
        sf = deepcopy(styles["BodyText"])
        sf.fontSize = 8
        sf.alignment = TA_CENTER
        story.append(Paragraph(xml_esc(subtitulo_filtros), sf))
    story.append(Spacer(1, 2.5 * mm))

    headers = ["Cód.", "OEM", "Descripción", "Cond.", "Vehíc.", "Cat.", "St", "Mín", "C.U.", "P.V."]
    if "precio_v_bs_ref" in df.columns:
        headers.append("P.Bs")
    if "costo_bs_ref" in df.columns:
        headers.append("C.Bs")
    n_h = len(headers)
    col_ws = _pdf_inventario_col_widths(n_h, tw)

    def fmt_int_st(x: Any) -> str:
        try:
            return f"{_inv_stock_int(x):d}"
        except (TypeError, ValueError):
            return ""

    def fmt2(x: Any) -> str:
        try:
            return f"{float(x):,.2f}"
        except (TypeError, ValueError):
            return ""

    def row_cells(r: pd.Series) -> list[str]:
        cd = _inv_cat_display(r.get("categoria"))
        _dcomp = _inv_compat_as_dict(r.get("compatibilidad"))
        _veh = _pdf_short_txt(_inv_compat_marcas_str(_dcomp), 14)
        cells = [
            _pdf_short_txt(r.get("codigo"), 8),
            _pdf_short_txt(r.get("sku_oem"), 10),
            _pdf_short_txt(r.get("descripcion"), 22),
            _pdf_short_txt(r.get("condicion"), 6),
            _veh,
            _pdf_short_txt(cd, 10),
            fmt_int_st(r.get("stock_actual")),
            fmt_int_st(r.get("stock_minimo")),
            fmt2(r.get("costo_usd")),
            fmt2(r.get("precio_v_usd")),
        ]
        if "precio_v_bs_ref" in df.columns:
            cells.append(fmt2(r.get("precio_v_bs_ref")))
        if "costo_bs_ref" in df.columns:
            cells.append(fmt2(r.get("costo_bs_ref")))
        return [xml_esc(c) for c in cells]

    tbl_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2a1f45")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 6.5),
            ("LEADING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
        ]
    )

    work = df.copy()
    work["_cdisp"] = work["categoria"].map(_inv_cat_display)

    if agrupar_categoria:
        h4_base = deepcopy(styles["Heading4"])
        h4_base.fontSize = 9.5
        h4_base.textColor = colors.HexColor("#e65100")
        for cat_name, grp in work.groupby("_cdisp", sort=False):
            story.append(Paragraph(f"<b>{xml_esc(str(cat_name))}</b>", h4_base))
            data: list[list[str]] = [headers]
            for _, r in grp.iterrows():
                data.append(row_cells(r))
            tbl = Table(data, colWidths=col_ws, repeatRows=1)
            tbl.setStyle(tbl_style)
            story.append(tbl)
            story.append(Spacer(1, 2 * mm))
    else:
        data = [headers]
        for _, r in work.iterrows():
            data.append(row_cells(r))
        tbl = Table(data, colWidths=col_ws, repeatRows=1)
        tbl.setStyle(tbl_style)
        story.append(tbl)

    doc.build(story)
    return buf.getvalue()


def _backup_file_timestamp() -> str:
    return datetime.now(ZoneInfo("America/Caracas")).strftime("%Y%m%d_%H%M%S")


def _json_backup_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _json_backup_bytes_compact_gzip(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    return gzip.compress(raw, compresslevel=9)


def decode_backup_upload_bytes(raw: bytes) -> dict[str, Any]:
    if len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B:
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


_ERP_KV_KEY_AUTO_DAY = "movi_auto_backup_day_v1"


def _auto_backup_config() -> dict[str, Any]:
    defaults: dict[str, Any] = {"enabled": True, "retain_days": 14, "storage_bucket": ""}
    try:
        ab = st.secrets.get("auto_backup")
    except Exception:
        return defaults
    if ab is None:
        return defaults
    try:
        rd = int(ab.get("retain_days", 14))
        rd = max(1, min(365, rd))
        return {
            "enabled": bool(ab.get("enabled", True)),
            "retain_days": rd,
            "storage_bucket": str(ab.get("storage_bucket") or "").strip(),
        }
    except Exception:
        return defaults


def _auto_backup_dir() -> Path:
    return _APP_DIR / "auto_backups"


def _local_auto_backup_day_path() -> Path:
    return _auto_backup_dir() / ".last_auto_day_v1"


def _read_local_auto_backup_day() -> str | None:
    try:
        s = _local_auto_backup_day_path().read_text(encoding="utf-8").strip()
        return s or None
    except Exception:
        return None


def _write_local_auto_backup_day(day: str) -> None:
    d = _auto_backup_dir()
    d.mkdir(parents=True, exist_ok=True)
    _local_auto_backup_day_path().write_text(day, encoding="utf-8")


def _erp_kv_get(sb: Client, key: str) -> str | None:
    try:
        r = sb.table("erp_kv").select("value").eq("key", key).limit(1).execute()
        row = (r.data or [{}])[0]
        s = str(row.get("value") or "").strip()
        return s or None
    except Exception:
        return None


def _erp_kv_set(sb: Client, key: str, value: str) -> bool:
    try:
        sb.table("erp_kv").upsert({"key": key, "value": value}).execute()
        return True
    except Exception:
        return False


def _prune_old_auto_backups(*, retain_days: int) -> None:
    dir_path = _auto_backup_dir()
    if not dir_path.is_dir():
        return
    today_c = _today_caracas()
    cutoff = today_c - timedelta(days=max(1, retain_days))
    for p in dir_path.glob("movi_erp_auto_*.json.gz"):
        if not p.is_file():
            continue
        name = p.name
        if not name.startswith("movi_erp_auto_") or not name.endswith(".json.gz"):
            continue
        mid = name[len("movi_erp_auto_") : -len(".json.gz")]
        try:
            d = date.fromisoformat(mid)
        except ValueError:
            continue
        if d < cutoff:
            try:
                p.unlink()
            except OSError:
                pass


def _storage_auto_backup_exists(sb: Client, bucket: str, day_str: str) -> bool:
    needle = f"movi_erp_auto_{day_str}.json.gz"
    try:
        items = sb.storage.from_(bucket).list("auto")
        for it in items or []:
            if str(it.get("name") or "") == needle:
                return True
    except Exception:
        pass
    return False


def _try_storage_auto_backup(sb: Client, bucket: str, day_str: str, data: bytes) -> bool:
    if not bucket:
        return False
    path = f"auto/movi_erp_auto_{day_str}.json.gz"
    try:
        sb.storage.from_(bucket).upload(
            path,
            data,
            file_options={"content-type": "application/gzip", "upsert": "true"},
        )
        return True
    except Exception:
        return False


def maybe_run_daily_auto_backup(sb: Client, rol: str) -> None:
    """
    Una vez al día (America/Caracas), si entra un superusuario: genera el mismo JSON
    que el respaldo completo pero compacto + gzip. Guarda en `auto_backups/` y/o
    Storage (secrets). Coordina con `erp_kv` o archivo local para no repetir.
    """
    if rol != "superuser":
        return
    cfg = _auto_backup_config()
    if not cfg["enabled"]:
        return
    today_str = _today_caracas().isoformat()

    if _erp_kv_get(sb, _ERP_KV_KEY_AUTO_DAY) == today_str:
        st.session_state["_movi_auto_backup_session_day"] = today_str
        return
    if _read_local_auto_backup_day() == today_str:
        st.session_state["_movi_auto_backup_session_day"] = today_str
        return
    bucket = str(cfg.get("storage_bucket") or "")
    if bucket and _storage_auto_backup_exists(sb, bucket, today_str):
        st.session_state["_movi_auto_backup_session_day"] = today_str
        return
    if st.session_state.get("_movi_auto_backup_session_day") == today_str:
        return
    if st.session_state.get("_movi_auto_backup_busy"):
        return

    st.session_state["_movi_auto_backup_busy"] = True
    try:
        payload = build_backup_erp_completo(sb)
        gz = _json_backup_bytes_compact_gzip(payload)
        ok_any = False
        bdir = _auto_backup_dir()
        try:
            bdir.mkdir(parents=True, exist_ok=True)
            (bdir / f"movi_erp_auto_{today_str}.json.gz").write_bytes(gz)
            ok_any = True
        except OSError:
            pass

        if bucket and _try_storage_auto_backup(sb, bucket, today_str, gz):
            ok_any = True

        if not ok_any:
            return

        _prune_old_auto_backups(retain_days=int(cfg["retain_days"]))
        if not _erp_kv_set(sb, _ERP_KV_KEY_AUTO_DAY, today_str):
            _write_local_auto_backup_day(today_str)
        st.session_state["_movi_auto_backup_session_day"] = today_str
        kb = max(1, len(gz) // 1024)
        st.session_state["_movi_auto_backup_toast"] = f"Respaldo automático del día guardado (~{kb} KB gzip)."
    except Exception as ex:
        st.session_state["_movi_auto_backup_toast_err"] = str(ex)
    finally:
        st.session_state["_movi_auto_backup_busy"] = False


def build_backup_inventario(sb: Client) -> dict[str, Any]:
    """Snapshot lógico: categorías + productos (todo el maestro de inventario)."""
    return {
        "meta": {
            "tipo": "inventario",
            "version": 1,
            "exportado_en_utc": datetime.now(timezone.utc).isoformat(),
            "app": "Movi Motors ERP",
        },
        "categorias": (sb.table("categorias").select("*").order("nombre").execute().data or []),
        "productos": (sb.table("productos").select("*").order("descripcion").execute().data or []),
    }


def build_backup_erp_completo(sb: Client) -> dict[str, Any]:
    """
    Snapshot amplio para recuperación ante fallos o antes de depuración.
    No exporta password_hash (seguridad); reasignar claves tras restaurar usuarios.
    """
    payload: dict[str, Any] = {
        "meta": {
            "tipo": "erp_completo",
            "version": 1,
            "exportado_en_utc": datetime.now(timezone.utc).isoformat(),
            "app": "Movi Motors ERP",
            "nota_usuarios": "erp_users sin password_hash. Restauración: volver a definir contraseñas en el módulo Usuarios o en Supabase.",
        },
    }
    specs: list[tuple[str, str]] = [
        ("categorias", "*"),
        ("productos", "*"),
        ("tasas_dia", "*"),
        ("cajas_bancos", "*"),
        ("erp_users", "id,username,nombre,email,rol,activo,created_at"),
        ("ventas", "*"),
        ("ventas_detalles", "*"),
        ("compras", "*"),
        ("compras_detalles", "*"),
        ("cuentas_por_cobrar", "*"),
        ("cuentas_por_pagar", "*"),
        ("movimientos_caja", "*"),
    ]
    errs: list[dict[str, str]] = []
    for tbl, cols in specs:
        try:
            payload[tbl] = sb.table(tbl).select(cols).execute().data or []
        except Exception as ex:
            errs.append({"tabla": tbl, "error": str(ex)})
            payload[tbl] = []
    if errs:
        payload["meta"]["errores_al_exportar"] = errs
    return payload


_PHONY_UUID = "00000000-0000-0000-0000-000000000000"


def _delete_all_rows(sb: Client, table: str) -> None:
    sb.table(table).delete().neq("id", _PHONY_UUID).execute()


def _insert_rows_batched(sb: Client, table: str, rows: list[dict[str, Any]], *, batch: int = 75) -> None:
    if not rows:
        return
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        sb.table(table).insert(chunk).execute()


def _merge_erp_users_from_backup(sb: Client, rows: list[dict[str, Any]]) -> list[str]:
    """Actualiza usuarios existentes; crea faltantes con contraseña temporal."""
    notes: list[str] = []
    for row in rows:
        uid = str(row.get("id") or "").strip()
        un = (row.get("username") or "").strip()
        if not uid or not un:
            continue
        ex = sb.table("erp_users").select("id").eq("id", uid).limit(1).execute()
        base = {
            "username": un.lower(),
            "nombre": (row.get("nombre") or un).strip(),
            "email": (row.get("email") or "").strip() or None,
            "rol": row.get("rol") or "vendedor",
            "activo": bool(row.get("activo", True)),
        }
        if ex.data:
            sb.table("erp_users").update(base).eq("id", uid).execute()
        else:
            try:
                sb.table("erp_users").insert(
                    {**base, "id": uid, "password_hash": _hash_password("Restaurar2025!")}
                ).execute()
                notes.append(
                    f"Usuario **{un}** creado desde respaldo — contraseña temporal: **Restaurar2025!** (cambiar en Usuarios)."
                )
            except Exception as ex:
                notes.append(f"No se pudo crear usuario `{un}`: {ex}")
    return notes


def restore_erp_completo_desde_json(sb: Client, payload: dict[str, Any]) -> tuple[bool, str, list[str]]:
    """
    Reemplaza datos operativos desde un JSON generado por *Descargar respaldo completo*.
    Orden: borra hijos primero; inserta categorías → … → movimientos.
    """
    meta = payload.get("meta") or {}
    if meta.get("tipo") != "erp_completo":
        return False, "El archivo no es un respaldo **erp_completo** (usá el JSON de Mantenimiento).", []
    if int(meta.get("version") or 0) < 1:
        return False, "Versión de respaldo no soportada.", []

    warns: list[str] = []
    try:
        _delete_all_rows(sb, "movimientos_caja")
        _delete_all_rows(sb, "ventas")
        _delete_all_rows(sb, "compras")
        _delete_all_rows(sb, "productos")
        _delete_all_rows(sb, "categorias")
        _delete_all_rows(sb, "tasas_dia")
        _delete_all_rows(sb, "cajas_bancos")

        _insert_rows_batched(sb, "categorias", list(payload.get("categorias") or []))
        _insert_rows_batched(sb, "productos", list(payload.get("productos") or []))
        _insert_rows_batched(sb, "tasas_dia", list(payload.get("tasas_dia") or []))
        _insert_rows_batched(sb, "cajas_bancos", list(payload.get("cajas_bancos") or []))

        urows = list(payload.get("erp_users") or [])
        if urows:
            warns.extend(_merge_erp_users_from_backup(sb, urows))

        _insert_rows_batched(sb, "ventas", list(payload.get("ventas") or []))
        _insert_rows_batched(sb, "ventas_detalles", list(payload.get("ventas_detalles") or []))
        _insert_rows_batched(sb, "compras", list(payload.get("compras") or []))
        _insert_rows_batched(sb, "compras_detalles", list(payload.get("compras_detalles") or []))
        _insert_rows_batched(sb, "cuentas_por_cobrar", list(payload.get("cuentas_por_cobrar") or []))
        _insert_rows_batched(sb, "cuentas_por_pagar", list(payload.get("cuentas_por_pagar") or []))
        _insert_rows_batched(sb, "movimientos_caja", list(payload.get("movimientos_caja") or []))

        try:
            sb.rpc("sync_erp_sequences").execute()
        except Exception:
            warns.append(
                "Ejecutá en Supabase `supabase/patch_009_sync_sequences.sql` para alinear números de venta/compra."
            )

        return True, "Restauración completa aplicada. Revisá avisos abajo si los hay.", warns
    except Exception as e:
        return False, f"Error durante la restauración (la base puede quedar incompleta): {e}", warns


def restore_inventario_desde_json(sb: Client, payload: dict[str, Any]) -> tuple[bool, str]:
    meta = payload.get("meta") or {}
    if meta.get("tipo") != "inventario":
        return False, "El archivo no es un respaldo de **inventario**."
    try:
        _delete_all_rows(sb, "productos")
        _delete_all_rows(sb, "categorias")
        _insert_rows_batched(sb, "categorias", list(payload.get("categorias") or []))
        _insert_rows_batched(sb, "productos", list(payload.get("productos") or []))
        return True, "Inventario restaurado desde el JSON."
    except Exception as e:
        err = str(e).lower()
        if "foreign key" in err or "23503" in err:
            return (
                False,
                "No se puede borrar productos: hay **ventas o compras** que los referencian. "
                "Usá **Mantenimiento → Restaurar todo** con el JSON completo, o depurá operaciones primero.",
            )
        return False, str(e)


def fmt_tri(usd: float, t_bs: float, t_usdt: float) -> str:
    usd = float(usd)
    return (
        f"**USD** {usd:,.2f} · **Bs** {usd * t_bs:,.2f} · **USDT** {usd * t_usdt:,.6f}"
    )


def _nf(x: Any, default: float | None = None) -> float | None:
    try:
        if x is None:
            return default
        v = float(x)
        return v
    except (TypeError, ValueError):
        return default


def _pct_vs_bcv(mercado: float | None, bcv: float | None) -> float | None:
    if mercado is None or bcv is None or bcv <= 0:
        return None
    return (mercado - bcv) / bcv * 100.0


def _p2p_bs_equiv_por_usd(t: dict[str, Any]) -> float | None:
    p2p = _nf(t.get("p2p_bs_por_usdt"))
    tusdt = _nf(t.get("tasa_usdt"))
    if p2p is None or tusdt is None or tusdt <= 0:
        return None
    return p2p * tusdt


def build_tasas_tabla_detalle(t: dict[str, Any]) -> pd.DataFrame:
    """Cruces: USD×Bs, EUR×VES, USDT×VES (P2P), más referencias."""
    bcv = _nf(t.get("bcv_bs_por_usd")) or _nf(t.get("tasa_bs"))
    par = _nf(t.get("paralelo_bs_por_usd")) or _nf(t.get("tasa_bs"))
    t_bs_oper = _nf(t.get("tasa_bs"))
    usd_eur = _nf(t.get("usd_por_eur"))
    p2p = _nf(t.get("p2p_bs_por_usdt"))
    tusdt = _nf(t.get("tasa_usdt"))
    p2p_usd = _p2p_bs_equiv_por_usd(t)

    eur_x_ves_par = (par * usd_eur) if (par is not None and usd_eur is not None and usd_eur > 0) else None
    eur_x_ves_bcv = (bcv * usd_eur) if (bcv is not None and usd_eur is not None and usd_eur > 0) else None

    rows: list[dict[str, Any]] = []

    def add_row(nombre: str, valor: float | None, unidad: str, vs_bcv: float | None = None) -> None:
        rows.append(
            {
                "Cruce": nombre,
                "Valor": float(valor) if valor is not None else None,
                "Unidad": unidad,
                "vs BCV (%)": float(vs_bcv) if vs_bcv is not None else None,
            }
        )

    if bcv is not None:
        add_row(
            "USD × Bs — oficial BCV",
            bcv,
            "Bolívares por 1 USD — Banco Central de Venezuela (no es paralelo)",
            None,
        )
    if par is not None:
        add_row(
            "USD × Bs — Binance P2P / mercado (ref.)",
            par,
            "Bolívares por 1 USD — referencia que cargás desde mercado (p. ej. alineada a Binance P2P); no es BCV",
            _pct_vs_bcv(par, bcv),
        )
    if t_bs_oper is not None:
        add_row(
            "USD × Bs — operativa (facturación)",
            t_bs_oper,
            "Valor guardado como `tasa_bs` (elegiste BCV o mercado al guardar)",
            _pct_vs_bcv(t_bs_oper, bcv),
        )
    if eur_x_ves_bcv is not None:
        add_row(
            "EUR × VES — referencia BCV",
            eur_x_ves_bcv,
            "Bs por 1 EUR si usaras solo BCV × (USD por 1 EUR)",
            None,
        )
    if eur_x_ves_par is not None and usd_eur is not None:
        pv_ev = (
            _pct_vs_bcv(eur_x_ves_par, eur_x_ves_bcv)
            if (eur_x_ves_bcv is not None and eur_x_ves_bcv > 0)
            else None
        )
        add_row(
            "EUR × VES — vía ref. mercado (P2P)",
            eur_x_ves_par,
            f"Bs por 1 EUR = (USD×Bs ref. mercado) × ({float(usd_eur):.6f} USD por 1 EUR)",
            pv_ev,
        )
    if p2p is not None:
        add_row(
            "USDT × VES (P2P)",
            p2p,
            "Bolívares por 1 USDT — mercado P2P / cripto",
            _pct_vs_bcv(p2p, bcv),
        )
    if p2p_usd is not None:
        add_row(
            "USD × Bs — vía USDT (equiv.)",
            p2p_usd,
            "(USDT×VES P2P) × (USDT por 1 USD del sistema)",
            _pct_vs_bcv(p2p_usd, bcv),
        )
    if tusdt is not None:
        add_row("Ref. USDT por 1 USD", tusdt, "Para pasar USD↔USDT en pantallas", None)
    if usd_eur is not None and usd_eur > 0:
        add_row("Ref. USD por 1 EUR", usd_eur, "1 EUR = X USD (dato para armar EUR×VES)", None)

    return pd.DataFrame(rows)


def _infer_tasa_bs_oper_index(lt: dict[str, Any]) -> int:
    """0 = operar con BCV; 1 = operar con ref. mercado P2P (campo 2) — según último `tasa_bs` guardado."""
    if not lt:
        return 0
    tb = _nf(lt.get("tasa_bs"))
    b0 = _nf(lt.get("bcv_bs_por_usd")) or tb
    p0 = _nf(lt.get("paralelo_bs_por_usd")) or tb
    if tb is None or b0 is None or p0 is None:
        return 0
    d_b = abs(float(tb) - float(b0))
    d_p = abs(float(tb) - float(p0))
    return 0 if d_b <= d_p else 1


DOC_TASA_BS_OPTS = ("BCV oficial", "P2P Binance (mercado)")


def _monto_nativo_a_usd(mon: str, monto: float, t_bs: float, t_usdt: float) -> float:
    """Convierte monto cobrado en VES / USD / USDT a equivalente USD (tasas de la venta)."""
    u = (mon or "").strip().upper()
    if u == "USD":
        return float(monto)
    if u == "USDT":
        return float(monto) / float(t_usdt) if t_usdt else 0.0
    if u in ("VES", "BS"):
        return float(monto) / float(t_bs) if t_bs else 0.0
    return 0.0


def _tasa_bs_para_documento(t: dict[str, Any], *, usar_bcv: bool) -> float:
    """Bs por 1 USD para esta venta/compra: BCV o ref. mercado (campo P2P). Los montos USD van 1:1."""
    tb = _nf(t.get("tasa_bs"))
    bcv = _nf(t.get("bcv_bs_por_usd")) or tb
    par = _nf(t.get("paralelo_bs_por_usd")) or tb
    if usar_bcv:
        v = bcv if bcv is not None and float(bcv) > 0 else tb
    else:
        v = par if par is not None and float(par) > 0 else tb
    if v is None or float(v) <= 0:
        raise ValueError("Sin tasa Bs/USD válida; cargá tasas en el Dashboard.")
    return float(v)


def render_tabla_tasas_ui(df: pd.DataFrame) -> None:
    if df.empty:
        st.caption("No hay filas para mostrar.")
        return
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cruce": st.column_config.TextColumn("Cruce", width="large"),
            "Valor": st.column_config.NumberColumn("Valor", format="%.6f"),
            "Unidad": st.column_config.TextColumn("Unidad / nota", width="large"),
            "vs BCV (%)": st.column_config.NumberColumn(
                "vs BCV (%)",
                format="%.2f",
                help="Sobre Bs/USD o cruces derivados comparables con el BCV guardado.",
            ),
        },
    )


@st.cache_data(ttl=120, show_spinner="Consultando tasas en internet…")
def get_live_exchange_rates() -> dict[str, Any]:
    from tasas_live import fetch_live_rates

    return fetch_live_rates()


def render_sidebar_welcome(*, nombre: str, username: str, rol: str) -> None:
    safe_n = html.escape(str(nombre or username or "Usuario"))
    safe_u = html.escape(str(username or ""))
    safe_r = html.escape(str(rol or ""))
    line_user = safe_n if safe_n else safe_u
    st.markdown(
        f"""
<div class="sb-welcome">
  <div class="sb-welcome-title">Movi Motor's Importadora</div>
  <div class="sb-welcome-sub">ERP · Multimoneda</div>
  <div class="sb-welcome-user">{line_user} · <span class="sb-role">{safe_r}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_sidebar_cotizaciones(t: dict[str, Any] | None) -> None:
    """
    Referencia web (caché ~2 min) + operativo en BD, en bloques visuales claros.
    """
    st.markdown('<p class="sb-block-title">Cotizaciones</p>', unsafe_allow_html=True)

    live = get_live_exchange_rates()
    ves = live.get("ves_bs_por_usd")
    p2p = live.get("usdt_x_ves_p2p") or live.get("p2p_bs_por_usdt_aprox")
    ut_ref = _nf(live.get("usdt_por_usd")) or 1.0
    t_bs_bd = _nf(t.get("tasa_bs")) if t else None

    with st.expander("Mercado en vivo (internet)", expanded=True):
        st.caption("Referencia pública · se renueva solo ~cada 2 min")
        if st.button(
            "Actualizar cotización web",
            key="sidebar_refresh_live_rates",
            use_container_width=True,
            help="Ignora la caché y vuelve a pedir datos a las APIs",
        ):
            get_live_exchange_rates.clear()
            st.rerun()

        if live.get("ok") and ves is not None:
            fv = float(ves)
            delta_vs = None
            if t_bs_bd is not None and t_bs_bd > 0:
                delta_vs = fv - float(t_bs_bd)
            st.metric(
                "Bs por 1 USD (web)",
                f"{fv:,.2f}",
                delta=f"{delta_vs:+,.2f} vs facturación" if delta_vs is not None else None,
                delta_color="off",
            )
            st.metric("USDT por 1 USD (ref.)", f"{float(ut_ref):,.4f}", delta_color="off")
        else:
            st.info("Sin datos web por ahora. Revisa la conexión.")
            for err in (live.get("errors") or [])[:2]:
                st.caption(html.escape(str(err)[:140]))

    with st.expander("USDT ↔ bolívares (P2P)", expanded=True):
        if live.get("ok") and p2p is not None:
            src = live.get("usdt_x_ves_p2p_source")
            p2p_lbl = "Binance P2P" if src == "binance_p2p_median_buy" else "API referencia"
            st.caption(f"Fuente: **{p2p_lbl}**")
            st.metric("Bs por 1 USDT", f"{float(p2p):,.4f}", delta_color="off")
        else:
            st.caption("Sin P2P hasta que carguen datos web.")

    with st.expander("Facturación · última cotización web", expanded=True):
        st.caption(
            "La **web** muestra **mercado** (ref. Bs/USD y P2P; no BCV oficial). Ventas/compras usan **`tasa_bs` en BD** "
            "(BCV o ref. P2P/mercado, según elegiste al guardar) hasta que actualices tasas o corra el **auto-sync**."
        )
        if live.get("ok") and ves is not None:
            st.metric(
                "Bs por 1 USD (última web)",
                f"{float(ves):,.2f}",
                delta_color="off",
            )
            st.metric(
                "USDT por 1 USD (última web)",
                f"{float(ut_ref):,.6f}",
                delta_color="off",
            )
        else:
            st.warning("Sin cotización web ahora. Revisa conexión o **Mercado en vivo**.")

        st.divider()
        st.caption("**En documentos hoy** (Supabase · `tasa_bs` / `tasa_usdt`)")
        if t:
            tb = float(t["tasa_bs"])
            delta_bd = None
            if live.get("ok") and ves is not None:
                delta_bd = f"{tb - float(ves):+,.2f} vs última web"
            st.metric(
                "Bs por 1 USD (guardado)",
                f"{tb:,.2f}",
                delta=delta_bd,
                delta_color="off",
            )
            st.metric(
                "USDT por 1 USD (guardado)",
                f"{float(t['tasa_usdt']):,.6f}",
                delta_color="off",
            )
        else:
            st.info("No hay tasas en base de datos. En **Dashboard** abre *Cargar / editar tasas en base de datos*.")


def render_tasas_tiempo_real(*, key_suffix: str, t_guardado: dict[str, Any] | None) -> dict[str, Any]:
    """Muestra tasas públicas en vivo (caché ~2 min) y opción de forzar refresco."""
    st.markdown("##### Tasas en tiempo real (internet)")
    st.caption(
        "Cruces: **USD×Bs**, **EUR×VES**, **USDT×VES (Binance P2P)**. Caché **~2 min**; usa **Refrescar ahora** para forzar. "
        "El **USD×Bs** web **no** es BCV oficial. **EUR×VES** = (Bs/USD web) × (USD por 1 EUR, Frankfurter). "
        "**USDT×VES** = mediana de anuncios en **Binance P2P** (VES/USDT); si Binance falla, se usa el mismo Bs/USD de la API de mercado como respaldo."
    )
    _, br = st.columns([3, 1])
    with br:
        if st.button("Refrescar ahora", key=f"live_refresh_{key_suffix}", help="Ignora la caché y vuelve a pedir datos"):
            get_live_exchange_rates.clear()
            st.rerun()

    data = get_live_exchange_rates()
    for err in data.get("errors") or []:
        st.warning(str(err))

    if not data.get("ok"):
        st.info("No se obtuvieron tasas web. Comprueba tu conexión o inténtalo más tarde.")
        return data

    bcv_ref = None
    if t_guardado:
        bcv_ref = _nf(t_guardado.get("bcv_bs_por_usd")) or _nf(t_guardado.get("tasa_bs"))

    rows: list[dict[str, Any]] = []
    ves = data.get("ves_bs_por_usd")
    eur_ves = data.get("eur_x_ves")
    p2p = data.get("usdt_x_ves_p2p") or data.get("p2p_bs_por_usdt_aprox")
    p2p_src = data.get("usdt_x_ves_p2p_source")
    eur = data.get("usd_por_eur")
    ut = data.get("usdt_por_usd")

    if ves is not None:
        pv = _pct_vs_bcv(float(ves), bcv_ref)
        rows.append(
            {
                "Cruce": "USD × Bs (web)",
                "Valor": float(ves),
                "Unidad": "Bs por 1 USD — ref. mercado web (no BCV); contrastá con tu precio en Binance P2P",
                "vs BCV guardado (%)": float(pv) if pv is not None else None,
            }
        )
    if eur_ves is not None:
        bcv_eur = None
        if t_guardado and eur:
            b0 = _nf(t_guardado.get("bcv_bs_por_usd")) or _nf(t_guardado.get("tasa_bs"))
            if b0 is not None and eur:
                bcv_eur = float(b0) * float(eur)
        pv_e = _pct_vs_bcv(float(eur_ves), bcv_eur) if bcv_eur else None
        rows.append(
            {
                "Cruce": "EUR × VES (web)",
                "Valor": float(eur_ves),
                "Unidad": f"Bs por 1 EUR = (USD×Bs web) × ({float(eur):.6f} USD por 1 EUR)" if eur else "Bs por 1 EUR",
                "vs BCV guardado (%)": float(pv_e) if pv_e is not None else None,
            }
        )
    if p2p is not None:
        pv2 = _pct_vs_bcv(float(p2p), bcv_ref)
        if p2p_src == "binance_p2p_median_buy":
            p2p_label = "USDT × VES (Binance P2P)"
            p2p_unit = "Bs por 1 USDT — mediana hasta 20 anuncios (comprar USDT con VES en Binance)"
        else:
            p2p_label = "USDT × VES (respaldo API)"
            p2p_unit = "Bs por 1 USDT — respaldo: mismo valor que USD×Bs web (Binance no respondió)"
        rows.append(
            {
                "Cruce": p2p_label,
                "Valor": float(p2p),
                "Unidad": p2p_unit,
                "vs BCV guardado (%)": float(pv2) if pv2 is not None else None,
            }
        )
    if eur is not None and eur_ves is None:
        rows.append(
            {
                "Cruce": "Ref. USD por 1 EUR (web)",
                "Valor": float(eur),
                "Unidad": "Dato para calcular EUR×VES cuando cargue USD×Bs",
                "vs BCV guardado (%)": None,
            }
        )
    if ut is not None:
        rows.append(
            {
                "Cruce": "Ref. USDT por 1 USD",
                "Valor": float(ut),
                "Unidad": "Solo referencia en la app al guardar tasas",
                "vs BCV guardado (%)": None,
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cruce": st.column_config.TextColumn("Cruce", width="large"),
            "Valor": st.column_config.NumberColumn("Valor", format="%.6f"),
            "Unidad": st.column_config.TextColumn("Unidad / nota", width="large"),
            "vs BCV guardado (%)": st.column_config.NumberColumn(
                "vs tu BCV en BD (%)",
                format="%.2f",
                help="Compara con el BCV guardado en Supabase (cuando aplica).",
            ),
        },
    )
    meta = " · ".join(data.get("sources") or [])
    if data.get("time_next_update_utc"):
        meta += f" · Próx. actualización (API VES): {data['time_next_update_utc']}"
    st.caption(meta)
    return data


def _plotly_apply_dash_theme(fig: Any, *, title: str | None = None) -> Any:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(22,27,34,0.55)",
        font=dict(color="#c9d1d9", family="system-ui, sans-serif"),
        margin=dict(t=56, b=48, l=24, r=24),
        hovermode="x unified",
        title=dict(text=title, font=dict(size=15, color="#00e5ff")) if title else None,
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False)
    return fig


def _dash_liquidity_bucket(*, tipo: str, nombre: str) -> str:
    n = (nombre or "").lower()
    if "binance" in n or "usdt" in n or "crypto" in n:
        return "Binance (crypto)"
    t = (tipo or "").strip()
    if t == "Efectivo":
        return "Caja fuerte"
    if t == "Banco":
        return "Bancos nacionales"
    if t == "Wallet":
        return "Binance (crypto)"
    return "Otros"


def _dash_trend_pct(curr: float, prev: float) -> float | None:
    if prev > 1e-9:
        return (curr - prev) / prev * 100.0
    if curr > 1e-9:
        return 100.0
    return None


def _dash_kpi_card(label: str, value: str, trend_pct: float | None = None, sub: str | None = None) -> None:
    if trend_pct is None:
        tr = '<span class="dash-kpi-trend-flat">— vs período anterior</span>'
    elif trend_pct > 0.05:
        tr = f'<span class="dash-kpi-trend-up">▲ {trend_pct:+.1f}%</span>'
    elif trend_pct < -0.05:
        tr = f'<span class="dash-kpi-trend-down">▼ {trend_pct:+.1f}%</span>'
    else:
        tr = '<span class="dash-kpi-trend-flat">≈ estable</span>'
    sub_html = f'<div class="dash-kpi-sub">{html.escape(sub)}</div>' if sub else ""
    st.markdown(
        f"""
<div class="dash-bento">
  <div class="dash-kpi-label">{html.escape(label)}</div>
  <div class="dash-kpi-value">{value}</div>
  <div class="dash-kpi-sub">{tr}</div>
  {sub_html}
</div>
""",
        unsafe_allow_html=True,
    )


def _dash_semaforo(*, stock: float, minimo: float, vendido_periodo: float) -> str:
    """Rojo / amarillo / verde para priorizar liquidación o reposición."""
    if stock <= minimo:
        return "🔴 Bajo mínimo"
    if stock <= minimo * 1.25:
        return "🟡 Cerca del mínimo"
    if vendido_periodo < 0.001 and stock > minimo:
        return "🟡 Baja rotación"
    return "🟢 OK"


def _dashboard_resumen_cobros_por_moneda(sb: Client, *, d_a: date, r_fut: str) -> None:
    """Ingresos a caja en el período: totales VES / USD / USDT y detalle por cuenta."""
    dsl = d_a.isoformat()
    try:
        mh = (
            sb.table("movimientos_caja")
            .select("caja_id, monto_usd, moneda, monto_moneda, concepto, created_at")
            .eq("tipo", "Ingreso")
            .gte("created_at", dsl)
            .lte("created_at", r_fut)
            .execute()
        )
    except Exception:
        st.caption(
            "Para ver cobros en **Bs / USD / USDT** por caja, ejecutá en Supabase "
            "`supabase/patch_008_movimientos_moneda_cobros.sql`."
        )
        return

    rows = mh.data or []
    if not rows:
        st.caption("Sin ingresos de caja en el período.")
        return

    caj_map = {
        str(c["id"]): f"{c.get('nombre', '')} ({c.get('tipo', '')})"
        for c in (sb.table("cajas_bancos").select("id,nombre,tipo").execute().data or [])
    }

    recs: list[dict[str, Any]] = []
    tot_ves = tot_usdt = tot_usd_cash = 0.0
    sum_equiv_usd = 0.0
    for r in rows:
        mon = (r.get("moneda") or "USD").strip().upper()
        mm = r.get("monto_moneda")
        mu = float(r.get("monto_usd") or 0)
        sum_equiv_usd += mu
        native = float(mm) if mm is not None else mu
        if mon == "VES":
            tot_ves += native
        elif mon == "USDT":
            tot_usdt += native
        else:
            tot_usd_cash += native
        recs.append(
            {
                "Fecha": str(r.get("created_at", ""))[:19],
                "Caja": caj_map.get(str(r.get("caja_id")), str(r.get("caja_id"))),
                "Moneda": mon,
                "Monto moneda": native,
                "Equiv. USD": mu,
                "Concepto": (r.get("concepto") or "")[:80],
            }
        )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Cobrado VES (Bs)", f"{tot_ves:,.2f}")
    with m2:
        st.metric("Cobrado USDT", f"{tot_usdt:,.4f}")
    with m3:
        st.metric("Cobrado USD", f"US$ {tot_usd_cash:,.2f}")
    with m4:
        st.metric("Ingresos (equiv. USD)", f"US$ {sum_equiv_usd:,.2f}")

    st.caption(
        "Equiv. USD es lo que suma al **saldo de cada caja** (VES y USDT convertidos con la tasa de la venta / cobro)."
    )
    st.dataframe(
        pd.DataFrame(recs).sort_values("Fecha", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Monto moneda": st.column_config.NumberColumn(format="%.4f"),
            "Equiv. USD": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def module_dashboard(sb: Client, t: dict[str, Any] | None) -> None:
    """Panel ejecutivo estilo Bento (dark + acentos cian/naranja). Streamlit + Plotly."""
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
        q_search = st.text_input("Buscar", placeholder="Producto, código…", key="dash_global_search", label_visibility="visible")
        live = get_live_exchange_rates()
        p2p = live.get("usdt_x_ves_p2p") or live.get("p2p_bs_por_usdt_aprox")
        ves = live.get("ves_bs_por_usd")
        if live.get("ok") and p2p is not None and ves is not None:
            src = "Binance P2P" if live.get("usdt_x_ves_p2p_source") == "binance_p2p_median_buy" else "Ref."
            st.markdown(
                f'<div class="dash-live-chip">USDT/VES · {float(p2p):,.2f} Bs <small>({html.escape(src)})</small><br/>'
                f"USD/VES web · {float(ves):,.2f}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="dash-live-chip">Tipo cambio web: sin datos</div>', unsafe_allow_html=True)

    if d_b < d_a:
        st.error("La fecha *Hasta* debe ser ≥ *Desde*.")
        st.stop()

    n_days = max(1, (d_b - d_a).days + 1)
    d_prev_b = d_a - timedelta(days=1)
    d_prev_a = d_prev_b - timedelta(days=n_days - 1)

    r_fut = f"{d_b.isoformat()}T23:59:59"

    # --- KPIs datos ---
    v_cur = (
        sb.table("ventas")
        .select("id, total_usd, fecha")
        .gte("fecha", str(d_a))
        .lte("fecha", r_fut)
        .execute()
    )
    v_prev = (
        sb.table("ventas")
        .select("total_usd")
        .gte("fecha", str(d_prev_a))
        .lte("fecha", f"{d_prev_b.isoformat()}T23:59:59")
        .execute()
    )
    df_vc = pd.DataFrame(v_cur.data or [])
    ventas_usd = float(pd.to_numeric(df_vc["total_usd"], errors="coerce").fillna(0).sum()) if not df_vc.empty else 0.0
    ventas_prev = float(
        pd.to_numeric(pd.DataFrame(v_prev.data or [])["total_usd"], errors="coerce").fillna(0).sum()
    ) if (v_prev.data or []) else 0.0

    vids = [str(x["id"]) for x in (v_cur.data or [])]
    margen_usd = 0.0
    if vids:
        det = (
            sb.table("ventas_detalles")
            .select("producto_id, cantidad, precio_unitario_usd")
            .in_("venta_id", vids)
            .execute()
        )
        det_rows = det.data or []
        pmap = {
            str(p["id"]): p
            for p in (sb.table("productos").select("id, costo_usd").execute().data or [])
        }
        for row in det_rows:
            pid = str(row["producto_id"])
            costo = float(pmap.get(pid, {}).get("costo_usd") or 0)
            cant = float(row["cantidad"])
            pu = float(row["precio_unitario_usd"])
            margen_usd += (pu - costo) * cant

    vids_prev = [
        str(x["id"])
        for x in (
            sb.table("ventas")
            .select("id")
            .gte("fecha", str(d_prev_a))
            .lte("fecha", f"{d_prev_b.isoformat()}T23:59:59")
            .execute()
            .data
            or []
        )
    ]
    margen_prev = 0.0
    if vids_prev:
        detp = (
            sb.table("ventas_detalles")
            .select("producto_id, cantidad, precio_unitario_usd")
            .in_("venta_id", vids_prev)
            .execute()
        )
        pmap2 = {
            str(p["id"]): p
            for p in (sb.table("productos").select("id, costo_usd").execute().data or [])
        }
        for row in detp.data or []:
            pid = str(row["producto_id"])
            costo = float(pmap2.get(pid, {}).get("costo_usd") or 0)
            cant = float(row["cantidad"])
            pu = float(row["precio_unitario_usd"])
            margen_prev += (pu - costo) * cant

    prods = sb.table("productos").select("stock_actual, activo").eq("activo", True).execute()
    unidades_stock = float(
        sum(float(p.get("stock_actual") or 0) for p in (prods.data or []))
    )
    n_sku = len(prods.data or [])

    try:
        bal = sb.table("v_balance_consolidado_usd").select("total_usd").execute()
        liquidez = float((bal.data or [{}])[0].get("total_usd") or 0)
    except Exception:
        liquidez = 0.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _dash_kpi_card(
            "Ventas totales (USD)",
            f"US$ {ventas_usd:,.2f}",
            _dash_trend_pct(ventas_usd, ventas_prev),
            f"Período {d_a} → {d_b}",
        )
    with k2:
        _dash_kpi_card(
            "Margen bruto (USD)",
            f"US$ {margen_usd:,.2f}",
            _dash_trend_pct(margen_usd, margen_prev),
            "Sobre costo de productos vendidos",
        )
    with k3:
        _dash_kpi_card(
            "Unidades en stock",
            f"{unidades_stock:,.0f}",
            None,
            f"{n_sku} SKU activos",
        )
    with k4:
        _dash_kpi_card(
            "Liquidez total",
            f"US$ {liquidez:,.2f}",
            None,
            "Saldos en cajas / bancos / wallets",
        )

    row2a, row2b = st.columns([1.15, 1])
    with row2a:
        st.markdown('<div class="dash-bento">', unsafe_allow_html=True)
        st.markdown("**Origen de la liquidez** (USD por tipo de caja)")
        caj_df = pd.DataFrame(sb.table("cajas_bancos").select("nombre, tipo, saldo_actual_usd").eq("activo", True).execute().data or [])
        if caj_df.empty:
            st.caption("No hay cajas activas.")
        else:
            caj_df["origen"] = caj_df.apply(
                lambda r: _dash_liquidity_bucket(tipo=str(r.get("tipo", "")), nombre=str(r.get("nombre", ""))),
                axis=1,
            )
            caj_df["saldo_actual_usd"] = pd.to_numeric(caj_df["saldo_actual_usd"], errors="coerce").fillna(0)
            agg_l = caj_df.groupby("origen", as_index=False)["saldo_actual_usd"].sum()
            order = ["Caja fuerte", "Bancos nacionales", "Binance (crypto)", "Otros"]
            agg_l["origen"] = pd.Categorical(agg_l["origen"], categories=order, ordered=True)
            agg_l = agg_l.sort_values("origen")
            agg_l = agg_l[agg_l["saldo_actual_usd"] > 0]
            if agg_l.empty:
                st.caption("Saldos en cero en todas las cajas.")
            else:
                colors = ["#00e5ff", "#ff9100", "#b388ff", "#78909c"]
                fig_liq = go.Figure()
                for idx, (_, row) in enumerate(agg_l.iterrows()):
                    fig_liq.add_trace(
                        go.Bar(
                            name=str(row["origen"]),
                            x=["Liquidez"],
                            y=[float(row["saldo_actual_usd"])],
                            marker_color=colors[idx % len(colors)],
                            text=[f"{float(row['saldo_actual_usd']):,.2f}"],
                            textposition="inside",
                            hovertemplate="%{fullData.name}: %{y:,.2f} USD<extra></extra>",
                        )
                    )
                fig_liq.update_layout(
                    barmode="stack",
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="top", y=-0.2, x=0),
                )
                _plotly_apply_dash_theme(fig_liq, title="Composición por origen")
                fig_liq.update_layout(hoverlabel=dict(bgcolor="#1a1f2e", font_size=12))
                st.plotly_chart(fig_liq, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with row2b:
        st.markdown('<div class="dash-bento">', unsafe_allow_html=True)
        st.markdown("**Compras por categoría** (USD en el período · proxy de gasto / abastecimiento)")
        cids = [
            str(x["id"])
            for x in (
                sb.table("compras")
                .select("id")
                .gte("fecha", str(d_a))
                .lte("fecha", r_fut)
                .execute()
                .data
                or []
            )
        ]
        if not cids:
            st.caption("Sin compras en el rango.")
        else:
            cdet = sb.table("compras_detalles").select("producto_id, subtotal_usd").in_("compra_id", cids).execute()
            cdf = pd.DataFrame(cdet.data or [])
            if cdf.empty:
                st.caption("Sin líneas de compra.")
            else:
                plist = sb.table("productos").select("id, categoria_id, categorias(nombre)").execute().data or []
                id_cat: dict[str, str] = {}
                for p in plist:
                    cid = str(p["id"])
                    cat = p.get("categorias")
                    if isinstance(cat, list) and cat:
                        cat = cat[0]
                    if isinstance(cat, dict) and cat.get("nombre"):
                        id_cat[cid] = str(cat["nombre"])
                    else:
                        id_cat[cid] = "Sin categoría"
                cdf["categoria"] = cdf["producto_id"].astype(str).map(lambda x: id_cat.get(x, "Sin categoría"))
                cdf["subtotal_usd"] = pd.to_numeric(cdf["subtotal_usd"], errors="coerce").fillna(0)
                gcat = cdf.groupby("categoria", as_index=False)["subtotal_usd"].sum()
                fig_d = px.pie(
                    gcat,
                    names="categoria",
                    values="subtotal_usd",
                    hole=0.52,
                    color_discrete_sequence=px.colors.sequential.Teal_r,
                )
                fig_d.update_traces(textposition="inside", textinfo="percent+label", hovertemplate="%{label}<br>%{value:,.2f} USD<extra></extra>")
                _plotly_apply_dash_theme(fig_d, title="Distribución (donut)")
                st.plotly_chart(fig_d, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    pinv = (
        sb.table("productos")
        .select("id, codigo, descripcion, stock_actual, stock_minimo, costo_usd, precio_v_usd, categorias(nombre)")
        .eq("activo", True)
        .execute()
        .data
        or []
    )

    row3a, row3b = st.columns([1.2, 1])
    with row3a:
        st.markdown('<div class="dash-bento">', unsafe_allow_html=True)
        st.markdown("**Productos con baja rotación** · semáforo de inventario")
        st.caption("🟢 OK · 🟡 revisar · 🔴 bajo mínimo")
        ventas_qty: dict[str, float] = {}
        if vids:
            dq = (
                sb.table("ventas_detalles")
                .select("producto_id, cantidad")
                .in_("venta_id", vids)
                .execute()
                .data
                or []
            )
            for r in dq:
                pid = str(r["producto_id"])
                ventas_qty[pid] = ventas_qty.get(pid, 0) + float(r.get("cantidad") or 0)
        rows_inv: list[dict[str, Any]] = []
        for p in pinv:
            pid = str(p["id"])
            st_a = float(p.get("stock_actual") or 0)
            st_m = float(p.get("stock_minimo") or 0)
            if st_a <= 0:
                continue
            vq = ventas_qty.get(pid, 0.0)
            cat = p.get("categorias")
            if isinstance(cat, list) and cat:
                cat = cat[0]
            cat_n = cat.get("nombre") if isinstance(cat, dict) else "—"
            rows_inv.append(
                {
                    "Semáforo": _dash_semaforo(stock=st_a, minimo=st_m, vendido_periodo=vq),
                    "Producto": str(p.get("descripcion", ""))[:80],
                    "Código": str(p.get("codigo") or "—"),
                    "Categoría": str(cat_n or "—")[:40],
                    "Stock": st_a,
                    "Mín.": st_m,
                    "Vendido (período)": vq,
                    "Valor inv. USD": round(st_a * float(p.get("costo_usd") or 0), 2),
                }
            )
        dfi = pd.DataFrame(rows_inv)
        if dfi.empty:
            st.info("No hay stock positivo para analizar.")
        else:

            def _sem_prio(s: str) -> int:
                if str(s).startswith("🔴"):
                    return 0
                if str(s).startswith("🟡"):
                    return 1
                return 2

            dfi["_prio"] = dfi["Semáforo"].map(_sem_prio)
            dfi = dfi.sort_values(["_prio", "Valor inv. USD"], ascending=[True, False]).drop(columns=["_prio"])
            if q_search and q_search.strip():
                qs = q_search.strip().lower()
                mask = dfi["Producto"].str.lower().str.contains(qs, na=False) | dfi["Código"].str.lower().str.contains(
                    qs, na=False
                )
                dfi = dfi[mask]
            st.dataframe(dfi, use_container_width=True, hide_index=True)
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
                _plotly_apply_dash_theme(fig_iv, title="Inventario por categoría")
                st.plotly_chart(fig_iv, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

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
        fig_ie = px.bar(
            merged_ie,
            x="dia",
            y=["Ingreso", "Egreso"],
            barmode="group",
            labels={"value": "USD", "dia": "Día", "variable": ""},
        )
        fig_ie.update_traces(marker_line_width=0)
        _plotly_apply_dash_theme(fig_ie, title="Ingresos y egresos por día")
        st.plotly_chart(fig_ie, use_container_width=True)

    st.markdown("##### Resumen: qué entró en Bs, USD y USDT (y en qué cuenta)")
    _dashboard_resumen_cobros_por_moneda(sb, d_a=d_a, r_fut=r_fut)

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
        fig_vc = px.line(
            out_vc,
            x="dia",
            y=["Ventas USD", "Compras USD"],
            markers=True,
            labels={"value": "USD", "dia": "Día"},
        )
        fig_vc.update_traces(line=dict(width=2))
        _plotly_apply_dash_theme(fig_vc, title="Ventas vs compras (USD)")
        st.plotly_chart(fig_vc, use_container_width=True)

    with st.expander("Tasas en vivo y tabla guardada (BCV · ref. mercado / P2P Binance)", expanded=False):
        render_tasas_tiempo_real(key_suffix="dash", t_guardado=t)
        if t:
            st.caption(f"Registro tasas **{t.get('fecha', '—')}**")
            render_tabla_tasas_ui(build_tasas_tabla_detalle(t))
        else:
            st.warning("Sin tasas del día en base de datos.")

    rol_dash = str(st.session_state.get("erp_rol", ""))
    if role_can(rol_dash, "tasas"):
        with st.expander("Cargar / editar tasas (BCV, ref. P2P Binance Bs/USD, USDT P2P)", expanded=False):
            module_tasas(sb, embedded=True)

    st.divider()
    st.markdown("##### Últimos movimientos de caja")
    mov = (
        sb.table("movimientos_caja")
        .select("created_at, tipo, monto_usd, concepto")
        .order("created_at", desc=True)
        .limit(15)
        .execute()
    )
    if mov.data:
        st.dataframe(pd.DataFrame(mov.data), use_container_width=True, hide_index=True)
    else:
        st.caption("Sin movimientos.")


def module_tasas(sb: Client, *, embedded: bool = False) -> None:
    """
    Guarda tasas en `tasas_dia`. Si `embedded=True`, no muestra el panel duplicado de tiempo real
    (se usa desde el Dashboard, donde ya existe el expander de tasas en vivo).
    """
    if not embedded:
        st.subheader("Tasas del día")
        st.caption(
            "Guardás **BCV oficial** (referencia legal), **ref. Bs/USD mercado** (la que usás desde **Binance P2P** u otra fuente, campo 2), "
            "**EUR** (vía *USD por 1 EUR*), **USDT×VES (P2P Binance)** y **USDT por USD**. "
            "En **Operativo** elegís si ventas/compras usan **BCV** o **esa ref. P2P/mercado** para `tasa_bs`. "
            "**Auto-sync web:** actualiza la ref. mercado Bs/USD; **no cambia el BCV** que cargaste; "
            "`tasa_bs` sigue en BCV si venías operando con BCV."
            f" Dispara si esa ref. web se mueve ≥ **{AUTO_TASA_ABS_MIN_BS}** Bs/USD"
            + (f" o **≥{AUTO_TASA_SYNC_REL_MIN*100:.1f} %**" if AUTO_TASA_SYNC_REL_MIN > 0 else "")
            + "."
        )
        st.info(
            "Si al guardar ves error de columna inexistente, ejecuta en Supabase el archivo "
            "`supabase/patch_005_tasas_dashboard.sql`."
        )
    else:
        st.caption(
            f"Elegís **BCV** o **ref. P2P/mercado (campo 2)** para `tasa_bs`. Auto-sync (~cada {int(AUTO_TASA_SYNC_MIN_SECONDS)}s, "
            f"≥{AUTO_TASA_ABS_MIN_BS} Bs/USD) actualiza esa ref.; **no pisa BCV**; respeta si operabas con BCV."
        )

    lt = latest_tasas(sb) or {}
    _applied_live = st.session_state.pop("_live_apply", None)

    def dv(key: str, fallback: float) -> float:
        v = _nf(lt.get(key))
        return float(v) if v is not None else float(fallback)

    if not embedded:
        render_tasas_tiempo_real(key_suffix="tasas_mod", t_guardado=lt or None)
        if st.button(
            "Aplicar tasas web al formulario (ref. Bs/USD, EUR, P2P y USDT)",
            key="apply_live_to_form",
            help="Rellena **ref. Bs/USD mercado** (campo 2) y P2P Binance donde aplique. El **BCV oficial** lo cargás vos a mano.",
        ):
            snap = get_live_exchange_rates()
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
            snap = get_live_exchange_rates()
            if snap.get("ok"):
                st.session_state["_live_apply"] = snap
                st.rerun()
            else:
                st.warning("No hay datos web listos. Usa **Actualizar cotización web** en la barra lateral.")

    if lt:
        with st.expander("Ver tasas guardadas en BD (detalle)", expanded=False):
            st.caption(f"Último registro — fecha **{lt.get('fecha', '—')}**.")
            render_tabla_tasas_ui(build_tasas_tabla_detalle(lt))
    else:
        st.warning("Aún no hay tasas en base de datos. Completa el formulario y guarda.")

    if embedded:
        st.info(
            "¿Error de columna al guardar? Ejecuta en Supabase `supabase/patch_005_tasas_dashboard.sql`."
        )

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

    _form_id = "f_tasa_embed" if embedded else "f_tasa"
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
            index=_infer_tasa_bs_oper_index(lt),
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
                    st.success("Tasas guardadas." + _refresh_productos_bs_equiv_note(sb, float(t_oper)))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    r = sb.table("tasas_dia").select("*").order("fecha", desc=True).limit(30).execute()
    if r.data:
        st.dataframe(pd.DataFrame(r.data), use_container_width=True, hide_index=True)


def module_inventario(sb: Client, erp_uid: str, t: dict[str, Any] | None) -> None:
    st.subheader("Inventario")
    if not t:
        st.warning("Registre tasas en **Dashboard** (expander *Cargar / editar tasas en base de datos*) para ver equivalentes.")

    try:
        cats = sb.table("categorias").select("id,nombre").order("nombre").execute()
        cats_list = cats.data or []
    except Exception as ex:
        cats_list = []
        st.error(f"No se pudieron leer **categorías** desde la base: {ex}")

    cat_opts = {c["nombre"]: c["id"] for c in cats_list if c.get("nombre")}
    _id_to_nombre_cat, _nombre_a_id_cat, _cat_select_opts = _categoria_maps_from_rows(cats_list)
    _marcas_veh_catalogo = _fetch_marcas_vehiculo_catalogo(sb)

    df = _inv_enrich_compat_columns(_normalize_productos_inventario_df(_fetch_productos_inventario_df(sb)))
    if not df.empty:
        if "categoria_id" in df.columns:
            df["categoria"] = df["categoria_id"].apply(
                lambda x: _id_to_nombre_cat.get(str(x).strip(), "")
                if x is not None and not (isinstance(x, float) and pd.isna(x)) and str(x).strip()
                else ""
            )
        else:
            df["categoria"] = ""
    else:
        df["categoria"] = pd.Series(dtype=object)

    st.caption(
        f"**{len(cats_list)}** categoría(s) en la base. "
        "Respaldo solo inventario y listados en PDF/Excel: **Mantenimiento** y **Reportes**."
    )

    st.markdown("##### Buscar y modificar productos")
    st.caption(
        "El **stock** baja con las **ventas** y sube con las **compras** (y cargas nuevas). "
        "Buscá por código, **OEM**, descripción, **marca del repuesto** o **marcas de carro**. "
        "La **tabla masiva** quedó **al final** del módulo (después de alta y CSV)."
    )
    _fc1, _fc2 = st.columns([2, 1])
    with _fc1:
        _inv_q = st.text_input(
            "Buscar (código, OEM, descripción, marca repuesto, marcas de carro…)",
            value="",
            key="inv_prod_filter",
            placeholder="Ej: filtro, 04465, Toyota, Bosch…",
        )
    with _fc2:
        _nombres_cat_ord = sorted(cat_opts.keys(), key=str.casefold)
        _opts_filtro_cat = ["Todas las categorías"] + _nombres_cat_ord + ["(Sin categoría)"]
        _sel_una_cat = st.selectbox(
            "Solo categoría",
            options=_opts_filtro_cat,
            index=0,
            key="inv_filtro_una_categoria",
            help="Filtrá por una categoría. Combinado con la búsqueda de texto.",
        )

    df_view = df
    if not df.empty:
        if _inv_q.strip():
            _q = _inv_q.strip()
            _mask = df_view.apply(lambda r: _inv_row_matches_query(r, _q), axis=1)
            df_view = df_view.loc[_mask]
        if _sel_una_cat == "(Sin categoría)":
            if "categoria_id" in df_view.columns:
                _m_sin_id = df_view["categoria_id"].isna() | (df_view["categoria_id"].astype(str).str.strip() == "")
            else:
                _m_sin_id = pd.Series(True, index=df_view.index)
            _m_sin_nom = df_view["categoria"].fillna("").astype(str).str.strip() == ""
            df_view = df_view.loc[_m_sin_id | _m_sin_nom]
        elif _sel_una_cat != "Todas las categorías":
            _cid_f = cat_opts.get(_sel_una_cat)
            if _cid_f is not None and "categoria_id" in df_view.columns:
                df_view = df_view.loc[df_view["categoria_id"].astype(str) == str(_cid_f)]
            else:
                df_view = df_view.loc[df_view["categoria"].fillna("").astype(str).str.strip() == _sel_una_cat]

    if df.empty:
        st.info(
            "No hay **productos** en la base. Más abajo podés **crear categorías y productos** o importar un **CSV**."
        )
    elif df_view.empty:
        st.info("No hay productos que coincidan con la búsqueda o la categoría elegida.")
    else:
        _sa = df["stock_actual"].map(_inv_stock_int)
        _sm = df["stock_minimo"].map(_inv_stock_int)
        crit_all = df.loc[_sa <= _sm]
        if len(crit_all):
            st.error(f"Alertas de stock crítico: {len(crit_all)} ítems")
            st.dataframe(crit_all, use_container_width=True, hide_index=True)

    if not df.empty and df_view.empty:
        crit_all = df.loc[df["stock_actual"].map(_inv_stock_int) <= df["stock_minimo"].map(_inv_stock_int)]
        if len(crit_all):
            st.error(f"Alertas de stock crítico: {len(crit_all)} ítems")
            st.dataframe(crit_all, use_container_width=True, hide_index=True)

    st.divider()
    with st.expander(
        "Productos — Editar · Nuevo (incluye categoría) · Eliminar · Carga/descarga inventario",
        expanded=True,
    ):
        _t_edit, _t_prod, _t_del, _t_mov = st.tabs(
            [
                "Editar Productos",
                "Nuevo Producto",
                "Eliminar Producto",
                "Carga /Descarga de inventario",
            ]
        )
        with _t_edit:
            st.caption(
                "Usa los mismos **filtros de búsqueda y categoría** de la sección *Buscar y modificar productos* arriba."
            )
            if df.empty:
                st.info(
                    "No hay **productos** en la base. Usá **Nuevo Producto** (y *Nueva categoría* dentro de esa pestaña) o importá un **CSV** más abajo."
                )
            elif df_view.empty:
                st.info(
                    "No hay productos que coincidan con la búsqueda o la categoría elegida. "
                    "Vacía el filtro o cambiá **Solo categoría** para ver ítems y editarlos desde acá."
                )
            else:
                _max_ficha = 200
                if len(df_view) > _max_ficha:
                    st.caption(
                        f"Hay **{len(df_view)}** productos en pantalla. Afiná la búsqueda o la categoría "
                        f"(menos de {_max_ficha}) para usar esta ficha."
                    )
                else:
                    _labels: dict[str, str] = {}
                    for _, _r in df_view.iterrows():
                        _cod = _export_cell_txt(_r.get("codigo")) or "—"
                        _desc = _export_cell_txt(_r.get("descripcion")) or "—"
                        _lid = str(_r.get("id") or "").strip()
                        if not _lid:
                            continue
                        _lab = f"{_cod} · {_desc[:48]}" + ("" if len(_desc) <= 48 else "…")
                        if _lab in _labels:
                            _lab = f"{_lab} [{_lid[:8]}]"
                        _labels[_lab] = _lid
                    _pick_labs = sorted(_labels.keys(), key=str.casefold)
                    _sel_lab = st.selectbox(
                        "Elegí el producto a editar",
                        options=["—"] + _pick_labs,
                        index=0,
                        key="inv_ficha_producto_pick",
                        help="El listado respeta búsqueda y categoría. Cambiá acá de ítem sin guardar el formulario.",
                    )
                    if _sel_lab != "—" and _sel_lab in _labels:
                        _pid = _labels[_sel_lab]
                        _row = df_view[df_view["id"].astype(str) == _pid]
                        if len(_row) != 1:
                            st.error("No se encontró el producto.")
                        else:
                            _rw = _row.iloc[0]
                            _d_comp = _inv_compat_as_dict(_rw.get("compatibilidad"))
                            _marcas_act: list[str] = []
                            for _m in _d_comp.get("marcas_vehiculo") or _d_comp.get("marcas") or []:
                                _s = str(_m).strip()
                                if _s:
                                    _marcas_act.append(_s)
                            _en_cat = [m for m in _marcas_act if m in _marcas_veh_catalogo]
                            _extras_list = [m for m in _marcas_act if m not in _marcas_veh_catalogo]
                            _extras_str = ", ".join(_extras_list)
                            _anos_ini = _inv_compat_anos_str(_d_comp)
                            _cat_nm = _export_cell_txt(_rw.get("categoria"))
                            try:
                                _cat_ix = _cat_select_opts.index(_cat_nm) if _cat_nm in _cat_select_opts else 0
                            except ValueError:
                                _cat_ix = 0
                            _cond_ini = _rw.get("condicion")
                            if _cond_ini not in ("Nuevo", "Usado"):
                                _cond_ini = "Nuevo"
                            with st.form(f"inv_ficha_prod_form_{_pid}"):
                                st.caption(f"ID interno: `{_pid}` · Los cambios reemplazan el registro en la base.")
                                fa, fb = st.columns(2)
                                _fcod = fa.text_input(
                                    "Código interno",
                                    value=_export_cell_txt(_rw.get("codigo")),
                                    key=f"inv_ficha_cod_{_pid}",
                                )
                                _fsku = fb.text_input(
                                    "OEM / código parte",
                                    value=_export_cell_txt(_rw.get("sku_oem")),
                                    key=f"inv_ficha_sku_{_pid}",
                                )
                                _fdesc = st.text_input(
                                    "Descripción",
                                    value=_export_cell_txt(_rw.get("descripcion")) or "Sin descripción",
                                    max_chars=500,
                                    key=f"inv_ficha_desc_{_pid}",
                                )
                                fm1, fm2 = st.columns(2)
                                _fmprod = fm1.text_input(
                                    "Marca del repuesto (ej. Bosch)",
                                    value=_export_cell_txt(_rw.get("marca_producto")),
                                    key=f"inv_ficha_mprod_{_pid}",
                                )
                                _fcond = fm2.selectbox(
                                    "Condición",
                                    ["Nuevo", "Usado"],
                                    index=0 if _cond_ini == "Nuevo" else 1,
                                    key=f"inv_ficha_cond_{_pid}",
                                )
                                st.markdown("**Compatibilidad (marcas de carro)**")
                                if _marcas_veh_catalogo:
                                    _fpick_mv = st.multiselect(
                                        "Del catálogo en base",
                                        options=_marcas_veh_catalogo,
                                        default=_en_cat,
                                        key=f"inv_ficha_mv_{_pid}",
                                    )
                                else:
                                    st.caption("Sin catálogo: ejecutá **patch_012** o escribí las marcas solo en texto.")
                                    _fpick_mv = []
                                fc1, fc2 = st.columns(2)
                                _fextra_mv = fc1.text_input(
                                    "Otras marcas (coma)",
                                    value=_extras_str,
                                    key=f"inv_ficha_mvx_{_pid}",
                                )
                                _fanos = fc2.text_input(
                                    "Años / rango",
                                    value=_anos_ini,
                                    key=f"inv_ficha_anos_{_pid}",
                                )
                                fu1, fu2 = st.columns(2)
                                _fubi = fu1.text_input(
                                    "Ubicación en almacén",
                                    value=_export_cell_txt(_rw.get("ubicacion")),
                                    key=f"inv_ficha_ubi_{_pid}",
                                )
                                _fimg = fu2.text_input(
                                    "URL imagen",
                                    value=_export_cell_txt(_rw.get("imagen_url")),
                                    key=f"inv_ficha_img_{_pid}",
                                )
                                st.markdown("**Stock y precios (USD)**")
                                fs1, fs2 = st.columns(2)
                                _ns = fs1.number_input(
                                    "Stock actual (unidades)",
                                    min_value=0,
                                    value=_inv_stock_int(_rw.get("stock_actual")),
                                    step=1,
                                    format="%d",
                                    key=f"inv_ficha_st_{_pid}",
                                )
                                _nsmin = fs2.number_input(
                                    "Stock mínimo (alerta)",
                                    min_value=0,
                                    value=_inv_stock_int(_rw.get("stock_minimo")),
                                    step=1,
                                    format="%d",
                                    key=f"inv_ficha_smin_{_pid}",
                                )
                                fp1, fp2 = st.columns(2)
                                _nco = fp1.number_input(
                                    "Costo USD",
                                    min_value=0.0,
                                    value=float(_rw.get("costo_usd") or 0),
                                    step=0.01,
                                    format="%.2f",
                                    key=f"inv_ficha_co_{_pid}",
                                )
                                _npv = fp2.number_input(
                                    "Precio venta USD (precio_v_usd)",
                                    min_value=0.0,
                                    value=float(_rw.get("precio_v_usd") or 0),
                                    step=0.01,
                                    format="%.2f",
                                    key=f"inv_ficha_pv_{_pid}",
                                )
                                if float(_nco) > 0:
                                    st.caption(
                                        f"Margen bruto: **{((float(_npv) - float(_nco)) / float(_nco) * 100):.1f}%** "
                                        f"· Diferencia USD: **{float(_npv) - float(_nco):.2f}**"
                                    )
                                st.markdown("**Estado y categoría**")
                                fx1, fx2 = st.columns(2)
                                _factivo = fx1.checkbox(
                                    "Producto activo",
                                    value=bool(_rw.get("activo", True)),
                                    key=f"inv_ficha_act_{_pid}",
                                )
                                _fsel_cat = fx2.selectbox(
                                    "Categoría",
                                    options=_cat_select_opts,
                                    index=_cat_ix,
                                    key=f"inv_ficha_cat_{_pid}",
                                )
                                if st.form_submit_button("Guardar cambios del producto"):
                                    _merged_mv = _inv_merge_marcas_catalogo_texto(_fpick_mv, _fextra_mv)
                                    _compat_f = _inv_build_compat_dict(_merged_mv, _fanos)
                                    _cid_f = (
                                        _nombre_a_id_cat.get(str(_fsel_cat).strip())
                                        if str(_fsel_cat or "").strip()
                                        else None
                                    )
                                    _upd_f: dict[str, Any] = {
                                        "codigo": str(_fcod).strip() or None,
                                        "descripcion": str(_fdesc).strip() or "Sin descripción",
                                        "stock_actual": int(_ns),
                                        "stock_minimo": int(_nsmin),
                                        "costo_usd": float(_nco),
                                        "precio_v_usd": float(_npv),
                                        "activo": bool(_factivo),
                                        "categoria_id": _cid_f,
                                        "condicion": _fcond if _fcond in ("Nuevo", "Usado") else "Nuevo",
                                        "compatibilidad": _compat_f,
                                    }
                                    if "sku_oem" in df_view.columns:
                                        _upd_f["sku_oem"] = str(_fsku).strip() or None
                                    if "marca_producto" in df_view.columns:
                                        _upd_f["marca_producto"] = str(_fmprod).strip() or None
                                    if "ubicacion" in df_view.columns:
                                        _upd_f["ubicacion"] = str(_fubi).strip() or None
                                    if "imagen_url" in df_view.columns:
                                        _upd_f["imagen_url"] = str(_fimg).strip() or None
                                    try:
                                        sb.table("productos").update(_upd_f).eq("id", _pid).execute()
                                        st.success("Producto actualizado.")
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(
                                            f"{ex} · Revisá que esté aplicado **patch_011** (columnas repuestos) en Supabase."
                                        )
        with _t_prod:
            with st.expander("Nueva categoría", expanded=False):
                st.caption("Creá la categoría acá si aún no existe; después elegila en el formulario de abajo.")
                with st.form("f_cat"):
                    cn = st.text_input("Nombre categoría", key="inv_alta_cat_nombre")
                    submitted_cat = st.form_submit_button("Crear categoría")
                    if submitted_cat:
                        if not cn.strip():
                            st.error("Escribí un nombre para la categoría.")
                        else:
                            try:
                                sb.table("categorias").insert({"nombre": cn.strip()}).execute()
                                st.success("Categoría guardada en la base.")
                                st.rerun()
                            except Exception as ex:
                                st.error(
                                    f"No se pudo guardar. Si el nombre ya existe, elegí otro (las categorías son únicas). Detalle: {ex}"
                                )
            with st.form("f_prod"):
                desc = st.text_input("Descripción", max_chars=500, key="inv_alta_prod_desc")
                cx, mx = st.columns(2)
                cname = cx.selectbox(
                    "Categoría",
                    options=[""] + sorted(cat_opts.keys(), key=str.casefold),
                    key="inv_alta_prod_cat",
                    help="Para código automático es obligatoria. Primeras 3 letras/números del nombre → tramo del código.",
                )
                marca_rep = mx.text_input(
                    "Marca del repuesto (ej. Bosch, Denso)",
                    key="inv_alta_marca_prod",
                    help="Primeras 3 letras/números → tramo del código. Vacío = **GEN** (ej. FIL-GEN-0001).",
                )
                cond_alta = st.selectbox("Condición", ["Nuevo", "Usado"], index=0, key="inv_alta_cond")
                st.markdown("**Código interno**")
                cod_auto = st.checkbox(
                    "Generar automático: **categoría + marca + número** (ej. `FIL-BOS-0001`)",
                    value=True,
                    key="inv_alta_cod_auto",
                )
                codigo_manual = ""
                if cod_auto:
                    if cname:
                        _prev_cod = _siguiente_codigo_interno_producto(sb, cname, marca_rep)
                        st.info(
                            f"Vista previa: **`{_prev_cod}`** · Al guardar se vuelve a calcular el siguiente libre "
                            "(por si otro usuario cargó algo al mismo tiempo)."
                        )
                    else:
                        st.warning("Elegí una **categoría** para poder generar el código automático.")
                else:
                    codigo_manual = st.text_input(
                        "Código manual",
                        key="inv_alta_prod_codigo",
                        placeholder="Ej. ARR-REN-01",
                    )
                a1, a2 = st.columns(2)
                sku_oem = a1.text_input("Código OEM / parte / fabricante", key="inv_alta_prod_sku_oem")
                a2.caption("El **código interno** es el tuyo para buscar en inventario; el OEM es el de la caja/fábrica.")
                if _marcas_veh_catalogo:
                    st.multiselect(
                        "Marcas de carro (catálogo en base)",
                        options=_marcas_veh_catalogo,
                        default=[],
                        key="inv_alta_marcas_pick",
                        help="Listado cargado con **patch_012_marcas_vehiculo.sql**. Podés sumar más en el campo de texto.",
                    )
                else:
                    st.caption(
                        "No hay catálogo de marcas en la base. Ejecutá **supabase/patch_012_marcas_vehiculo.sql** "
                        "en Supabase y recargá la app."
                    )
                    st.session_state["inv_alta_marcas_pick"] = []
                c1, c2 = st.columns(2)
                marcas_auto = c1.text_input(
                    "Otras marcas de carro (texto, coma)",
                    key="inv_alta_marcas_veh",
                    placeholder="Ej. otra que no esté en la lista…",
                    help="Se unen con las que marcaste arriba en el catálogo.",
                )
                anos_auto = c2.text_input("Años / rango (opcional)", key="inv_alta_anos", placeholder="2010-2015")
                u1, u2 = st.columns(2)
                ubic = u1.text_input("Ubicación en almacén", key="inv_alta_ubic")
                img_url = u2.text_input("URL imagen (Storage o web)", key="inv_alta_img")
                stock = st.number_input("Stock actual (unidades)", min_value=0, value=0, step=1, format="%d")
                smin = st.number_input("Stock mínimo (alerta)", min_value=0, value=0, step=1, format="%d")
                costo = st.number_input("Costo USD", min_value=0.0, value=0.0, format="%.2f")
                pv = st.number_input("Precio venta USD (precio_v_usd)", min_value=0.0, value=0.0, format="%.2f")
                if float(costo) > 0:
                    st.caption(
                        f"Margen bruto sobre costo: **{((float(pv) - float(costo)) / float(costo) * 100):.1f}%** "
                        f"· Diferencia USD: **{float(pv) - float(costo):.2f}**"
                    )
                cid = cat_opts.get(cname) if cname else None
                if st.form_submit_button("Guardar producto"):
                    try:
                        _pick_mv = list(st.session_state.get("inv_alta_marcas_pick") or [])
                        _merged_mv = _inv_merge_marcas_catalogo_texto(_pick_mv, marcas_auto)
                        _compat_ins = _inv_build_compat_dict(_merged_mv, anos_auto)
                        if cod_auto:
                            if not cname:
                                st.error("Para código automático elegí una **categoría**.")
                            else:
                                codigo_final: str | None = _siguiente_codigo_interno_producto(sb, cname, marca_rep)
                                _insert_ok = False
                                _last_ex: Exception | None = None
                                for _ in range(10):
                                    try:
                                        sb.table("productos").insert(
                                            {
                                                "codigo": codigo_final,
                                                "sku_oem": sku_oem.strip() or None,
                                                "descripcion": desc.strip() or "Sin descripción",
                                                "marca_producto": marca_rep.strip() or None,
                                                "condicion": cond_alta,
                                                "ubicacion": ubic.strip() or None,
                                                "compatibilidad": _compat_ins,
                                                "imagen_url": img_url.strip() or None,
                                                "stock_actual": int(stock),
                                                "stock_minimo": int(smin),
                                                "costo_usd": float(costo),
                                                "precio_v_usd": float(pv),
                                                "categoria_id": cid,
                                                "activo": True,
                                            }
                                        ).execute()
                                        _insert_ok = True
                                        break
                                    except Exception as ex_i:
                                        _last_ex = ex_i
                                        es = str(ex_i).lower()
                                        if "duplicate" in es or "unique" in es or "23505" in es:
                                            codigo_final = _siguiente_codigo_interno_producto(sb, cname, marca_rep)
                                        else:
                                            raise
                                if _insert_ok:
                                    st.success(f"Producto guardado con código **{codigo_final}**.")
                                    st.rerun()
                                else:
                                    st.error(
                                        str(_last_ex)
                                        if _last_ex
                                        else "No se pudo asignar código único. Reintentá o usá código manual."
                                    )
                        else:
                            _cm = (codigo_manual or "").strip()
                            if not _cm:
                                st.error("Ingresá un **código manual** o activá el generador automático.")
                            else:
                                sb.table("productos").insert(
                                    {
                                        "codigo": _cm or None,
                                        "sku_oem": sku_oem.strip() or None,
                                        "descripcion": desc.strip() or "Sin descripción",
                                        "marca_producto": marca_rep.strip() or None,
                                        "condicion": cond_alta,
                                        "ubicacion": ubic.strip() or None,
                                        "compatibilidad": _compat_ins,
                                        "imagen_url": img_url.strip() or None,
                                        "stock_actual": int(stock),
                                        "stock_minimo": int(smin),
                                        "costo_usd": float(costo),
                                        "precio_v_usd": float(pv),
                                        "categoria_id": cid,
                                        "activo": True,
                                    }
                                ).execute()
                                st.success("Producto guardado en la base.")
                                st.rerun()
                    except Exception as ex:
                        st.error(
                            f"No se pudo guardar el producto: {ex}. "
                            "Si falta alguna columna, ejecutá **patch_011_productos_repuestos.sql** en Supabase."
                        )

        with _t_del:
            st.caption(
                "Solo con **stock en cero**. Si el producto ya tiene **ventas o compras**, la base suele **no dejar borrarlo**; "
                "en ese caso desactivalo (**Activo** = no) en la tabla de abajo."
            )
            try:
                _pz = (
                    sb.table("productos")
                    .select("id,codigo,descripcion,stock_actual")
                    .eq("stock_actual", 0)
                    .order("descripcion")
                    .execute()
                )
                _rows_z = _pz.data or []
            except Exception as exz:
                _rows_z = []
                st.error(str(exz))
            if not _rows_z:
                st.info("No hay productos con stock **0** para eliminar.")
            else:
                _lab_z: dict[str, str] = {}
                for _rz in _rows_z:
                    _iz = str(_rz.get("id") or "").strip()
                    if not _iz:
                        continue
                    _cz = _export_cell_txt(_rz.get("codigo")) or "—"
                    _dz = (_export_cell_txt(_rz.get("descripcion")) or "")[:56]
                    _lab_z[f"{_cz} · {_dz}"] = _iz
                _keys_z = sorted(_lab_z.keys(), key=str.casefold)
                with st.form("inv_form_del_prod"):
                    _sel_z = st.selectbox("Producto a eliminar", options=_keys_z, key="inv_del_prod_sel")
                    _cf_z = st.text_input('Confirmación: escribí **ELIMINAR**', key="inv_del_prod_conf")
                    if st.form_submit_button("Eliminar definitivamente"):
                        _pid_z = _lab_z.get(str(_sel_z))
                        if not _pid_z:
                            st.error("Elegí un producto.")
                        else:
                            _ok_z, _msg_z = _inv_eliminar_producto_stock_cero(sb, _pid_z, _cf_z)
                            if _ok_z:
                                st.success(_msg_z)
                                st.rerun()
                            else:
                                st.error(_msg_z)

        with _t_mov:
            st.caption(
                "**Entrada** suma stock (hallazgo, ajuste de inventario). **Salida** resta (merma, rotura). "
                "Se guarda historial en **movimientos_inventario** si ejecutaste **patch_013_movimientos_inventario.sql**."
            )
            try:
                _pm = (
                    sb.table("productos")
                    .select("id,codigo,descripcion,stock_actual")
                    .eq("activo", True)
                    .order("descripcion")
                    .limit(2000)
                    .execute()
                )
                _rows_m = _pm.data or []
            except Exception as exm:
                _rows_m = []
                st.error(str(exm))
            if not _rows_m:
                st.warning("No hay productos activos.")
            else:
                _lab_m: dict[str, str] = {}
                for _rm in _rows_m:
                    _im = str(_rm.get("id") or "").strip()
                    if not _im:
                        continue
                    _cm = _export_cell_txt(_rm.get("codigo")) or "—"
                    _dm = (_export_cell_txt(_rm.get("descripcion")) or "")[:48]
                    _stm = _inv_stock_int(_rm.get("stock_actual"))
                    _lab_m[f"{_cm} · {_dm} · stock {_stm}"] = _im
                _keys_m = sorted(_lab_m.keys(), key=str.casefold)
                with st.form("inv_form_mov_stock"):
                    _sel_m = st.selectbox("Producto", options=_keys_m, key="inv_mov_prod_sel")
                    _tipo_m = st.radio("Movimiento", ["Entrada", "Salida"], horizontal=True, key="inv_mov_tipo")
                    _cant_m = st.number_input(
                        "Cantidad (unidades)",
                        min_value=1,
                        value=1,
                        step=1,
                        format="%d",
                        key="inv_mov_cant",
                    )
                    _mot_m = st.text_area(
                        "Motivo (obligatorio)",
                        key="inv_mov_mot",
                        placeholder="Ej. Inventario físico, merma, hallazgo en bodega…",
                    )
                    if st.form_submit_button("Aplicar movimiento"):
                        _pid_m = _lab_m.get(str(_sel_m))
                        if not _pid_m:
                            st.error("Elegí un producto.")
                        elif not (_mot_m or "").strip():
                            st.error("El **motivo** es obligatorio.")
                        else:
                            _ok_m, _msg_m = _inv_aplicar_movimiento_stock(
                                sb,
                                erp_uid,
                                _pid_m,
                                str(_tipo_m),
                                int(_cant_m),
                                str(_mot_m),
                            )
                            if _ok_m:
                                st.success(_msg_m)
                                st.rerun()
                            else:
                                st.error(_msg_m)
                try:
                    _hist = (
                        sb.table("movimientos_inventario")
                        .select("created_at,tipo,cantidad,motivo,stock_antes,stock_despues,producto_id")
                        .order("created_at", desc=True)
                        .limit(25)
                        .execute()
                    )
                    if _hist.data:
                        st.markdown("##### Últimos movimientos")
                        st.dataframe(pd.DataFrame(_hist.data), use_container_width=True, hide_index=True)
                except Exception:
                    pass

    st.caption(
        "CSV: obligatorias **codigo** (en import no hay autogenerado; ponelos vos), **descripcion**, **stock_actual**, "
        "**stock_minimo**, **costo_usd**, **precio_v_usd**. Opcional: **categoria**, **sku_oem**, **marca_producto**, "
        "**condicion**, **ubicacion**, **marcas_vehiculo**, **años**, **imagen_url**."
    )
    up = st.file_uploader("CSV", type=["csv"], key="inv_csv_upload")
    if up is not None:
        df_csv = pd.read_csv(up)
        required = {
            "codigo",
            "descripcion",
            "stock_actual",
            "stock_minimo",
            "costo_usd",
            "precio_v_usd",
        }
        if not required.issubset(set(df_csv.columns.str.lower())):
            st.error(f"Faltan columnas. Requeridas: {required}")
        else:
            df_csv.columns = [c.lower() for c in df_csv.columns]
            if st.button("Insertar filas", key="inv_csv_insert"):
                rows_csv = df_csv.to_dict(orient="records")
                batch_ins: list[dict[str, Any]] = []
                err_cat: list[str] = []
                for i, row in enumerate(rows_csv):
                    cid_csv: str | None = None
                    if "categoria" in df_csv.columns and row.get("categoria") is not None:
                        raw_c = str(row["categoria"]).strip()
                        if raw_c and raw_c.lower() not in ("nan", "none"):
                            cid_csv = _resolve_categoria_id_por_nombre(raw_c, _nombre_a_id_cat)
                            if cid_csv is None:
                                err_cat.append(f"fila {i + 1}: categoría «{raw_c}» no encontrada")
                    _mv = ""
                    if "marcas_vehiculo" in df_csv.columns and row.get("marcas_vehiculo") is not None:
                        _mv = str(row["marcas_vehiculo"])
                    elif "marcas vehiculo" in df_csv.columns and row.get("marcas vehiculo") is not None:
                        _mv = str(row["marcas vehiculo"])
                    _an = ""
                    if "años" in df_csv.columns and row.get("años") is not None:
                        _an = str(row["años"])
                    elif "anos" in df_csv.columns and row.get("anos") is not None:
                        _an = str(row["anos"])
                    _compat_csv = _inv_build_compat_dict(_mv, _an)
                    _cond_csv = "Nuevo"
                    if "condicion" in df_csv.columns and row.get("condicion") is not None:
                        cs = str(row["condicion"]).strip()
                        if cs in ("Nuevo", "Usado"):
                            _cond_csv = cs
                    _row_ins: dict[str, Any] = {
                        "codigo": str(row["codigo"]).strip() or None,
                        "descripcion": str(row["descripcion"]),
                        "stock_actual": _inv_stock_int(row["stock_actual"]),
                        "stock_minimo": _inv_stock_int(row["stock_minimo"]),
                        "costo_usd": float(row["costo_usd"]),
                        "precio_v_usd": float(row["precio_v_usd"]),
                        "categoria_id": cid_csv,
                        "activo": True,
                        "condicion": _cond_csv,
                        "compatibilidad": _compat_csv,
                    }
                    if "sku_oem" in df_csv.columns and row.get("sku_oem") is not None:
                        s = str(row["sku_oem"]).strip()
                        _row_ins["sku_oem"] = s or None
                    if "marca_producto" in df_csv.columns and row.get("marca_producto") is not None:
                        s = str(row["marca_producto"]).strip()
                        _row_ins["marca_producto"] = s or None
                    if "ubicacion" in df_csv.columns and row.get("ubicacion") is not None:
                        s = str(row["ubicacion"]).strip()
                        _row_ins["ubicacion"] = s or None
                    if "imagen_url" in df_csv.columns and row.get("imagen_url") is not None:
                        s = str(row["imagen_url"]).strip()
                        _row_ins["imagen_url"] = s or None
                    batch_ins.append(_row_ins)
                if err_cat:
                    st.error("Revisá el CSV:\n- " + "\n- ".join(err_cat[:12]))
                    if len(err_cat) > 12:
                        st.caption(f"… y {len(err_cat) - 12} errores más.")
                else:
                    _insert_rows_batched(sb, "productos", batch_ins)
                    st.success(f"Insertados {len(batch_ins)} productos.")
                    st.rerun()

    st.divider()
    st.markdown("##### Tabla de productos (edición masiva — al final del módulo)")
    st.caption(
        "Mismos **filtros de búsqueda y categoría** de arriba. Podés editar **varias filas** y guardar una vez. "
        "**OEM** = código de parte; **vehículos** = marcas de carro separadas por coma. "
        "**precio_v_bs_ref** / **costo_bs_ref**: solo referencia en Bs (solo lectura aquí)."
    )
    if df.empty:
        st.info("Cuando cargues productos en la base, la tabla aparecerá acá.")
    elif df_view.empty:
        st.info(
            "No hay filas con el filtro actual. Cambiá la búsqueda o la categoría para ver la tabla, "
            "o usá la pestaña **Editar Productos** en el expander *Productos* más arriba."
        )
    else:
        _inv_skip_cols = {"id", "categoria_id", "compatibilidad"}
        _inv_editor_order = [
            "codigo",
            "sku_oem",
            "descripcion",
            "marca_producto",
            "condicion",
            "vehiculos_compat",
            "años_compat",
            "ubicacion",
            "imagen_url",
            "stock_actual",
            "stock_minimo",
            "costo_usd",
            "precio_v_usd",
            "precio_v_bs_ref",
            "costo_bs_ref",
            "activo",
            "categoria",
        ]
        _editor_cols = [c for c in _inv_editor_order if c in df_view.columns]
        for c in df_view.columns:
            if c not in _editor_cols and c not in _inv_skip_cols:
                _editor_cols.append(c)
        _ed_df = df_view[_editor_cols].copy()
        _disabled_cols = ["id"]
        if "precio_v_bs_ref" in _ed_df.columns:
            _disabled_cols.extend(["precio_v_bs_ref", "costo_bs_ref"])
        _inv_col_cfg_tbl: dict[str, Any] = {
            "categoria": st.column_config.SelectboxColumn(
                "Categoría",
                options=_cat_select_opts,
            ),
            "condicion": st.column_config.SelectboxColumn(
                "Condición",
                options=["Nuevo", "Usado"],
                required=True,
            ),
            "stock_actual": st.column_config.NumberColumn(
                "Stock",
                min_value=0,
                step=1,
                format="%d",
            ),
            "stock_minimo": st.column_config.NumberColumn(
                "Stock mín.",
                min_value=0,
                step=1,
                format="%d",
            ),
        }
        edited = st.data_editor(
            _ed_df,
            num_rows="fixed",
            disabled=_disabled_cols,
            column_config=_inv_col_cfg_tbl,
            use_container_width=True,
            key="editor_prod",
        )
        if st.button("Guardar cambios de inventario", key="inv_btn_guardar_tabla"):
            for _, row in edited.iterrows():
                _cv = row.get("categoria")
                if _cv is None or (isinstance(_cv, float) and pd.isna(_cv)):
                    _cv = ""
                _cv = str(_cv).strip()
                _cid_up = _nombre_a_id_cat.get(_cv) if _cv else None
                _cond = row.get("condicion")
                if _cond not in ("Nuevo", "Usado"):
                    _cond = "Nuevo"
                _sku = row.get("sku_oem")
                _sku = None if _sku is None or (isinstance(_sku, float) and pd.isna(_sku)) else str(_sku).strip() or None
                _mprod = row.get("marca_producto")
                _mprod = (
                    None
                    if _mprod is None or (isinstance(_mprod, float) and pd.isna(_mprod))
                    else str(_mprod).strip() or None
                )
                _ubi = row.get("ubicacion")
                _ubi = None if _ubi is None or (isinstance(_ubi, float) and pd.isna(_ubi)) else str(_ubi).strip() or None
                _img = row.get("imagen_url")
                _img = None if _img is None or (isinstance(_img, float) and pd.isna(_img)) else str(_img).strip() or None
                _compat = _inv_build_compat_dict(
                    str(row.get("vehiculos_compat") or ""),
                    str(row.get("años_compat") or ""),
                )
                _upd: dict[str, Any] = {
                    "codigo": None
                    if row.get("codigo") is None
                    or (isinstance(row.get("codigo"), float) and pd.isna(row.get("codigo")))
                    else (str(row.get("codigo")).strip() or None),
                    "descripcion": str(row.get("descripcion") or ""),
                    "stock_actual": _inv_stock_int(row.get("stock_actual")),
                    "stock_minimo": _inv_stock_int(row.get("stock_minimo")),
                    "costo_usd": float(row.get("costo_usd", 0)),
                    "precio_v_usd": float(row.get("precio_v_usd", 0)),
                    "activo": bool(row.get("activo", True)),
                    "categoria_id": _cid_up,
                    "condicion": _cond,
                    "compatibilidad": _compat,
                }
                if "sku_oem" in df_view.columns:
                    _upd["sku_oem"] = _sku
                if "marca_producto" in df_view.columns:
                    _upd["marca_producto"] = _mprod
                if "ubicacion" in df_view.columns:
                    _upd["ubicacion"] = _ubi
                if "imagen_url" in df_view.columns:
                    _upd["imagen_url"] = _img
                try:
                    sb.table("productos").update(_upd).eq("id", str(row["id"])).execute()
                except Exception as ex:
                    st.error(
                        f"Error al guardar fila id={row.get('id')}: {ex}. "
                        "¿Ejecutaste **supabase/patch_011_productos_repuestos.sql** en Supabase?"
                    )
                    st.stop()
            st.success("Productos actualizados.")
            st.rerun()


def module_ventas(sb: Client, erp_uid: str, t: dict[str, Any] | None) -> None:
    st.subheader("Ventas y CXC")
    if not t:
        st.stop()

    t_usdt = float(t["tasa_usdt"])
    st.caption(
        "Líneas en **USD**: precio unitario y total son **1 USD = 1 USD** en el sistema. "
        "Si cobrás o referenciás en **bolívares**, elegí la tasa (**BCV** o **P2P Binance**); "
        "se guarda en la venta para equivalentes en Bs."
    )

    prods = (
        sb.table("productos")
        .select("id,descripcion,precio_v_usd,stock_actual")
        .eq("activo", True)
        .order("descripcion")
        .execute()
    )
    plist = prods.data or []
    if not plist:
        st.warning("No hay productos activos.")
        st.stop()

    id_to_label = {str(p["id"]): f"{p['descripcion']} (stock {p['stock_actual']})" for p in plist}
    id_to_price = {str(p["id"]): float(p["precio_v_usd"]) for p in plist}

    cajas = sb.table("cajas_bancos").select("id,nombre,tipo").eq("activo", True).execute()
    cj = {f"{c['nombre']} ({c['tipo']})": str(c["id"]) for c in (cajas.data or [])}

    if "venta_lines" not in st.session_state:
        st.session_state["venta_lines"] = [
            {"producto_id": str(plist[0]["id"]), "cantidad": 1, "precio_unitario_usd": id_to_price[str(plist[0]["id"])]}
        ]

    st.session_state.setdefault("venta_n_cobros", 1)
    b1, b2 = st.columns([1, 3])
    with b1:
        if st.button("➕ Otro medio de cobro", help="Suma una fila VES / USD / USDT en la misma venta al contado"):
            st.session_state["venta_n_cobros"] = min(10, int(st.session_state.get("venta_n_cobros", 1)) + 1)
            st.rerun()
    with b2:
        if st.button("↺ Una sola fila de cobro", help="Vuelve a un solo medio de pago"):
            st.session_state["venta_n_cobros"] = 1
            st.rerun()

    with st.form("f_venta"):
        cliente = st.text_input("Cliente")
        forma = st.selectbox("Forma de pago", ["contado", "credito"])
        fv = st.date_input("Vencimiento (crédito)", value=date.today() + timedelta(days=30))
        notas = st.text_area("Notas")

        doc_tasa = st.radio(
            "Tasa Bs/USD para esta venta (equivalente en bolívares y registro en BD):",
            options=DOC_TASA_BS_OPTS,
            index=_infer_tasa_bs_oper_index(t),
            horizontal=True,
            key="venta_doc_tasa_bs",
            help="Sirve para convertir VES en equivalente USD al cuadrar cobros y para el registro de la venta.",
        )

        st.caption("Líneas (montos en USD)")
        new_lines: list[dict[str, Any]] = []
        for i, line in enumerate(st.session_state["venta_lines"]):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            pid = c1.selectbox(
                f"Producto {i+1}",
                options=list(id_to_label.keys()),
                format_func=lambda x: id_to_label[x],
                key=f"vp_{i}",
                index=list(id_to_label.keys()).index(line["producto_id"]) if line["producto_id"] in id_to_label else 0,
            )
            qty = c2.number_input(
                "Cant.",
                min_value=1,
                value=_line_qty_int(line.get("cantidad"), default=1),
                step=1,
                format="%d",
                key=f"vq_{i}",
            )
            pu = c3.number_input("P.U. USD", min_value=0.0, value=float(id_to_price.get(pid, 0)), format="%.2f", key=f"vpu_{i}")
            new_lines.append({"producto_id": pid, "cantidad": int(qty), "precio_unitario_usd": float(pu)})

        est_total = round(sum(float(l["cantidad"]) * float(l["precio_unitario_usd"]) for l in new_lines), 2)

        cobros_pl: list[dict[str, Any]] = []
        if forma == "contado":
            st.markdown("**Cobro al contado — por moneda y cuenta**")
            st.caption(
                f"Total venta **US$ {est_total:,.2f}**. La suma en USD equivalente de las filas debe coincidir (±0,05). "
                "**VES** = bolívares cobrados; **USDT** = unidades USDT; **USD** = dólares en efectivo/banco."
            )
            if not cj:
                st.error("No hay cajas activas. Cree una en el módulo Cajas.")
            n_cob = int(st.session_state.get("venta_n_cobros", 1))
            for i in range(n_cob):
                r1, r2, r3 = st.columns([2, 1, 1])
                ck = r1.selectbox(f"Caja cobro {i + 1}", options=list(cj.keys()), key=f"vcb_ck_{i}")
                mon = r2.selectbox(
                    "Moneda",
                    options=["USD", "VES", "USDT"],
                    key=f"vcb_mon_{i}",
                    help="Monto en la moneda elegida (no en USD salvo que elija USD).",
                )
                default_m = float(est_total) if (n_cob == 1 and i == 0 and mon == "USD") else 0.0
                mval = r3.number_input(
                    f"Monto ({mon})",
                    min_value=0.0,
                    value=default_m,
                    format="%.4f" if mon != "USD" else "%.2f",
                    key=f"vcb_mv_{i}",
                )
                cobros_pl.append({"caja_key": ck, "moneda": mon, "monto": float(mval)})

        if st.form_submit_button("Registrar venta (atómica)"):
            try:
                t_bs_doc = _tasa_bs_para_documento(t, usar_bcv=(doc_tasa == DOC_TASA_BS_OPTS[0]))
            except ValueError as e:
                st.error(str(e))
            else:
                payload: dict[str, Any] = {
                    "p_usuario_id": erp_uid,
                    "p_cliente": cliente,
                    "p_forma_pago": forma,
                    "p_caja_id": None,
                    "p_tasa_bs": t_bs_doc,
                    "p_tasa_usdt": t_usdt,
                    "p_fecha_vencimiento": str(fv) if forma == "credito" else None,
                    "p_notas": notas,
                    "p_lineas": new_lines,
                }
                if forma == "contado":
                    if not cj:
                        st.error("Sin cajas.")
                    else:
                        p_cobros = [
                            {"caja_id": str(cj[row["caja_key"]]), "moneda": row["moneda"], "monto": row["monto"]}
                            for row in cobros_pl
                        ]
                        sum_eq = round(
                            sum(
                                _monto_nativo_a_usd(r["moneda"], r["monto"], t_bs_doc, t_usdt) for r in p_cobros
                            ),
                            2,
                        )
                        if any(r["monto"] <= 0 for r in p_cobros):
                            st.error("Cada línea de cobro debe tener monto > 0.")
                        elif abs(sum_eq - est_total) > 0.05:
                            st.error(
                                f"Los cobros equivalen a ~**US$ {sum_eq:,.2f}**; el total de la venta es **US$ {est_total:,.2f}**."
                            )
                        else:
                            payload["p_caja_id"] = str(p_cobros[0]["caja_id"])
                            payload["p_cobros"] = p_cobros
                            try:
                                sb.rpc("crear_venta_erp", payload).execute()
                                st.success("Venta registrada.")
                                st.session_state["venta_lines"] = [
                                    {
                                        "producto_id": str(plist[0]["id"]),
                                        "cantidad": 1,
                                        "precio_unitario_usd": id_to_price[str(plist[0]["id"])],
                                    }
                                ]
                                st.session_state["venta_n_cobros"] = 1
                                st.rerun()
                            except Exception as e:
                                err = str(e)
                                if "p_cobros" in err or "could not find" in err.lower():
                                    st.error(
                                        f"{err} · Si falta el parámetro en BD, ejecutá `supabase/patch_008_movimientos_moneda_cobros.sql`."
                                    )
                                else:
                                    st.error(f"No se pudo registrar: {e}")
                else:
                    try:
                        sb.rpc("crear_venta_erp", payload).execute()
                        st.success("Venta registrada.")
                        st.session_state["venta_lines"] = [
                            {
                                "producto_id": str(plist[0]["id"]),
                                "cantidad": 1,
                                "precio_unitario_usd": id_to_price[str(plist[0]["id"])],
                            }
                        ]
                        st.session_state["venta_n_cobros"] = 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo registrar: {e}")

    if st.button("Añadir línea"):
        st.session_state["venta_lines"].append(
            {"producto_id": str(plist[0]["id"]), "cantidad": 1, "precio_unitario_usd": id_to_price[str(plist[0]["id"])]}
        )
        st.rerun()

    st.divider()
    st.caption("Cobrar CXC (ingreso a caja + baja de pendiente)")
    cxc = (
        sb.table("cuentas_por_cobrar")
        .select("id, venta_id, monto_pendiente_usd, fecha_vencimiento, estado")
        .in_("estado", ["Pendiente", "Parcial"])
        .execute()
    )
    if cxc.data:
        df = pd.DataFrame(cxc.data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        row_id = st.selectbox("ID CXC", options=[str(x["id"]) for x in cxc.data])
        monto = st.number_input("Monto a cobrar USD", min_value=0.01, value=float(next(x["monto_pendiente_usd"] for x in cxc.data if str(x["id"]) == row_id)), format="%.2f")
        caja_cobro = st.selectbox("Caja cobro", options=list(cj.keys()), key="cxc_caja")
        if st.button("Registrar cobro CXC"):
            try:
                sb.rpc(
                    "cobrar_cxc_erp",
                    {
                        "p_usuario_id": erp_uid,
                        "p_cxc_id": row_id,
                        "p_caja_id": cj[caja_cobro],
                        "p_monto_usd": float(monto),
                    },
                ).execute()
                st.success("Cobro registrado.")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    else:
        st.info("No hay cuentas por cobrar pendientes.")


def module_compras(sb: Client, erp_uid: str, t: dict[str, Any] | None) -> None:
    st.subheader("Compras y CXP")
    if not t:
        st.stop()

    t_usdt = float(t["tasa_usdt"])
    st.caption(
        "Líneas en **USD** (1:1). Para equivalente en **bolívares** en esta compra, elegí **BCV** o **P2P Binance**."
    )

    prods = (
        sb.table("productos")
        .select("id,descripcion,costo_usd")
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

    cajas = sb.table("cajas_bancos").select("id,nombre,tipo").eq("activo", True).execute()
    cj = {f"{c['nombre']} ({c['tipo']})": str(c["id"]) for c in (cajas.data or [])}

    if "compra_lines" not in st.session_state:
        st.session_state["compra_lines"] = [
            {"producto_id": str(plist[0]["id"]), "cantidad": 1, "costo_unitario_usd": id_to_cost[str(plist[0]["id"])]}
        ]

    with st.form("f_compra"):
        prov = st.text_input("Proveedor")
        forma = st.selectbox("Forma de pago compra", ["contado", "credito"], key="forma_compra")
        caja_label = st.selectbox("Caja (solo contado)", options=list(cj.keys()), key="caja_compra") if cj else None
        fv = st.date_input("Vencimiento (crédito compra)", value=date.today() + timedelta(days=30), key="fv_compra")
        notas = st.text_area("Notas compra")

        doc_tasa_c = st.radio(
            "Tasa Bs/USD para esta compra:",
            options=DOC_TASA_BS_OPTS,
            index=_infer_tasa_bs_oper_index(t),
            horizontal=True,
            key="compra_doc_tasa_bs",
            help="Montos de línea en USD sin cambio; la tasa queda en el registro de compra.",
        )

        new_lines: list[dict[str, Any]] = []
        for i, line in enumerate(st.session_state["compra_lines"]):
            c1, c2, c3 = st.columns([3, 1, 1])
            pid = c1.selectbox(
                f"Producto {i+1}",
                options=list(id_to_label.keys()),
                format_func=lambda x: id_to_label[x],
                key=f"cp_{i}",
                index=list(id_to_label.keys()).index(line["producto_id"]) if line["producto_id"] in id_to_label else 0,
            )
            qty = c2.number_input(
                "Cant.",
                min_value=1,
                value=_line_qty_int(line.get("cantidad"), default=1),
                step=1,
                format="%d",
                key=f"cq_{i}",
            )
            cu = c3.number_input("Costo u. USD", min_value=0.0, value=float(id_to_cost.get(pid, 0)), format="%.2f", key=f"ccu_{i}")
            new_lines.append({"producto_id": pid, "cantidad": int(qty), "costo_unitario_usd": float(cu)})

        if st.form_submit_button("Registrar compra (atómica)"):
            try:
                t_bs_doc = _tasa_bs_para_documento(t, usar_bcv=(doc_tasa_c == DOC_TASA_BS_OPTS[0]))
            except ValueError as e:
                st.error(str(e))
            else:
                payload = {
                    "p_usuario_id": erp_uid,
                    "p_proveedor": prov,
                    "p_forma_pago": forma,
                    "p_caja_id": cj[caja_label] if forma == "contado" and caja_label else None,
                    "p_tasa_bs": t_bs_doc,
                    "p_tasa_usdt": t_usdt,
                    "p_fecha_vencimiento": str(fv) if forma == "credito" else None,
                    "p_notas": notas,
                    "p_lineas": new_lines,
                }
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
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo registrar: {e}")

    if st.button("Añadir línea compra"):
        st.session_state["compra_lines"].append(
            {"producto_id": str(plist[0]["id"]), "cantidad": 1, "costo_unitario_usd": id_to_cost[str(plist[0]["id"])]}
        )
        st.rerun()


def module_cajas(sb: Client, erp_uid: str) -> None:
    st.subheader("Cajas y bancos")
    rows = sb.table("cajas_bancos").select("*").order("nombre").execute()
    if rows.data:
        st.dataframe(pd.DataFrame(rows.data), use_container_width=True, hide_index=True)

    with st.expander("Nueva caja / cuenta"):
        with st.form("f_caja"):
            nombre = st.text_input("Nombre")
            tipo = st.selectbox("Tipo", ["Banco", "Wallet", "Efectivo"])
            if st.form_submit_button("Crear"):
                sb.table("cajas_bancos").insert({"nombre": nombre.strip(), "tipo": tipo, "saldo_actual_usd": 0}).execute()
                st.success("Caja creada.")
                st.rerun()

    cjrows = sb.table("cajas_bancos").select("id,nombre,tipo").eq("activo", True).execute()
    cj = {f"{c['nombre']} ({c['tipo']})": str(c["id"]) for c in (cjrows.data or [])}
    if not cj:
        st.stop()

    st.caption("Movimiento manual (ajuste de caja)")
    with st.form("f_mov"):
        lbl = st.selectbox("Caja", options=list(cj.keys()))
        tipo = st.selectbox("Tipo movimiento", ["Ingreso", "Egreso"])
        monto = st.number_input("Monto USD", min_value=0.01, format="%.2f")
        concepto = st.text_input("Concepto")
        ref = st.text_input("Referencia")
        if st.form_submit_button("Registrar"):
            try:
                sb.rpc(
                    "registrar_movimiento_caja_erp",
                    {
                        "p_usuario_id": erp_uid,
                        "p_caja_id": cj[lbl],
                        "p_tipo": tipo,
                        "p_monto_usd": float(monto),
                        "p_concepto": concepto,
                        "p_referencia": ref,
                    },
                ).execute()
                st.success("Movimiento registrado.")
                st.rerun()
            except Exception as e:
                st.error(str(e))


def panel_reportes_inventario_export(sb: Client, t: dict[str, Any] | None) -> None:
    if not t:
        st.warning("Registrá tasas en el **Dashboard** para que el reporte muestre referencias en Bs.")
        return
    st.caption(
        "Filtrá por categoría, costo o precio; descargá **Excel**, **PDF** o **HTML** para imprimir. "
        "Requiere `openpyxl` y `reportlab`."
    )
    try:
        cats_list_rp = (sb.table("categorias").select("id,nombre").order("nombre").execute().data or [])
    except Exception:
        cats_list_rp = []
    _id_rp, _, _ = _categoria_maps_from_rows(cats_list_rp)
    df = _inv_enrich_compat_columns(_normalize_productos_inventario_df(_fetch_productos_inventario_df(sb)))
    if not df.empty:
        if "categoria_id" in df.columns:
            df["categoria"] = df["categoria_id"].apply(
                lambda x: _id_rp.get(str(x).strip(), "")
                if x is not None and not (isinstance(x, float) and pd.isna(x)) and str(x).strip()
                else ""
            )
        else:
            df["categoria"] = ""
    else:
        df["categoria"] = pd.Series(dtype=object)

    _from_db = sorted(
        {str(c.get("nombre") or "").strip() for c in cats_list_rp if str(c.get("nombre") or "").strip()},
        key=str.casefold,
    )
    _from_prod = (
        sorted(
            {str(x) for x in df["categoria"].map(_inv_cat_display).tolist() if str(x).strip()},
            key=str.casefold,
        )
        if not df.empty and "categoria" in df.columns
        else []
    )
    _lab_cat = sorted(set(_from_db) | set(_from_prod), key=str.casefold)
    if not _lab_cat:
        _lab_cat = ["(Sin categoría)"]
    _pick_cat = st.multiselect(
        "Categorías a incluir en el reporte",
        options=_lab_cat,
        default=_lab_cat,
        key="rep_inv_print_cats",
    )
    _use_cats = _pick_cat if _pick_cat else _lab_cat
    _ic1, _ic2 = st.columns(2)
    with _ic1:
        _solo_act = st.checkbox("Solo productos activos", value=True, key="rep_inv_print_act")
    with _ic2:
        _agrup_cat = st.checkbox("Agrupar por categoría en el impreso", value=True, key="rep_inv_print_grp")
    _oc1, _oc2 = st.columns(2)
    with _oc1:
        st.markdown("**Costo USD**")
        _cmin = st.number_input("Desde (0 = sin mínimo)", min_value=0.0, value=0.0, step=0.01, key="rep_inv_cmin")
        _cmax = st.number_input("Hasta (0 = sin máximo)", min_value=0.0, value=0.0, step=0.01, key="rep_inv_cmax")
    with _oc2:
        st.markdown("**Precio venta USD**")
        _pmin = st.number_input("Desde (0 = sin mínimo)", min_value=0.0, value=0.0, step=0.01, key="rep_inv_pmin")
        _pmax = st.number_input("Hasta (0 = sin máximo)", min_value=0.0, value=0.0, step=0.01, key="rep_inv_pmax")
    _orden_lbl = st.selectbox(
        "Ordenar por",
        options=[
            "Descripción (A-Z)",
            "Código (A-Z)",
            "Costo USD: menor → mayor",
            "Costo USD: mayor → menor",
            "Precio venta USD: menor → mayor",
            "Precio venta USD: mayor → menor",
        ],
        key="rep_inv_sort",
    )
    _orden_map = {
        "Descripción (A-Z)": "descripcion",
        "Código (A-Z)": "codigo",
        "Costo USD: menor → mayor": "costo_asc",
        "Costo USD: mayor → menor": "costo_desc",
        "Precio venta USD: menor → mayor": "precio_asc",
        "Precio venta USD: mayor → menor": "precio_desc",
    }
    _orden_key = _orden_map[_orden_lbl]

    _df_p = _df_inventario_filtrado_impresion(
        df,
        categorias_sel=_use_cats,
        costo_min=float(_cmin),
        costo_max=float(_cmax),
        precio_min=float(_pmin),
        precio_max=float(_pmax),
        solo_activos=bool(_solo_act),
    )
    _parts_sub: list[str] = []
    if _pick_cat and len(_pick_cat) < len(_lab_cat):
        _parts_sub.append(f"categorías: {len(_pick_cat)} seleccionadas")
    if _cmin > 0 or _cmax > 0:
        _parts_sub.append(f"costo USD {_cmin if _cmin > 0 else '…'} — {_cmax if _cmax > 0 else '…'}")
    if _pmin > 0 or _pmax > 0:
        _parts_sub.append(f"precio USD {_pmin if _pmin > 0 else '…'} — {_pmax if _pmax > 0 else '…'}")
    _parts_sub.append(_orden_lbl)
    if _agrup_cat:
        _parts_sub.append("agrupado por categoría")
    _sub_f = " · ".join(_parts_sub)

    if _df_p.empty:
        st.warning("No hay productos con esos filtros. Igual podés descargar archivos con solo encabezados.")
        _df_out = _df_p
    else:
        _df_out = _df_inventario_orden_impresion(_df_p, _orden_key, agrupar_categoria=bool(_agrup_cat))
    _html_inv = _html_inventario_listado(
        _df_out, t, agrupar_categoria=bool(_agrup_cat), subtitulo_filtros=_sub_f
    )
    _df_flat = _df_inventario_export_flat(_df_out)
    _ts_p = _backup_file_timestamp()
    _bx, _bp = st.columns(2)
    with _bx:
        try:
            _xlsx_b = _xlsx_inventario_bytes(_df_flat)
        except ImportError:
            st.caption("Instalá **openpyxl** para Excel.")
        else:
            st.download_button(
                label=f"Excel — inventario_{_ts_p}.xlsx",
                data=_xlsx_b,
                file_name=f"inventario_{_ts_p}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="rep_inv_dl_xlsx",
                use_container_width=True,
            )
    with _bp:
        try:
            _pdf_b = _pdf_inventario_bytes(
                _df_out, t, agrupar_categoria=bool(_agrup_cat), subtitulo_filtros=_sub_f
            )
        except ImportError:
            st.caption("Instalá **reportlab** para PDF.")
        else:
            st.download_button(
                label=f"PDF — inventario_{_ts_p}.pdf",
                data=_pdf_b,
                file_name=f"inventario_{_ts_p}.pdf",
                mime="application/pdf",
                key="rep_inv_dl_pdf",
                use_container_width=True,
            )
    st.download_button(
        label=f"HTML — inventario_{_ts_p}.html",
        data=_html_inv.encode("utf-8"),
        file_name=f"inventario_{_ts_p}.html",
        mime="text/html",
        key="rep_inv_dl_html",
    )
    st.caption("Vista previa (Ctrl+P desde el recuadro o abrí el HTML descargado).")
    components.html(_html_inv, height=480, scrolling=True)


def module_reportes(sb: Client, t: dict[str, Any] | None) -> None:
    st.subheader("Reportes")
    if not t:
        st.stop()
    t_bs = float(t["tasa_bs"])
    t_usdt = float(t["tasa_usdt"])

    tab_inv, tab_ven, tab_comp = st.tabs(["Inventario", "Ventas y cobranzas", "Compras y pagos"])
    with tab_inv:
        st.markdown("#### Listados de inventario")
        panel_reportes_inventario_export(sb, t)

    with tab_ven:
        st.markdown("#### Ventas y análisis")
        d1, d2 = st.columns(2)
        a = d1.date_input("Desde", value=date.today() - timedelta(days=30), key="rep_ven_desde")
        b = d2.date_input("Hasta", value=date.today(), key="rep_ven_hasta")

        ventas = (
            sb.table("ventas")
            .select("numero, cliente, fecha, total_usd, forma_pago")
            .gte("fecha", str(a))
            .lte("fecha", f"{b}T23:59:59")
            .order("fecha", desc=True)
            .execute()
        )
        st.markdown("##### Ventas en el rango")
        if ventas.data:
            dfv = pd.DataFrame(ventas.data)
            dfv["equiv_bs"] = dfv["total_usd"].astype(float) * t_bs
            dfv["fecha_d"] = pd.to_datetime(dfv["fecha"]).dt.date.astype(str)
            st.dataframe(dfv, use_container_width=True, hide_index=True)
            agg = dfv.groupby("fecha_d", as_index=False)["total_usd"].sum()
            fig = px.bar(agg, x="fecha_d", y="total_usd", title="Total USD por día")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin ventas en el rango.")

        st.markdown("##### Utilidad bruta por producto (mismo rango)")
        vr = (
            sb.table("ventas")
            .select("id")
            .gte("fecha", str(a))
            .lte("fecha", f"{b}T23:59:59")
            .execute()
        )
        vids = [str(x["id"]) for x in (vr.data or [])]
        det_rows: list[dict[str, Any]] = []
        if vids:
            det = (
                sb.table("ventas_detalles")
                .select("producto_id, cantidad, precio_unitario_usd")
                .in_("venta_id", vids)
                .execute()
            )
            det_rows = det.data or []

        if det_rows:
            pmap = {
                str(p["id"]): p
                for p in (sb.table("productos").select("id,descripcion,costo_usd").execute().data or [])
            }
            rows = []
            for row in det_rows:
                pid = str(row["producto_id"])
                pr = pmap.get(pid, {})
                desc = pr.get("descripcion", pid)
                costo = float(pr.get("costo_usd") or 0)
                cant = float(row["cantidad"])
                pu = float(row["precio_unitario_usd"])
                margin = (pu - costo) * cant
                rows.append({"producto": desc, "utilidad_bruta_usd": margin})
            dfm = pd.DataFrame(rows).groupby("producto", as_index=False)["utilidad_bruta_usd"].sum()
            st.dataframe(dfm, use_container_width=True, hide_index=True)
            st.caption(fmt_tri(float(dfm["utilidad_bruta_usd"].sum()), t_bs, t_usdt))
        else:
            st.info("Sin líneas de venta en el rango.")

        st.markdown("##### Cuentas por cobrar")
        cxc = sb.table("cuentas_por_cobrar").select("*").execute()
        if cxc.data:
            dfc = pd.DataFrame(cxc.data)
            st.dataframe(dfc, use_container_width=True, hide_index=True)
            pend = dfc[dfc["estado"].isin(["Pendiente", "Parcial"])]["monto_pendiente_usd"].astype(float).sum()
            st.metric("Pendiente total USD", f"{pend:,.2f}")
            st.caption(fmt_tri(pend, t_bs, t_usdt))
        else:
            st.info("Sin CXC.")

    with tab_comp:
        st.markdown("#### Compras y cuentas por pagar")
        st.caption("Listado de compras por fechas: usá el módulo **Compras** para el detalle operativo.")
        st.markdown("##### Cuentas por pagar")
        cxp = sb.table("cuentas_por_pagar").select("*").execute()
        if cxp.data:
            dfp = pd.DataFrame(cxp.data)
            st.dataframe(dfp, use_container_width=True, hide_index=True)
            pend_p = dfp[dfp["estado"].isin(["Pendiente", "Parcial"])]["monto_pendiente_usd"].astype(float).sum()
            st.metric("Por pagar total USD", f"{pend_p:,.2f}")
            st.caption(fmt_tri(pend_p, t_bs, t_usdt))
        else:
            st.info("Sin CXP.")


def module_usuarios(sb: Client) -> None:
    st.subheader("Usuarios del sistema")
    st.caption("Solo el superusuario puede crear cuentas y definir la contraseña inicial de cada persona.")

    r = (
        sb.table("erp_users")
        .select("id,username,nombre,email,rol,activo,created_at")
        .order("nombre")
        .execute()
    )
    rows = r.data or []
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Nuevo usuario")
    with st.form("f_new_user"):
        nu = st.text_input("Usuario (solo letras/números, sin espacios)", key="nu_user")
        nn = st.text_input("Nombre completo", key="nu_nom")
        ne = st.text_input("Correo (opcional)", key="nu_mail")
        nr = st.selectbox(
            "Rol",
            options=["vendedor", "admin", "almacen", "superuser"],
            format_func=lambda x: {
                "vendedor": "Vendedor (ventas y cobros CXC)",
                "admin": "Administrador (compras, cajas, reportes, tasas…)",
                "almacen": "Almacén (solo inventario)",
                "superuser": "Superusuario (acceso total)",
            }[x],
            key="nu_rol",
        )
        p1 = st.text_input("Contraseña inicial", type="password", key="nu_p1")
        p2 = st.text_input("Repetir contraseña", type="password", key="nu_p2")
        if st.form_submit_button("Crear usuario"):
            un = (nu or "").strip().lower()
            if not un or not nn.strip():
                st.error("Usuario y nombre son obligatorios.")
            elif not p1 or p1 != p2:
                st.error("Las contraseñas no coinciden o están vacías.")
            elif len(p1) < 4:
                st.error("La contraseña debe tener al menos 4 caracteres.")
            else:
                ex = sb.table("erp_users").select("id").eq("username", un).limit(1).execute()
                if (ex.data or []):
                    st.error("Ese usuario ya existe.")
                else:
                    sb.table("erp_users").insert(
                        {
                            "username": un,
                            "nombre": nn.strip(),
                            "email": ne.strip() or None,
                            "rol": nr,
                            "password_hash": _hash_password(p1),
                            "activo": True,
                        }
                    ).execute()
                    st.success(f"Usuario **{un}** creado. Ya puede iniciar sesión.")
                    st.rerun()

    if not rows:
        return

    st.divider()
    st.markdown("#### Editar usuario")
    labels = {f"{u['nombre']} (@{u['username']})": u for u in rows}
    pick = st.selectbox("Seleccionar", options=list(labels.keys()))
    u = labels[pick]
    uid = str(u["id"])
    with st.form("f_edit_user"):
        act = st.checkbox("Activo", value=bool(u.get("activo", True)), key="ed_act")
        _roles = ["vendedor", "admin", "almacen", "superuser"]
        _ri = _roles.index(u["rol"]) if u["rol"] in _roles else 0
        new_rol = st.selectbox(
            "Rol",
            options=_roles,
            index=_ri,
            format_func=lambda x: {
                "vendedor": "Vendedor",
                "admin": "Administrador",
                "almacen": "Almacén",
                "superuser": "Superusuario",
            }[x],
            key="ed_rol",
        )
        np1 = st.text_input("Nueva contraseña (dejar vacío para no cambiar)", type="password", key="ed_p1")
        np2 = st.text_input("Repetir nueva contraseña", type="password", key="ed_p2")
        if st.form_submit_button("Guardar cambios"):
            if np1 or np2:
                if np1 != np2:
                    st.error("Las contraseñas nuevas no coinciden.")
                elif len(np1) < 4:
                    st.error("La contraseña debe tener al menos 4 caracteres.")
                else:
                    sb.table("erp_users").update(
                        {
                            "activo": act,
                            "rol": new_rol,
                            "password_hash": _hash_password(np1),
                        }
                    ).eq("id", uid).execute()
                    st.success("Usuario actualizado.")
                    st.rerun()
            else:
                sb.table("erp_users").update({"activo": act, "rol": new_rol}).eq("id", uid).execute()
                st.success("Usuario actualizado.")
                st.rerun()

    st.caption(
        "Si eres el único superusuario, evita desactivarte o quedarte sin contraseña."
    )


def render_cambiar_mi_password(sb: Client, erp_uid: str) -> None:
    if st.session_state.pop("pwd_updated_ok", False):
        st.success("Contraseña actualizada correctamente.")
    with st.expander("Cambiar mi contraseña", expanded=False):
        with st.form("f_mi_password"):
            cur = st.text_input("Contraseña actual", type="password", autocomplete="current-password")
            n1 = st.text_input("Nueva contraseña", type="password", autocomplete="new-password")
            n2 = st.text_input("Confirmar nueva contraseña", type="password", autocomplete="new-password")
            if st.form_submit_button("Guardar nueva contraseña"):
                if not cur or not n1 or not n2:
                    st.error("Completa todos los campos.")
                elif n1 != n2:
                    st.error("La nueva contraseña y la confirmación no coinciden.")
                elif len(n1) < 4:
                    st.error("La nueva contraseña debe tener al menos 4 caracteres.")
                elif n1 == cur:
                    st.error("La nueva contraseña debe ser distinta a la actual.")
                else:
                    r = (
                        sb.table("erp_users")
                        .select("password_hash")
                        .eq("id", erp_uid)
                        .limit(1)
                        .execute()
                    )
                    row = (r.data or [{}])[0]
                    ph = (row.get("password_hash") or "").strip()
                    if not ph or not _password_ok(cur, ph):
                        st.error("La contraseña actual no es correcta.")
                    else:
                        sb.table("erp_users").update({"password_hash": _hash_password(n1)}).eq("id", erp_uid).execute()
                        st.session_state["pwd_updated_ok"] = True
                        st.rerun()


def panel_respaldo_inventario_mantenimiento(sb: Client) -> None:
    """Respaldo y restauración JSON solo de categorías + productos (superusuario / Mantenimiento)."""
    st.caption(
        "Incluye **categorías** y **productos**. Para deshacer un cambio grande en el maestro de inventario. "
        "Si hay ventas o compras que usan esos productos, restaurar solo inventario puede fallar: en ese caso usá el **respaldo completo** arriba."
    )
    try:
        inv_payload = build_backup_inventario(sb)
        ts = _backup_file_timestamp()
        st.download_button(
            label=f"Descargar respaldo inventario — movi_inventario_{ts}.json",
            data=_json_backup_bytes(inv_payload),
            file_name=f"movi_inventario_{ts}.json",
            mime="application/json",
            key="mnt_dl_backup_inventario",
        )
        st.download_button(
            label=f"Mismo respaldo (.json.gz) — movi_inventario_{ts}.json.gz",
            data=_json_backup_bytes_compact_gzip(inv_payload),
            file_name=f"movi_inventario_{ts}.json.gz",
            mime="application/gzip",
            key="mnt_dl_backup_inventario_gz",
        )
        st.caption(
            f"**{len(inv_payload.get('categorias') or [])}** categorías · **{len(inv_payload.get('productos') or [])}** productos."
        )
    except Exception as e:
        st.error(f"No se pudo generar el respaldo de inventario: {e}")

    st.divider()
    st.markdown("**Restaurar inventario desde archivo**")
    up_inv = st.file_uploader("JSON o gzip de inventario", type=["json", "gz"], key="mnt_restore_inv_json")
    c_inv = st.text_input("Escribe **RESTAURAR_INVENTARIO** para confirmar", key="mnt_restore_inv_ok")
    if st.button("Restaurar inventario ahora", key="mnt_btn_restore_inv"):
        if up_inv is None:
            st.error("Subí el archivo JSON o .json.gz.")
        elif c_inv.strip() != "RESTAURAR_INVENTARIO":
            st.error("Confirmación incorrecta.")
        else:
            try:
                data_inv = decode_backup_upload_bytes(up_inv.getvalue())
            except Exception as ex:
                st.error(f"Archivo inválido: {ex}")
            else:
                ok_i, msg_i = restore_inventario_desde_json(sb, data_inv)
                if ok_i:
                    st.success(msg_i)
                    st.rerun()
                else:
                    st.error(msg_i)


def module_mantenimiento(sb: Client) -> None:
    st.subheader("Mantenimiento")
    st.markdown("#### Respaldo de seguridad")
    st.caption(
        "Generá un archivo **JSON** con las tablas principales del ERP (ventas, compras, caja, productos, tasas, etc.). "
        "**No** incluye `password_hash` de usuarios: si restaurás en otra base, tendrás que **reasignar contraseñas**."
    )
    try:
        full_payload = build_backup_erp_completo(sb)
        ts = _backup_file_timestamp()
        st.download_button(
            label=f"Descargar respaldo completo — movi_erp_completo_{ts}.json",
            data=_json_backup_bytes(full_payload),
            file_name=f"movi_erp_completo_{ts}.json",
            mime="application/json",
            key="dl_backup_erp_completo",
        )
        st.download_button(
            label=f"Descargar mismo respaldo (liviano .json.gz) — movi_erp_completo_{ts}.json.gz",
            data=_json_backup_bytes_compact_gzip(full_payload),
            file_name=f"movi_erp_completo_{ts}.json.gz",
            mime="application/gzip",
            key="dl_backup_erp_completo_gz",
        )
        st.caption(
            "**Respaldo automático diario** (superusuario): al abrir la app se guarda "
            f"`auto_backups/movi_erp_auto_YYYY-MM-DD.json.gz` (JSON sin indentar + gzip). "
            "Ejecutá `supabase/patch_010_erp_kv.sql` para coordinar el día en la nube. "
            "Opcional: en `secrets.toml`, `[auto_backup]` → `storage_bucket` = bucket privado en Supabase Storage (carpeta `auto/`). "
            "Los archivos locales antiguos se borran pasado `retain_days` (default 14). "
            "Podés **restaurar** subiendo `.json` o `.json.gz`."
        )
        err_part = full_payload.get("meta", {}).get("errores_al_exportar")
        if err_part:
            st.warning("Algunas tablas fallaron al exportar (revisá permisos o columnas en Supabase).")
            st.json(err_part)
    except Exception as e:
        st.error(f"No se pudo generar el respaldo completo: {e}")

    st.divider()
    st.markdown("#### Respaldo y restauración — solo inventario")
    panel_respaldo_inventario_mantenimiento(sb)

    st.divider()
    st.markdown("#### Restaurar todo desde respaldo (1 clic)")
    st.warning(
        "**Sobrescribe** movimientos, ventas, compras, CXC/CXP, productos, categorías, tasas del día y cajas con el contenido del JSON. "
        "**No borra** filas de `erp_users`: actualiza datos básicos y crea usuarios faltantes con clave **Restaurar2025!** (cambiar después). "
        "Hacé un respaldo reciente antes."
    )
    up_full = st.file_uploader(
        "Archivo **movi_erp_completo_*.json** o **.json.gz**", type=["json", "gz"], key="restore_full_json"
    )
    c_full = st.text_input("Confirmación: escribe **RESTAURAR_TODO**", key="restore_full_ok")
    if st.button("Restaurar todo ahora", type="primary", key="btn_restore_full"):
        if up_full is None:
            st.error("Subí el archivo JSON del respaldo completo.")
        elif c_full.strip() != "RESTAURAR_TODO":
            st.error("Escribí exactamente RESTAURAR_TODO para confirmar.")
        else:
            try:
                blob = decode_backup_upload_bytes(up_full.getvalue())
            except Exception as ex:
                st.error(f"Archivo inválido (JSON o gzip+JSON): {ex}")
            else:
                ok_r, msg_r, warns_r = restore_erp_completo_desde_json(sb, blob)
                if ok_r:
                    st.success(msg_r)
                    for w in warns_r:
                        st.warning(w)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg_r)
                    for w in warns_r:
                        st.warning(w)

    st.divider()
    st.markdown("#### Depuración (peligroso)")
    st.warning(
        "Elimina movimientos, ventas y compras. Reinicia saldos de cajas a 0. **No borra productos ni usuarios.** "
        "**Descargá antes el respaldo completo** de arriba."
    )
    palabra = st.text_input('Escribe ELIMINAR para confirmar')
    if st.button("Ejecutar depuración") and palabra.strip().upper() == "ELIMINAR":
        try:
            sb.table("movimientos_caja").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            sb.table("ventas").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            sb.table("compras").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            sb.table("cajas_bancos").update({"saldo_actual_usd": 0}).neq("id", "00000000-0000-0000-0000-000000000000").execute()
            st.success("Depuración aplicada.")
            st.rerun()
        except Exception as e:
            st.error(str(e))


def main() -> None:
    if not _secrets_ready():
        st.error(
            "Falta configuración en `.streamlit/secrets.toml`. "
            "Copia `.streamlit/secrets.toml.example` y completa la conexión a Supabase."
        )
        st.stop()

    sb = get_supabase()
    cm: Any | None = None
    if _cookie_support():
        try:
            cm = _erp_cookie_manager()
            _try_restore_session_from_cookie(sb, cm)
        except Exception:
            cm = None
    erp = gate_user_login(sb, cm)
    if not erp:
        st.stop()

    rol = str(erp["rol"])
    erp_uid = str(erp["id"])
    username = str(erp.get("username", ""))

    maybe_run_daily_auto_backup(sb, rol)
    _bk_err = st.session_state.pop("_movi_auto_backup_toast_err", None)
    if _bk_err:
        st.toast(f"Respaldo automático no aplicado: {_bk_err}")

    t = latest_tasas(sb)
    t_synced = maybe_auto_sync_tasas_from_web(sb)
    if t_synced is not None:
        t = t_synced
    _auto_msg = st.session_state.pop("_tasas_auto_sync_msg", None)
    if _auto_msg:
        st.toast(_auto_msg)
    _bk_ok = st.session_state.pop("_movi_auto_backup_toast", None)
    if _bk_ok:
        st.toast(_bk_ok)

    with st.sidebar:
        render_brand_logo()
        render_sidebar_welcome(nombre=str(erp.get("nombre", username)), username=username, rol=rol)
        render_sidebar_cotizaciones(t)
        render_cambiar_mi_password(sb, erp_uid)
        opts: list[str] = []
        if role_can(rol, "dashboard"):
            opts.append("Dashboard")
        if role_can(rol, "inventario"):
            opts.append("Inventario")
        if role_can(rol, "ventas"):
            opts.append("Ventas / CXC")
        if role_can(rol, "compras"):
            opts.append("Compras / CXP")
        if role_can(rol, "cajas"):
            opts.append("Cajas y bancos")
        if role_can(rol, "reportes"):
            opts.append("Reportes")
        if role_can(rol, "usuarios"):
            opts.append("Usuarios")
        if rol == "superuser":
            opts.append("Mantenimiento")
        if not opts:
            st.error("Tu rol no tiene módulos asignados. Pide al superusuario que revise tu cuenta.")
            st.stop()
        mod = st.radio("Módulo", opts, label_visibility="collapsed")
        if st.button("Salir", use_container_width=True):
            _logout()
            st.rerun()

    if mod == "Dashboard" and role_can(rol, "dashboard"):
        module_dashboard(sb, t)
    elif mod == "Inventario" and role_can(rol, "inventario"):
        module_inventario(sb, erp_uid, t)
    elif mod == "Ventas / CXC" and role_can(rol, "ventas"):
        module_ventas(sb, erp_uid, t)
    elif mod == "Compras / CXP" and role_can(rol, "compras"):
        module_compras(sb, erp_uid, t)
    elif mod == "Cajas y bancos" and role_can(rol, "cajas"):
        module_cajas(sb, erp_uid)
    elif mod == "Reportes" and role_can(rol, "reportes"):
        module_reportes(sb, t)
    elif mod == "Usuarios" and role_can(rol, "usuarios"):
        module_usuarios(sb)
    elif mod == "Mantenimiento" and rol == "superuser":
        module_mantenimiento(sb)


if __name__ == "__main__":
    main()
