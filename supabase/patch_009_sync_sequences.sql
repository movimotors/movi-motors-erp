-- Tras importar ventas/compras con número explícito, alinea secuencias para el próximo DEFAULT.
CREATE OR REPLACE FUNCTION public.sync_erp_sequences()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM setval(
    'public.ventas_numero_seq',
    GREATEST((SELECT COALESCE(MAX(numero), 0) FROM public.ventas), 1)
  );
  PERFORM setval(
    'public.compras_numero_seq',
    GREATEST((SELECT COALESCE(MAX(numero), 0) FROM public.compras), 1)
  );
END;
$$;

REVOKE ALL ON FUNCTION public.sync_erp_sequences() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.sync_erp_sequences() TO service_role;

NOTIFY pgrst, 'reload schema';
