# Movi Motors ERP (Streamlit + Supabase)

1. En Supabase → SQL Editor: ejecutar `supabase/schema_erp_multimoneda.sql` (proyecto nuevo recomendado).
2. Copiar `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y completar URL + `service_role`. El acceso es con **usuario y contraseña** definidos en Supabase (`erp_users`); el primer acceso suele ser usuario `admin` y contraseña `admin` (cámbiala en el módulo **Usuarios**). Si tu base ya existía, ejecuta también `supabase/patch_004_erp_users_password_vendedor.sql` y, para el dashboard de tasas (BCV, paralelo, EUR, P2P), `supabase/patch_005_tasas_dashboard.sql` (corrige **PGRST204** si faltan columnas en `tasas_dia`). Para recalcular equivalentes Bs en productos al sincronizar tasas, ejecuta `supabase/patch_007_productos_bs_ref.sql`. Para **cobros en Bs / USD / USDT por caja** y el resumen en el dashboard, ejecuta `supabase/patch_008_movimientos_moneda_cobros.sql`.

**Tasas en vivo:** el panel “tiempo real” usa APIs públicas (`tasas_live.py`: VES vía open.er-api.com, EUR/USD vía Frankfurter). El VES de esa API **no** es el BCV oficial; el BCV debes cargarlo a mano desde **Dashboard → Cargar / editar tasas en base de datos**.
3. Ejecutar la app:

```bash
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

El esquema anterior `supabase/schema.sql` es otra variante (auth de Supabase); no mezclar ambos en la misma base sin migrar.

## Streamlit Community Cloud

Para publicar la app en internet (sin dejar tu PC encendido), sigue **[DEPLOY_STREAMLIT_CLOUD.md](DEPLOY_STREAMLIT_CLOUD.md)**. Resumen: conectas el repo en [share.streamlit.io](https://share.streamlit.io), pones **Main file** `app.py` y copias los **Secrets** (mismo TOML que `secrets.toml`).
