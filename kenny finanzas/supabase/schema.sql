-- =============================================================================
-- Kenny Finanzas — SOLO finanzas personales (Orlando / BofA, etc.)
-- =============================================================================
-- Este archivo es INDEPENDIENTE del ERP de la empresa (Movi / schema_erp / patch_0xx).
-- Creá un proyecto Supabase NUEVO para Kenny Finanzas y ejecutá ÚNICAMENTE este script.
-- NO ejecutes aquí los patches del repo `supabase/` de la empresa: son otra base de datos.
-- =============================================================================
-- Supabase → SQL Editor → New query → pegar → Run.

create extension if not exists "pgcrypto";

-- Cuenta (ej. BofA Orlando Linares)
create table if not exists public.kf_account (
  id uuid primary key default gen_random_uuid(),
  label text not null,
  bank_name text,
  holder_name text,
  currency text not null default 'USD',
  opening_balance numeric(14, 2) not null default 0,
  opening_balance_date date not null default (current_date),
  notes text,
  created_at timestamptz not null default now()
);

-- Movimientos
create table if not exists public.kf_transaction (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.kf_account (id) on delete cascade,
  tx_type text not null check (tx_type in ('ingreso', 'egreso')),
  amount numeric(14, 2) not null check (amount > 0),
  tx_date date not null,
  description text not null default '',
  category text,
  created_at timestamptz not null default now()
);

create index if not exists kf_transaction_account_date_idx
  on public.kf_transaction (account_id, tx_date desc);

alter table public.kf_account enable row level security;
alter table public.kf_transaction enable row level security;

-- La app Streamlit usa la service_role key (bypass RLS).
-- Si más adelante usas anon + Auth, añade políticas aquí.

comment on table public.kf_account is 'Cuentas bancarias / efectivo (saldo inicial desde Excel u otro origen).';
comment on table public.kf_transaction is 'Ingresos y egresos asociados a una cuenta.';
