-- Promover tu usuario a administrador del ERP Movi (Streamlit).
-- En Supabase el CHECK `erp_users_rol_check` solo permite:
--   'superuser' | 'admin' | 'vendedor' | 'almacen'
-- NO usar 'administrador' (no está en el CHECK): en esta base el valor válido es exactamente **admin**.
--
-- Ejecutá en SQL Editor. Reemplazá el usuario antes de correr.
UPDATE public.erp_users
SET rol = 'admin'
WHERE username = 'CAMBIAR_POR_TU_USUARIO';

-- Almacén (rol en BD):
-- UPDATE public.erp_users SET rol = 'almacen' WHERE username = 'CAMBIAR_POR_TU_USUARIO';

-- Verificación:
-- SELECT id, username, nombre, rol, activo FROM public.erp_users;
