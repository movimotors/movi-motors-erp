-- Promover tu usuario actual a administrador (movi-erp / inventario completo).
-- Ejecutá esto en Supabase → SQL Editor (o psql). Revisá el WHERE antes de correr.
--
-- Opción recomendada: por nombre de usuario (reemplazá el valor entre comillas).
UPDATE public.erp_users
SET rol = 'administrador'
WHERE username = 'CAMBIAR_POR_TU_USUARIO';

-- Si preferís almacén en lugar de administrador:
-- UPDATE public.erp_users SET rol = 'almacen' WHERE username = 'CAMBIAR_POR_TU_USUARIO';

-- Verificación (opcional):
-- SELECT id, username, nombre, rol, activo FROM public.erp_users;
