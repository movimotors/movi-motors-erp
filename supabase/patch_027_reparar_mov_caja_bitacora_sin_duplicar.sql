-- patch_027: Reparar movimientos de caja para bitácora (cambios_tesoreria) SIN usar de nuevo el formulario.
--
-- Caso de uso: guardaste cambios en bitácora como "solo anotación" o la BD aún no tenía patch_024,
-- y ahora los saldos no reflejan el cambio. Si volvieras a registrar lo mismo en la app,
-- duplicarías filas en cambios_tesoreria y descuadrarías todo.
--
-- Este script:
--   - Solo toca filas de cambios_tesoreria que tienen origen y destino y
--     NO tienen NINGÚN movimiento en movimientos_caja con referencia = id del cambio.
--   - Inserta el par egreso VES + ingreso destino en un solo paso (UNION ALL).
--   - El trigger trg_mov_caja_saldo actualiza saldo_actual_usd al insertar cada fila.
--
-- NO ejecutes esto si ya hay 1 o 2 movimientos con esa referencia (revisá el diagnóstico abajo).
-- Si hay exactamente 1 movimiento (estado roto), corregilo a mano antes de automatizar.

-- -----------------------------------------------------------------------------
-- 0) Diagnóstico (ejecutá primero; no modifica datos)
-- -----------------------------------------------------------------------------
-- Cambios de bitácora sin ningún movimiento de caja enlazado:
-- SELECT c.id, c.fecha, c.monto_ves, c.monto_usd_obtenido,
--        c.caja_origen_id, c.caja_destino_id, c.usuario_id
-- FROM public.cambios_tesoreria c
-- WHERE c.caja_origen_id IS NOT NULL
--   AND c.caja_destino_id IS NOT NULL
--   AND NOT EXISTS (
--     SELECT 1 FROM public.movimientos_caja m WHERE m.referencia = c.id::text
--   )
-- ORDER BY c.fecha;

-- Sospechosos: hay movimientos pero no el par (≠ 2 filas) — revisar antes de reparar:
-- SELECT c.id, c.fecha, COUNT(m.id) AS n_mov
-- FROM public.cambios_tesoreria c
-- LEFT JOIN public.movimientos_caja m ON m.referencia = c.id::text
-- GROUP BY c.id, c.fecha
-- HAVING COUNT(m.id) NOT IN (0, 2);

-- -----------------------------------------------------------------------------
-- 1) Inserción idempotente (ejecutar en una transacción)
-- -----------------------------------------------------------------------------
BEGIN;

WITH pend AS (
  SELECT
    c.id,
    c.fecha,
    c.monto_ves,
    c.monto_usd_obtenido,
    c.nota,
    c.usuario_id,
    c.caja_origen_id,
    c.caja_destino_id,
    upper(trim(co.moneda_cuenta)) AS mo,
    upper(trim(cd.moneda_cuenta)) AS md
  FROM public.cambios_tesoreria c
  INNER JOIN public.cajas_bancos co ON co.id = c.caja_origen_id AND co.activo = TRUE
  INNER JOIN public.cajas_bancos cd ON cd.id = c.caja_destino_id AND cd.activo = TRUE
  WHERE c.caja_origen_id IS NOT NULL
    AND c.caja_destino_id IS NOT NULL
    AND c.caja_origen_id <> c.caja_destino_id
    AND upper(trim(co.moneda_cuenta)) = 'VES'
    AND upper(trim(cd.moneda_cuenta)) IN ('USD', 'USDT')
    AND NOT EXISTS (
      SELECT 1 FROM public.movimientos_caja m WHERE m.referencia = c.id::text
    )
),
egreso AS (
  SELECT
    p.caja_origen_id AS caja_id,
    'Egreso'::TEXT AS tipo,
    ROUND(p.monto_usd_obtenido, 2)::NUMERIC(16, 2) AS monto_usd,
    'VES'::TEXT AS moneda,
    ROUND(p.monto_ves, 4) AS monto_moneda,
    'Salida Bs por cambio de moneda (bitácora)'::TEXT AS concepto,
    p.id::TEXT AS referencia,
    NULLIF(TRIM(p.nota), '') AS nota_operacion,
    NULL::UUID AS venta_id,
    NULL::UUID AS compra_id,
    p.usuario_id
  FROM pend p
),
ingreso AS (
  SELECT
    p.caja_destino_id AS caja_id,
    'Ingreso'::TEXT AS tipo,
    ROUND(p.monto_usd_obtenido, 2)::NUMERIC(16, 2) AS monto_usd,
    p.md AS moneda,
    CASE p.md
      WHEN 'USDT' THEN
        ROUND(
          ROUND(p.monto_usd_obtenido, 2) * COALESCE(
            (
              SELECT td.tasa_usdt
              FROM public.tasas_dia td
              WHERE td.fecha = (p.fecha AT TIME ZONE 'America/Caracas')::date
              LIMIT 1
            ),
            1.0
          ),
          4
        )
      ELSE ROUND(p.monto_usd_obtenido, 2)::NUMERIC(18, 4)
    END AS monto_moneda,
    ('Entrada por cambio Bs → ' || p.md || ' (bitácora)')::TEXT AS concepto,
    p.id::TEXT AS referencia,
    NULLIF(TRIM(p.nota), '') AS nota_operacion,
    NULL::UUID AS venta_id,
    NULL::UUID AS compra_id,
    p.usuario_id
  FROM pend p
)
INSERT INTO public.movimientos_caja (
  caja_id, tipo, monto_usd, moneda, monto_moneda,
  concepto, referencia, nota_operacion, venta_id, compra_id, usuario_id
)
SELECT * FROM egreso
UNION ALL
SELECT * FROM ingreso;

COMMIT;

NOTIFY pgrst, 'reload schema';
