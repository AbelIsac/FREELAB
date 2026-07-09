from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from config.supabase import supabase
from utils.decorators import login_required, role_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    try:
        productos = (
            supabase.table("productos")
            .select("id, estado", count="exact")
            .execute()
        )

        ventas = (
            supabase.table("ventas")
            .select("id, estado, monto", count="exact")
            .execute()
        )

        perfiles = (
            supabase.table("perfiles")
            .select("id, rol", count="exact")
            .execute()
        )

        comprobantes = (
            supabase.table("comprobantes")
            .select("id", count="exact")
            .execute()
        )

        valoraciones = (
            supabase.table("valoraciones")
            .select("id, calificacion", count="exact")
            .execute()
        )

        productos_data = productos.data or []
        ventas_data = ventas.data or []
        perfiles_data = perfiles.data or []
        valoraciones_data = valoraciones.data or []

        ingresos_totales = sum(
            float(v.get("monto") or 0)
            for v in ventas_data
            if v.get("estado") == "completado"
        )

        promedio_global = 0
        if valoraciones_data:
            promedio_global = round(
                sum(v.get("calificacion") or 0 for v in valoraciones_data) / len(valoraciones_data),
                1
            )

        stats = {
            "total_productos": len(productos_data),
            "productos_pendientes": len([p for p in productos_data if p.get("estado") == "pendiente"]),
            "productos_activos": len([p for p in productos_data if p.get("estado") == "activo"]),
            "total_ventas": len(ventas_data),
            "ventas_completadas": len([v for v in ventas_data if v.get("estado") == "completado"]),
            "ventas_activas": len([
                v for v in ventas_data
                if v.get("estado") in [
                    "pendiente_adelanto",
                    "adelanto_enviado",
                    "en_proceso",
                    "entrega_realizada",
                    "pago_final_enviado"
                ]
            ]),
            "usuarios": len(perfiles_data),
            "estudiantes": len([p for p in perfiles_data if p.get("rol") == "estudiante"]),
            "compradores": len([p for p in perfiles_data if p.get("rol") == "comprador"]),
            "comprobantes": comprobantes.count or 0,
            "valoraciones": len(valoraciones_data),
            "promedio_global": promedio_global,
            "ingresos_totales": ingresos_totales
        }

    except Exception as e:
        print("ERROR ADMIN DASHBOARD:", e)
        stats = {
            "total_productos": 0,
            "productos_pendientes": 0,
            "productos_activos": 0,
            "total_ventas": 0,
            "ventas_completadas": 0,
            "ventas_activas": 0,
            "usuarios": 0,
            "estudiantes": 0,
            "compradores": 0,
            "comprobantes": 0,
            "valoraciones": 0,
            "promedio_global": 0,
            "ingresos_totales": 0
        }

    return render_template("admin/dashboard.html", stats=stats)

@admin_bp.route("/admin/categorias")
@login_required
@role_required("admin")
def admin_categorias():
    categorias = supabase.table("categorias").select("*").order("id").execute()
    return render_template("admin/categorias.html", categorias=categorias.data)


@admin_bp.route("/admin/categoria/crear", methods=["POST"])
@login_required
@role_required("admin")
def admin_categoria_crear():
    nombre = request.form.get("nombre")
    descripcion = request.form.get("descripcion")

    if not nombre:
        flash("El nombre es obligatorio", "error")
        return redirect(url_for("admin.admin_categorias"))

    supabase.table("categorias").insert({
        "nombre": nombre,
        "descripcion": descripcion
    }).execute()

    flash("Categoría creada", "success")
    return redirect(url_for("admin.admin_categorias"))


@admin_bp.route("/admin/todas-publicaciones")
@login_required
@role_required("admin")
def admin_todas_publicaciones():
    try:
        productos = (
            supabase.table("productos")
            .select("*, perfiles(nombre)")
            .order("fecha_publicacion", desc=True)
            .execute()
        )

        return render_template(
            "admin/todas_publicaciones.html",
            productos=productos.data
        )

    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/publicacion/aprobar/<int:producto_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_aprobar_producto(producto_id):
    supabase.table("productos").update({
        "estado": "activo"
    }).eq("id", producto_id).execute()

    flash("Servicio aprobado y visible para compradores", "success")
    return redirect(url_for("admin.admin_todas_publicaciones"))


