-- patch_023: números de serie para productos tipo motor (categoría Motores u otros con tracking).
-- - Columna `seriales` en `ventas_detalles` (JSON array de textos, uno por unidad vendida).
-- - `crear_venta_erp`: guarda seriales, valida cantidad, opcionalmente quita del pool en `productos.compatibilidad.seriales_motor`.
-- - `anular_venta_erp`: al anular, devuelve esos seriales al pool.
--
-- Ejecutar en Supabase SQL Editor **después** de patch_017 (u otros que reemplacen `crear_venta_erp` con la misma firma).

ALTER TABLE public.ventas_detalles
  ADD COLUMN IF NOT EXISTS seriales JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.ventas_detalles.seriales IS
  'Números de serie vendidos (ej. motores): JSON array de strings, misma longitud que cantidad entera.';

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
  v_nota TEXT;
  v_seriales JSONB;
  v_sold TEXT;
  v_txt TEXT;
  v_new JSONB;
  v_is_sold BOOLEAN;
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

    v_seriales := COALESCE(r->'seriales', '[]'::jsonb);
    IF jsonb_typeof(v_seriales) <> 'array' THEN
      v_seriales := '[]'::jsonb;
    END IF;

    SELECT p.stock_actual, COALESCE(p.es_compuesto, FALSE)
    INTO v_stock, v_es_comp
    FROM public.productos p
    WHERE p.id = v_pid AND p.activo = TRUE
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Producto no encontrado o inactivo: %', v_pid;
    END IF;

    IF jsonb_array_length(v_seriales) > 0 THEN
      IF v_es_comp THEN
        RAISE EXCEPTION 'No uses seriales en líneas de kit (producto %)', v_pid;
      END IF;
      IF v_cant <> TRUNC(v_cant) THEN
        RAISE EXCEPTION 'Seriales: la cantidad debe ser entera (producto %)', v_pid;
      END IF;
      IF jsonb_array_length(v_seriales) <> TRUNC(v_cant)::INT THEN
        RAISE EXCEPTION 'Seriales: deben ser % número(s) de serie (uno por unidad)', TRUNC(v_cant)::INT;
      END IF;
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

    v_seriales := COALESCE(r->'seriales', '[]'::jsonb);
    IF jsonb_typeof(v_seriales) <> 'array' THEN
      v_seriales := '[]'::jsonb;
    END IF;

    SELECT COALESCE(es_compuesto, FALSE) INTO v_es_comp FROM public.productos WHERE id = v_pid;

    IF jsonb_array_length(v_seriales) > 0 AND NOT v_es_comp THEN
      FOR v_sold IN SELECT e FROM jsonb_array_elements_text(v_seriales) AS t(e)
      LOOP
        IF NOT EXISTS (
          SELECT 1
          FROM jsonb_array_elements_text(
            COALESCE(
              (SELECT p.compatibilidad->'seriales_motor' FROM public.productos p WHERE p.id = v_pid),
              '[]'::jsonb
            )
          ) AS pool(serial_val)
          WHERE trim(both from serial_val) = trim(both from v_sold)
        ) THEN
          RAISE EXCEPTION 'Serial "%" no está en el inventario del producto (compatibilidad.seriales_motor)', v_sold;
        END IF;
      END LOOP;
    END IF;

    INSERT INTO public.ventas_detalles (venta_id, producto_id, cantidad, precio_unitario_usd, subtotal_usd, seriales)
    VALUES (v_venta_id, v_pid, v_cant, v_pu, v_line, v_seriales);

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

      IF jsonb_array_length(v_seriales) > 0 THEN
        v_new := '[]'::jsonb;
        FOR v_txt IN
          SELECT e FROM jsonb_array_elements_text(
            COALESCE(
              (SELECT p.compatibilidad->'seriales_motor' FROM public.productos p WHERE p.id = v_pid),
              '[]'::jsonb
            )
          ) AS tpool(e)
        LOOP
          v_is_sold := false;
          FOR v_sold IN SELECT e2 FROM jsonb_array_elements_text(v_seriales) AS ts(e2)
          LOOP
            IF trim(both from v_txt) = trim(both from v_sold) THEN
              v_is_sold := true;
              EXIT;
            END IF;
          END LOOP;
          IF NOT v_is_sold THEN
            v_new := v_new || jsonb_build_array(trim(both from v_txt));
          END IF;
        END LOOP;
        UPDATE public.productos
        SET compatibilidad = jsonb_set(
          COALESCE(compatibilidad, '{}'::jsonb),
          '{seriales_motor}',
          v_new
        )
        WHERE id = v_pid;
      END IF;
    END IF;
  END LOOP;

  IF p_forma_pago = 'contado' THEN
    IF p_cobros IS NOT NULL AND jsonb_array_length(p_cobros) > 0 THEN
      FOR r IN SELECT * FROM jsonb_array_elements(p_cobros)
      LOOP
        v_caja_line := (r->>'caja_id')::UUID;
        v_mon := upper(trim(r->>'moneda'));
        v_monto := (r->>'monto')::NUMERIC;
        v_nota := NULLIF(TRIM(r->>'nota_operacion'), '');

        IF v_caja_line IS NULL OR NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = v_caja_line AND activo = TRUE) THEN
          RAISE EXCEPTION 'Caja inválida en cobro';
        END IF;
        IF v_mon NOT IN ('VES', 'USD', 'USDT', 'ZELLE') THEN
          RAISE EXCEPTION 'moneda inválida (use VES, USD, USDT o ZELLE)';
        END IF;
        IF v_monto IS NULL OR v_monto <= 0 THEN
          RAISE EXCEPTION 'Monto de cobro inválido';
        END IF;

        v_eq := CASE v_mon
          WHEN 'USD' THEN ROUND(v_monto, 4)
          WHEN 'ZELLE' THEN ROUND(v_monto, 4)
          WHEN 'USDT' THEN ROUND(v_monto / p_tasa_usdt, 4)
          WHEN 'VES' THEN ROUND(v_monto / p_tasa_bs, 4)
        END;

        v_sum_cobros := v_sum_cobros + v_eq;

        INSERT INTO public.movimientos_caja (
          caja_id, tipo, monto_usd, moneda, monto_moneda,
          concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
        ) VALUES (
          v_caja_line,
          'Ingreso',
          ROUND(v_eq, 2),
          v_mon,
          ROUND(v_monto, 4),
          'Venta #' || v_num::TEXT,
          NULL,
          v_nota,
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
        concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
      ) VALUES (
        p_caja_id,
        'Ingreso',
        v_total,
        'USD',
        v_total,
        'Venta #' || v_num::TEXT,
        NULL,
        NULL,
        v_venta_id,
        NULL,
        p_usuario_id
      );
    END IF;
  ELSE
    v_sum_cobros := 0;
    IF p_cobros IS NOT NULL AND jsonb_array_length(p_cobros) > 0 THEN
      FOR r IN SELECT * FROM jsonb_array_elements(p_cobros)
      LOOP
        v_caja_line := (r->>'caja_id')::UUID;
        v_mon := upper(trim(r->>'moneda'));
        v_monto := (r->>'monto')::NUMERIC;
        v_nota := NULLIF(TRIM(r->>'nota_operacion'), '');

        IF v_caja_line IS NULL OR NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = v_caja_line AND activo = TRUE) THEN
          RAISE EXCEPTION 'Caja inválida en abono de venta a crédito';
        END IF;
        IF v_mon NOT IN ('VES', 'USD', 'USDT', 'ZELLE') THEN
          RAISE EXCEPTION 'moneda inválida (use VES, USD, USDT o ZELLE)';
        END IF;
        IF v_monto IS NULL OR v_monto <= 0 THEN
          RAISE EXCEPTION 'Monto de abono inválido';
        END IF;

        v_eq := CASE v_mon
          WHEN 'USD' THEN ROUND(v_monto, 4)
          WHEN 'ZELLE' THEN ROUND(v_monto, 4)
          WHEN 'USDT' THEN ROUND(v_monto / p_tasa_usdt, 4)
          WHEN 'VES' THEN ROUND(v_monto / p_tasa_bs, 4)
        END;

        v_sum_cobros := v_sum_cobros + v_eq;

        INSERT INTO public.movimientos_caja (
          caja_id, tipo, monto_usd, moneda, monto_moneda,
          concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
        ) VALUES (
          v_caja_line,
          'Ingreso',
          ROUND(v_eq, 2),
          v_mon,
          ROUND(v_monto, 4),
          'Abono / seña — venta crédito #' || v_num::TEXT,
          NULL,
          v_nota,
          v_venta_id,
          NULL,
          p_usuario_id
        );
      END LOOP;

      v_sum_cobros := ROUND(v_sum_cobros, 2);
      IF v_sum_cobros > v_total + 0.05 THEN
        RAISE EXCEPTION 'El abono (≈ % USD) no puede ser mayor al total de la venta (% USD)', v_sum_cobros, v_total;
      END IF;
      IF (v_total - v_sum_cobros) > 0.05 THEN
        INSERT INTO public.cuentas_por_cobrar (venta_id, monto_pendiente_usd, fecha_vencimiento, estado)
        VALUES (v_venta_id, ROUND(v_total - v_sum_cobros, 2), p_fecha_vencimiento, 'Pendiente');
      END IF;
    ELSE
      INSERT INTO public.cuentas_por_cobrar (venta_id, monto_pendiente_usd, fecha_vencimiento, estado)
      VALUES (v_venta_id, v_total, p_fecha_vencimiento, 'Pendiente');
    END IF;
  END IF;

  RETURN v_venta_id;
