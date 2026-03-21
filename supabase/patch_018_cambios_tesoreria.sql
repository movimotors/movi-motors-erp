-- patch_018: bitácora cambios Bs → USD/estable (seguimiento vs tasa referencia) + RPC.
-- Ejecutar en Supabase SQL Editor después de patch_015 (cajas detalle) u orden habitual de patches.

CREATE TABLE IF NOT EXISTS public.cambios_tesoreria (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  caja_origen_id UUID REFERENCES public.cajas_bancos (id) ON DELETE SET NULL,
  caja_destino_id UUID REFERENCES public.cajas_bancos (id) ON DELETE SET NULL,
  monto_ves NUMERIC(22, 4) NOT NULL CHECK (monto_ves > 0),
  monto_usd_obtenido NUMERIC(18, 4) NOT NULL CHECK (monto_usd_obtenido > 0),
  tasa_referencia_bs_por_usd NUMERIC(24, 8) NOT NULL CHECK (tasa_referencia_bs_por_usd > 0),
  nota TEXT,
  usuario_id UUID REFERENCES public.erp_users (id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cambios_tesoreria_fecha ON public.cambios_tesoreria (fecha DESC);

CREATE OR REPLACE FUNCTION public.registrar_cambio_tesoreria_erp(
  p_usuario_id UUID,
  p_caja_origen_id UUID,
  p_caja_destino_id UUID,
  p_monto_ves NUMERIC,
  p_monto_usd_obtenido NUMERIC,
  p_tasa_referencia_bs_por_usd NUMERIC,
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
  IF p_tasa_referencia_bs_por_usd IS NULL OR p_tasa_referencia_bs_por_usd <= 0 THEN
    RAISE EXCEPTION 'Tasa referencia Bs/USD inválida';
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
    tasa_referencia_bs_por_usd,
    nota,
    usuario_id
  ) VALUES (
    COALESCE(p_fecha, NOW()),
    p_caja_origen_id,
    p_caja_destino_id,
    ROUND(p_monto_ves, 4),
    ROUND(p_monto_usd_obtenido, 4),
    p_tasa_referencia_bs_por_usd,
    NULLIF(TRIM(p_nota), ''),
    p_usuario_id
  )
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.registrar_cambio_tesoreria_erp(UUID, UUID, UUID, NUMERIC, NUMERIC, NUMERIC, TEXT, TIMESTAMPTZ) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.registrar_cambio_tesoreria_erp(UUID, UUID, UUID, NUMERIC, NUMERIC, NUMERIC, TEXT, TIMESTAMPTZ) TO service_role;

NOTIFY pgrst, 'reload schema';
