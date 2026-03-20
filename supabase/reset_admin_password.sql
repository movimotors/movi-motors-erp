-- Si no puedes entrar con admin/admin tras crear el usuario en SQL:
-- 1) En tu PC (misma carpeta del proyecto, con bcrypt instalado):
--    py -c "import bcrypt; print(bcrypt.hashpw(b'admin', bcrypt.gensalt()).decode())"
-- 2) Copia la línea que empieza por $2b$ o $2a$ y pégala abajo en lugar de PEGA_HASH_AQUI
-- 3) Ejecuta este script en Supabase → SQL Editor

UPDATE public.erp_users
SET password_hash = 'PEGA_HASH_AQUI'
WHERE lower(trim(username)) = 'admin';

-- Si no existe la fila admin, créala (ajusta el hash igual que arriba):
-- INSERT INTO public.erp_users (username, nombre, email, rol, password_hash, activo)
-- VALUES ('admin', 'Superusuario', 'admin@movi.local', 'superuser', 'PEGA_HASH_AQUI', true);
