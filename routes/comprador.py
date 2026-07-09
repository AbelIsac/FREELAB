from flask import Blueprint, render_template, session, flash, redirect, url_for, request
from config.supabase import supabase
from routes.notificaciones import crear_notificacion
from utils.decorators import login_required, role_required

import cloudinary.uploader

comprador_bp = Blueprint("comprador", __name__)


@comprador_bp.route("/comprador/inicio")
@login_required
@role_required("comprador")
def inicio_comprador():
    q = request.args.get("q", "").strip()
    categoria = request.args.get("categoria")

    try:
        query = (
            supabase.table("productos")
            .select("*")
            .eq("estado", "activo")
            .order("fecha_publicacion", desc=True)
        )

        if categoria and categoria.isdigit():
            query = query.eq("categoria_id", int(categoria))

        if q:
            query = query.ilike("titulo", f"%{q}%")

        servicios = query.execute().data or []

    except Exception as e:
        print("ERROR CARGANDO SERVICIOS COMPRADOR:", e)
        servicios = []

    return render_template(
        "comprador/inicio_comprador.html",
        servicios=servicios,
        q=q
    )


@comprador_bp.route("/solicitar-servicio/<int:producto_id>", methods=["POST"])
@login_required
@role_required("comprador")
def solicitar_servicio(producto_id):
    comprador_id = session["user"]["id"]

    try:
        producto_resp = (
            supabase.table("productos")
            .select("*")
            .eq("id", producto_id)
            .eq("estado", "activo")
            .single()
            .execute()
        )

        if not producto_resp.data:
            flash("El servicio no está disponible.", "error")
            return redirect(url_for("comprador.inicio_comprador"))

        servicio = producto_resp.data

        if servicio["vendedor_id"] == comprador_id:
            flash("No puedes contratar tu propio servicio.", "error")
            return redirect(url_for("servicios.detalle_producto", producto_id=producto_id))

        estados_activos = [
            "pendiente_adelanto",
            "adelanto_enviado",
            "adelanto_confirmado",
            "en_proceso",
            "entrega_realizada",
            "pendiente_pago_final",
            "pago_final_enviado"
        ]

        solicitud_existente = (
            supabase.table("ventas")
            .select("id, estado")
            .eq("producto_id", producto_id)
            .eq("comprador_id", comprador_id)
            .in_("estado", estados_activos)
            .execute()
        )

        if solicitud_existente.data:
            venta_id = solicitud_existente.data[0]["id"]
            flash("Ya tienes una contratación activa para este servicio.", "info")
            return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))

        monto_total = float(servicio["precio"])
        monto_adelanto = round(monto_total * 0.5, 2)
        monto_restante = round(monto_total - monto_adelanto, 2)

        nueva_venta = {
            "producto_id": producto_id,
            "comprador_id": comprador_id,
            "vendedor_id": servicio["vendedor_id"],
            "monto": monto_total,
            "monto_adelanto": monto_adelanto,
            "monto_restante": monto_restante,
            "estado": "pendiente_adelanto"
        }

        venta_creada = (
            supabase.table("ventas")
            .insert(nueva_venta)
            .execute()
        )

        venta_id = venta_creada.data[0]["id"]

        crear_notificacion(
            servicio["vendedor_id"],
            venta_id,
            "Nueva solicitud recibida",
            "Un comprador solicitó uno de tus servicios. Revisa tu panel de solicitudes.",
            "info"
        )

        flash("Solicitud creada. Ahora debes coordinar y subir el comprobante del adelanto 50%.", "success")
        return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))

    except Exception as e:
        print("ERROR AL SOLICITAR SERVICIO:", e)
        flash("No se pudo solicitar el servicio.", "error")
        return redirect(url_for("servicios.detalle_producto", producto_id=producto_id))


@comprador_bp.route("/contratacion/<int:venta_id>")
@login_required
@role_required("comprador")
def detalle_contratacion(venta_id):
    comprador_id = session["user"]["id"]

    try:
        venta = (
            supabase.table("ventas")
            .select(
                "*, producto:productos(*), vendedor:perfiles!vendedor_id(*)"
            )
            .eq("id", venta_id)
            .eq("comprador_id", comprador_id)
            .single()
            .execute()
        )

        if not venta.data:
            flash("Contratación no encontrada.", "error")
            return redirect(url_for("comprador.mis_compras"))

        comprobantes = (
            supabase.table("comprobantes")
            .select("*")
            .eq("venta_id", venta_id)
            .order("fecha", desc=True)
            .execute()
        )
        valoracion = (
            supabase.table("valoraciones")
            .select("*")
            .eq("venta_id", venta_id)
            .execute()
        )

        return render_template(
            "comprador/detalle_contratacion.html",
            venta=venta.data,
            comprobantes=comprobantes.data or [],
            valoracion=valoracion.data[0] if valoracion.data else None
        )

    except Exception as e:
        print("ERROR DETALLE CONTRATACION:", e)
        flash("No se pudo cargar la contratación.", "error")
        return redirect(url_for("comprador.mis_compras"))


@comprador_bp.route("/dashboard/comprador")
@login_required
@role_required("comprador")
def dashboard_comprador():
    return redirect(url_for("comprador.inicio_comprador"))


@comprador_bp.route("/mis-compras")
@login_required
@role_required("comprador")
def mis_compras():
    comprador_id = session["user"]["id"]

    

    try:
        compras_resp = (
            supabase.table("ventas")
            .select("*, producto:productos(*)")
            .eq("comprador_id", comprador_id)
            .order("fecha_venta", desc=True)
            .execute()
        )

    

        return render_template(
            "comprador/mis_compras.html",
            compras=compras_resp.data or []
        )

    except Exception as e:
        print("ERROR MIS COMPRAS:", e)
        flash(f"Error al cargar tus compras: {str(e)}", "error")
        return render_template("comprador/mis_compras.html", compras=[])


