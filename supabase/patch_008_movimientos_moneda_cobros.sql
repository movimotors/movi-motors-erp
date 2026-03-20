-- Cobros por moneda (VES / USD / USDT) y caja, con equivalente USD para saldos.
-- Ejecutar en Supabase SQL Editor después de patch_005 y funciones ERP.

ALTER TABLE public.movimientos_caja
  ADD COLUMN IF NOT EXISTS moneda TEXT,
  ADD COLUMN IF NOT EXISTS monto_moneda NUMERIC(18, 4);

COMMENT ON COLUMN public.movimientos_caja.moneda IS 'VES | USD | USDT; NULL = legado (solo monto_usd en USD)';
COMMENT ON COLUMN public.movimientos_caja.monto_moneda IS 'Monto en moneda nativa; NULL en filas legado (usar monto_usd)';

-- -----------------------------------------------------------------------------
-- crear_venta_erp: último parámetro p_cobros opcional
-- p_cobros: [{"caja_id":"uuid","moneda":"VES|USD|USDT","monto":123.45}, ...]
-- Si NULL o []: un ingreso USD en p_caja_id (comportamiento anterior).
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.crear_venta_erp(UUID, TEXT, TEXT, UUID, NUMERIC, NUMERIC, DATE, TEXT, JSONB);

