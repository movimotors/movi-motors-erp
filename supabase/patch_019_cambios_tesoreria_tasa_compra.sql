-- patch_019: tasa a la que compraste (pactada) vs tasa de comparación opcional (BCV/mercado).
-- Ejecutar después de patch_018.

ALTER TABLE public.cambios_tesoreria ADD COLUMN IF NOT EXISTS tasa_compra_bs_por_usd NUMERIC(24, 8);

UPDATE public.cambios_tesoreria
SET tasa_compra_bs_por_usd = (monto_ves / NULLIF(monto_usd_obtenido, 0))
WHERE tasa_compra_bs_por_usd IS NULL;

UPDATE public.cambios_tesoreria
SET tasa_compra_bs_por_usd = tasa_referencia_bs_por_usd
WHERE tasa_compra_bs_por_usd IS NULL AND tasa_referencia_bs_por_usd IS NOT NULL;

UPDATE public.cambios_tesoreria SET tasa_compra_bs_por_usd = 1 WHERE tasa_compra_bs_por_usd IS NULL;

ALTER TABLE public.cambios_tesoreria ALTER COLUMN tasa_compra_bs_por_usd SET NOT NULL;

ALTER TABLE public.cambios_tesoreria DROP CONSTRAINT IF EXISTS cambios_tesoreria_tasa_compra_bs_por_usd_check;
ALTER TABLE public.cambios_tesoreria ADD CONSTRAINT cambios_tesoreria_tasa_compra_bs_por_usd_check CHECK (tasa_compra_bs_por_usd > 0);

ALTER TABLE public.cambios_tesoreria DROP CONSTRAINT IF EXISTS cambios_tesoreria_tasa_referencia_bs_por_usd_check;
ALTER TABLE public.cambios_tesoreria ALTER COLUMN tasa_referencia_bs_por_usd DROP NOT NULL;
ALTER TABLE public.cambios_tesoreria ADD CONSTRAINT cambios_tesoreria_tasa_ref_opcional_chk CHECK (tasa_referencia_bs_por_usd IS NULL OR tasa_referencia_bs_por_usd > 0);

DROP FUNCTION IF EXISTS public.registrar_cambio_tesoreria_erp(UUID, UUID, UUID, NUMERIC, NUMERIC, NUMERIC, TEXT, TIMESTAMPTZ);

CREATE OR REPLACE FUNCTION public.registrar_cambio_tesoreria_erp(
  p_usuario_id UUID,
  p_caja_origen_id UUID,
  p_caja_destino_id UUID,
  p_monto_ves NUMERIC,
  p_monto_usd_obtenido NUMERIC,
  p_tasa_compra_bs_por_usd NUMERIC,
  p_tasa_comparacion_bs_por_usd NUMERIC DEFAULT NULL,
  p_nota TEXT DEFAULT NULL,
  p_fecha TIMESTAMPTZ DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id UUID;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.erp_users WHERE id = p_usuario_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Usuario ERP inválido o inactivo';
  END IF;

  IF p_monto_ves IS NULL OR p_monto_ves <= 0 THEN
    RAISE EXCEPTION 'Monto en bolívares inválido';
  END IF;
  IF p_monto_usd_obtenido IS NULL OR p_monto_usd_obtenido <= 0 THEN
    RAISE EXCEPTION 'Monto USD obtenido inválido';
  END IF;
  IF p_tasa_compra_bs_por_usd IS NULL OR p_tasa_compra_bs_por_usd <= 0 THEN
    RAISE EXCEPTION 'Tasa de compra Bs/USD inválida';
  END IF;
  IF p_tasa_comparacion_bs_por_usd IS NOT NULL AND p_tasa_comparacion_bs_por_usd <= 0 THEN
    RAISE EXCEPTION 'Tasa de comparación Bs/USD inválida (debe ser NULL o > 0)';
  END IF;

  IF p_caja_origen_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = p_caja_origen_id) THEN
    RAISE EXCEPTION 'Caja origen no existe';
  END IF;
  IF p_caja_destino_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = p_caja_destino_id) THEN
    RAISE EXCEPTION 'Caja destino no existe';
  END IF;

  INSERT INTO public.cambios_tesoreria (
    fecha,
    caja_origen_id,
    caja_destino_id,
    monto_ves,
    monto_usd_obtenido,
    tasa_compra_bs_por_usd,
    tasa_referencia_bs_por_usd,
    nota,
    usuario_id
  ) VALUES (
    COALESCE(p_fecha, NOW()),
    p_caja_origen_id,
    p_caja_destino_id,
    ROUND(p_monto_ves, 4),
    ROUND(p_monto_usd_obtenido, 4),
    p_tasa_compra_bs_por_usd,
    p_tasa_comparacion_bs_por_usd,
    NULLIF(TRIM(p_nota), ''),
    p_usuario_id
  )
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.registrar_cambio_tesoreria_erp(UUID, UUID, UUID, NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, TIMESTAMPTZ) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.registrar_cambio_tesoreria_erp(UUID, UUID, UUID, NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, TIMESTAMPTZ) TO service_role;

NOTIFY pgrst, 'reload schema';
