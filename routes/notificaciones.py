from flask import Blueprint, render_template, session, redirect, url_for, flash
from config.supabase import supabase
from utils.decorators import login_required

notificaciones_bp = Blueprint("notificaciones", __name__)


def crear_notificacion(usuario_id, venta_id, titulo, mensaje, tipo="info"):
    try:
        supabase.table("notificaciones").insert({
            "usuario_id": usuario_id,
            "venta_id": venta_id,
            "titulo": titulo,
            "mensaje": mensaje,
            "tipo": tipo
        }).execute()
    except Exception as e:
        print("ERROR CREANDO NOTIFICACION:", e)


@notificaciones_bp.route("/notificaciones")
@login_required
def listar_notificaciones():
    user_id = session["user"]["id"]

    try:
        notificaciones = (
            supabase.table("notificaciones")
            .select("*, venta:ventas(id, estado)")
            .eq("usuario_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return render_template(
            "notificaciones/lista.html",
            notificaciones=notificaciones.data or []
        )

    except Exception as e:
        print("ERROR NOTIFICACIONES:", e)
        flash("No se pudieron cargar tus notificaciones.", "error")
        return render_template("notificaciones/lista.html", notificaciones=[])


@notificaciones_bp.route("/notificaciones/<int:notificacion_id>/leer", methods=["POST"])
@login_required
def marcar_leida(notificacion_id):
    user_id = session["user"]["id"]

    try:
        supabase.table("notificaciones").update({
            "leida": True
        }).eq("id", notificacion_id).eq("usuario_id", user_id).execute()

    except Exception as e:
        print("ERROR MARCANDO NOTIFICACION:", e)

    return redirect(url_for("notificaciones.listar_notificaciones"))