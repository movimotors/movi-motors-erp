-- =============================================================================
-- Movi Motors ERP — Esquema multimoneda (USD base) + cajas + CXC/CXP
-- Ejecutar en Supabase SQL Editor (proyecto nuevo recomendado).
-- Seguridad: la app Streamlit usa service_role en servidor; permisos por rol en Python.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- Usuarios ERP (contraseña hasheada en BD; login usuario + clave desde la app)
-- Roles: superuser (todo + gestión de usuarios), admin, vendedor, almacen
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.erp_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username TEXT NOT NULL UNIQUE,
  nombre TEXT NOT NULL,
  email TEXT,
  rol TEXT NOT NULL CHECK (rol IN ('superuser', 'admin', 'vendedor', 'almacen')),
  password_hash TEXT,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_erp_users_username ON public.erp_users (lower(username));

-- -----------------------------------------------------------------------------
-- Tasas del día: operativas (facturación) + referencia BCV / paralelo / EUR / P2P
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tasas_dia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fecha DATE NOT NULL DEFAULT (CURRENT_DATE AT TIME ZONE 'America/Caracas')::DATE,
  tasa_bs NUMERIC(24, 8) NOT NULL CHECK (tasa_bs > 0),
  tasa_usdt NUMERIC(24, 8) NOT NULL CHECK (tasa_usdt > 0),
  bcv_bs_por_usd NUMERIC(24, 8),
  paralelo_bs_por_usd NUMERIC(24, 8),
  usd_por_eur NUMERIC(24, 8),
  p2p_bs_por_usdt NUMERIC(24, 8),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (fecha)
);

-- -----------------------------------------------------------------------------
-- Categorías y productos (montos en USD)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.categorias (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.productos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo TEXT UNIQUE,
  descripcion TEXT NOT NULL DEFAULT '',
  stock_actual NUMERIC(14, 3) NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
  stock_minimo NUMERIC(14, 3) NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
  costo_usd NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (costo_usd >= 0),
  precio_v_usd NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (precio_v_usd >= 0),
  precio_v_bs_ref NUMERIC(18, 4),
  costo_bs_ref NUMERIC(18, 4),
  categoria_id UUID REFERENCES public.categorias (id) ON DELETE SET NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_productos_activo ON public.productos (activo);
CREATE INDEX IF NOT EXISTS idx_productos_codigo ON public.productos (codigo);

-- -----------------------------------------------------------------------------
-- Cajas / bancos / wallets
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cajas_bancos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('Banco', 'Wallet', 'Efectivo')),
  saldo_actual_usd NUMERIC(18, 2) NOT NULL DEFAULT 0,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- Ventas
-- -----------------------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS public.ventas_numero_seq;

CREATE TABLE IF NOT EXISTS public.ventas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  numero BIGINT NOT NULL DEFAULT nextval('public.ventas_numero_seq'),
  cliente TEXT NOT NULL DEFAULT '',
  fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  total_usd NUMERIC(16, 2) NOT NULL DEFAULT 0 CHECK (total_usd >= 0),
  tasa_bs NUMERIC(24, 8) NOT NULL CHECK (tasa_bs > 0),
  tasa_usdt NUMERIC(24, 8) NOT NULL CHECK (tasa_usdt > 0),
  forma_pago TEXT NOT NULL CHECK (forma_pago IN ('contado', 'credito')),
  caja_id UUID REFERENCES public.cajas_bancos (id) ON DELETE RESTRICT,
  usuario_id UUID NOT NULL REFERENCES public.erp_users (id) ON DELETE RESTRICT,
  notas TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (numero)
);

CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON public.ventas (fecha DESC);
CREATE INDEX IF NOT EXISTS idx_ventas_usuario ON public.ventas (usuario_id);

