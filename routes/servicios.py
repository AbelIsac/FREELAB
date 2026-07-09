from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from config.supabase import supabase
from utils.decorators import login_required, role_required
import os
from datetime import datetime
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
load_dotenv(override=True)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "doc", "docx"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

servicios_bp = Blueprint("servicios", __name__)


@servicios_bp.route("/explorar-servicios")
def explorar_productos():
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

        servicios = query.execute().data

    except Exception as e:
        print("ERROR EXPLORANDO SERVICIOS:", e)
        servicios = []

    return render_template(
        "servicios/explorar_productos.html",
        servicios=servicios,
        q=q
    )


@servicios_bp.route("/producto/<int:producto_id>")
def detalle_producto(producto_id):
    try:
        producto = (
            supabase.table("productos")
            .select("*")
            .eq("id", producto_id)
            .single()
            .execute()
        )

        if not producto.data:
            flash("Servicio no encontrado", "error")
            return redirect(url_for("servicios.explorar_productos"))

        vendedor = (
            supabase.table("perfiles")
            .select("nombre")
            .eq("id", producto.data["vendedor_id"])
            .execute()
        )

        vendedor_nombre = vendedor.data[0]["nombre"] if vendedor.data else "Estudiante"

        return render_template(
            "servicios/detalle_producto.html",
            producto=producto.data,
            vendedor_nombre=vendedor_nombre
        )

    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("servicios.explorar_productos"))


@servicios_bp.route("/publicar-producto")
@login_required
@role_required("estudiante")
def publicar_producto():
    return render_template("estudiante/publicar_producto.html")


@servicios_bp.route("/guardar-producto", methods=["POST"])
@login_required
@role_required("estudiante")
def guardar_producto():
    titulo = request.form.get("titulo")
    descripcion = request.form.get("descripcion")
    precio = request.form.get("precio")
    categoria_id = request.form.get("categoria")

    if not titulo or not precio:
        flash("Título y precio son obligatorios", "error")
        return redirect(url_for("servicios.publicar_producto"))

    try:
        data = {
            "vendedor_id": session["user"]["id"],
            "titulo": titulo,
            "descripcion": descripcion,
            "precio": float(precio),
            "categoria_id": int(categoria_id) if categoria_id and categoria_id.isdigit() else None,
            "estado": "pendiente"
        }

        # Imagen principal del servicio - Cloudinary
        if "imagen" in request.files:
            file = request.files["imagen"]

            if file and file.filename and allowed_file(file.filename):
                resultado = cloudinary.uploader.upload(
                    file,
                    folder="freelab/servicios",
                    transformation=[
                        {"quality": "auto", "fetch_format": "auto"}
                    ]
                )

                data["imagen_url"] = resultado["secure_url"]

        respuesta = supabase.table("productos").insert(data).execute()

        print("SERVICIO GUARDADO:", respuesta.data)

        flash("Servicio enviado a revisión del administrador", "success")
        return redirect(url_for("servicios.mis_productos"))

    except Exception as e:
        print("ERROR AL GUARDAR SERVICIO:", e)
        flash(f"Error al publicar servicio: {str(e)}", "error")
        return redirect(url_for("servicios.publicar_producto"))


@servicios_bp.route("/mis-productos")
@login_required
@role_required("estudiante")
def mis_productos():
    print("USUARIO LOGUEADO:", session["user"]["id"])

    try:
        productos = (
            supabase.table("productos")
            .select("*, categorias(nombre)")
            .eq("vendedor_id", session["user"]["id"])
            .order("fecha_publicacion", desc=True)
            .execute()
        )

        print("PRODUCTOS ENCONTRADOS:", productos.data)

        return render_template("estudiante/mis_productos.html", productos=productos.data)

    except Exception as e:
        flash(f"Error al cargar tus servicios: {str(e)}", "error")
        return render_template("estudiante/mis_productos.html", productos=[])

@servicios_bp.route("/mis-servicios/<int:producto_id>")
@login_required
@role_required("estudiante")
def detalle_mi_servicio(producto_id):
    try:
        servicio = (
            supabase.table("productos")
            .select("*, categorias(nombre)")
            .eq("id", producto_id)
            .eq("vendedor_id", session["user"]["id"])
            .single()
            .execute()
        )

        if not servicio.data:
            flash("Servicio no encontrado o no tienes permiso para verlo", "error")
            return redirect(url_for("servicios.mis_productos"))

        return render_template(
            "estudiante/detalle_mi_servicio.html",
            servicio=servicio.data
        )

    except Exception as e:
        flash(f"Error al cargar el servicio: {str(e)}", "error")
        return redirect(url_for("servicios.mis_productos"))


@servicios_bp.route("/productos-destacados")
def productos_destacados():
    try:
        response = (
            supabase.table("productos")
            .select("*")
            .eq("estado", "activo")
            .order("fecha_publicacion", desc=True)
            .limit(8)
            .execute()
        )

        return jsonify({"productos": response.data})

    except Exception:
        return jsonify({"productos": []})
    
@servicios_bp.route("/mis-servicios/eliminar/<int:producto_id>", methods=["DELETE"])
@login_required
@role_required("estudiante")
def eliminar_mi_servicio(producto_id):
    try:
        servicio = (
            supabase.table("productos")
            .select("id, vendedor_id")
            .eq("id", producto_id)
            .eq("vendedor_id", session["user"]["id"])
            .single()
            .execute()
        )

        if not servicio.data:
            return {"success": False, "error": "Servicio no encontrado"}, 404

        supabase.table("productos").delete().eq("id", producto_id).execute()

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}, 500
    
@servicios_bp.route("/mis-servicios/editar/<int:producto_id>", methods=["GET", "POST"])
@login_required
@role_required("estudiante")
def editar_mi_servicio(producto_id):
    try:
        servicio = (
            supabase.table("productos")
            .select("*")
            .eq("id", producto_id)
            .eq("vendedor_id", session["user"]["id"])
            .single()
            .execute()
        )

        if not servicio.data:
            flash("Servicio no encontrado", "error")
            return redirect(url_for("servicios.mis_productos"))

        if request.method == "POST":
            titulo = request.form.get("titulo")
            descripcion = request.form.get("descripcion")
            precio = request.form.get("precio")
            categoria_id = request.form.get("categoria")

            data_update = {
                "titulo": titulo,
                "descripcion": descripcion,
                "precio": float(precio),
                "categoria_id": int(categoria_id) if categoria_id else None,
                "estado": "pendiente"
            }

            if "imagen" in request.files:
                file = request.files["imagen"]

                if file and file.filename and allowed_file(file.filename):
                    resultado = cloudinary.uploader.upload(
                        file,
                        folder="freelab/servicios",
                        transformation=[
                            {"quality": "auto", "fetch_format": "auto"}
                        ]
                    )

                    data_update["imagen_url"] = resultado["secure_url"]

            supabase.table("productos").update(data_update) \
                .eq("id", producto_id) \
                .eq("vendedor_id", session["user"]["id"]) \
                .execute()

            flash("Servicio actualizado y enviado nuevamente a revisión", "success")
            return redirect(url_for("servicios.detalle_mi_servicio", producto_id=producto_id))

        return render_template(
            "estudiante/editar_servicio.html",
            servicio=servicio.data
        )

    except Exception as e:
        flash(f"Error al editar servicio: {str(e)}", "error")
        return redirect(url_for("servicios.mis_productos"))