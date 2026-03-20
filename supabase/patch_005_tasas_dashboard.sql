-- Tasas extendidas para dashboard (BCV, paralelo, EUR, P2P USDT) y comparativos.
-- Ejecutar en Supabase SQL Editor después de schema_erp_multimoneda.

ALTER TABLE public.tasas_dia
  ADD COLUMN IF NOT EXISTS bcv_bs_por_usd NUMERIC(24, 8),
  ADD COLUMN IF NOT EXISTS paralelo_bs_por_usd NUMERIC(24, 8),
  ADD COLUMN IF NOT EXISTS usd_por_eur NUMERIC(24, 8),
  ADD COLUMN IF NOT EXISTS p2p_bs_por_usdt NUMERIC(24, 8);

COMMENT ON COLUMN public.tasas_dia.bcv_bs_por_usd IS 'BCV oficial: Bs por 1 USD';
COMMENT ON COLUMN public.tasas_dia.paralelo_bs_por_usd IS 'Paralelo / mercado: Bs por 1 USD';
COMMENT ON COLUMN public.tasas_dia.usd_por_eur IS 'USD por 1 EUR (ej. 1 EUR = 1,08 USD → 1.08)';
COMMENT ON COLUMN public.tasas_dia.p2p_bs_por_usdt IS 'P2P: Bs por 1 USDT';

UPDATE public.tasas_dia SET bcv_bs_por_usd = tasa_bs WHERE bcv_bs_por_usd IS NULL;
UPDATE public.tasas_dia SET paralelo_bs_por_usd = tasa_bs WHERE paralelo_bs_por_usd IS NULL;
UPDATE public.tasas_dia SET p2p_bs_por_usdt = tasa_bs / NULLIF(tasa_usdt, 0) WHERE p2p_bs_por_usdt IS NULL AND tasa_usdt IS NOT NULL;
UPDATE public.tasas_dia SET usd_por_eur = 1.08 WHERE usd_por_eur IS NULL;

-- Evita PGRST204 hasta que PostgREST refresque el esquema
NOTIFY pgrst, 'reload schema';
