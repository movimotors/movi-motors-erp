-- Promover tu usuario a administrador del ERP (movi-erp / Streamlit).
-- En Supabase el CHECK `erp_users_rol_check` solo permite:
--   'superuser' | 'admin' | 'vendedor' | 'almacen'
-- NO usar 'administrador' (no está en el CHECK). En Laravel eso se mapea desde 'admin'.
--
-- Ejecutá en SQL Editor. Reemplazá el usuario antes de correr.
UPDATE public.erp_users
SET rol = 'admin'
WHERE username = 'CAMBIAR_POR_TU_USUARIO';

-- Almacén (mismo nombre en BD y en Laravel):
-- UPDATE public.erp_users SET rol = 'almacen' WHERE username = 'CAMBIAR_POR_TU_USUARIO';

-- Verificación:
-- SELECT id, username, nombre, rol, activo FROM public.erp_users;
