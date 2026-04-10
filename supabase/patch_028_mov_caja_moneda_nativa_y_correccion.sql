-- patch_028: movimientos manuales con moneda nativa (moneda + monto_moneda) y corrección segura
-- de monto/datos sin romper saldos (el trigger solo aplica en INSERT).
-- Ejecutar en Supabase SQL Editor después de patch_025 (y patch_008 si aplica columnas moneda/monto_moneda).

-- -----------------------------------------------------------------------------
-- registrar_movimiento_caja_erp: + p_moneda, p_monto_moneda (opcionales)
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

  INSERT INTO public.movimientos_caja (
    caja_id, tipo, monto_usd, moneda, monto_moneda, concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id, categoria_gasto
  ) VALUES (
    p_caja_id,
    p_tipo,
    p_monto_usd,
    v_mon,
    v_mm,
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
-- Corregir movimiento manual (sin venta_id ni compra_id): ajusta saldo y fila.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.corregir_movimiento_caja_manual_erp(UUID, UUID, NUMERIC, TEXT, TEXT, TEXT, TEXT, NUMERIC);
DROP FUNCTION IF EXISTS public.corregir_movimiento_caja_manual_erp(UUID, UUID, NUMERIC, TEXT, TEXT, TEXT, BOOLEAN, TEXT, NUMERIC);

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

  SELECT m.tipo, m.caja_id, m.monto_usd, m.venta_id, m.compra_id, m.moneda, m.monto_moneda
  INTO v_tipo, v_caja, v_old, v_venta, v_compra, v_keep_mon, v_keep_mm
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
  ELSE
    v_mon := v_keep_mon;
    v_mm := v_keep_mm;
  END IF;

  -- Ajustar saldo (trigger solo en INSERT): revertir efecto del monto viejo y aplicar el nuevo.
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
    monto_moneda = v_mm
  WHERE id = p_movimiento_id;
END;
$$;

REVOKE ALL ON FUNCTION public.corregir_movimiento_caja_manual_erp(UUID, UUID, NUMERIC, TEXT, TEXT, TEXT, BOOLEAN, TEXT, NUMERIC) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.corregir_movimiento_caja_manual_erp(UUID, UUID, NUMERIC, TEXT, TEXT, TEXT, BOOLEAN, TEXT, NUMERIC) TO service_role;

COMMENT ON FUNCTION public.corregir_movimiento_caja_manual_erp IS
  'Corrige monto_usd (saldo) y texto/moneda nativa de un movimiento sin venta_id ni compra_id.';