@comprador_bp.route("/favoritos")
@login_required
@role_required("comprador")
def favoritos():
    try:
        favs = (
            supabase.table("favoritos")
            .select("*, producto:productos(*)")
            .eq("usuario_id", session["user"]["id"])
            .execute()
        )

        return render_template("comprador/favoritos.html", favoritos=favs.data or [])

    except Exception as e:
        flash(f"Error al cargar favoritos: {str(e)}", "error")
        return render_template("comprador/favoritos.html", favoritos=[])


@comprador_bp.route("/mis-resenas")
@login_required
@role_required("comprador")
def mis_resenas():
    try:
        ventas = (
            supabase.table("ventas")
            .select("*, producto:productos(*), valoraciones(*)")
            .eq("comprador_id", session["user"]["id"])
            .execute()
        )

        con_resena = [
            v for v in ventas.data or []
            if v.get("valoraciones") and len(v["valoraciones"]) > 0
        ]

        return render_template("comprador/mis_resenas.html", resenas=con_resena)

    except Exception as e:
        flash(f"Error al cargar reseñas: {str(e)}", "error")
        return render_template("comprador/mis_resenas.html", resenas=[])


@comprador_bp.route("/configuracion")
@login_required
@role_required("comprador")
def configuracion():
    return render_template("comprador/configuracion.html", user=session["user"])

@comprador_bp.route("/contratacion/<int:venta_id>/subir-comprobante", methods=["POST"])
@login_required
@role_required("comprador")
def subir_comprobante(venta_id):
    comprador_id = session["user"]["id"]

    tipo_pago = request.form.get("tipo_pago")
    etapa = request.form.get("etapa")
    archivo = request.files.get("comprobante")

    if not tipo_pago or not etapa or not archivo:
        flash("Completa todos los datos del comprobante.", "error")
        return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))

    try:
        venta = (
            supabase.table("ventas")
            .select("*")
            .eq("id", venta_id)
            .eq("comprador_id", comprador_id)
            .single()
            .execute()
        )

        if not venta.data:
            flash("Contratación no encontrada.", "error")
            return redirect(url_for("comprador.mis_compras"))

        resultado = cloudinary.uploader.upload(
            archivo,
            folder="freelab/comprobantes",
            transformation=[
                {"quality": "auto", "fetch_format": "auto"}
            ]
        )

        comprobante_data = {
            "venta_id": venta_id,
            "imagen_url": resultado["secure_url"],
            "tipo_pago": tipo_pago,
            "etapa": etapa,
            "estado": "pendiente"
        }

        supabase.table("comprobantes").insert(comprobante_data).execute()

        nuevo_estado = venta.data["estado"]

        if etapa == "adelanto" and venta.data["estado"] == "pendiente_adelanto":
            nuevo_estado = "adelanto_enviado"

        if etapa == "pago_final" and venta.data["estado"] == "entrega_realizada":
            nuevo_estado = "pago_final_enviado"

        if nuevo_estado != venta.data["estado"]:
            supabase.table("ventas").update({
                "estado": nuevo_estado
            }).eq("id", venta_id).execute()

            if nuevo_estado == "adelanto_enviado":
                crear_notificacion(
                    venta.data["vendedor_id"],
                    venta_id,
                    "Adelanto enviado",
                    "El comprador subió el comprobante del adelanto 50%.",
                    "success"
                )

            if nuevo_estado == "pago_final_enviado":
                crear_notificacion(
                    venta.data["vendedor_id"],
                    venta_id,
                    "Pago final enviado",
                    "El comprador subió el comprobante del pago final.",
                    "success"
                )

        flash("Comprobante subido correctamente.", "success")
        return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))

    except Exception as e:
        print("ERROR SUBIENDO COMPROBANTE:", e)
        flash("No se pudo subir el comprobante.", "error")
        return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))
    

@comprador_bp.route("/contratacion/<int:venta_id>/resena", methods=["POST"])
@login_required
@role_required("comprador")
def dejar_resena(venta_id):
    comprador_id = session["user"]["id"]

    calificacion = request.form.get("calificacion")
    comentario = request.form.get("comentario")

    if not calificacion:
        flash("Selecciona una calificación.", "error")
        return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))

    try:
        venta_resp = (
            supabase.table("ventas")
            .select("*")
            .eq("id", venta_id)
            .eq("comprador_id", comprador_id)
            .single()
            .execute()
        )

        if not venta_resp.data:
            flash("Contratación no encontrada.", "error")
            return redirect(url_for("comprador.mis_compras"))

        venta = venta_resp.data

        if venta["estado"] != "completado":
            flash("Solo puedes valorar contrataciones completadas.", "error")
            return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))

        existe = (
            supabase.table("valoraciones")
            .select("id")
            .eq("venta_id", venta_id)
            .execute()
        )

        if existe.data:
            flash("Ya valoraste esta contratación.", "info")
            return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))

        supabase.table("valoraciones").insert({
            "venta_id": venta_id,
            "comprador_id": comprador_id,
            "vendedor_id": venta["vendedor_id"],
            "producto_id": venta["producto_id"],
            "calificacion": int(calificacion),
            "comentario": comentario
        }).execute()

        flash("Reseña registrada correctamente.", "success")
        return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))

    except Exception as e:
        print("ERROR RESEÑA:", e)
        flash("No se pudo registrar la reseña.", "error")
        return redirect(url_for("comprador.detalle_contratacion", venta_id=venta_id))