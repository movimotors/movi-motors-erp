"""Búsqueda asistida de productos: varias palabras (AND) sobre código, OEM, texto y compat."""

from __future__ import annotations

import json
from typing import Any


def _compat_as_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
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


def _compat_anos_str(d: dict[str, Any]) -> str:
    a = d.get("años") if "años" in d else d.get("anos")
    if a is None:
        return ""
    return str(a).strip()


def texto_busqueda_producto_dict(p: dict[str, Any]) -> str:
    """Texto en minúsculas para filtrar un registro `productos` (o fila API similar)."""
    parts: list[str] = []
    for k in ("descripcion", "codigo", "sku_oem", "marca_producto"):
        v = p.get(k)
        if v is not None and str(v).strip():
            parts.append(str(v))
    cat = p.get("categorias")
    if isinstance(cat, dict) and str(cat.get("nombre") or "").strip():
        parts.append(str(cat["nombre"]))
    elif isinstance(cat, list) and cat:
        c0 = cat[0]
        if isinstance(c0, dict) and str(c0.get("nombre") or "").strip():
            parts.append(str(c0["nombre"]))
    cid = p.get("categoria_id")
    if cid is not None and str(cid).strip():
        parts.append(str(cid))
    d = _compat_as_dict(p.get("compatibilidad"))
    for m in d.get("marcas_vehiculo") or d.get("marcas") or []:
        parts.append(str(m))
    parts.append(_compat_anos_str(d))
    for k in ("vehiculos_compat", "años_compat", "seriales_motor"):
        v = p.get(k)
        if v is not None and str(v).strip():
            parts.append(str(v))
    pid = str(p.get("id") or "").strip()
    if pid:
        parts.append(pid)
        parts.append(pid.replace("-", ""))
    return " ".join(parts).lower()


def coincide_busqueda_tokens(blob: str, q: str) -> bool:
    raw = (q or "").strip()
    if not raw:
        return True
    b = (blob or "").lower()
    tokens = [x for x in raw.lower().split() if x]
    if not tokens:
        return True
    return all(tok in b for tok in tokens)


def producto_dict_coincide(p: dict[str, Any], q: str) -> bool:
    return coincide_busqueda_tokens(texto_busqueda_producto_dict(p), q)


def filtrar_productos_por_busqueda(
    productos: list[dict[str, Any]],
    q: str,
    *,
    siempre_incluir_id: str | None = None,
    max_opciones: int = 450,
) -> list[dict[str, Any]]:
    """Filtra por consulta; mantiene el ítem `siempre_incluir_id` aunque no matchee (p. ej. línea ya elegida)."""
    sid = str(siempre_incluir_id or "").strip()
    base = [p for p in productos if producto_dict_coincide(p, q)]
    if sid:
        want = next((p for p in productos if str(p.get("id") or "").strip() == sid), None)
        if want is not None and not any(str(x.get("id") or "").strip() == sid for x in base):
            base = [want] + base
    if len(base) > max_opciones:
        return base[:max_opciones]
    return base
