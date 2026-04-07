# Checklist Movi ERP — mantenimiento simple

Resumen operativo: código en Git, datos en respaldos JSON, secretos fuera del repo. Complementa [README.md](README.md) y [MAINTENANCE.md](MAINTENANCE.md).

---

## Cada vez que programás algo que ya funciona

- [ ] `git add` / `git commit` / `git push` a la rama que usa Streamlit (suele ser `main`).

---

## Una vez por semana (ej. viernes)

- [ ] Entrar como **superusuario** → **Mantenimiento** → **Descargar respaldo completo** (`.json.gz`).
- [ ] Guardar el archivo en **2 sitios** (ej. PC + Drive o pendrive), con **fecha en el nombre** (ej. `movi_respaldo_2026-04-07.json.gz`).
- [ ] Verificar que el archivo existe y el tamaño tiene sentido.

---

## Una vez al mes

- [ ] Probar login con usuario normal y con **superusuario**.
- [ ] Revisar **usuarios**: desactivar quien no deba entrar.
- [ ] Si aplicaste **parches SQL** en Supabase, anotar **número de patch** y **fecha** (celular, hoja, Notion).

---

## Antes de cosas peligrosas

- [ ] **Restaurar** desde JSON, borrar datos masivos o pruebas grandes en producción → **respaldo completo ese mismo día** antes de tocar nada.

---

## Secretos y recuperación

- [ ] Tener **`secrets.toml`** (o los valores) **copiados fuera del repo** (gestor de contraseñas, USB, carpeta cifrada).
- [ ] **No** subir `secrets.toml` a GitHub.

---

## Si cambiás de PC o se rompe el disco

- [ ] En la máquina nueva: instalar **Git** + **Python**, `git clone` del repo.
- [ ] Copiar **`.streamlit/secrets.toml`** desde tu resguardo.
- [ ] `pip install -r requirements.txt` y probar `streamlit run app.py` (si trabajás local).

---

## Supabase (proyecto nuevo o base vacía)

- [ ] Ejecutar **`supabase/schema_erp_multimoneda.sql`** (o lo que indique el README).
- [ ] Ejecutar los **`patch_*.sql`** pendientes **en orden** según el historial de la base (no reordenar en producción sin revisar).
- [ ] Configurar **URL + service_role** en secrets (local y/o Streamlit Cloud).

---

## Streamlit Cloud

- [ ] Mismo repo/rama; **`requirements.txt`** actualizado.
- [ ] **Secrets** en el panel de Cloud = mismos datos que `secrets.toml` (sin subirlos al repo).

---

## Regla corta

| Qué | Dónde |
|-----|--------|
| Código | GitHub (`git push`) |
| Datos del negocio | JSON completo desde **Mantenimiento** (semanal + antes de riesgos) |
| Claves | Fuera del repo; copia segura |
| Parches SQL | Carpeta `supabase/` en Git; ejecutar en Supabase **a mano** cuando toque |

---

*Última revisión sugerida: al cambiar flujo de despliegue o de respaldos.*
