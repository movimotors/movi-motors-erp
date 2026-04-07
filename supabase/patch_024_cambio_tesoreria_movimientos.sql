-- patch_024: al registrar bitácora Bs→USD/USDT, opcionalmente genera movimientos de caja
-- (egreso VES en origen, ingreso USD/USDT en destino) para reflejar saldos reales.
-- Ejecutar después de patch_019.

DROP FUNCTION IF EXISTS public.registrar_cambio_tesoreria_erp(UUID, UUID, UUID, NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, TIMESTAMPTZ);

CREATE OR REPLACE FUNCTION public.registrar_cambio_tesoreria_erp(
  p_usuario_id UUID,
  p_caja_origen_id UUID,
  p_caja_destino_id UUID,
  p_monto_ves NUMERIC,
  p_monto_usd_obtenido NUMERIC,
  p_tasa_compra_bs_por_usd NUMERIC,
  p_tasa_comparacion_bs_por_usd NUMERIC DEFAULT NULL,
  p_nota TEXT DEFAULT NULL,
  p_fecha TIMESTAMPTZ DEFAULT NULL,
  p_tasa_usdt NUMERIC DEFAULT NULL,
  p_aplicar_movimientos BOOLEAN DEFAULT TRUE
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id UUID;
  v_mo TEXT;
  v_md TEXT;
  v_musd NUMERIC(16, 2);
  v_monto_dest_nativo NUMERIC(18, 4);
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

  v_musd := ROUND(p_monto_usd_obtenido, 2);

  IF p_aplicar_movimientos THEN
    IF p_caja_origen_id IS NULL OR p_caja_destino_id IS NULL THEN
      RAISE EXCEPTION 'Para mover saldos: indicá caja origen (VES) y caja destino (USD o USDT)';
    END IF;
    IF p_caja_origen_id = p_caja_destino_id THEN
      RAISE EXCEPTION 'Caja origen y destino deben ser distintas';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = p_caja_origen_id AND activo = TRUE) THEN
      RAISE EXCEPTION 'Caja origen no existe o está inactiva';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = p_caja_destino_id AND activo = TRUE) THEN
      RAISE EXCEPTION 'Caja destino no existe o está inactiva';
    END IF;

    SELECT upper(trim(moneda_cuenta)) INTO v_mo FROM public.cajas_bancos WHERE id = p_caja_origen_id;
    SELECT upper(trim(moneda_cuenta)) INTO v_md FROM public.cajas_bancos WHERE id = p_caja_destino_id;

    IF v_mo IS NULL OR v_md IS NULL THEN
      RAISE EXCEPTION 'No se pudo leer la moneda de las cajas';
    END IF;
    IF v_mo <> 'VES' THEN
      RAISE EXCEPTION 'La caja origen debe ser en bolívares (VES)';
    END IF;
    IF v_md NOT IN ('USD', 'USDT') THEN
      RAISE EXCEPTION 'La caja destino debe ser en USD o USDT';
    END IF;

    IF v_md = 'USDT' THEN
      IF p_tasa_usdt IS NULL OR p_tasa_usdt <= 0 THEN
        RAISE EXCEPTION 'Indicá tasa_usdt (USDT por 1 USD) para ingresar en caja USDT';
      END IF;
      v_monto_dest_nativo := ROUND(v_musd * p_tasa_usdt, 4);
    ELSE
      v_monto_dest_nativo := v_musd;
    END IF;
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

  IF p_aplicar_movimientos THEN
    INSERT INTO public.movimientos_caja (
      caja_id, tipo, monto_usd, moneda, monto_moneda,
      concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
    ) VALUES (
      p_caja_origen_id,
      'Egreso',
      v_musd,
      'VES',
      ROUND(p_monto_ves, 4),
      'Salida Bs por cambio de moneda (bitácora)',
      v_id::TEXT,
      NULLIF(TRIM(p_nota), ''),
      NULL,
      NULL,
      p_usuario_id
    );

    INSERT INTO public.movimientos_caja (
      caja_id, tipo, monto_usd, moneda, monto_moneda,
      concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
    ) VALUES (
      p_caja_destino_id,
      'Ingreso',
      v_musd,
      v_md,
      v_monto_dest_nativo,
      'Entrada por cambio Bs → ' || v_md || ' (bitácora)',
      v_id::TEXT,
      NULLIF(TRIM(p_nota), ''),
      NULL,
      NULL,
      p_usuario_id
    );
  END IF;

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.registrar_cambio_tesoreria_erp(
  UUID, UUID, UUID, NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, TIMESTAMPTZ, NUMERIC, BOOLEAN
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.registrar_cambio_tesoreria_erp(
  UUID, UUID, UUID, NUMERIC, NUMERIC, NUMERIC, NUMERIC, TEXT, TIMESTAMPTZ, NUMERIC, BOOLEAN
) TO service_role;

NOTIFY pgrst, 'reload schema';
