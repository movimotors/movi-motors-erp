"""Dependencias inyectadas desde `app.py` para el módulo Reportes (todas las pestañas)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from supabase import Client


@dataclass(frozen=True)
class ReportesModuleDeps:
    modulo_titulo_info: Callable[..., None]
    dashboard_kpis_periodo: Callable[..., Any]
    panel_resumen_ejecutivo_periodo_ui: Callable[..., None]
    panel_reportes_inventario_export: Callable[[Client, dict[str, Any] | None], None]
    cajas_fetch_rows: Callable[..., Any]
    caja_select_options: Callable[[list[dict[str, Any]]], tuple[list[str], Any]]
    caja_etiqueta_lista: Callable[[dict[str, Any]], str]
    rep_movimientos_caja_filtrados: Callable[..., list[dict[str, Any]]]
    round_money_2: Callable[..., float]
    movimiento_monto_explicito_columnas: Callable[..., Any]
    backup_file_timestamp: Callable[[], str]
    reporte_tabla_a_excel: Callable[..., bytes]
    reporte_tabla_a_csv: Callable[[Any], bytes]
    rep_series_montos_enteros: Callable[..., Any]
    export_cell_txt: Callable[..., str]
    fmt_tri: Callable[[float, float, float], str]
    rep_texto_plazo_vencimiento: Callable[..., str]
    rep_bucket_antiguedad: Callable[..., str]
    panel_reportes_catalogo_fotos: Callable[[Client, str], None]
