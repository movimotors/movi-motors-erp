## Movi Motors ERP — Continuar trabajo (estado)

### Repositorios (IMPORTANTE)

- **Repo principal para Streamlit Cloud (donde debe quedar el código):** `movimotors/erp2movi` (privado)
- **Repo espejo / público (si se usa):** `movimotors/movi-motors-erp` (público)

En Streamlit Cloud, los logs mostraban que la app clona **`erp2movi`**. Por eso, para que lo que ves en local sea igual a la nube, hay que hacer `push` a **`movimotors/erp2movi`**.

### Feature reciente: fotos por producto + catálogo imprimible

- **Código**: agregado módulo **`Catálogo`** en `app.py`
  - Subida de foto al **crear producto** (Inventario → Nuevo producto).
  - Galería por producto (subir varias, marcar principal, eliminar).
  - Catálogo **online** y **descargable/imprimible** como HTML (A4).
- **BD (Supabase)**: patch `supabase/patch_021_catalogo_fotos_productos.sql`
  - Tabla `producto_fotos` (múltiples fotos + una principal).
- **Storage (Supabase)**:
  - Bucket recomendado: **`movi-productos`** (ideal público para que las imágenes carguen en el HTML).
  - Configurable en secrets:

```toml
[catalogo]
bucket = "movi-productos"
```

### Después de cambiar código (nube al día)

1. **Push** al repositorio que Streamlit Cloud tiene conectado (suele ser **`erp2movi`**; si solo empujás a **`movi-motors-erp`**, la URL `.streamlit.app` no verá esos commits hasta que empujes al otro remoto o cambies el repo en Cloud).
2. En [share.streamlit.io](https://share.streamlit.io) → tu app → **Manage app** → **Reboot** o **Redeploy** si no se actualiza sola.

### Qué falta / próximos pasos

1) Asegurar que **Streamlit Cloud** esté desplegando desde `movimotors/erp2movi` y que tenga los **Secrets** correctos.
2) Subir el código al repo **`movimotors/erp2movi`** (si aún no está):

```powershell
cd "c:\Proyectos IA\Movi"
git remote -v
git push erp2movi main
```

Si Git rechaza por historial distinto y querés que “mande tu PC”:

```powershell
git push --force erp2movi main
```

### Nota de conectividad

Si aparece `Could not resolve host: github.com`, es un problema de red/DNS/proxy. En ese caso:
- probar otra red (hotspot),
- revisar VPN/proxy,
- reintentar el `git push`.

