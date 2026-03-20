-- Ejecutar en Supabase SQL Editor si ya tenías schema_erp_multimoneda sin password_hash ni rol vendedor.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Columna contraseña
ALTER TABLE public.erp_users
  ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- 2) Ampliar roles (quitar constraint viejo y crear uno nuevo)
ALTER TABLE public.erp_users DROP CONSTRAINT IF EXISTS erp_users_rol_check;
ALTER TABLE public.erp_users
  ADD CONSTRAINT erp_users_rol_check
  CHECK (rol IN ('superuser', 'admin', 'vendedor', 'almacen'));

-- 3) Usuario admin: contraseña inicial "admin" (cámbiala al entrar)
UPDATE public.erp_users
SET password_hash = crypt('admin', gen_salt('bf'))
WHERE lower(username) = 'admin'
  AND (password_hash IS NULL OR btrim(password_hash) = '');
