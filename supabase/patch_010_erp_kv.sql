-- Clave-valor mínima para la app (p. ej. coordinar respaldo automático diario entre instancias).
CREATE TABLE IF NOT EXISTS public.erp_kv (
  key text PRIMARY KEY,
  value text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.erp_kv IS 'Pares clave-valor internos del ERP (service_role).';

ALTER TABLE public.erp_kv ENABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
