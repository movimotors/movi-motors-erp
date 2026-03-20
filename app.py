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
import hashlib
import hmac
import html
import json
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import bcrypt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from supabase import Client


_APP_DIR = Path(__file__).resolve().parent
BRAND_LOGO_PATH = _APP_DIR / "assets" / "logo_movimotors.png"


def brand_logo_file() -> str | None:
    return str(BRAND_LOGO_PATH) if BRAND_LOGO_PATH.is_file() else None


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


def _fetch_productos_inventario_df(sb: Client) -> pd.DataFrame:
    cols_full = (
        "id,codigo,descripcion,stock_actual,stock_minimo,costo_usd,precio_v_usd,"
        "precio_v_bs_ref,costo_bs_ref,activo"
    )
    cols_base = "id,codigo,descripcion,stock_actual,stock_minimo,costo_usd,precio_v_usd,activo"
    try:
        r = sb.table("productos").select(cols_full).order("descripcion").execute()
    except Exception:
        r = sb.table("productos").select(cols_base).order("descripcion").execute()
    return pd.DataFrame(r.data or [])


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


def module_inventario(sb: Client, t: dict[str, Any] | None) -> None:
    st.subheader("Inventario")
    if not t:
        st.warning("Registre tasas en **Dashboard** (expander *Cargar / editar tasas en base de datos*) para ver equivalentes.")

    cats = sb.table("categorias").select("id,nombre").order("nombre").execute()
    cat_opts = {c["nombre"]: c["id"] for c in (cats.data or [])}

    with st.expander("Nueva categoría"):
        with st.form("f_cat"):
            cn = st.text_input("Nombre categoría")
            if st.form_submit_button("Crear") and cn.strip():
                sb.table("categorias").insert({"nombre": cn.strip()}).execute()
                st.success("Categoría creada.")
                st.rerun()

    with st.expander("Nuevo producto"):
        with st.form("f_prod"):
            codigo = st.text_input("Código")
            desc = st.text_input("Descripción", max_chars=500)
            stock = st.number_input("Stock actual", min_value=0.0, value=0.0, step=0.001, format="%.3f")
            smin = st.number_input("Stock mínimo", min_value=0.0, value=0.0, step=0.001, format="%.3f")
            costo = st.number_input("Costo USD", min_value=0.0, value=0.0, format="%.2f")
            pv = st.number_input("Precio venta USD", min_value=0.0, value=0.0, format="%.2f")
            cname = st.selectbox("Categoría", options=[""] + list(cat_opts.keys()))
            cid = cat_opts.get(cname) if cname else None
            if st.form_submit_button("Guardar producto"):
                sb.table("productos").insert(
                    {
                        "codigo": codigo.strip() or None,
                        "descripcion": desc.strip() or "Sin descripción",
                        "stock_actual": float(stock),
                        "stock_minimo": float(smin),
                        "costo_usd": float(costo),
                        "precio_v_usd": float(pv),
                        "categoria_id": cid,
                        "activo": True,
                    }
                ).execute()
                st.success("Producto creado.")
                st.rerun()

    st.caption("Carga masiva (CSV): columnas codigo,descripcion,stock_actual,stock_minimo,costo_usd,precio_v_usd")
    up = st.file_uploader("CSV", type=["csv"])
    if up is not None:
        df = pd.read_csv(up)
        required = {
            "codigo",
            "descripcion",
            "stock_actual",
            "stock_minimo",
            "costo_usd",
            "precio_v_usd",
        }
        if not required.issubset(set(df.columns.str.lower())):
            st.error(f"Faltan columnas. Requeridas: {required}")
        else:
            df.columns = [c.lower() for c in df.columns]
            if st.button("Insertar filas"):
                rows = df.to_dict(orient="records")
                for row in rows:
                    sb.table("productos").insert(
                        {
                            "codigo": str(row["codigo"]).strip() or None,
                            "descripcion": str(row["descripcion"]),
                            "stock_actual": float(row["stock_actual"]),
                            "stock_minimo": float(row["stock_minimo"]),
                            "costo_usd": float(row["costo_usd"]),
                            "precio_v_usd": float(row["precio_v_usd"]),
                            "activo": True,
                        }
                    ).execute()
                st.success(f"Insertados {len(rows)} productos.")
                st.rerun()

    df = _fetch_productos_inventario_df(sb)
    if df.empty:
        st.info("No hay productos.")
        return

    st.caption(
        "Columnas **precio_v_bs_ref** y **costo_bs_ref**: referencia en Bs según la última **tasa_bs** "
        "guardada (se actualizan al guardar tasas o al auto-sync web). Los precios maestros siguen en USD."
    )
    crit = df[df["stock_actual"].astype(float) <= df["stock_minimo"].astype(float)]
    if len(crit):
        st.error(f"Alertas de stock crítico: {len(crit)} ítems")
        st.dataframe(crit, use_container_width=True, hide_index=True)

    _disabled_cols = ["id"]
    if "precio_v_bs_ref" in df.columns:
        _disabled_cols.extend(["precio_v_bs_ref", "costo_bs_ref"])
    edited = st.data_editor(
        df,
        num_rows="fixed",
        disabled=_disabled_cols,
        use_container_width=True,
        key="editor_prod",
    )
    if st.button("Guardar cambios de inventario"):
        for _, row in edited.iterrows():
            sb.table("productos").update(
                {
                    "codigo": row.get("codigo"),
                    "descripcion": row.get("descripcion"),
                    "stock_actual": float(row.get("stock_actual", 0)),
                    "stock_minimo": float(row.get("stock_minimo", 0)),
                    "costo_usd": float(row.get("costo_usd", 0)),
                    "precio_v_usd": float(row.get("precio_v_usd", 0)),
                    "activo": bool(row.get("activo", True)),
                }
            ).eq("id", str(row["id"])).execute()
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
            {"producto_id": str(plist[0]["id"]), "cantidad": 1.0, "precio_unitario_usd": id_to_price[str(plist[0]["id"])]}
        ]

    with st.form("f_venta"):
        cliente = st.text_input("Cliente")
        forma = st.selectbox("Forma de pago", ["contado", "credito"])
        caja_label = st.selectbox("Caja (solo contado)", options=list(cj.keys())) if cj else None
        fv = st.date_input("Vencimiento (crédito)", value=date.today() + timedelta(days=30))
        notas = st.text_area("Notas")

        doc_tasa = st.radio(
            "Tasa Bs/USD para esta venta (equivalente en bolívares y registro en BD):",
            options=DOC_TASA_BS_OPTS,
            index=_infer_tasa_bs_oper_index(t),
            horizontal=True,
            key="venta_doc_tasa_bs",
            help="No cambia los montos en USD de las líneas; solo qué Bs/USD se asocia a la venta.",
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
            qty = c2.number_input("Cant.", min_value=0.001, value=float(line.get("cantidad", 1)), step=0.001, format="%.3f", key=f"vq_{i}")
            pu = c3.number_input("P.U. USD", min_value=0.0, value=float(id_to_price.get(pid, 0)), format="%.2f", key=f"vpu_{i}")
            new_lines.append({"producto_id": pid, "cantidad": float(qty), "precio_unitario_usd": float(pu)})

        if st.form_submit_button("Registrar venta (atómica)"):
            try:
                t_bs_doc = _tasa_bs_para_documento(t, usar_bcv=(doc_tasa == DOC_TASA_BS_OPTS[0]))
            except ValueError as e:
                st.error(str(e))
            else:
                payload = {
                    "p_usuario_id": erp_uid,
                    "p_cliente": cliente,
                    "p_forma_pago": forma,
                    "p_caja_id": cj[caja_label] if forma == "contado" and caja_label else None,
                    "p_tasa_bs": t_bs_doc,
                    "p_tasa_usdt": t_usdt,
                    "p_fecha_vencimiento": str(fv) if forma == "credito" else None,
                    "p_notas": notas,
                    "p_lineas": new_lines,
                }
                try:
                    sb.rpc("crear_venta_erp", payload).execute()
                    st.success("Venta registrada.")
                    st.session_state["venta_lines"] = [
                        {
                            "producto_id": str(plist[0]["id"]),
                            "cantidad": 1.0,
                            "precio_unitario_usd": id_to_price[str(plist[0]["id"])],
                        }
                    ]
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo registrar: {e}")

    if st.button("Añadir línea"):
        st.session_state["venta_lines"].append(
            {"producto_id": str(plist[0]["id"]), "cantidad": 1.0, "precio_unitario_usd": id_to_price[str(plist[0]["id"])]}
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
            {"producto_id": str(plist[0]["id"]), "cantidad": 1.0, "costo_unitario_usd": id_to_cost[str(plist[0]["id"])]}
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
            qty = c2.number_input("Cant.", min_value=0.001, value=float(line.get("cantidad", 1)), step=0.001, format="%.3f", key=f"cq_{i}")
            cu = c3.number_input("Costo u. USD", min_value=0.0, value=float(id_to_cost.get(pid, 0)), format="%.2f", key=f"ccu_{i}")
            new_lines.append({"producto_id": pid, "cantidad": float(qty), "costo_unitario_usd": float(cu)})

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
                            "cantidad": 1.0,
                            "costo_unitario_usd": id_to_cost[str(plist[0]["id"])],
                        }
                    ]
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo registrar: {e}")

    if st.button("Añadir línea compra"):
        st.session_state["compra_lines"].append(
            {"producto_id": str(plist[0]["id"]), "cantidad": 1.0, "costo_unitario_usd": id_to_cost[str(plist[0]["id"])]}
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


def module_reportes(sb: Client, t: dict[str, Any] | None) -> None:
    st.subheader("Reportes")
    if not t:
        st.stop()
    t_bs = float(t["tasa_bs"])
    t_usdt = float(t["tasa_usdt"])

    d1, d2 = st.columns(2)
    a = d1.date_input("Desde", value=date.today() - timedelta(days=30))
    b = d2.date_input("Hasta", value=date.today())

    ventas = (
        sb.table("ventas")
        .select("numero, cliente, fecha, total_usd, forma_pago")
        .gte("fecha", str(a))
        .lte("fecha", f"{b}T23:59:59")
        .order("fecha", desc=True)
        .execute()
    )
    st.markdown("#### Ventas en rango")
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

    st.markdown("#### Utilidad bruta por producto (histórico ventas en rango)")
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

    st.markdown("#### Cuentas por cobrar")
    cxc = sb.table("cuentas_por_cobrar").select("*").execute()
    if cxc.data:
        dfc = pd.DataFrame(cxc.data)
        st.dataframe(dfc, use_container_width=True, hide_index=True)
        pend = dfc[dfc["estado"].isin(["Pendiente", "Parcial"])]["monto_pendiente_usd"].astype(float).sum()
        st.metric("Pendiente total USD", f"{pend:,.2f}")
        st.caption(fmt_tri(pend, t_bs, t_usdt))
    else:
        st.info("Sin CXC.")

    st.markdown("#### Cuentas por pagar")
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


def module_mantenimiento(sb: Client) -> None:
    st.subheader("Mantenimiento (peligroso)")
    st.warning("Elimina movimientos, ventas y compras. Reinicia saldos de cajas a 0. No borra productos ni usuarios.")
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

    t = latest_tasas(sb)
    t_synced = maybe_auto_sync_tasas_from_web(sb)
    if t_synced is not None:
        t = t_synced
    _auto_msg = st.session_state.pop("_tasas_auto_sync_msg", None)
    if _auto_msg:
        st.toast(_auto_msg)

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
        module_inventario(sb, t)
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
