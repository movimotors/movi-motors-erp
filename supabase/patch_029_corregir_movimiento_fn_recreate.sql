-- patch_029: asegurar RPC corregir_movimiento_caja_manual_erp (firma 9 args) y refrescar PostgREST.
-- Usar si el cliente responde: "Could not find the function ... corregir_movimiento_caja_manual_erp ... in the schema cache".
-- Ejecutar en Supabase → SQL Editor (todo el archivo). Luego: Dashboard → Project Settings → API → "Reload schema" si sigue fallando.

-- Quitar TODAS las sobrecargas con ese nombre (evita que quede una firma vieja y PostgREST no encuentre la correcta).
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

COMMENT ON FUNCTION public.corregir_movimiento_caja_manual_erp(UUID, UUID, NUMERIC, TEXT, TEXT, TEXT, BOOLEAN, TEXT, NUMERIC) IS
  'Corrige monto_usd (saldo) y texto/moneda nativa de un movimiento sin venta_id ni compra_id.';

-- Refrescar caché de esquema de PostgREST (Supabase API).
NOTIFY pgrst, 'reload schema';
