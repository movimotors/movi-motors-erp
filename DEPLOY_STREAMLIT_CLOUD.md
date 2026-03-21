# Desplegar en Streamlit Community Cloud

Guía para publicar **erp2movi** en [share.streamlit.io](https://share.streamlit.io) (gratis con cuenta GitHub).

## Requisitos previos

1. Código en GitHub (p. ej. `movimotors/erp2movi`), rama `main`.
2. Proyecto **Supabase** con el SQL aplicado (`schema_erp_multimoneda.sql` + parches que uses).
3. Clave **`service_role`** de Supabase (solo en secretos del Cloud, **nunca** en el repo).

## Pasos en Streamlit Cloud

1. Entra en [share.streamlit.io](https://share.streamlit.io) e inicia sesión con GitHub.
2. **New app** → elige el repositorio y la rama **`main`**.
3. **Main file path:** `app.py` (raíz del repo).
4. **App URL:** elige un subdominio disponible (quedará algo como `https://TU-APP.streamlit.app`).

## Secrets (obligatorio)

En la app → **Settings** (⚙️) → **Secrets**, pega un TOML **igual** a tu `.streamlit/secrets.toml` local (sin comentarios de ejemplo si quieres):

```toml
[connections.supabase]
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...."

# Opcional (recomendado en producción):
# [auth]
# SESSION_SIGNING_KEY = "una-cadena-larga-y-aleatoria-solo-tuya"
```

Guarda. **Redeploy** la app si ya estaba creada.

## Comprobar que arranca

- Si falla el import, revisa que `requirements.txt` esté en la raíz (ya está en el repo).
- Si ves error de Supabase, revisa URL y que la clave sea **service_role** (no la anon pública, salvo que hayas adaptado RLS y el código).

## Seguridad

- La `service_role` **omite RLS**: trátala como contraseña de root. No la compartas ni la subas a Git.
- Si la pegaste en un chat o en un commit por error, **rótala** en Supabase (Settings → API).

## Notas

- **Python:** el repo incluye `runtime.txt` para alinear versión en Cloud (evita sorpresas con librerías).
- **Cookies de sesión:** en `https://*.streamlit.app` suelen funcionar; si algo raro pasa al refrescar, prueba otro navegador o revisa bloqueo de cookies.
- **Binance P2P / APIs externas:** algunos despliegues en la nube comparten IPs que Binance a veces limita; si el P2P falla, el código usa respaldo (mismo VES que la API USD→VES). El BCV sigue siendo manual en **Tasas del día**.
- **Operación continua:** ver **[MAINTENANCE.md](MAINTENANCE.md)** (respaldos, parches SQL, secretos).

## Actualizar la app

Cada `git push` a la rama conectada puede redeployar solo (según tu configuración en Cloud). También puedes usar **Manage app → Reboot** o **Redeploy**.

## No veo los últimos cambios en la URL `.streamlit.app`

1. **GitHub:** abrí el repo `erp2movi` → rama **`main`** → confirmá que el último commit (fecha/mensaje) es el que acabás de subir.
2. **Streamlit Cloud:** [share.streamlit.io](https://share.streamlit.io) → tu app → **⋮** o **Manage app**:
   - **App source:** que el repo y la rama sean los correctos (no otra rama ni fork viejo).
   - **Main file:** `app.py` en la raíz.
3. Forzá redeploy: **Manage app → Reboot** o **Redeploy** (a veces el webhook de GitHub llega tarde o falla).
4. Esperá **1–3 minutos** y revisá **Manage app → Logs** por errores de build o de import.
5. En el navegador: recarga fuerte (**Ctrl+F5**) o probá en ventana privada (caché del cliente).
6. Si la app pide login de sesión, **Cerrar sesión** y volvé a entrar por si quedó estado viejo en cookies.
