"""Módulo Usuarios del sistema (superusuario): alta, listado y edición."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
import streamlit as st
from supabase import Client


@dataclass(frozen=True)
class UsuariosModuleDeps:
    modulo_titulo_info: Callable[..., None]
    hash_password: Callable[[str], str]
    movi_ss_pop_keys: Callable[..., None]
    movi_bump_form_nonce: Callable[[str], None]


def render_module_usuarios(sb: Client, *, embedded_in_mantenimiento: bool, deps: UsuariosModuleDeps) -> None:
    d = deps
    if embedded_in_mantenimiento:
        _uu1, _uu2 = st.columns([4.5, 1.05], gap="small")
        with _uu1:
            st.markdown("### Usuarios del sistema")
        with _uu2:
            with st.expander("Información", expanded=False, key="modinfo_exp_usuarios_emb"):
                st.markdown(
                    "Solo el **superusuario** puede crear cuentas y definir la contraseña inicial de cada persona."
                )
    else:
        d.modulo_titulo_info(
            "Usuarios del sistema",
            key="usuarios",
            ayuda_md="Solo el **superusuario** puede crear cuentas y definir la contraseña inicial de cada persona.",
        )

    r = (
        sb.table("erp_users")
        .select("id,username,nombre,email,rol,activo,created_at")
        .order("nombre")
        .execute()
    )
    rows = r.data or []
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Nuevo usuario")
    with st.form(f"f_new_user_{int(st.session_state.get('erp_new_user_form_nonce', 0))}"):
        nu = st.text_input("Usuario (solo letras/números, sin espacios)", key="nu_user")
        nn = st.text_input("Nombre completo", key="nu_nom")
        ne = st.text_input("Correo (opcional)", key="nu_mail")
        nr = st.selectbox(
            "Rol",
            options=["vendedor", "admin", "almacen", "superuser"],
            format_func=lambda x: {
                "vendedor": "Vendedor (ventas y cobros CXC)",
                "admin": "Administrador (compras, cajas, reportes, tasas…)",
                "almacen": "Almacén (inventario; catálogo y etiquetas en Reportes)",
                "superuser": "Superusuario (acceso total)",
            }[x],
            key="nu_rol",
        )
        p1 = st.text_input("Contraseña inicial", type="password", key="nu_p1")
        p2 = st.text_input("Repetir contraseña", type="password", key="nu_p2")
        if st.form_submit_button("Crear usuario"):
            un = (nu or "").strip().lower()
            if not un or not nn.strip():
                st.error("Usuario y nombre son obligatorios.")
            elif not p1 or p1 != p2:
                st.error("Las contraseñas no coinciden o están vacías.")
            elif len(p1) < 4:
                st.error("La contraseña debe tener al menos 4 caracteres.")
            else:
                ex = sb.table("erp_users").select("id").eq("username", un).limit(1).execute()
                if (ex.data or []):
                    st.error("Ese usuario ya existe.")
                else:
                    sb.table("erp_users").insert(
                        {
                            "username": un,
                            "nombre": nn.strip(),
                            "email": ne.strip() or None,
                            "rol": nr,
                            "password_hash": d.hash_password(p1),
                            "activo": True,
                        }
                    ).execute()
                    st.success(f"Usuario **{un}** creado. Ya puede iniciar sesión.")
                    d.movi_ss_pop_keys("nu_user", "nu_nom", "nu_mail", "nu_rol", "nu_p1", "nu_p2")
                    d.movi_bump_form_nonce("erp_new_user_form_nonce")
                    st.rerun()

    if not rows:
        return

    st.divider()
    st.markdown("#### Editar usuario")
    labels = {f"{u['nombre']} (@{u['username']})": u for u in rows}
    pick = st.selectbox("Seleccionar", options=list(labels.keys()))
    u = labels[pick]
    uid = str(u["id"])
    with st.form(f"f_edit_user_{uid}_{int(st.session_state.get(f'erp_edit_user_form_nonce_{uid}', 0))}"):
        act = st.checkbox("Activo", value=bool(u.get("activo", True)), key="ed_act")
        _roles = ["vendedor", "admin", "almacen", "superuser"]
        _ri = _roles.index(u["rol"]) if u["rol"] in _roles else 0
        new_rol = st.selectbox(
            "Rol",
            options=_roles,
            index=_ri,
            format_func=lambda x: {
                "vendedor": "Vendedor",
                "admin": "Administrador",
                "almacen": "Almacén",
                "superuser": "Superusuario",
            }[x],
            key="ed_rol",
        )
        np1 = st.text_input("Nueva contraseña (dejar vacío para no cambiar)", type="password", key="ed_p1")
        np2 = st.text_input("Repetir nueva contraseña", type="password", key="ed_p2")
        if st.form_submit_button("Guardar cambios"):
            if np1 or np2:
                if np1 != np2:
                    st.error("Las contraseñas nuevas no coinciden.")
                elif len(np1) < 4:
                    st.error("La contraseña debe tener al menos 4 caracteres.")
                else:
                    sb.table("erp_users").update(
                        {
                            "activo": act,
                            "rol": new_rol,
                            "password_hash": d.hash_password(np1),
                        }
                    ).eq("id", uid).execute()
                    st.success("Usuario actualizado.")
                    d.movi_ss_pop_keys("ed_act", "ed_rol", "ed_p1", "ed_p2")
                    d.movi_bump_form_nonce(f"erp_edit_user_form_nonce_{uid}")
                    st.rerun()
            else:
                sb.table("erp_users").update({"activo": act, "rol": new_rol}).eq("id", uid).execute()
                st.success("Usuario actualizado.")
                d.movi_ss_pop_keys("ed_act", "ed_rol", "ed_p1", "ed_p2")
                d.movi_bump_form_nonce(f"erp_edit_user_form_nonce_{uid}")
                st.rerun()

    st.caption(
        "Si eres el único superusuario, evita desactivarte o quedarte sin contraseña."
    )
