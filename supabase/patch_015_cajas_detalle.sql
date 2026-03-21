-- Detalle por cuenta: entidad (banco), número, titular, moneda de la cuenta (etiqueta).
-- El saldo sigue siendo en USD equivalente; movimientos ya usan VES/USD/USDT.
-- Ejecutar en Supabase SQL Editor una vez.

ALTER TABLE public.cajas_bancos ADD COLUMN IF NOT EXISTS entidad TEXT;
ALTER TABLE public.cajas_bancos ADD COLUMN IF NOT EXISTS numero_cuenta TEXT;
ALTER TABLE public.cajas_bancos ADD COLUMN IF NOT EXISTS titular TEXT;
ALTER TABLE public.cajas_bancos ADD COLUMN IF NOT EXISTS moneda_cuenta TEXT;

UPDATE public.cajas_bancos
SET moneda_cuenta = 'USD'
WHERE moneda_cuenta IS NULL OR btrim(moneda_cuenta) = '';

ALTER TABLE public.cajas_bancos ALTER COLUMN moneda_cuenta SET DEFAULT 'USD';
ALTER TABLE public.cajas_bancos ALTER COLUMN moneda_cuenta SET NOT NULL;

ALTER TABLE public.cajas_bancos
  DROP CONSTRAINT IF EXISTS cajas_bancos_moneda_cuenta_chk;

ALTER TABLE public.cajas_bancos
  ADD CONSTRAINT cajas_bancos_moneda_cuenta_chk
  CHECK (moneda_cuenta IN ('USD', 'VES', 'USDT'));

COMMENT ON COLUMN public.cajas_bancos.entidad IS 'Banco o plataforma (ej. Banesco, Bancamiga).';
COMMENT ON COLUMN public.cajas_bancos.numero_cuenta IS 'Número de cuenta o identificador en listas.';
COMMENT ON COLUMN public.cajas_bancos.titular IS 'Titular de la cuenta.';
COMMENT ON COLUMN public.cajas_bancos.moneda_cuenta IS 'Moneda nativa de la cuenta (referencia; saldo en USD eq.).';

NOTIFY pgrst, 'reload schema';
