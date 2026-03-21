# Mantenimiento a largo plazo — Movi ERP

Checklist operativo para quien mantenga **Streamlit + Supabase** sin perder trazabilidad. Complementa [README.md](README.md) y [DEPLOY_STREAMLIT_CLOUD.md](DEPLOY_STREAMLIT_CLOUD.md).

**Paquete para Google Drive y repo Git nuevo:** [empresa_backup_drive/INSTRUCCIONES.md](empresa_backup_drive/INSTRUCCIONES.md) + script `generar_respaldo.ps1` (salida en **`respaldos/`**).

---

## Antes de tocar producción

- [ ] **Git:** cambios en una rama o commit claro en `main` (mensaje que diga qué y por qué).
- [ ] **SQL:** si hay cambio de BD, existe un archivo `supabase/patch_XXX_....sql` (o actualización documentada del schema) **antes** de ejecutar en Supabase.
- [ ] **Respaldo:** descarga un **respaldo completo** (Mantenimiento → `.json` o `.json.gz`) y guardalo **fuera** del servidor y del repo.
- [ ] **Secrets:** `.streamlit/secrets.toml` local y Secrets de Streamlit Cloud **no** subidos a Git; si rotaste API keys, actualizá ambos lados.

---

## Cadencia sugerida

### Cada vez que desplegás código

- [ ] `git push` a la rama que usa Streamlit Cloud (suele ser `main`).
- [ ] Si falla el arranque: **Manage app → Logs** en Cloud; local: consola donde corre `streamlit run app.py`.
- [ ] Si agregaste dependencias: revisá que `requirements.txt` esté actualizado (Cloud instala desde ahí).

### Semanal (o tras muchos cambios en BD)

- [ ] Anotá en una libreta / issue / tabla interna: **fecha + nombre del patch** aplicado en Supabase (ej. `patch_019_...`).
- [ ] Revisá que el **superusuario** pueda entrar y que **tasas del día** estén cargadas si usan multimoneda en pantalla.

### Mensual

- [ ] **Respaldo completo** descargado y copiado a otro medio (PC, disco, nube privada).
- [ ] Revisar **usuarios activos** en módulo Usuarios: desactivar quien ya no debe entrar.
- [ ] Opcional: revisar en Supabase **uso / límites** y logs de API si algo “anda raro”.

### Tras incidente (error, restauración, hackeo)

- [ ] Documentar qué pasó y qué hiciste (una línea en un doc interno basta).
- [ ] Si restauraste JSON: verificar login y contraseñas temporales (`Restaurar2025!` si aplica).
- [ ] Si filtró la `service_role`: **rotar** en Supabase y actualizar secrets.

---

## Archivos y convenciones del repo

| Qué | Dónde |
|-----|--------|
| Esquema base | `supabase/schema_erp_multimoneda.sql` |
| Evolución de BD | `supabase/patch_*.sql` (numerados; no reordenar números ya aplicados en prod) |
| App | `app.py` |
| Dependencias | `requirements.txt` |
| Python en Cloud | `runtime.txt` (ej. `python-3.12.8`) |
| Secretos locales | `.streamlit/secrets.toml` (gitignored) |
| Ejemplo secretos | `.streamlit/secrets.toml.example` |

---

## Respaldos (recordatorio)

- **Completo:** Mantenimiento → descarga → guardar fuera del repo. Restaurar solo con confirmación **`RESTAURAR_TODO`**.
- **Automático diario:** primer login del día de un **superusuario**; ver README para `patch_010` y bucket opcional en Storage.
- **Solo inventario:** más limitado; no sustituye al completo si hay ventas/compras.

---

## Mejora continua (1 línea de deuda)

Mantené una lista corta (GitHub Issues, Notion o `TODO.md`) con: *bug conocido*, *parche pendiente en prod*, *idea de reporte*. Así el mantenimiento no depende de memoria.

---

*Última revisión sugerida del documento: al cambiar de versión mayor de Python o al migrar de host (Cloud → VPS).*
