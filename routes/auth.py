from flask import Blueprint, redirect, request, url_for, flash, session, render_template
from config.supabase import supabase

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login():
    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            "redirect_to": "https://freelab-szln.onrender.com/callback"
        }
    })
    return redirect(res.url)


@auth_bp.route("/callback")
def callback():
    codigo = request.args.get("code")

    if not codigo:
        flash("No se recibió código de Google", "error")
        return redirect(url_for("home"))

    try:
        sesion = supabase.auth.exchange_code_for_session({
            "auth_code": codigo
        })

        usuario = sesion.user

        perfil = (
            supabase.table("perfiles")
            .select("id, rol")
            .eq("id", usuario.id)
            .execute()
        )

        if not perfil.data:
            supabase.table("perfiles").insert({
                "id": usuario.id,
                "email": usuario.email,
                "nombre": usuario.user_metadata.get("name", "Usuario"),
                "avatar_url": usuario.user_metadata.get(
                    "avatar_url",
                    "https://via.placeholder.com/40"
                ),
                "rol": None
            }).execute()

            rol = None
        else:
            rol = perfil.data[0].get("rol")

        session["user"] = {
            "id": usuario.id,
            "email": usuario.email,
            "name": usuario.user_metadata.get("name", "Usuario"),
            "avatar": usuario.user_metadata.get(
                "avatar_url",
                "https://via.placeholder.com/40"
            ),
            "rol": rol
        }

        if not rol:
            return redirect(url_for("auth.elegir_rol"))

        flash(f"Bienvenido {session['user']['name']}", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        flash(f"Error en callback: {str(e)}", "error")
        return redirect(url_for("home"))


@auth_bp.route("/logout")
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    session.clear()
    flash("Sesión cerrada", "success")
    return redirect(url_for("home"))


@auth_bp.route("/elegir-rol")
def elegir_rol():
    if "user" not in session:
        flash("Inicia sesión primero", "error")
        return redirect(url_for("home"))

    return render_template("elegir_rol.html", user_id=session["user"]["id"])


@auth_bp.route("/guardar-rol")
def guardar_rol():
    if "user" not in session:
        flash("Inicia sesión primero", "error")
        return redirect(url_for("home"))

    rol = request.args.get("rol")
    user_id = session["user"]["id"]

    if rol not in ["estudiante", "comprador"]:
        flash("Rol no válido", "error")
        return redirect(url_for("auth.elegir_rol"))

    try:
        supabase.table("perfiles").update({
            "rol": rol
        }).eq("id", user_id).execute()

        session["user"]["rol"] = rol
        flash(f"Perfil creado como {rol}", "success")

        return redirect(url_for("dashboard"))

    except Exception as e:
        flash(f"Error al guardar rol: {str(e)}", "error")
        return redirect(url_for("auth.elegir_rol"))