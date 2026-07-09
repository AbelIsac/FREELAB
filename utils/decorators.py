from functools import wraps
from flask import session, flash, redirect, url_for
from config.supabase import supabase


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Inicia sesión", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user" not in session:
                flash("Inicia sesión", "error")
                return redirect(url_for("home"))

            user_id = session["user"]["id"]

            respuesta = (
                supabase.table("perfiles")
                .select("rol")
                .eq("id", user_id)
                .execute()
            )

            rol = respuesta.data[0]["rol"] if respuesta.data else None

            if rol not in roles:
                flash("Acceso no autorizado", "error")
                return redirect(url_for("dashboard"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator