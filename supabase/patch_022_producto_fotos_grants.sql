-- Permisos para `producto_fotos` (clave service_role / Streamlit).
-- Si aplicaste patch_021 sin GRANT, los INSERT desde la app pueden fallar en la tabla de fotos.
-- Idempotente: repetir no rompe.

GRANT SELECT, INSERT, UPDATE, DELETE ON public.producto_fotos TO service_role;
