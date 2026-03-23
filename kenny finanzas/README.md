# Kenny Finanzas

App Streamlit para registrar **ingresos** y **egresos** (por ejemplo cuenta BofA — Orlando Linares), con **saldo inicial** desde Excel y datos en **Supabase**.

## Separación del sistema de la empresa

- **Kenny Finanzas** usa **otro proyecto de Supabase** y **otro SQL** que el ERP Movi.
- Solo debés ejecutar el archivo de esta carpeta: **`kenny finanzas/supabase/schema.sql`**.
- **No** uses los `patch_*.sql`, `schema_erp_*.sql` ni demás scripts de `Movi/supabase/` en la base de finanzas personales: son del negocio y no aplican aquí.

## 1. Proyecto en Supabase (dedicado)

1. Creá un **proyecto nuevo** en [Supabase](https://supabase.com) solo para finanzas personales.
2. En **SQL Editor**, ejecutá **únicamente** `kenny finanzas/supabase/schema.sql`.

## 2. Secretos locales

1. Copiá `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml`.
2. Pegá `SUPABASE_URL` y `SUPABASE_KEY`. Para uso solo personal desde tu PC, suele usarse la clave **service_role** (no la expongas en repositorios públicos).

## 3. Entorno y ejecución

```bash
cd "kenny finanzas"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## 4. GitHub

- **Repo aparte:** dentro de esta carpeta, `git init`, creá el repo en GitHub y `git remote add origin …` + `push`.
- **Dentro del repo Movi:** la carpeta ya queda versionada con el resto del monorepo.

## Saldo

El **saldo mostrado** = saldo inicial (fecha de referencia) + ingresos − egresos registrados en la app. Ajustá el saldo inicial en la pestaña correspondiente si alineás con Excel.
