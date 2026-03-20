-- =============================================================================
-- PATCH 011 — Repuestos: OEM, marca del producto, vehículos (JSON), condición,
--               ubicación, imagen; stock en unidades enteras (sin decimales).
-- Ejecutar en Supabase SQL Editor (una vez). Luego: NOTIFY ya recarga PostgREST.
-- =============================================================================
--
-- JSON compatibilidad (lo usa la app Streamlit):
--   {"marcas_vehiculo": ["Toyota", "Ford"], "años": "2010-2015"}
--   (También se lee la clave legacy "marcas" si existiera en datos viejos.)
--
-- =============================================================================

-- Columnas nuevas (idempotente)
ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS sku_oem TEXT,
  ADD COLUMN IF NOT EXISTS marca_producto TEXT,
  ADD COLUMN IF NOT EXISTS condicion TEXT NOT NULL DEFAULT 'Nuevo'
    CHECK (condicion IN ('Nuevo', 'Usado')),
  ADD COLUMN IF NOT EXISTS ubicacion TEXT,
  ADD COLUMN IF NOT EXISTS compatibilidad JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS imagen_url TEXT;

COMMENT ON COLUMN public.productos.sku_oem IS 'Código de parte / OEM / referencia fabricante';
COMMENT ON COLUMN public.productos.marca_producto IS 'Marca del repuesto (Bosch, Denso, etc.)';
COMMENT ON COLUMN public.productos.condicion IS 'Nuevo o Usado';
COMMENT ON COLUMN public.productos.ubicacion IS 'Estante, pasillo, ubicación física';
COMMENT ON COLUMN public.productos.compatibilidad IS 'Marcas de carro y años: marcas_vehiculo[], años';
COMMENT ON COLUMN public.productos.imagen_url IS 'URL en Storage u otro';

CREATE INDEX IF NOT EXISTS idx_productos_compatibilidad_gin
  ON public.productos USING GIN (compatibilidad jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_productos_sku_oem_lower
  ON public.productos (lower(sku_oem))
  WHERE sku_oem IS NOT NULL AND btrim(sku_oem) <> '';

CREATE INDEX IF NOT EXISTS idx_productos_marca_prod_lower
  ON public.productos (lower(marca_producto))
  WHERE marca_producto IS NOT NULL AND btrim(marca_producto) <> '';

-- Stock y mínimo como enteros (repuestos por unidad)
ALTER TABLE public.productos DROP CONSTRAINT IF EXISTS productos_stock_actual_check;
ALTER TABLE public.productos DROP CONSTRAINT IF EXISTS productos_stock_minimo_check;

ALTER TABLE public.productos
  ALTER COLUMN stock_actual TYPE INT4 USING ROUND(COALESCE(stock_actual, 0))::INT,
  ALTER COLUMN stock_minimo TYPE INT4 USING ROUND(COALESCE(stock_minimo, 0))::INT;

ALTER TABLE public.productos
  ADD CONSTRAINT productos_stock_actual_check CHECK (stock_actual >= 0),
  ADD CONSTRAINT productos_stock_minimo_check CHECK (stock_minimo >= 0);

NOTIFY pgrst, 'reload schema';
