-- Anular una venta o compra mal cargada (superusuario desde la app).
-- Venta: revierte ingresos/egresos de caja, restaura stock (incl. kits), borra venta + detalle + CXC.
-- Compra: revierte egreso de caja, descuenta stock y recalcula costo promedio como inverso de la compra.

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
    SELECT vd.producto_id, vd.cantidad
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
    END IF;
  END LOOP;

  DELETE FROM public.ventas WHERE id = p_venta_id;
END;
$$;

REVOKE ALL ON FUNCTION public.anular_venta_erp(UUID, UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.anular_venta_erp(UUID, UUID) TO service_role;


CREATE OR REPLACE FUNCTION public.anular_compra_erp(
  p_usuario_id UUID,
  p_compra_id UUID
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  m RECORD;
  v_num BIGINT;
  det RECORD;
  v_old_stock NUMERIC(14, 3);
  v_old_cost NUMERIC(14, 2);
  v_cant NUMERIC(14, 3);
  v_cu NUMERIC(14, 2);
  v_new_s NUMERIC(20, 6);
  v_new_cost NUMERIC(14, 2);
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.erp_users WHERE id = p_usuario_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Usuario ERP inválido o inactivo';
  END IF;

  SELECT c.numero INTO v_num FROM public.compras c WHERE c.id = p_compra_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Compra no encontrada';
  END IF;

  FOR m IN
    SELECT * FROM public.movimientos_caja WHERE compra_id = p_compra_id ORDER BY created_at ASC
  LOOP
    IF m.tipo = 'Egreso' THEN
      INSERT INTO public.movimientos_caja (
        caja_id, tipo, monto_usd, moneda, monto_moneda,
        concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
      ) VALUES (
        m.caja_id,
        'Ingreso',
        m.monto_usd,
        m.moneda,
        m.monto_moneda,
        'Anulación compra #' || v_num::TEXT,
        m.referencia,
        m.nota_operacion,
        NULL,
        NULL,
        p_usuario_id
      );
    ELSIF m.tipo = 'Ingreso' THEN
      INSERT INTO public.movimientos_caja (
        caja_id, tipo, monto_usd, moneda, monto_moneda,
        concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
      ) VALUES (
        m.caja_id,
        'Egreso',
        m.monto_usd,
        m.moneda,
        m.monto_moneda,
        'Anulación compra #' || v_num::TEXT,
        m.referencia,
        m.nota_operacion,
        NULL,
        NULL,
        p_usuario_id
      );
    END IF;
  END LOOP;

  DELETE FROM public.movimientos_caja WHERE compra_id = p_compra_id;

  FOR det IN
    SELECT cd.producto_id, cd.cantidad, cd.costo_unitario_usd
    FROM public.compras_detalles cd
    WHERE cd.compra_id = p_compra_id
  LOOP
    v_cant := det.cantidad;
    v_cu := det.costo_unitario_usd;

    SELECT p.stock_actual::NUMERIC, p.costo_usd INTO v_old_stock, v_old_cost
    FROM public.productos p
    WHERE p.id = det.producto_id
    FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Producto de línea de compra no encontrado: %', det.producto_id;
    END IF;

    v_new_s := v_old_stock - v_cant;
    IF v_new_s < 0 THEN
      RAISE EXCEPTION
        'No se puede anular: stock actual % menor que la cantidad comprada % (producto %)',
        v_old_stock, v_cant, det.producto_id;
    END IF;

    IF v_new_s > 0 THEN
      v_new_cost := ROUND(
        ((v_old_cost * v_old_stock) - (v_cu * v_cant)) / v_new_s,
        2
      );
      IF v_new_cost < 0 THEN
        v_new_cost := 0;
      END IF;
      UPDATE public.productos
      SET stock_actual = ROUND(v_new_s)::INT, costo_usd = v_new_cost
      WHERE id = det.producto_id;
    ELSE
      UPDATE public.productos
      SET stock_actual = 0, costo_usd = v_old_cost
      WHERE id = det.producto_id;
    END IF;
  END LOOP;

  DELETE FROM public.compras WHERE id = p_compra_id;
END;
$$;

REVOKE ALL ON FUNCTION public.anular_compra_erp(UUID, UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.anular_compra_erp(UUID, UUID) TO service_role;

COMMENT ON FUNCTION public.anular_venta_erp IS 'Anula una venta: revierte caja, restaura stock, elimina venta/CXC/detalles.';
COMMENT ON FUNCTION public.anular_compra_erp IS 'Anula una compra: revierte caja, descuenta stock y costo promedio, elimina compra/CXP/detalles.';