CREATE TABLE IF NOT EXISTS public.ventas_detalles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  venta_id UUID NOT NULL REFERENCES public.ventas (id) ON DELETE CASCADE,
  producto_id UUID NOT NULL REFERENCES public.productos (id) ON DELETE RESTRICT,
  cantidad NUMERIC(14, 3) NOT NULL CHECK (cantidad > 0),
  precio_unitario_usd NUMERIC(14, 2) NOT NULL CHECK (precio_unitario_usd >= 0),
  subtotal_usd NUMERIC(16, 2) NOT NULL CHECK (subtotal_usd >= 0)
);

CREATE INDEX IF NOT EXISTS idx_ventas_det_venta ON public.ventas_detalles (venta_id);

CREATE TABLE IF NOT EXISTS public.cuentas_por_cobrar (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  venta_id UUID NOT NULL UNIQUE REFERENCES public.ventas (id) ON DELETE CASCADE,
  monto_pendiente_usd NUMERIC(16, 2) NOT NULL CHECK (monto_pendiente_usd >= 0),
  fecha_vencimiento DATE NOT NULL,
  estado TEXT NOT NULL DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Parcial', 'Pagado')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- Compras
-- -----------------------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS public.compras_numero_seq;

CREATE TABLE IF NOT EXISTS public.compras (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  numero BIGINT NOT NULL DEFAULT nextval('public.compras_numero_seq'),
  proveedor TEXT NOT NULL DEFAULT '',
  fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  total_usd NUMERIC(16, 2) NOT NULL DEFAULT 0 CHECK (total_usd >= 0),
  tasa_bs NUMERIC(24, 8) NOT NULL CHECK (tasa_bs > 0),
  tasa_usdt NUMERIC(24, 8) NOT NULL CHECK (tasa_usdt > 0),
  forma_pago TEXT NOT NULL CHECK (forma_pago IN ('contado', 'credito')),
  caja_id UUID REFERENCES public.cajas_bancos (id) ON DELETE RESTRICT,
  usuario_id UUID NOT NULL REFERENCES public.erp_users (id) ON DELETE RESTRICT,
  notas TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (numero)
);

CREATE TABLE IF NOT EXISTS public.compras_detalles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  compra_id UUID NOT NULL REFERENCES public.compras (id) ON DELETE CASCADE,
  producto_id UUID NOT NULL REFERENCES public.productos (id) ON DELETE RESTRICT,
  cantidad NUMERIC(14, 3) NOT NULL CHECK (cantidad > 0),
  costo_unitario_usd NUMERIC(14, 2) NOT NULL CHECK (costo_unitario_usd >= 0),
  subtotal_usd NUMERIC(16, 2) NOT NULL CHECK (subtotal_usd >= 0)
);

