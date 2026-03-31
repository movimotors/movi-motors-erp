-- Catálogo de fotos por producto (Supabase Storage + tabla de metadatos).
-- Objetivo: permitir múltiples fotos por producto + foto principal.
--
-- Requisitos:
-- - Crear un bucket en Supabase Storage (recomendado público) llamado `movi-productos`
--   o el que configures en la app (ver `app.py`).
-- - La app sube archivos a `productos/<producto_id>/...` dentro del bucket.
--
-- Nota: este parche crea SOLO la tabla en Postgres; el bucket se crea desde el panel de Supabase.

create table if not exists public.producto_fotos (
  id uuid primary key default gen_random_uuid(),
  producto_id uuid not null references public.productos (id) on delete cascade,
  storage_path text not null,
  is_primary boolean not null default false,
  created_at timestamptz not null default now(),
  created_by uuid null references public.erp_users (id) on delete set null
);

create index if not exists producto_fotos_producto_idx
  on public.producto_fotos (producto_id, created_at desc);

-- Solo una foto principal por producto.
create unique index if not exists producto_fotos_one_primary_per_producto
  on public.producto_fotos (producto_id)
  where (is_primary is true);

comment on table public.producto_fotos is
  'Fotos de productos para catálogo (paths en Supabase Storage).';

comment on column public.producto_fotos.storage_path is
  'Ruta del objeto dentro del bucket (ej. productos/<producto_id>/<archivo>.jpg).';

-- Misma convención que en schema_erp_multimoneda.sql (Streamlit con service_role).
GRANT SELECT, INSERT, UPDATE, DELETE ON public.producto_fotos TO service_role;
