-- patch_026: revertir movimientos de caja de venta sin venta asociada (huérfanos).
--
-- Si borrás una fila de `ventas` a mano o desde la API, el FK pone venta_id = NULL
-- en movimientos_caja pero el ingreso/egreso ya sumó al saldo. Esta función inserta
-- el movimiento opuesto (ajuste de saldo vía trigger) y borra el movimiento huérfano.
--
-- Solo acepta movimientos con venta_id y compra_id NULL y concepto típico de cobro de venta.
-- Ejecutar en Supabase SQL Editor (cualquier base con movimientos_caja y moneda/monto_moneda como en patch_017+).

CREATE OR REPLACE FUNCTION public.revertir_movimientos_caja_venta_huerfanos_erp(
  p_usuario_id UUID,
  p_movimiento_ids UUID[]
) RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  m RECORD;
  v_n INT := 0;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.erp_users WHERE id = p_usuario_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Usuario ERP inválido o inactivo';
  END IF;

  IF p_movimiento_ids IS NULL OR cardinality(p_movimiento_ids) = 0 THEN
    RETURN 0;
  END IF;

  FOR m IN
    SELECT *
    FROM public.movimientos_caja
    WHERE id IN (SELECT DISTINCT unnest(p_movimiento_ids))
    ORDER BY created_at ASC
    FOR UPDATE
  LOOP
    IF m.venta_id IS NOT NULL OR m.compra_id IS NOT NULL THEN
      RAISE EXCEPTION 'Movimiento % sigue ligado a venta/compra; usá Anular venta o Anular compra', m.id;
    END IF;

    IF m.concepto NOT LIKE 'Venta #%' AND m.concepto NOT LIKE 'Abono / seña — venta crédito #%' THEN
      RAISE EXCEPTION 'Movimiento %: concepto no es cobro de venta reconocido (solo Venta #… o Abono crédito)', m.id;
    END IF;

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
        'Corrección: venta eliminada — ' || m.concepto,
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
        'Corrección: venta eliminada — ' || m.concepto,
        m.referencia,
        m.nota_operacion,
        NULL,
        NULL,
        p_usuario_id
      );
    ELSE
      RAISE EXCEPTION 'Movimiento %: tipo inválido', m.id;
    END IF;

    DELETE FROM public.movimientos_caja WHERE id = m.id;
    v_n := v_n + 1;
  END LOOP;

  RETURN v_n;
END;
$$;

REVOKE ALL ON FUNCTION public.revertir_movimientos_caja_venta_huerfanos_erp(UUID, UUID[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.revertir_movimientos_caja_venta_huerfanos_erp(UUID, UUID[]) TO service_role;

COMMENT ON FUNCTION public.revertir_movimientos_caja_venta_huerfanos_erp IS
  'Revierte saldos por movimientos de cobro de venta cuya venta fue borrada (venta_id NULL). Inserta movimiento opuesto y elimina el huérfano.';
