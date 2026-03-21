-- =============================================================================
-- PATCH 013 — Historial de ajustes de stock (carga / descarga) sin venta ni compra
-- Ejecutar en Supabase SQL Editor (una vez). Requiere productos y erp_users.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.movimientos_inventario (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  producto_id UUID NOT NULL REFERENCES public.productos (id) ON DELETE CASCADE,
  tipo TEXT NOT NULL CHECK (tipo IN ('Entrada', 'Salida')),
  cantidad INT NOT NULL CHECK (cantidad > 0),
  motivo TEXT NOT NULL DEFAULT '',
  stock_antes INT NOT NULL,
  stock_despues INT NOT NULL,
  usuario_id UUID REFERENCES public.erp_users (id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_movimientos_inventario_producto
  ON public.movimientos_inventario (producto_id, created_at DESC);

COMMENT ON TABLE public.movimientos_inventario IS
  'Entrada/Salida manual de stock (ajuste, merma, hallazgo, etc.); no reemplaza ventas/compras.';

GRANT SELECT, INSERT, UPDATE, DELETE ON public.movimientos_inventario TO service_role;

NOTIFY pgrst, 'reload schema';
