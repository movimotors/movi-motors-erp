-- Equivalentes en Bs guardados en productos (se recalculan al sincronizar tasa web desde la app).
-- Ejecutar en Supabase SQL Editor después de tener tasas_dia con columnas extendidas.

ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS precio_v_bs_ref NUMERIC(18, 4),
  ADD COLUMN IF NOT EXISTS costo_bs_ref NUMERIC(18, 4);

COMMENT ON COLUMN public.productos.precio_v_bs_ref IS 'Precio venta en Bs según última tasa_bs sincronizada (referencia)';
COMMENT ON COLUMN public.productos.costo_bs_ref IS 'Costo en Bs según última tasa_bs sincronizada (referencia)';

CREATE OR REPLACE FUNCTION public.refresh_productos_bs_equiv(p_tasa_bs NUMERIC)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.productos
  SET
    precio_v_bs_ref = ROUND((precio_v_usd * p_tasa_bs)::numeric, 4),
    costo_bs_ref = ROUND((costo_usd * p_tasa_bs)::numeric, 4),
    updated_at = NOW()
  WHERE activo = TRUE
    AND p_tasa_bs IS NOT NULL
    AND p_tasa_bs > 0;
$$;

REVOKE ALL ON FUNCTION public.refresh_productos_bs_equiv(NUMERIC) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.refresh_productos_bs_equiv(NUMERIC) TO service_role;

NOTIFY pgrst, 'reload schema';
