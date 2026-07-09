from flask import Blueprint, render_template, session, redirect, url_for, flash, jsonify, request
from config.supabase import supabase
from utils.decorators import login_required

chat_bp = Blueprint("chat", __name__)


def _get_venta_o_none(venta_id, user_id):
    """Trae la venta solo si el usuario logueado es el comprador o el vendedor."""
    venta = (
        supabase.table("ventas")
        .select(
            "*, producto:productos(titulo), "
            "comprador:perfiles!comprador_id(id, nombre, avatar_url), "
            "vendedor:perfiles!vendedor_id(id, nombre, avatar_url)"
        )
        .eq("id", venta_id)
        .single()
        .execute()
    )

    if not venta.data:
        return None

    if user_id not in (venta.data["comprador_id"], venta.data["vendedor_id"]):
        return None

    return venta.data


@chat_bp.route("/chat/<int:venta_id>")
@login_required
def ver_chat(venta_id):
    user_id = session["user"]["id"]
    venta = _get_venta_o_none(venta_id, user_id)

    if not venta:
        flash("No tienes acceso a esta conversación.", "error")
        return redirect(url_for("dashboard"))

    otro = venta["vendedor"] if user_id == venta["comprador_id"] else venta["comprador"]

    try:
        mensajes = (
            supabase.table("mensajes")
            .select("*")
            .eq("venta_id", venta_id)
            .order("created_at")
            .execute()
        )
        mensajes_data = mensajes.data or []
    except Exception as e:
        print("ERROR CARGANDO MENSAJES:", e)
        mensajes_data = []

    # marcar como leídos los mensajes que me enviaron a mí
    try:
        supabase.table("mensajes") \
            .update({"leido": True}) \
            .eq("venta_id", venta_id) \
            .neq("emisor_id", user_id) \
            .eq("leido", False) \
            .execute()
    except Exception as e:
        print("ERROR MARCANDO LEIDOS:", e)

    return render_template(
        "chat/chat.html",
        venta=venta,
        otro=otro,
        mensajes=mensajes_data,
        user_id=user_id,
    )


@chat_bp.route("/chat/<int:venta_id>/enviar", methods=["POST"])
@login_required
def enviar_mensaje(venta_id):
    user_id = session["user"]["id"]
    venta = _get_venta_o_none(venta_id, user_id)

    if not venta:
        return jsonify({"ok": False, "error": "Sin acceso"}), 403

    contenido = (request.form.get("contenido") or "").strip()
    if not contenido:
        return jsonify({"ok": False, "error": "Mensaje vacío"}), 400

    try:
        nuevo = (
            supabase.table("mensajes")
            .insert({
                "venta_id": venta_id,
                "emisor_id": user_id,
                "contenido": contenido,
            })
            .execute()
        )
        return jsonify({"ok": True, "mensaje": nuevo.data[0]})
    except Exception as e:
        print("ERROR ENVIANDO MENSAJE:", e)
        return jsonify({"ok": False, "error": "No se pudo enviar"}), 500


@chat_bp.route("/chat/<int:venta_id>/mensajes")
@login_required
def obtener_mensajes(venta_id):
    """Endpoint que el JS del chat consulta cada pocos segundos (polling)."""
    user_id = session["user"]["id"]
    venta = _get_venta_o_none(venta_id, user_id)

    if not venta:
        return jsonify({"ok": False, "error": "Sin acceso"}), 403

    desde_id = request.args.get("desde_id", 0, type=int)

    try:
        query = (
            supabase.table("mensajes")
            .select("*")
            .eq("venta_id", venta_id)
            .order("created_at")
        )
        if desde_id:
            query = query.gt("id", desde_id)

        mensajes = query.execute()

        # marcar como leidos los nuevos que no son mios
        supabase.table("mensajes") \
            .update({"leido": True}) \
            .eq("venta_id", venta_id) \
            .neq("emisor_id", user_id) \
            .eq("leido", False) \
            .execute()

        return jsonify({"ok": True, "mensajes": mensajes.data or []})
    except Exception as e:
        print("ERROR POLLING MENSAJES:", e)
        return jsonify({"ok": False, "mensajes": []})
