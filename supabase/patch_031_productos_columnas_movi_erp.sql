-- =============================================================================
-- PATCH 031 — Columnas extendidas en public.productos
--   (nombre_producto, modelo, marca_id, precio_costo, precio_venta_detal).
-- Ejecutar UNA VEZ en Supabase SQL Editor.
-- Mantiene costo_usd / precio_v_usd en sync vía trigger (columnas duplicadas alineadas).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1) Columnas nuevas (idempotente)
-- -----------------------------------------------------------------------------
ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS nombre_producto TEXT;

ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS modelo TEXT;

ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS marca_id UUID REFERENCES public.marcas (id) ON DELETE SET NULL;

ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS precio_costo NUMERIC(14, 2);

ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS precio_venta_detal NUMERIC(14, 2);

COMMENT ON COLUMN public.productos.nombre_producto IS 'Nombre corto / título (UI; opcional si se usa solo descripcion)';
COMMENT ON COLUMN public.productos.modelo IS 'Modelo de parte o referencia comercial';
COMMENT ON COLUMN public.productos.marca_id IS 'FK a marcas (catálogo); opcional; marca_producto sigue siendo texto libre';
COMMENT ON COLUMN public.productos.precio_costo IS 'Costo en USD; sincronizado con costo_usd';
COMMENT ON COLUMN public.productos.precio_venta_detal IS 'Precio venta detalle USD; sincronizado con precio_v_usd';

CREATE INDEX IF NOT EXISTS idx_productos_marca_id
  ON public.productos (marca_id)
  WHERE marca_id IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 2) Rellenar desde columnas legacy ya existentes
-- -----------------------------------------------------------------------------
UPDATE public.productos
SET precio_costo = COALESCE(precio_costo, costo_usd, 0)
WHERE precio_costo IS NULL;

UPDATE public.productos
SET precio_venta_detal = COALESCE(precio_venta_detal, precio_v_usd, 0)
WHERE precio_venta_detal IS NULL;

-- -----------------------------------------------------------------------------
-- 3) Trigger: una sola fuente de verdad por par (costo / precio venta)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.productos_sync_precios_movi_erp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  v_costo NUMERIC(14, 2);
  v_venta NUMERIC(14, 2);
BEGIN
  v_costo := COALESCE(NEW.precio_costo, NEW.costo_usd, 0);
  v_venta := COALESCE(NEW.precio_venta_detal, NEW.precio_v_usd, 0);

  IF v_costo < 0 THEN
    v_costo := 0;
  END IF;
  IF v_venta < 0 THEN
    v_venta := 0;
  END IF;

  NEW.precio_costo := v_costo;
  NEW.costo_usd := v_costo;
  NEW.precio_venta_detal := v_venta;
  NEW.precio_v_usd := v_venta;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_productos_sync_precios_movi_erp ON public.productos;

CREATE TRIGGER trg_productos_sync_precios_movi_erp
  BEFORE INSERT OR UPDATE OF precio_costo, costo_usd, precio_venta_detal, precio_v_usd
  ON public.productos
  FOR EACH ROW
  EXECUTE FUNCTION public.productos_sync_precios_movi_erp();

COMMENT ON FUNCTION public.productos_sync_precios_movi_erp() IS
  'PATCH 031: alinea precio_costo↔costo_usd y precio_venta_detal↔precio_v_usd en cada escritura.';

-- -----------------------------------------------------------------------------
-- 4) PostgREST
-- -----------------------------------------------------------------------------
NOTIFY pgrst, 'reload schema';
