-- patch_030: columnas explícitas por moneda en movimientos_caja (Bs, USDT, USD de cuenta)
-- + RPCs que las mantienen alineadas con moneda/monto_moneda.
-- monto_usd sigue siendo el equivalente interno para saldos (motor).
--
-- Ejecutar en Supabase SQL Editor después de patch_028 / patch_029.
-- Luego: Reload schema (API) si hace falta.

ALTER TABLE public.movimientos_caja
  ADD COLUMN IF NOT EXISTS monto_bs NUMERIC(18, 4),
  ADD COLUMN IF NOT EXISTS monto_usdt NUMERIC(18, 4),
  ADD COLUMN IF NOT EXISTS monto_usd_caja NUMERIC(18, 4);

COMMENT ON COLUMN public.movimientos_caja.monto_bs IS 'Bolívares efectivos del movimiento (cuenta VES); NULL si no aplica';
COMMENT ON COLUMN public.movimientos_caja.monto_usdt IS 'USDT del movimiento; NULL si no aplica';
COMMENT ON COLUMN public.movimientos_caja.monto_usd_caja IS 'USD de la cuenta (Zelle, etc.); NULL si no aplica. Distinto de monto_usd (equiv. motor).';

-- Rellenar desde moneda + monto_moneda (y caja si moneda NULL)
UPDATE public.movimientos_caja m
SET monto_bs = m.monto_moneda
WHERE m.monto_moneda IS NOT NULL AND m.monto_moneda > 0
  AND UPPER(TRIM(COALESCE(m.moneda, ''))) IN ('VES', 'BS')
  AND m.monto_bs IS NULL;

UPDATE public.movimientos_caja m
SET monto_usdt = m.monto_moneda
WHERE m.monto_moneda IS NOT NULL AND m.monto_moneda > 0
  AND UPPER(TRIM(COALESCE(m.moneda, ''))) = 'USDT'
  AND m.monto_usdt IS NULL;

UPDATE public.movimientos_caja m
SET monto_usd_caja = m.monto_moneda
WHERE m.monto_moneda IS NOT NULL AND m.monto_moneda > 0
  AND UPPER(TRIM(COALESCE(m.moneda, ''))) = 'USD'
  AND m.monto_usd_caja IS NULL;

UPDATE public.movimientos_caja m
SET monto_bs = m.monto_moneda
FROM public.cajas_bancos c
WHERE m.caja_id = c.id
  AND m.monto_moneda IS NOT NULL AND m.monto_moneda > 0
  AND (m.moneda IS NULL OR TRIM(COALESCE(m.moneda::text, '')) = '')
  AND UPPER(TRIM(COALESCE(c.moneda_cuenta, ''))) IN ('VES', 'BS')
  AND m.monto_bs IS NULL;

UPDATE public.movimientos_caja m
SET monto_usdt = m.monto_moneda
FROM public.cajas_bancos c
WHERE m.caja_id = c.id
  AND m.monto_moneda IS NOT NULL AND m.monto_moneda > 0
  AND (m.moneda IS NULL OR TRIM(COALESCE(m.moneda::text, '')) = '')
  AND UPPER(TRIM(COALESCE(c.moneda_cuenta, ''))) = 'USDT'
  AND m.monto_usdt IS NULL;

UPDATE public.movimientos_caja m
SET monto_usd_caja = m.monto_moneda
FROM public.cajas_bancos c
WHERE m.caja_id = c.id
  AND m.monto_moneda IS NOT NULL AND m.monto_moneda > 0
  AND (m.moneda IS NULL OR TRIM(COALESCE(m.moneda::text, '')) = '')
  AND UPPER(TRIM(COALESCE(c.moneda_cuenta, ''))) = 'USD'
  AND m.monto_usd_caja IS NULL;

-- -----------------------------------------------------------------------------
-- registrar_movimiento_caja_erp (misma firma que patch_028)
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, TEXT, TEXT, TEXT, NUMERIC);

