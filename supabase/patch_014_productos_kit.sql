-- Productos compuestos (kits): ej. "Conversión Corsa" = varios repuestos.
-- La venta registra el kit en ventas_detalles; el stock baja solo en los componentes.
-- Ejecutar en Supabase SQL Editor (service_role en la app).

ALTER TABLE public.productos
  ADD COLUMN IF NOT EXISTS es_compuesto BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS public.productos_kit_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kit_producto_id UUID NOT NULL REFERENCES public.productos (id) ON DELETE CASCADE,
  componente_producto_id UUID NOT NULL REFERENCES public.productos (id) ON DELETE RESTRICT,
  cantidad NUMERIC(14, 3) NOT NULL CHECK (cantidad > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT productos_kit_items_kit_neq_comp CHECK (kit_producto_id <> componente_producto_id),
  CONSTRAINT productos_kit_items_kit_comp_unique UNIQUE (kit_producto_id, componente_producto_id)
);

CREATE INDEX IF NOT EXISTS idx_productos_kit_items_kit
  ON public.productos_kit_items (kit_producto_id);

CREATE INDEX IF NOT EXISTS idx_productos_kit_items_comp
  ON public.productos_kit_items (componente_producto_id);

COMMENT ON TABLE public.productos_kit_items IS
  'BOM: cantidad de cada componente por 1 unidad del kit (producto con es_compuesto = true).';

GRANT SELECT, INSERT, UPDATE, DELETE ON public.productos_kit_items TO service_role;

-- -----------------------------------------------------------------------------
-- crear_venta_erp: kits validan y descuentan stock en componentes (no en el kit).
-- -----------------------------------------------------------------------------
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
  v_es_comp BOOLEAN;
  kit_rec RECORD;
  v_comp_id UUID;
  v_comp_cant NUMERIC(14, 3);
  v_need INT;
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

    SELECT p.stock_actual, COALESCE(p.es_compuesto, FALSE)
    INTO v_stock, v_es_comp
    FROM public.productos p
    WHERE p.id = v_pid AND p.activo = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Producto no encontrado o inactivo: %', v_pid;
    END IF;

    IF v_es_comp THEN
      IF NOT EXISTS (SELECT 1 FROM public.productos_kit_items k WHERE k.kit_producto_id = v_pid) THEN
        RAISE EXCEPTION 'Producto compuesto sin componentes definidos (id %)', v_pid;
      END IF;
      FOR kit_rec IN
        SELECT k.componente_producto_id, k.cantidad
        FROM public.productos_kit_items k
        WHERE k.kit_producto_id = v_pid
      LOOP
        v_comp_id := kit_rec.componente_producto_id;
        v_comp_cant := kit_rec.cantidad;
        SELECT p2.stock_actual INTO v_stock
        FROM public.productos p2
        WHERE p2.id = v_comp_id AND p2.activo = TRUE
        FOR UPDATE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'Componente de kit no encontrado o inactivo: %', v_comp_id;
        END IF;
        v_need := CEIL(v_cant * v_comp_cant)::INT;
        IF v_stock < v_need THEN
          RAISE EXCEPTION 'Stock insuficiente para componente % del kit (necesita % unidades)', v_comp_id, v_need;
        END IF;
      END LOOP;
    ELSE
      IF v_stock < v_cant THEN
        RAISE EXCEPTION 'Stock insuficiente para producto %', v_pid;
      END IF;
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

    SELECT COALESCE(es_compuesto, FALSE) INTO v_es_comp FROM public.productos WHERE id = v_pid;

    IF v_es_comp THEN
      FOR kit_rec IN
        SELECT k.componente_producto_id, k.cantidad
        FROM public.productos_kit_items k
        WHERE k.kit_producto_id = v_pid
      LOOP
        v_need := CEIL(v_cant * kit_rec.cantidad)::INT;
        UPDATE public.productos
        SET stock_actual = stock_actual - v_need
        WHERE id = kit_rec.componente_producto_id;
      END LOOP;
    ELSE
      UPDATE public.productos
      SET stock_actual = stock_actual - v_cant
      WHERE id = v_pid;
    END IF;
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

NOTIFY pgrst, 'reload schema';
