"""
Módulo **Reportes** partido por pestaña para facilitar cambios:

- `layout.py` — permisos, título Streamlit y enrutado de tabs
- `deps.py` — `ReportesModuleDeps` (inyectado desde `app.py`)
- `tab_resumen.py` — Resumen ejecutivo
- `tab_inventario.py` — Export inventario (delega en `panel_reportes_inventario_export`)
- `tab_caja.py` — Movimientos de caja
- `tab_ventas.py` — Ventas y detalle
- `tab_compras.py` — Compras, detalle y CXP
- `tab_cartera.py` — Cobrar / pagar
- `tab_catalogo.py` — Catálogo y fotos (delega en `panel_reportes_catalogo_fotos`)
"""

from movi.modules.reportes.deps import ReportesModuleDeps
from movi.modules.reportes.layout import render_module_reportes

__all__ = ["ReportesModuleDeps", "render_module_reportes"]