@admin_bp.route("/admin/publicacion/rechazar/<int:producto_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_rechazar_producto(producto_id):
    supabase.table("productos").update({
        "estado": "rechazado"
    }).eq("id", producto_id).execute()

    flash("Servicio rechazado", "warning")
    return redirect(url_for("admin.admin_todas_publicaciones"))


@admin_bp.route("/admin/transacciones")
@login_required
@role_required("admin")
def admin_transacciones():
    try:
        ventas = (
            supabase.table("ventas")
            .select(
                "*, producto:productos(titulo, precio), comprador:perfiles!comprador_id(nombre, rol), vendedor:perfiles!vendedor_id(nombre, carrera), comprobantes(*), valoraciones(*)"
            )
            .order("fecha_venta", desc=True)
            .execute()
        )

        return render_template("admin/transacciones.html", ventas=ventas.data or [])

    except Exception as e:
        print("ERROR ADMIN TRANSACCIONES:", e)
        flash(f"Error: {str(e)}", "error")
        return render_template("admin/transacciones.html", ventas=[])


@admin_bp.route("/admin/transaccion/aprobar/<int:venta_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_aprobar_transaccion(venta_id):
    supabase.table("ventas").update({
        "estado": "completado"
    }).eq("id", venta_id).execute()

    flash("Transacción aprobada", "success")
    return redirect(url_for("admin.admin_transacciones"))


@admin_bp.route("/admin/transaccion/cancelar/<int:venta_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_cancelar_transaccion(venta_id):
    supabase.table("ventas").update({
        "estado": "cancelado"
    }).eq("id", venta_id).execute()

    flash("Transacción cancelada", "warning")
    return redirect(url_for("admin.admin_transacciones"))


@admin_bp.route("/admin/eliminar-publicacion/<int:producto_id>", methods=["DELETE"])
@login_required
@role_required("admin")
def admin_eliminar_publicacion(producto_id):
    try:
        producto = (
            supabase.table("productos")
            .select("*")
            .eq("id", producto_id)
            .single()
            .execute()
        )

        if not producto.data:
            return jsonify({"success": False, "error": "Servicio no encontrado"}), 404

        supabase.table("productos").delete().eq("id", producto_id).execute()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
@admin_bp.route("/admin/usuarios")
@login_required
@role_required("admin")
def admin_usuarios():
    try:
        usuarios = (
            supabase.table("perfiles")
            .select("*")
            .order("creado_en", desc=True)
            .execute()
        )

        return render_template(
            "admin/usuarios.html",
            usuarios=usuarios.data or []
        )

    except Exception as e:
        print("ERROR ADMIN USUARIOS:", e)
        flash("No se pudieron cargar los usuarios.", "error")
        return render_template("admin/usuarios.html", usuarios=[])
    
@admin_bp.route("/admin/valoraciones")
@login_required
@role_required("admin")
def admin_valoraciones():
    try:
        valoraciones = (
            supabase.table("valoraciones")
            .select(
                "*, producto:productos(titulo), comprador:perfiles!comprador_id(nombre), vendedor:perfiles!vendedor_id(nombre)"
            )
            .order("fecha", desc=True)
            .execute()
        )

        return render_template(
            "admin/valoraciones.html",
            valoraciones=valoraciones.data or []
        )

    except Exception as e:
        print("ERROR ADMIN VALORACIONES:", e)
        flash("No se pudieron cargar las valoraciones.", "error")
        return render_template("admin/valoraciones.html", valoraciones=[])
    
@admin_bp.route("/admin/comprobantes")
@login_required
@role_required("admin")
def admin_comprobantes():
    try:
        comprobantes = (
            supabase.table("comprobantes")
            .select(
                "*, venta:ventas(id, monto, estado, producto:productos(titulo), comprador:perfiles!comprador_id(nombre), vendedor:perfiles!vendedor_id(nombre))"
            )
            .order("fecha", desc=True)
            .execute()
        )

        return render_template(
            "admin/comprobantes.html",
            comprobantes=comprobantes.data or []
        )

    except Exception as e:
        print("ERROR ADMIN COMPROBANTES:", e)
        flash("No se pudieron cargar los comprobantes.", "error")
        return render_template("admin/comprobantes.html", comprobantes=[])