CREATE OR REPLACE FUNCTION public.registrar_movimiento_caja_erp(
  p_usuario_id UUID,
  p_caja_id UUID,
  p_tipo TEXT,
  p_monto_usd NUMERIC,
  p_concepto TEXT,
  p_referencia TEXT,
  p_nota_operacion TEXT DEFAULT NULL,
  p_categoria_gasto TEXT DEFAULT NULL,
  p_moneda TEXT DEFAULT NULL,
  p_monto_moneda NUMERIC DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id UUID;
  v_cat TEXT;
  v_mon TEXT;
  v_mm NUMERIC;
  v_bs NUMERIC;
  v_ut NUMERIC;
  v_usdc NUMERIC;
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

  v_mon := NULLIF(UPPER(TRIM(p_moneda)), '');
  v_mm := p_monto_moneda;

  IF v_mon IS NOT NULL THEN
    IF v_mm IS NULL OR v_mm <= 0 THEN
      RAISE EXCEPTION 'Si indicás moneda nativa, el monto en esa moneda debe ser > 0';
    END IF;
    IF v_mon NOT IN ('VES', 'USD', 'USDT') THEN
      RAISE EXCEPTION 'moneda inválida (use VES, USD o USDT)';
    END IF;
  ELSE
    v_mm := NULL;
  END IF;

  v_bs := CASE WHEN v_mon = 'VES' THEN v_mm ELSE NULL END;
  v_ut := CASE WHEN v_mon = 'USDT' THEN v_mm ELSE NULL END;
  v_usdc := CASE WHEN v_mon = 'USD' THEN v_mm ELSE NULL END;

  INSERT INTO public.movimientos_caja (
    caja_id, tipo, monto_usd, moneda, monto_moneda,
    monto_bs, monto_usdt, monto_usd_caja,
    concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id, categoria_gasto
  ) VALUES (
    p_caja_id,
    p_tipo,
    p_monto_usd,
    v_mon,
    v_mm,
    v_bs,
    v_ut,
    v_usdc,
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

REVOKE ALL ON FUNCTION public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, TEXT, TEXT, TEXT, NUMERIC) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT, TEXT, TEXT, TEXT, NUMERIC) TO service_role;

-- -----------------------------------------------------------------------------
-- corregir_movimiento_caja_manual_erp (misma firma)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT p.oid::regprocedure AS pfn
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE p.proname = 'corregir_movimiento_caja_manual_erp'
      AND n.nspname = 'public'
  LOOP
    EXECUTE 'DROP FUNCTION IF EXISTS ' || r.pfn || ' CASCADE';
  END LOOP;
END $$;