CREATE OR REPLACE FUNCTION public.crear_venta_erp(
  p_usuario_id UUID,
  p_cliente TEXT,
  p_forma_pago TEXT,
  p_caja_id UUID,
  p_tasa_bs NUMERIC,
  p_tasa_usdt NUMERIC,
  p_fecha_vencimiento DATE,
  p_notas TEXT,
  p_lineas JSONB,
  p_cobros JSONB DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_venta_id UUID;
  v_total NUMERIC(16, 2) := 0;
  r JSONB;
  v_pid UUID;
  v_cant NUMERIC(14, 3);
  v_pu NUMERIC(14, 2);
  v_line NUMERIC(16, 2);
  v_stock NUMERIC(14, 3);
  v_num BIGINT;
  v_caja_line UUID;
  v_mon TEXT;
  v_monto NUMERIC(18, 4);
  v_eq NUMERIC(16, 4);
  v_sum_cobros NUMERIC(16, 4) := 0;
  v_first_caja UUID;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.erp_users WHERE id = p_usuario_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Usuario ERP inválido o inactivo';
  END IF;

  IF p_forma_pago NOT IN ('contado', 'credito') THEN
    RAISE EXCEPTION 'forma_pago inválida';
  END IF;

  IF p_forma_pago = 'credito' AND p_fecha_vencimiento IS NULL THEN
    RAISE EXCEPTION 'Fecha de vencimiento requerida para venta a crédito';
  END IF;

  IF p_lineas IS NULL OR jsonb_array_length(p_lineas) = 0 THEN
    RAISE EXCEPTION 'La venta debe tener al menos una línea';
  END IF;

  IF p_tasa_bs IS NULL OR p_tasa_bs <= 0 OR p_tasa_usdt IS NULL OR p_tasa_usdt <= 0 THEN
    RAISE EXCEPTION 'Tasas inválidas';
  END IF;

  IF p_forma_pago = 'contado' THEN
    IF (p_cobros IS NULL OR jsonb_array_length(p_cobros) = 0) AND p_caja_id IS NULL THEN
      RAISE EXCEPTION 'Caja requerida para venta al contado (o indicá p_cobros)';
    END IF;
    IF (p_cobros IS NULL OR jsonb_array_length(p_cobros) = 0) AND p_caja_id IS NOT NULL THEN
      IF NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = p_caja_id AND activo = TRUE) THEN
        RAISE EXCEPTION 'Caja inválida o inactiva';
      END IF;
    END IF;
  END IF;

  FOR r IN SELECT * FROM jsonb_array_elements(p_lineas)
  LOOP
    v_pid := (r->>'producto_id')::UUID;
    v_cant := (r->>'cantidad')::NUMERIC;
    v_pu := (r->>'precio_unitario_usd')::NUMERIC;

    IF v_pid IS NULL OR v_cant IS NULL OR v_cant <= 0 OR v_pu IS NULL OR v_pu < 0 THEN
      RAISE EXCEPTION 'Línea de venta inválida';
    END IF;

    SELECT stock_actual INTO v_stock
    FROM public.productos
    WHERE id = v_pid AND activo = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Producto no encontrado o inactivo: %', v_pid;
    END IF;

    IF v_stock < v_cant THEN
      RAISE EXCEPTION 'Stock insuficiente para producto %', v_pid;
    END IF;

    v_line := ROUND(v_cant * v_pu, 2);
    v_total := v_total + v_line;
  END LOOP;

  v_total := ROUND(v_total, 2);

  IF p_forma_pago = 'contado' AND p_cobros IS NOT NULL AND jsonb_array_length(p_cobros) > 0 THEN
    v_first_caja := (p_cobros->0->>'caja_id')::UUID;
  ELSE
    v_first_caja := p_caja_id;
  END IF;

  INSERT INTO public.ventas (
    cliente, total_usd, tasa_bs, tasa_usdt, forma_pago, caja_id, usuario_id, notas
  ) VALUES (
    COALESCE(NULLIF(TRIM(p_cliente), ''), 'Cliente'),
    v_total,
    p_tasa_bs,
    p_tasa_usdt,
    p_forma_pago,
    CASE WHEN p_forma_pago = 'contado' THEN v_first_caja ELSE NULL END,
    p_usuario_id,
    NULLIF(TRIM(p_notas), '')
  )
  RETURNING id, numero INTO v_venta_id, v_num;

  FOR r IN SELECT * FROM jsonb_array_elements(p_lineas)
  LOOP
    v_pid := (r->>'producto_id')::UUID;
    v_cant := (r->>'cantidad')::NUMERIC;
    v_pu := (r->>'precio_unitario_usd')::NUMERIC;
    v_line := ROUND(v_cant * v_pu, 2);

    INSERT INTO public.ventas_detalles (venta_id, producto_id, cantidad, precio_unitario_usd, subtotal_usd)
    VALUES (v_venta_id, v_pid, v_cant, v_pu, v_line);

    UPDATE public.productos
    SET stock_actual = stock_actual - v_cant
    WHERE id = v_pid;
  END LOOP;

  IF p_forma_pago = 'contado' THEN
    IF p_cobros IS NOT NULL AND jsonb_array_length(p_cobros) > 0 THEN
      FOR r IN SELECT * FROM jsonb_array_elements(p_cobros)
      LOOP
        v_caja_line := (r->>'caja_id')::UUID;
        v_mon := upper(trim(r->>'moneda'));
        v_monto := (r->>'monto')::NUMERIC;

        IF v_caja_line IS NULL OR NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = v_caja_line AND activo = TRUE) THEN
          RAISE EXCEPTION 'Caja inválida en cobro';
        END IF;
        IF v_mon NOT IN ('VES', 'USD', 'USDT') THEN
          RAISE EXCEPTION 'moneda inválida (use VES, USD o USDT)';
        END IF;
        IF v_monto IS NULL OR v_monto <= 0 THEN
          RAISE EXCEPTION 'Monto de cobro inválido';
        END IF;

        v_eq := CASE v_mon
          WHEN 'USD' THEN ROUND(v_monto, 4)
          WHEN 'USDT' THEN ROUND(v_monto / p_tasa_usdt, 4)
          WHEN 'VES' THEN ROUND(v_monto / p_tasa_bs, 4)
        END;

        v_sum_cobros := v_sum_cobros + v_eq;

        INSERT INTO public.movimientos_caja (
          caja_id, tipo, monto_usd, moneda, monto_moneda,
          concepto, referencia, venta_id, compra_id, usuario_id
        ) VALUES (
          v_caja_line,
          'Ingreso',
          ROUND(v_eq, 2),
          v_mon,
          ROUND(v_monto, 4),
          'Venta #' || v_num::TEXT,
          NULL,
          v_venta_id,
          NULL,
          p_usuario_id
        );
      END LOOP;

      IF ABS(v_sum_cobros - v_total) > 0.05 THEN
        RAISE EXCEPTION 'Los cobros (≈ % USD) no cuadran con el total de la venta (% USD)', v_sum_cobros, v_total;
      END IF;
    ELSE
      INSERT INTO public.movimientos_caja (
        caja_id, tipo, monto_usd, moneda, monto_moneda,
        concepto, referencia, venta_id, compra_id, usuario_id
      ) VALUES (
        p_caja_id,
        'Ingreso',
        v_total,
        'USD',
        v_total,
        'Venta #' || v_num::TEXT,
        NULL,
        v_venta_id,
        NULL,
        p_usuario_id
      );
    END IF;
  ELSE
    INSERT INTO public.cuentas_por_cobrar (venta_id, monto_pendiente_usd, fecha_vencimiento, estado)
    VALUES (v_venta_id, v_total, p_fecha_vencimiento, 'Pendiente');
  END IF;

  RETURN v_venta_id;
