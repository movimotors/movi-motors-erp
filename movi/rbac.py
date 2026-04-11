"""Roles y permisos por módulo."""

from __future__ import annotations

MOVI_MOD_ICONS: dict[str, str] = {
    "Dashboard": "📊",
    "Inventario": "📦",
    "Ventas / CXC": "🧾",
    "Compras / CXP": "📥",
    "Cajas y bancos": "🏦",
    "Gastos operativos": "💸",
    "Reportes": "📈",
    "Mantenimiento": "🛠️",
}


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
            "catalogo",
        }
    if rol == "vendedor":
        return module in {"ventas"}
    if rol == "almacen":
        return module in {"inventario", "catalogo"}
    return False


def movi_nav_options_for_role(rol: str) -> list[str]:
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
        opts.append("Gastos operativos")
    if role_can(rol, "reportes"):
        opts.append("Reportes")
    elif role_can(rol, "catalogo"):
        opts.append("Reportes")
    if rol == "superuser":
        opts.append("Mantenimiento")
    return opts
