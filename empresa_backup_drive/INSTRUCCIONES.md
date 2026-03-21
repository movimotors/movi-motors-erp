# Respaldo para Google Drive + repo nuevo Git

## Cómo se manejan las rutas (para hablar con el asistente o con vos)

- **Ruta del proyecto:** la carpeta donde está `app.py` (ej. `C:\Proyectos IA\Movi`).
- En el código y en Cursor suele usarse la **ruta relativa** desde la raíz del repo: `empresa_backup_drive\INSTRUCCIONES.md`.
- En PowerShell, el script usa **`$PSScriptRoot`**: siempre sabe dónde está él y sube un nivel para llegar a la raíz del ERP, así podés ejecutarlo sin “adivinar” rutas.

---

## Paso 1 — Generar la carpeta lista para copiar

1. Abrí **PowerShell**.
2. Andá a la raíz del proyecto (donde está `app.py`):

   ```powershell
   cd "C:\Proyectos IA\Movi"
   ```

   *(Ajustá la ruta si tu carpeta tiene otro nombre o disco.)*

3. Ejecutá:

   ```powershell
   powershell -ExecutionPolicy Bypass -File ".\empresa_backup_drive\generar_respaldo.ps1"
   ```

4. El script crea una carpeta **dentro de `Movi\respaldos\`**, con nombre tipo:

   `respaldos\Movi_backup_para_drive_20260319_1530`

   Ahí dentro queda **todo el código y SQL** listo para subir. **No incluye** (por seguridad y tamaño):

   - `.git` (así el “nuevo repo” empieza limpio)
   - `__pycache__`, `venv`, `.venv`
   - `.streamlit\secrets.toml` (**tus claves**; sí se copia `secrets.toml.example`)
   - `auto_backups`, `auth_state.json`, `*.pyc`

---

## Paso 2 — Subir a Google Drive de la empresa

1. Abrí **Explorador de archivos** en tu proyecto: `Movi\respaldos\`.
2. Copiá la carpeta `Movi_backup_para_drive_....` completa.
3. Pegala en **Google Drive** (carpeta acordada con la empresa).

> **Importante:** `secrets.toml` no va en el zip/carpeta por defecto. Guardá las claves en un gestor seguro o en un documento interno aparte, no público en Drive.

---

## Paso 3 — Subir todo a un **nuevo** repositorio Git (GitHub u otro)

En la máquina donde tengas la carpeta del respaldo (o después de bajarla de Drive):

1. Entrá a la carpeta generada:

   ```powershell
   cd "C:\Proyectos IA\Movi\respaldos\Movi_backup_para_drive_20260319_1530"
   ```

2. Inicializá repo y primer commit:

   ```powershell
   git init
   git add .
   git commit -m "Respaldo inicial Movi ERP (Streamlit + Supabase)"
   git branch -M main
   ```

3. En GitHub: **New repository** → **sin** README ni .gitignore (repo vacío). Copiá la URL HTTPS.

4. Conectá y subí:

   ```powershell
   git remote add origin https://github.com/TU_ORG/TU_REPO_NUEVO.git
   git push -u origin main
   ```

5. En el servidor (ej. Streamlit Cloud): conectá la app al **nuevo repo** y volvé a cargar **Secrets** con el mismo contenido que tu `secrets.toml` local (URL + `SUPABASE_KEY`, etc.).

---

## Resumen

| Acción | Qué usar |
|--------|-----------|
| Carpeta para Drive | La que genera `generar_respaldo.ps1` |
| Repo nuevo | `git init` dentro de esa carpeta + `remote` + `push` |
| Claves Supabase | No van en el respaldo por defecto; configurar de nuevo en cada entorno |

Si algo falla, copiá el mensaje de PowerShell o de `git` y pegalo en el chat del asistente.
