## Movi Motors ERP — Continuar trabajo (estado)

### Repositorios (IMPORTANTE)

- **Repo principal para Streamlit Cloud (donde debe quedar el código):** `movimotors/erp2movi` (privado)
- **Repo espejo / público (si se usa):** `movimotors/movi-motors-erp` (público)

En Streamlit Cloud, los logs mostraban que la app clona **`erp2movi`**. Por eso, para que lo que ves en local sea igual a la nube, hay que hacer `push` a **`movimotors/erp2movi`**.

### Último cambio en repo (abril 2026)

- **Refactor Reportes:** el módulo **Reportes** quedó en `movi/modules/reportes/` (pestañas en `tab_*.py`, orquestación en `layout.py`, dependencias en `deps.py`). `app.py` solo delega con `render_module_reportes` + `ReportesModuleDeps` (mismo patrón que Cajas).
- **Push hecho** a **`erp2movi/main`** y **`origin/main`** (commit `d4ef5a7` en adelante). Si la URL `.streamlit.app` no refleja el cambio: **Manage app → Reboot / Redeploy**.

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

### Checklist Secrets (Streamlit Cloud)

En **Settings → Secrets** de la app, replicar lo que tenés en local (ver `.streamlit/secrets.toml.example`). Mínimo:

| Bloque | Qué va | Notas |
|--------|--------|--------|
| `[connections.supabase]` | `SUPABASE_URL`, `SUPABASE_KEY` | La clave debe ser **service_role** (como indica el propio `app.py`). |
| `[auth]` (opcional) | `SESSION_SIGNING_KEY` | Si no está, la app puede derivar la firma de la clave de Supabase. |
| `[catalogo]` (opcional) | `bucket`, `storage_fotos` / `enabled` | Fotos en Storage; el HTML del catálogo puede seguir sin fotos en nube si apagás subida. |
| `[auto_backup]` (opcional) | `enabled`, `storage_bucket`, `retain_days` | Respaldo automático; requiere bucket y tabla `erp_kv` según patches del proyecto. |

Tras editar Secrets, Streamlit suele **reiniciar** la app sola; si no, **Reboot** manual.

### Después de cambiar código (nube al día)

1. **Push** al repositorio que Streamlit Cloud tiene conectado (suele ser **`erp2movi`**; si solo empujás a **`movi-motors-erp`**, la URL `.streamlit.app` no verá esos commits hasta que empujes al otro remoto o cambies el repo en Cloud).
2. En [share.streamlit.io](https://share.streamlit.io) → tu app → **Manage app** → **Reboot** o **Redeploy** si no se actualiza sola.

### Qué falta / próximos pasos

1) En Streamlit Cloud: confirmar que el repo conectado sea **`movimotors/erp2movi`** y que **Secrets** coincidan con la checklist de arriba.
2) Si hacés cambios nuevos y querés subirlos:

```powershell
cd "c:\Proyectos IA\Movi"
git remote -v
git push origin main
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
