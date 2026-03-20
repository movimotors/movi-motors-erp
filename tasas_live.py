"""
Tasas de referencia desde internet (sin API keys).
- USD→VES: open.er-api.com (agregador; NO es el BCV oficial).
- EUR→USD: Frankfurter (BCE).
- USDT→VES (P2P): Binance P2P (mediana de anuncios); fallback al VES/USD de la API si falla.
"""

from __future__ import annotations

import json
import ssl
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = "MoviMotors-ERP/1.0 (Streamlit; contacto local)"

BINANCE_P2P_SEARCH = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"


def _urlopen(req: Request, timeout: float = 25.0):
    try:
        return urlopen(req, timeout=timeout, context=ssl.create_default_context())
    except ssl.SSLError:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return urlopen(req, timeout=timeout, context=ctx)


def _get_json(url: str, timeout: float = 25.0) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with _urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, body: dict[str, Any], *, headers: dict[str, str] | None = None, timeout: float = 25.0) -> dict[str, Any]:
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    h = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }
    if headers:
        h.update(headers)
    req = Request(url, data=raw, headers=h, method="POST")
    with _urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# Sin cabeceras de navegador, Binance suele responder code 000002 (bloqueo/WAF).
_BINANCE_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Origin": "https://p2p.binance.com",
    "Referer": "https://p2p.binance.com/trade/all-payments/USDT?fiat=VES",
    "Accept": "application/json",
}


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    m = n // 2
    if n % 2:
        return s[m]
    return (s[m - 1] + s[m]) / 2.0


def fetch_binance_p2p_usdt_ves(
    *,
    trade_type: str = "BUY",
    rows: int = 20,
) -> tuple[float | None, str | None]:
    """
    Precio de mercado P2P: Bs (VES) por 1 USDT.
    tradeType BUY = anuncios de quienes venden USDT a cambio de Bs (tú compras USDT).
    """
    body: dict[str, Any] = {
        "asset": "USDT",
        "fiat": "VES",
        "tradeType": trade_type,
        "page": 1,
        "rows": min(20, max(1, int(rows))),
        "payTypes": [],
        "publisherType": None,
        "merchantCheck": False,
    }
    try:
        d = _post_json(BINANCE_P2P_SEARCH, body, headers=_BINANCE_BROWSER_HEADERS, timeout=25.0)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError, TypeError) as e:
        return None, f"Binance P2P: {e}"

    if str(d.get("code")) != "000000":
        return None, f"Binance P2P: API code {d.get('code')!r}"

    data = d.get("data")
    if not isinstance(data, list) or not data:
        return None, "Binance P2P: sin anuncios en la respuesta"

    prices: list[float] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        adv = item.get("adv")
        if not isinstance(adv, dict):
            continue
        p = adv.get("price")
        try:
            v = float(p)
        except (TypeError, ValueError):
            continue
        if v > 0:
            prices.append(v)

    med = _median(prices)
    if med is None:
        return None, "Binance P2P: no se pudo leer precios válidos"
    return med, None


def fetch_live_rates() -> dict[str, Any]:
    """
    Devuelve tasas en vivo y metadatos. No lanza: errores van en 'errors'.
    """
    out: dict[str, Any] = {
        "ok": False,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "errors": [],
        "sources": [],
        "ves_bs_por_usd": None,
        "usd_por_eur": None,
        "usdt_por_usd": 1.0,
        "p2p_bs_por_usdt_aprox": None,
        "usdt_x_ves_p2p": None,
        "usdt_x_ves_p2p_source": None,
    }

    try:
        d = _get_json("https://open.er-api.com/v6/latest/USD")
        rates = d.get("rates") or {}
        ves = rates.get("VES")
        if ves is not None:
            out["ves_bs_por_usd"] = float(ves)
        out["sources"].append("open.er-api.com (USD→VES, referencia mercado)")
        out["time_next_update_utc"] = d.get("time_next_update_utc")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError, TypeError) as e:
        out["errors"].append(f"USD/VES: {e}")

    try:
        d2 = _get_json("https://api.frankfurter.app/latest?from=EUR&to=USD")
        usd = (d2.get("rates") or {}).get("USD")
        if usd is not None:
            out["usd_por_eur"] = float(usd)
        out["sources"].append("api.frankfurter.app (1 EUR = X USD)")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError, TypeError) as e:
        out["errors"].append(f"EUR/USD: {e}")

    p2p_med, p2p_err = fetch_binance_p2p_usdt_ves(trade_type="BUY", rows=20)
    if p2p_err:
        out["errors"].append(p2p_err)
    v = out.get("ves_bs_por_usd")

    if p2p_med is not None and p2p_med > 0:
        out["p2p_bs_por_usdt_aprox"] = float(p2p_med)
        out["usdt_x_ves_p2p"] = float(p2p_med)
        out["usdt_x_ves_p2p_source"] = "binance_p2p_median_buy"
        out["sources"].append(
            "p2p.binance.com — mediana Bs por 1 USDT (hasta 20 anuncios, comprar USDT con VES)"
        )
    elif v is not None and float(v) > 0:
        out["p2p_bs_por_usdt_aprox"] = float(v)
        out["usdt_x_ves_p2p"] = float(v)
        out["usdt_x_ves_p2p_source"] = "fallback_same_as_usd_ves_api"
        out["sources"].append(
            "USDT×VES: fallback = mismo Bs/USD que open.er-api (Binance P2P no disponible)"
        )

    upe = out.get("usd_por_eur")
    if v is not None and upe is not None and float(v) > 0 and float(upe) > 0:
        out["eur_x_ves"] = float(v) * float(upe)

    if v is not None:
        out["usd_x_bs"] = float(v)

    out["ok"] = bool(
        out.get("ves_bs_por_usd") is not None
        or out.get("usd_por_eur") is not None
        or out.get("usdt_x_ves_p2p") is not None
    )
    return out