END;
$$;

REVOKE ALL ON FUNCTION public.crear_venta_erp(UUID, TEXT, TEXT, UUID, NUMERIC, NUMERIC, DATE, TEXT, JSONB, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.crear_venta_erp(UUID, TEXT, TEXT, UUID, NUMERIC, NUMERIC, DATE, TEXT, JSONB, JSONB) TO service_role;


-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.anular_venta_erp(
  p_usuario_id UUID,
  p_venta_id UUID
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  m RECORD;
  v_num BIGINT;
  det RECORD;
  v_es_comp BOOLEAN;
  kit_rec RECORD;
  v_need INT;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.erp_users WHERE id = p_usuario_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Usuario ERP inválido o inactivo';
  END IF;

  SELECT v.numero INTO v_num FROM public.ventas v WHERE v.id = p_venta_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Venta no encontrada';
  END IF;

  FOR m IN
    SELECT * FROM public.movimientos_caja WHERE venta_id = p_venta_id ORDER BY created_at ASC
  LOOP
    IF m.tipo = 'Ingreso' THEN
      INSERT INTO public.movimientos_caja (
        caja_id, tipo, monto_usd, moneda, monto_moneda,
        concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
      ) VALUES (
        m.caja_id,
        'Egreso',
        m.monto_usd,
        m.moneda,
        m.monto_moneda,
        'Anulación venta #' || v_num::TEXT,
        m.referencia,
        m.nota_operacion,
        NULL,
        NULL,
        p_usuario_id
      );
    ELSIF m.tipo = 'Egreso' THEN
      INSERT INTO public.movimientos_caja (
        caja_id, tipo, monto_usd, moneda, monto_moneda,
        concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
      ) VALUES (
        m.caja_id,
        'Ingreso',
        m.monto_usd,
        m.moneda,
        m.monto_moneda,
        'Anulación venta #' || v_num::TEXT,
        m.referencia,
        m.nota_operacion,
        NULL,
        NULL,
        p_usuario_id
      );
    END IF;
  END LOOP;

  DELETE FROM public.movimientos_caja WHERE venta_id = p_venta_id;

  FOR det IN
    SELECT vd.producto_id, vd.cantidad, COALESCE(vd.seriales, '[]'::jsonb) AS seriales
    FROM public.ventas_detalles vd
    WHERE vd.venta_id = p_venta_id
  LOOP
    SELECT COALESCE(p.es_compuesto, FALSE) INTO v_es_comp
    FROM public.productos p
    WHERE p.id = det.producto_id
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Producto de línea de venta no encontrado: %', det.producto_id;
    END IF;

    IF v_es_comp THEN
      FOR kit_rec IN
        SELECT k.componente_producto_id, k.cantidad
        FROM public.productos_kit_items k
        WHERE k.kit_producto_id = det.producto_id
      LOOP
        v_need := CEIL(det.cantidad * kit_rec.cantidad)::INT;
        UPDATE public.productos
        SET stock_actual = stock_actual + v_need
        WHERE id = kit_rec.componente_producto_id;
      END LOOP;
    ELSE
      UPDATE public.productos
      SET stock_actual = stock_actual + det.cantidad
      WHERE id = det.producto_id;

      IF jsonb_array_length(det.seriales) > 0 THEN
        UPDATE public.productos p
        SET compatibilidad = jsonb_set(
          COALESCE(p.compatibilidad, '{}'::jsonb),
          '{seriales_motor}',
          COALESCE(p.compatibilidad->'seriales_motor', '[]'::jsonb) || det.seriales
        )
        WHERE p.id = det.producto_id;
      END IF;
    END IF;
  END LOOP;

  DELETE FROM public.ventas WHERE id = p_venta_id;
END;
$$;

REVOKE ALL ON FUNCTION public.anular_venta_erp(UUID, UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.anular_venta_erp(UUID, UUID) TO service_role;
