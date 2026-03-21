# Movi Motors ERP (Streamlit + Supabase)

**Mantenimiento a largo plazo:** checklist operativo en **[MAINTENANCE.md](MAINTENANCE.md)** (Git, SQL, respaldos, despliegue).

**Respaldo para Google Drive + repo Git nuevo:** carpeta **[empresa_backup_drive/](empresa_backup_drive/)** → leé `INSTRUCCIONES.md` y ejecutá `generar_respaldo.ps1` (el paquete queda en **`respaldos/`**).

1. En Supabase → SQL Editor: ejecutar `supabase/schema_erp_multimoneda.sql` (proyecto nuevo recomendado).
2. Copiar `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y completar URL + `service_role`. Para **anular una venta o compra** mal cargada (superusuario → Mantenimiento), ejecutá también `supabase/patch_020_anular_venta_compra.sql`. El acceso es con **usuario y contraseña** definidos en Supabase (`erp_users`); el primer acceso suele ser usuario `admin` y contraseña `admin` (cámbiala en el módulo **Usuarios**). Si tu base ya existía, ejecuta también `supabase/patch_004_erp_users_password_vendedor.sql` y, para el dashboard de tasas (BCV, paralelo, EUR, P2P), `supabase/patch_005_tasas_dashboard.sql` (corrige **PGRST204** si faltan columnas en `tasas_dia`). Para recalcular equivalentes Bs en productos al sincronizar tasas, ejecuta `supabase/patch_007_productos_bs_ref.sql`. Para **cobros en Bs / USD / USDT por caja** y el resumen en el dashboard, ejecuta `supabase/patch_008_movimientos_moneda_cobros.sql`. Para que la **restauración completa desde JSON** pueda alinear los números de factura/compra (`sync_erp_sequences`), ejecuta `supabase/patch_009_sync_sequences.sql` (también incluido en `schema_erp_multimoneda.sql` si creás el proyecto desde cero). Para el **respaldo automático diario** (tabla `erp_kv` que marca el día ya respaldado), ejecuta `supabase/patch_010_erp_kv.sql` (también va en el esquema completo si empezás de cero).

**Tasas en vivo:** el panel “tiempo real” usa APIs públicas (`tasas_live.py`: VES vía open.er-api.com, EUR/USD vía Frankfurter). El VES de esa API **no** es el BCV oficial; el BCV debes cargarlo a mano desde **Dashboard → Cargar / editar tasas en base de datos**.

3. **Respaldos y restauración (casi un clic):** guardá los archivos **fuera del repo**.  
   - **Todo el ERP:** **Mantenimiento** (superusuario) → *Descargar respaldo completo* (`movi_erp_completo_*.json`) o la variante **`.json.gz`** (mismo contenido, mucho más liviana). Para volver atrás: subís `.json` o `.gz`, escribís **`RESTAURAR_TODO`** y **Restaurar todo ahora**. La app borra datos actuales y reimporta; si un usuario del respaldo no existía en la base, queda con contraseña temporal **`Restaurar2025!`** (cambiala en **Usuarios**). Si falla el RPC de secuencias, ejecutá `patch_009` en el SQL Editor.  
   - **Respaldo automático diario (bajo peso):** el primer acceso del día de un **superusuario** genera `auto_backups/movi_erp_auto_YYYY-MM-DD.json.gz` (JSON compacto + gzip). Sin `patch_010`, se usa un archivo local `.last_auto_day_v1` en esa carpeta (vale en un solo servidor). Con **Streamlit Cloud** u otra nube, ejecutá **`patch_010`** y, si querés copia en la nube, creá un bucket privado en Supabase Storage y definí `[auto_backup] storage_bucket = "nombre"` en los secrets (la app sube a `auto/`). Los gzip locales viejos se eliminan según `retain_days` (por defecto 14).  
   - **Solo inventario:** **Inventario** → expander de respaldo → descarga JSON o **`.json.gz`**; restaurar con **`RESTAURAR_INVENTARIO`** (también acepta `.json.gz`). Si hay ventas/compras que referencian productos, puede fallar por claves foráneas: en ese caso usá el respaldo completo o depurá antes. En la grilla podés **filtrar**, asignar **categoría** por lista y, en CSV masivo, columna opcional **`categoria`** (nombre de la categoría). **Imprimir / exportar listado:** expander homónimo → mismos filtros y orden; descarga **Excel (.xlsx)**, **PDF** (A4 **vertical**, márgenes ~18 mm, **logo** `assets/logo_movimotors.png` si existe) y **HTML** (A4 vertical, `@page` con márgenes, logo incrustado, botón imprimir oculto al imprimir). Dependencias: `openpyxl` y `reportlab`.

4. Ejecutar la app:

```bash
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

El esquema anterior `supabase/schema.sql` es otra variante (auth de Supabase); no mezclar ambos en la misma base sin migrar.

## Streamlit Community Cloud

Para publicar la app en internet (sin dejar tu PC encendido), sigue **[DEPLOY_STREAMLIT_CLOUD.md](DEPLOY_STREAMLIT_CLOUD.md)**. Resumen: conectas el repo en [share.streamlit.io](https://share.streamlit.io), pones **Main file** `app.py` y copias los **Secrets** (mismo TOML que `secrets.toml`).