CREATE TABLE IF NOT EXISTS public.cuentas_por_pagar (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  compra_id UUID NOT NULL UNIQUE REFERENCES public.compras (id) ON DELETE CASCADE,
  monto_pendiente_usd NUMERIC(16, 2) NOT NULL CHECK (monto_pendiente_usd >= 0),
  fecha_vencimiento DATE NOT NULL,
  estado TEXT NOT NULL DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Parcial', 'Pagado')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- Movimientos de caja (montos en USD)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.movimientos_caja (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  caja_id UUID NOT NULL REFERENCES public.cajas_bancos (id) ON DELETE RESTRICT,
  tipo TEXT NOT NULL CHECK (tipo IN ('Ingreso', 'Egreso')),
  monto_usd NUMERIC(16, 2) NOT NULL CHECK (monto_usd > 0),
  moneda TEXT,
  monto_moneda NUMERIC(18, 4),
  concepto TEXT NOT NULL,
  referencia TEXT,
  venta_id UUID REFERENCES public.ventas (id) ON DELETE SET NULL,
  compra_id UUID REFERENCES public.compras (id) ON DELETE SET NULL,
  usuario_id UUID REFERENCES public.erp_users (id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mov_caja_caja ON public.movimientos_caja (caja_id);
CREATE INDEX IF NOT EXISTS idx_mov_caja_created ON public.movimientos_caja (created_at DESC);

-- -----------------------------------------------------------------------------
-- Trigger: actualizar saldo de caja al registrar movimiento
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.aplicar_movimiento_caja_saldo()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.tipo = 'Ingreso' THEN
    UPDATE public.cajas_bancos
    SET saldo_actual_usd = saldo_actual_usd + NEW.monto_usd
    WHERE id = NEW.caja_id;
  ELSE
    UPDATE public.cajas_bancos
    SET saldo_actual_usd = saldo_actual_usd - NEW.monto_usd
    WHERE id = NEW.caja_id;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_mov_caja_saldo ON public.movimientos_caja;
CREATE TRIGGER trg_mov_caja_saldo
  AFTER INSERT ON public.movimientos_caja
  FOR EACH ROW
  EXECUTE PROCEDURE public.aplicar_movimiento_caja_saldo();

-- -----------------------------------------------------------------------------
-- updated_at productos
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_productos_updated ON public.productos;
CREATE TRIGGER trg_productos_updated
  BEFORE UPDATE ON public.productos
  FOR EACH ROW
  EXECUTE PROCEDURE public.set_updated_at();

-- -----------------------------------------------------------------------------
-- -----------------------------------------------------------------------------
-- RPC: crear venta (p_cobros opcional: VES / USD / USDT por caja)
-- p_lineas: [{"producto_id":"uuid","cantidad":1,"precio_unitario_usd":10.5}, ...]
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

-- RPC: crear compra (stock + costo promedio + compra + caja y/o CXP)
-- p_lineas: [{"producto_id":"uuid","cantidad":1,"costo_unitario_usd":5}, ...]
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.crear_compra_erp(
  p_usuario_id UUID,
  p_proveedor TEXT,
  p_forma_pago TEXT,
  p_caja_id UUID,
  p_tasa_bs NUMERIC,
  p_tasa_usdt NUMERIC,
  p_fecha_vencimiento DATE,
  p_notas TEXT,
  p_lineas JSONB
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_compra_id UUID;
  v_total NUMERIC(16, 2) := 0;
  r JSONB;
  v_pid UUID;
  v_cant NUMERIC(14, 3);
  v_cu NUMERIC(14, 2);
  v_line NUMERIC(16, 2);
  v_old_stock NUMERIC(14, 3);
  v_old_cost NUMERIC(14, 2);
  v_num BIGINT;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.erp_users WHERE id = p_usuario_id AND activo = TRUE) THEN
    RAISE EXCEPTION 'Usuario ERP inválido o inactivo';
  END IF;

  IF p_forma_pago NOT IN ('contado', 'credito') THEN
    RAISE EXCEPTION 'forma_pago inválida';
  END IF;

  IF p_forma_pago = 'contado' AND p_caja_id IS NULL THEN
    RAISE EXCEPTION 'Caja requerida para compra al contado';
  END IF;

  IF p_forma_pago = 'credito' AND p_fecha_vencimiento IS NULL THEN
    RAISE EXCEPTION 'Fecha de vencimiento requerida para compra a crédito';
  END IF;

  IF p_lineas IS NULL OR jsonb_array_length(p_lineas) = 0 THEN
    RAISE EXCEPTION 'La compra debe tener al menos una línea';
  END IF;

  IF p_tasa_bs IS NULL OR p_tasa_bs <= 0 OR p_tasa_usdt IS NULL OR p_tasa_usdt <= 0 THEN
    RAISE EXCEPTION 'Tasas inválidas';
  END IF;

  IF p_forma_pago = 'contado' THEN
    IF NOT EXISTS (SELECT 1 FROM public.cajas_bancos WHERE id = p_caja_id AND activo = TRUE) THEN
      RAISE EXCEPTION 'Caja inválida o inactiva';
    END IF;
  END IF;

  FOR r IN SELECT * FROM jsonb_array_elements(p_lineas)
  LOOP
    v_pid := (r->>'producto_id')::UUID;
    v_cant := (r->>'cantidad')::NUMERIC;
    v_cu := (r->>'costo_unitario_usd')::NUMERIC;

    IF v_pid IS NULL OR v_cant IS NULL OR v_cant <= 0 OR v_cu IS NULL OR v_cu < 0 THEN
      RAISE EXCEPTION 'Línea de compra inválida';
    END IF;

    PERFORM 1 FROM public.productos WHERE id = v_pid AND activo = TRUE FOR UPDATE;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'Producto no encontrado o inactivo: %', v_pid;
    END IF;

    v_line := ROUND(v_cant * v_cu, 2);
    v_total := v_total + v_line;
  END LOOP;

  v_total := ROUND(v_total, 2);

  INSERT INTO public.compras (
    proveedor, total_usd, tasa_bs, tasa_usdt, forma_pago, caja_id, usuario_id, notas
  ) VALUES (
    COALESCE(NULLIF(TRIM(p_proveedor), ''), 'Proveedor'),
    v_total,
    p_tasa_bs,
    p_tasa_usdt,
    p_forma_pago,
    CASE WHEN p_forma_pago = 'contado' THEN p_caja_id ELSE NULL END,
    p_usuario_id,
    NULLIF(TRIM(p_notas), '')
  )
  RETURNING id, numero INTO v_compra_id, v_num;

  FOR r IN SELECT * FROM jsonb_array_elements(p_lineas)
  LOOP
    v_pid := (r->>'producto_id')::UUID;
    v_cant := (r->>'cantidad')::NUMERIC;
    v_cu := (r->>'costo_unitario_usd')::NUMERIC;
    v_line := ROUND(v_cant * v_cu, 2);

    INSERT INTO public.compras_detalles (compra_id, producto_id, cantidad, costo_unitario_usd, subtotal_usd)
    VALUES (v_compra_id, v_pid, v_cant, v_cu, v_line);

    SELECT stock_actual, costo_usd INTO v_old_stock, v_old_cost
    FROM public.productos
    WHERE id = v_pid
    FOR UPDATE;

    IF v_old_stock + v_cant > 0 THEN
      UPDATE public.productos
      SET
        stock_actual = v_old_stock + v_cant,
        costo_usd = ROUND(
          (v_old_cost * v_old_stock + v_cu * v_cant) / (v_old_stock + v_cant),
          2
        )
      WHERE id = v_pid;
    ELSE
      UPDATE public.productos
      SET stock_actual = v_old_stock + v_cant, costo_usd = v_cu
      WHERE id = v_pid;
    END IF;
  END LOOP;

  IF p_forma_pago = 'contado' THEN
    INSERT INTO public.movimientos_caja (
      caja_id, tipo, monto_usd, concepto, referencia, venta_id, compra_id, usuario_id
    ) VALUES (
      p_caja_id,
      'Egreso',
      v_total,
      'Compra #' || v_num::TEXT,
      NULL,
      NULL,
      v_compra_id,
      p_usuario_id
    );
  ELSE
    INSERT INTO public.cuentas_por_pagar (compra_id, monto_pendiente_usd, fecha_vencimiento, estado)
    VALUES (v_compra_id, v_total, p_fecha_vencimiento, 'Pendiente');
  END IF;

  RETURN v_compra_id;
END;
$$;

REVOKE ALL ON FUNCTION public.crear_compra_erp(UUID, TEXT, TEXT, UUID, NUMERIC, NUMERIC, DATE, TEXT, JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.crear_compra_erp(UUID, TEXT, TEXT, UUID, NUMERIC, NUMERIC, DATE, TEXT, JSONB) TO service_role;

-- -----------------------------------------------------------------------------
-- RPC: movimiento manual de caja
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.registrar_movimiento_caja_erp(
  p_usuario_id UUID,
  p_caja_id UUID,
  p_tipo TEXT,
  p_monto_usd NUMERIC,
  p_concepto TEXT,
  p_referencia TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_id UUID;
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

  INSERT INTO public.movimientos_caja (
    caja_id, tipo, monto_usd, concepto, referencia, venta_id, compra_id, usuario_id
  ) VALUES (
    p_caja_id,
    p_tipo,
    p_monto_usd,
    TRIM(p_concepto),
    NULLIF(TRIM(p_referencia), ''),
    NULL,
    NULL,
    p_usuario_id
  )
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.registrar_movimiento_caja_erp(UUID, UUID, TEXT, NUMERIC, TEXT, TEXT) TO service_role;

-- -----------------------------------------------------------------------------
-- -----------------------------------------------------------------------------
-- RPC: cobro CXC (p_cobros opcional, mismas monedas)
-- -----------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------
-- Vista: saldo consolidado (suma de cajas)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_balance_consolidado_usd AS
SELECT COALESCE(SUM(saldo_actual_usd), 0)::NUMERIC(18, 2) AS total_usd
FROM public.cajas_bancos
WHERE activo = TRUE;

GRANT SELECT ON public.v_balance_consolidado_usd TO service_role;

-- -----------------------------------------------------------------------------
-- Recalcular equivalentes Bs en productos (llama la app tras sincronizar tasa web)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.refresh_productos_bs_equiv(p_tasa_bs NUMERIC)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.productos
  SET
    precio_v_bs_ref = ROUND((precio_v_usd * p_tasa_bs)::numeric, 4),
    costo_bs_ref = ROUND((costo_usd * p_tasa_bs)::numeric, 4),
    updated_at = NOW()
  WHERE activo = TRUE
    AND p_tasa_bs IS NOT NULL
    AND p_tasa_bs > 0;
$$;

REVOKE ALL ON FUNCTION public.refresh_productos_bs_equiv(NUMERIC) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.refresh_productos_bs_equiv(NUMERIC) TO service_role;

-- -----------------------------------------------------------------------------
-- Datos semilla (opcional): tasas de ejemplo, cajas y usuario admin (username admin)
-- -----------------------------------------------------------------------------
INSERT INTO public.tasas_dia (fecha, tasa_bs, tasa_usdt)
VALUES (
  (CURRENT_DATE AT TIME ZONE 'America/Caracas')::DATE,
  36.5,
  1.0
)
ON CONFLICT (fecha) DO NOTHING;

INSERT INTO public.erp_users (username, nombre, email, rol, password_hash)
SELECT
  'admin',
  'Superusuario',
  'admin@movi.local',
  'superuser',
  crypt('admin', gen_salt('bf'))
WHERE NOT EXISTS (SELECT 1 FROM public.erp_users WHERE lower(username) = 'admin');

-- Si ya existía admin sin contraseña (instalaciones anteriores), asignar una inicial
UPDATE public.erp_users
SET password_hash = crypt('admin', gen_salt('bf'))
WHERE lower(username) = 'admin'
  AND (password_hash IS NULL OR btrim(password_hash) = '');

INSERT INTO public.cajas_bancos (nombre, tipo, saldo_actual_usd)
SELECT v.nombre, v.tipo, 0::NUMERIC(18, 2)
FROM (
  VALUES
    ('Banesco USD', 'Banco'),
    ('Binance USDT', 'Wallet'),
    ('Caja Chica', 'Efectivo')
) AS v(nombre, tipo)
WHERE NOT EXISTS (SELECT 1 FROM public.cajas_bancos cb WHERE cb.nombre = v.nombre);

COMMENT ON TABLE public.erp_users IS 'Usuarios ERP: password_hash con bcrypt (crypt gen_salt bf o app Python).';
COMMENT ON FUNCTION public.crear_venta_erp IS 'Transacción atómica: valida stock, inserta venta, descuenta stock, caja o CXC.';
COMMENT ON FUNCTION public.crear_compra_erp IS 'Transacción atómica: actualiza stock y costo promedio, compra, caja o CXP.';

-- Permisos para la clave service_role (Streamlit en servidor / Edge)
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON
  public.erp_users,
  public.tasas_dia,
  public.categorias,
  public.productos,
  public.cajas_bancos,
  public.ventas,
  public.ventas_detalles,
  public.cuentas_por_cobrar,
  public.compras,
  public.compras_detalles,
  public.cuentas_por_pagar,
  public.movimientos_caja
TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.ventas_numero_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.compras_numero_seq TO service_role;