CREATE OR REPLACE FUNCTION public.corregir_movimiento_caja_manual_erp(
  p_usuario_id UUID,
  p_movimiento_id UUID,
  p_monto_usd NUMERIC,
  p_concepto TEXT,
  p_referencia TEXT,
  p_categoria_gasto TEXT DEFAULT NULL,
  p_actualizar_moneda_nativa BOOLEAN DEFAULT FALSE,
  p_moneda TEXT DEFAULT NULL,
  p_monto_moneda NUMERIC DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_tipo TEXT;
  v_caja UUID;
  v_old NUMERIC;
  v_venta UUID;
  v_compra UUID;
  v_cat TEXT;
  v_mon TEXT;
  v_mm NUMERIC;
  v_keep_mon TEXT;
  v_keep_mm NUMERIC;
  v_keep_bs NUMERIC;
  v_keep_ut NUMERIC;
  v_keep_usdc NUMERIC;
  v_bs NUMERIC;
  v_ut NUMERIC;
  v_usdc NUMERIC;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.erp_users WHERE id = p_usuario_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Usuario ERP inválido o inactivo';
  END IF;

  IF p_monto_usd IS NULL OR p_monto_usd <= 0 THEN
    RAISE EXCEPTION 'monto inválido';
  END IF;

  IF p_concepto IS NULL OR TRIM(p_concepto) = '' THEN
    RAISE EXCEPTION 'concepto requerido';
  END IF;

  SELECT
    m.tipo, m.caja_id, m.monto_usd, m.venta_id, m.compra_id,
    m.moneda, m.monto_moneda, m.monto_bs, m.monto_usdt, m.monto_usd_caja
  INTO
    v_tipo, v_caja, v_old, v_venta, v_compra,
    v_keep_mon, v_keep_mm, v_keep_bs, v_keep_ut, v_keep_usdc
  FROM public.movimientos_caja m
  WHERE m.id = p_movimiento_id
  FOR UPDATE;

  IF v_caja IS NULL THEN
    RAISE EXCEPTION 'Movimiento no encontrado';
  END IF;

  IF v_venta IS NOT NULL OR v_compra IS NOT NULL THEN
    RAISE EXCEPTION 'No se puede editar este movimiento desde acá (está ligado a venta o compra). Usá anulación o soporte.';
  END IF;

  v_cat := NULLIF(TRIM(p_categoria_gasto), '');
  IF v_cat IS NOT NULL AND v_tipo <> 'Egreso' THEN
    v_cat := NULL;
  END IF;

  IF COALESCE(p_actualizar_moneda_nativa, FALSE) THEN
    v_mon := NULLIF(UPPER(TRIM(p_moneda)), '');
    v_mm := p_monto_moneda;
    IF v_mon IS NOT NULL THEN
      IF v_mm IS NULL OR v_mm <= 0 THEN
        RAISE EXCEPTION 'Si indicás moneda nativa, el monto en esa moneda debe ser > 0';
      END IF;
      IF v_mon NOT IN ('VES', 'USD', 'USDT') THEN
        RAISE EXCEPTION 'moneda inválida (use VES, USD o USDT)';
      END IF;
    ELSE
      v_mm := NULL;
    END IF;
    v_bs := CASE WHEN v_mon = 'VES' THEN v_mm ELSE NULL END;
    v_ut := CASE WHEN v_mon = 'USDT' THEN v_mm ELSE NULL END;
    v_usdc := CASE WHEN v_mon = 'USD' THEN v_mm ELSE NULL END;
  ELSE
    v_mon := v_keep_mon;
    v_mm := v_keep_mm;
    v_bs := v_keep_bs;
    v_ut := v_keep_ut;
    v_usdc := v_keep_usdc;
  END IF;

  IF v_tipo = 'Ingreso' THEN
    UPDATE public.cajas_bancos
    SET saldo_actual_usd = saldo_actual_usd - v_old + p_monto_usd
    WHERE id = v_caja;
  ELSE
    UPDATE public.cajas_bancos
    SET saldo_actual_usd = saldo_actual_usd + v_old - p_monto_usd
    WHERE id = v_caja;
  END IF;

  UPDATE public.movimientos_caja
  SET
    monto_usd = p_monto_usd,
    concepto = TRIM(p_concepto),
    referencia = NULLIF(TRIM(p_referencia), ''),
    categoria_gasto = CASE WHEN v_tipo = 'Egreso' THEN v_cat ELSE categoria_gasto END,
    moneda = v_mon,
    monto_moneda = v_mm,
    monto_bs = v_bs,
    monto_usdt = v_ut,
    monto_usd_caja = v_usdc
  WHERE id = p_movimiento_id;
END;
$$;

REVOKE ALL ON FUNCTION public.corregir_movimiento_caja_manual_erp(UUID, UUID, NUMERIC, TEXT, TEXT, TEXT, BOOLEAN, TEXT, NUMERIC) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.corregir_movimiento_caja_manual_erp(UUID, UUID, NUMERIC, TEXT, TEXT, TEXT, BOOLEAN, TEXT, NUMERIC) TO service_role;

NOTIFY pgrst, 'reload schema';
