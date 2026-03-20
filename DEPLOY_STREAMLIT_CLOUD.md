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

## Actualizar la app

Cada `git push` a la rama conectada puede redeployar solo (según tu configuración en Cloud). También puedes usar **Manage app → Reboot** o **Redeploy**.