END;
$$;

REVOKE ALL ON FUNCTION public.crear_venta_erp(UUID, TEXT, TEXT, UUID, NUMERIC, NUMERIC, DATE, TEXT, JSONB, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.crear_venta_erp(UUID, TEXT, TEXT, UUID, NUMERIC, NUMERIC, DATE, TEXT, JSONB, JSONB) TO service_role;

-- -----------------------------------------------------------------------------
-- cobrar_cxc_erp: 5º parámetro p_cobros opcional (misma forma que venta)
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.cobrar_cxc_erp(UUID, UUID, UUID, NUMERIC);

CREATE OR REPLACE FUNCTION public.cobrar_cxc_erp(
  p_usuario_id UUID,
  p_cxc_id UUID,
  p_caja_id UUID,
  p_monto_usd NUMERIC,
  p_cobros JSONB DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_venta_id UUID;
  v_pend NUMERIC(16, 2);
  v_num BIGINT;
  v_nuevo NUMERIC(16, 2);
  v_estado TEXT;
  v_tasa_bs NUMERIC(24, 8);
  v_tasa_usdt NUMERIC(24, 8);
  r JSONB;
  v_caja_line UUID;
  v_mon TEXT;
  v_monto NUMERIC(18, 4);
  v_eq NUMERIC(16, 4);
  v_sum_cobros NUMERIC(16, 4) := 0;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.erp_users WHERE id = p_usuario_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Usuario ERP inválido o inactivo';
  END IF;

  IF p_monto_usd IS NULL OR p_monto_usd <= 0 THEN
    RAISE EXCEPTION 'Monto inválido';
  END IF;

  SELECT c.venta_id, c.monto_pendiente_usd
  INTO v_venta_id, v_pend
  FROM public.cuentas_por_cobrar c
  WHERE c.id = p_cxc_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Cuenta por cobrar no encontrada';
  END IF;

  IF v_pend <= 0 THEN
    RAISE EXCEPTION 'Documento ya liquidado';
  END IF;

  IF p_monto_usd > v_pend THEN
    RAISE EXCEPTION 'Monto mayor al pendiente';
  END IF;

  SELECT v.tasa_bs, v.tasa_usdt INTO v_tasa_bs, v_tasa_usdt
  FROM public.ventas v WHERE v.id = v_venta_id;

  IF v_tasa_bs IS NULL OR v_tasa_bs <= 0 OR v_tasa_usdt IS NULL OR v_tasa_usdt <= 0 THEN
    RAISE EXCEPTION 'Tasas de la venta inválidas';
  END IF;

  SELECT v.numero INTO v_num FROM public.ventas v WHERE v.id = v_venta_id;

  IF p_cobros IS NOT NULL AND jsonb_array_length(p_cobros) > 0 THEN
    FOR r IN SELECT * FROM jsonb_array_elements(p_cobros)
    LOOP
      v_caja_line := (r->>'caja_id')::UUID;
      v_mon := upper(trim(r->>'moneda'));
      v_monto := (r->>'monto')::NUMERIC;

      IF v_caja_line IS NULL OR NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = v_caja_line AND activo = TRUE) THEN
        RAISE EXCEPTION 'Caja inválida en cobro CXC';
      END IF;
      IF v_mon NOT IN ('VES', 'USD', 'USDT') THEN
        RAISE EXCEPTION 'moneda inválida';
      END IF;
      IF v_monto IS NULL OR v_monto <= 0 THEN
        RAISE EXCEPTION 'Monto inválido en cobro CXC';
      END IF;

      v_eq := CASE v_mon
        WHEN 'USD' THEN ROUND(v_monto, 4)
        WHEN 'USDT' THEN ROUND(v_monto / v_tasa_usdt, 4)
        WHEN 'VES' THEN ROUND(v_monto / v_tasa_bs, 4)
      END;
      v_sum_cobros := v_sum_cobros + v_eq;
    END LOOP;

    IF ABS(v_sum_cobros - p_monto_usd) > 0.05 THEN
      RAISE EXCEPTION 'Cobros CXC (≈ % USD) no cuadran con monto indicado (% USD)', v_sum_cobros, p_monto_usd;
    END IF;
  ELSE
    IF p_caja_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = p_caja_id AND activo = TRUE) THEN
      RAISE EXCEPTION 'Caja inválida';
    END IF;
  END IF;

  IF p_cobros IS NOT NULL AND jsonb_array_length(p_cobros) > 0 THEN
    FOR r IN SELECT * FROM jsonb_array_elements(p_cobros)
    LOOP
      v_caja_line := (r->>'caja_id')::UUID;
      v_mon := upper(trim(r->>'moneda'));
      v_monto := (r->>'monto')::NUMERIC;
      v_eq := CASE v_mon
        WHEN 'USD' THEN ROUND(v_monto, 4)
        WHEN 'USDT' THEN ROUND(v_monto / v_tasa_usdt, 4)
        WHEN 'VES' THEN ROUND(v_monto / v_tasa_bs, 4)
      END;

      INSERT INTO public.movimientos_caja (
        caja_id, tipo, monto_usd, moneda, monto_moneda,
        concepto, referencia, venta_id, compra_id, usuario_id
      ) VALUES (
        v_caja_line,
        'Ingreso',
        ROUND(v_eq, 2),
        v_mon,
        ROUND(v_monto, 4),
        'Cobro CXC Venta #' || COALESCE(v_num::TEXT, '?'),
        'cxc:' || p_cxc_id::TEXT,
        v_venta_id,
        NULL,
        p_usuario_id
      );
    END LOOP;
  ELSE
    INSERT INTO public.movimientos_caja (
      caja_id, tipo, monto_usd, moneda, monto_moneda,
      concepto, referencia, venta_id, compra_id, usuario_id
    ) VALUES (
      p_caja_id,
      'Ingreso',
      p_monto_usd,
      'USD',
      p_monto_usd,
      'Cobro CXC Venta #' || COALESCE(v_num::TEXT, '?'),
      'cxc:' || p_cxc_id::TEXT,
      v_venta_id,
      NULL,
      p_usuario_id
    );
  END IF;

  v_nuevo := ROUND(v_pend - p_monto_usd, 2);
  v_estado := CASE WHEN v_nuevo <= 0 THEN 'Pagado' ELSE 'Parcial' END;

  UPDATE public.cuentas_por_cobrar
  SET monto_pendiente_usd = GREATEST(v_nuevo, 0), estado = v_estado
  WHERE id = p_cxc_id;
END;
$$;

REVOKE ALL ON FUNCTION public.cobrar_cxc_erp(UUID, UUID, UUID, NUMERIC, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.cobrar_cxc_erp(UUID, UUID, UUID, NUMERIC, JSONB) TO service_role;

NOTIFY pgrst, 'reload schema';
