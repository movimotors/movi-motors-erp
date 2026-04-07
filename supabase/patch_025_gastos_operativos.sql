-- patch_025: categoría de gasto operativo en movimientos_caja + RPC ampliado.
-- Ejecutar en Supabase (SQL editor) en bases que ya tienen patch_017 u equivalente.

ALTER TABLE public.movimientos_caja
  ADD COLUMN IF NOT EXISTS categoria_gasto TEXT;

COMMENT ON COLUMN public.movimientos_caja.categoria_gasto IS
  'Opcional. Categoría de gasto operativo (no compra de mercancía). NULL en movimientos de venta/compra/cobro.';

DROP FUNCTION IF EXISTS public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, TEXT, TEXT);

CREATE OR REPLACE FUNCTION public.registrar_movimiento_caja_erp(
  p_usuario_id UUID,
  p_caja_id UUID,
  p_tipo TEXT,
  p_monto_usd NUMERIC,
  p_concepto TEXT,
  p_referencia TEXT,
  p_nota_operacion TEXT DEFAULT NULL,
  p_categoria_gasto TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id UUID;
  v_cat TEXT;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.erp_users WHERE id = p_usuario_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Usuario ERP inválido o inactivo';
  END IF;

  IF p_tipo NOT IN ('Ingreso', 'Egreso') THEN
    RAISE EXCEPTION 'tipo inválido';
  END IF;

  IF p_monto_usd IS NULL OR p_monto_usd <= 0 THEN
    RAISE EXCEPTION 'monto inválido';
  END IF;

  IF p_concepto IS NULL OR TRIM(p_concepto) = '' THEN
    RAISE EXCEPTION 'concepto requerido';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = p_caja_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Caja inválida';
  END IF;

  v_cat := NULLIF(TRIM(p_categoria_gasto), '');
  IF v_cat IS NOT NULL AND p_tipo <> 'Egreso' THEN
    v_cat := NULL;
  END IF;

  INSERT INTO public.movimientos_caja (
    caja_id, tipo, monto_usd, concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id, categoria_gasto
  ) VALUES (
    p_caja_id,
    p_tipo,
    p_monto_usd,
    TRIM(p_concepto),
    NULLIF(TRIM(p_referencia), ''),
    NULLIF(TRIM(p_nota_operacion), ''),
    NULL,
    NULL,
    p_usuario_id,
    v_cat
  )
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, TEXT, TEXT) TO service_role;
