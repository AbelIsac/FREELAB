from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from config.supabase import supabase
from routes import notificaciones
from utils.decorators import login_required, role_required
from routes.notificaciones import crear_notificacion
import cloudinary.uploader

estudiante_bp = Blueprint("estudiante", __name__)

@estudiante_bp.route("/portafolio")
@login_required
@role_required("estudiante")
def mi_portafolio():
    estudiante_id = session["user"]["id"]

    try:
        trabajos = (
            supabase.table("portafolio")
            .select("*")
            .eq("estudiante_id", estudiante_id)
            .order("created_at", desc=True)
            .execute()
        )

        return render_template(
            "estudiante/portafolio.html",
            trabajos=trabajos.data
        )

    except Exception as e:
        print("ERROR PORTAFOLIO:", e)
        flash("Error al cargar portafolio", "error")
        return redirect(url_for("estudiante.dashboard_estudiante"))


@estudiante_bp.route("/portafolio/crear", methods=["POST"])
@login_required
@role_required("estudiante")
def crear_portafolio():
    estudiante_id = session["user"]["id"]

    titulo = request.form.get("titulo")
    descripcion = request.form.get("descripcion")
    categoria = request.form.get("categoria")
    link_demo = request.form.get("link_demo")

    if not titulo:
        flash("El título del trabajo es obligatorio", "error")
        return redirect(url_for("estudiante.mi_portafolio"))

    data = {
        "estudiante_id": estudiante_id,
        "titulo": titulo,
        "descripcion": descripcion,
        "categoria": categoria,
        "link_demo": link_demo
    }

    try:
        if "imagen" in request.files:
            file = request.files["imagen"]

            if file and file.filename:
                resultado = cloudinary.uploader.upload(
                    file,
                    folder="freelab/portafolio",
                    transformation=[
                        {"quality": "auto", "fetch_format": "auto"}
                    ]
                )

                data["imagen_url"] = resultado["secure_url"]

        supabase.table("portafolio").insert(data).execute()

        flash("Trabajo agregado al portafolio", "success")
        return redirect(url_for("estudiante.mi_portafolio"))

    except Exception as e:
        print("ERROR CREANDO PORTAFOLIO:", e)
        flash("No se pudo agregar el trabajo", "error")
        return redirect(url_for("estudiante.mi_portafolio"))


@estudiante_bp.route("/portafolio/eliminar/<int:trabajo_id>", methods=["POST"])
@login_required
@role_required("estudiante")
def eliminar_portafolio(trabajo_id):
    estudiante_id = session["user"]["id"]

    try:
        supabase.table("portafolio") \
            .delete() \
            .eq("id", trabajo_id) \
            .eq("estudiante_id", estudiante_id) \
            .execute()

        flash("Trabajo eliminado del portafolio", "success")

    except Exception as e:
        print("ERROR ELIMINANDO PORTAFOLIO:", e)
        flash("No se pudo eliminar el trabajo", "error")

    return redirect(url_for("estudiante.mi_portafolio"))
@estudiante_bp.route("/dashboard/estudiante")
@login_required
@role_required("estudiante")
def dashboard_estudiante():
    user_id = session["user"]["id"]

    try:
        productos = (
            supabase.table("productos")
            .select("id, estado")
            .eq("vendedor_id", user_id)
            .execute()
        )

        ventas = (
            supabase.table("ventas")
            .select("id, estado, monto, fecha_venta, comprador_id, producto:productos(titulo), comprador:perfiles!comprador_id(nombre)")
            .eq("vendedor_id", user_id)
            .order("fecha_venta", desc=True)
            .execute()
        )

        total_productos = sum(
            1 for p in productos.data if p.get("estado") == "activo"
        )

        clientes_unicos = (
            len(set(v["comprador_id"] for v in ventas.data))
            if ventas.data else 0
        )

        stats = {
            "ventas": len(ventas.data),
            "productos": total_productos,
            "calificacion": "—",
            "clientes": clientes_unicos
        }

        ventas_data = ventas.data or []

        trabajos_recientes = ventas_data[:5]
        chart_estados = [
            {
                "label": "Pendiente",
                "total": len([v for v in ventas_data if v.get("estado") == "pendiente_adelanto"])
            },
            {
                "label": "Adelanto",
                "total": len([v for v in ventas_data if v.get("estado") == "adelanto_enviado"])
            },
            {
                "label": "Proceso",
                "total": len([v for v in ventas_data if v.get("estado") == "en_proceso"])
            },
            {
                "label": "Entregado",
                "total": len([v for v in ventas_data if v.get("estado") == "entrega_realizada"])
            },
            {
                "label": "Pago final",
                "total": len([v for v in ventas_data if v.get("estado") == "pago_final_enviado"])
            },
            {
                "label": "Completado",
                "total": len([v for v in ventas_data if v.get("estado") == "completado"])
            }
        ]

        max_chart = max([c["total"] for c in chart_estados]) if chart_estados else 1

        for c in chart_estados:
            c["height"] = 8 if c["total"] == 0 else max(22, round((c["total"] / max_chart) * 100))

        ingresos_completados = sum(
            float(v.get("monto") or 0)
            for v in ventas_data
            if v.get("estado") == "completado"
        )

        en_proceso = len([
            v for v in ventas_data
            if v.get("estado") in ["en_proceso", "entrega_realizada", "pago_final_enviado"]
        ])

    except Exception:
        stats = {
            "ventas": 0,
            "productos": 0,
            "calificacion": "—",
            "clientes": 0,
            "ingresos": ingresos_completados,
            "en_proceso": en_proceso
        }

    class UsuarioMock:
        def __init__(self, data):
            self.id = data["id"]
            self.email = data["email"]
            self.user_metadata = {
                "name": data.get("name", "Usuario"),
                "avatar_url": data.get("avatar", "https://via.placeholder.com/40")
            }

    usuario = UsuarioMock(session["user"])

    perfil = (
    supabase.table("perfiles")
    .select("perfil_completado")
    .eq("id", user_id)
    .single()
    .execute()
    )

    if perfil.data and not perfil.data.get("perfil_completado"):
        return redirect(url_for("estudiante.perfil_freelance"))
    

    notificaciones = (
        supabase.table("notificaciones")
        .select("*")
        .eq("usuario_id", user_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )

    notificaciones_data = notificaciones.data or []
    notificaciones_no_leidas = len([n for n in notificaciones_data if not n.get("leida")])

    return render_template(
        "estudiante/dashboard.html",
        usuario=usuario,
        stats=stats,
        ocultar_header=True,
        notificaciones=notificaciones_data,
        notificaciones_no_leidas=notificaciones_no_leidas,
        trabajos_recientes=trabajos_recientes,
        chart_estados=chart_estados,
    )


@estudiante_bp.route("/estadisticas")
@login_required
@role_required("estudiante")
def estadisticas():
    
    user_id = session["user"]["id"]

    try:
        ventas = (
            supabase.table("ventas")
            .select("id, monto, producto_id")
            .eq("vendedor_id", user_id)
            .execute()
        )

        total_ventas = len(ventas.data)
        ingresos = sum(v["monto"] for v in ventas.data) if ventas.data else 0
        productos_unicos = (
            len(set(v["producto_id"] for v in ventas.data))
            if ventas.data else 0
        )

        stats = {
            "total_ventas": total_ventas,
            "ingresos": ingresos,
            "productos_vendidos": productos_unicos,
            "calificacion": "—"
        }

        return render_template("estudiante/estadisticas.html", stats=stats)

    except Exception as e:
        flash(f"Error al cargar estadísticas: {str(e)}", "error")
        return render_template(
            "estudiante/estadisticas.html",
            stats={
                "total_ventas": 0,
                "ingresos": 0,
                "productos_vendidos": 0,
                "calificacion": "—"
            }
        )   
    

@estudiante_bp.route("/perfil-freelance", methods=["GET", "POST"])
@login_required
@role_required("estudiante")
def perfil_freelance():
    user_id = session["user"]["id"]

    if request.method == "POST":
        carrera = request.form.get("carrera")
        descripcion = request.form.get("descripcion")
        habilidades = request.form.get("habilidades")
        yape = request.form.get("yape")
        plin = request.form.get("plin")
        ubicacion = request.form.get("ubicacion")

        supabase.table("perfiles").update({
            "carrera": carrera,
            "descripcion": descripcion,
            "habilidades": habilidades,
            "yape": yape,
            "plin": plin,
            "ubicacion": ubicacion,
            "perfil_completado": True
        }).eq("id", user_id).execute()

        flash("Perfil freelance completado correctamente", "success")
        return redirect(url_for("estudiante.dashboard_estudiante"))

    perfil = (
        supabase.table("perfiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
    )

    return render_template(
        "estudiante/perfil_freelance.html",
        perfil=perfil.data,
        usuario=session["user"],
        ocultar_header=True
    )

@estudiante_bp.route("/solicitudes-recibidas")
@login_required
@role_required("estudiante")
def solicitudes_recibidas():
    estudiante_id = session["user"]["id"]

    try:
        solicitudes = (
            supabase.table("ventas")
            .select("*, producto:productos(*)")
            .eq("vendedor_id", estudiante_id)
            .order("fecha_venta", desc=True)
            .execute()
        )

        stats = {
            "total": len(solicitudes.data),
            "pendientes": len([s for s in solicitudes.data if s.get("estado") == "pendiente_adelanto"]),
            "proceso": len([s for s in solicitudes.data if s.get("estado") == "en_proceso"]),
            "completadas": len([s for s in solicitudes.data if s.get("estado") == "completado"]),
        }

        return render_template(
            "estudiante/solicitudes_recibidas.html",
            solicitudes=solicitudes.data,
            stats=stats
        )

    except Exception as e:
        print("ERROR SOLICITUDES RECIBIDAS:", e)
        flash("Error al cargar solicitudes", "error")
        return redirect(url_for("estudiante.dashboard_estudiante"))


@estudiante_bp.route("/solicitudes/<int:venta_id>/estado/<nuevo_estado>", methods=["POST"])
@login_required
@role_required("estudiante")
def cambiar_estado_solicitud(venta_id, nuevo_estado):
    estudiante_id = session["user"]["id"]


    transiciones_validas = {
        "pendiente_adelanto": ["cancelado"],
        "adelanto_enviado": ["en_proceso"],
        "en_proceso": ["entrega_realizada"],
        "entrega_realizada": [],
        "pago_final_enviado": ["completado"],
        "completado": [],
        "cancelado": []
    }

    try:
        venta_resp = (
            supabase.table("ventas")
            .select("id, estado, vendedor_id, comprador_id")
            .eq("id", venta_id)
            .single()
            .execute()
        )


        if not venta_resp.data:
            flash("Solicitud no encontrada.", "error")
            return redirect(url_for("estudiante.solicitudes_recibidas"))

        venta = venta_resp.data
        estado_actual = venta["estado"]

        if venta["vendedor_id"] != estudiante_id:
            flash("No tienes permiso para modificar esta solicitud.", "error")
            return redirect(url_for("estudiante.solicitudes_recibidas"))

        if nuevo_estado not in transiciones_validas.get(estado_actual, []):
            flash(f"No se puede cambiar de {estado_actual} a {nuevo_estado}.", "error")
            return redirect(url_for("estudiante.solicitudes_recibidas"))

        update_resp = (
            supabase.table("ventas")
            .update({"estado": nuevo_estado})
            .eq("id", venta_id)
            .execute()
        )

        if nuevo_estado == "en_proceso":
            crear_notificacion(
                venta["comprador_id"],
                venta_id,
                "Adelanto confirmado",
                "El freelancer confirmó el adelanto y empezó el trabajo.",
                "success"
            )

        if nuevo_estado == "entrega_realizada":
            crear_notificacion(
                venta["comprador_id"],
                venta_id,
                "Trabajo entregado",
                "El freelancer marcó el trabajo como entregado. Revisa la entrega y sube el pago final.",
                "info"
            )

        if nuevo_estado == "completado":
            crear_notificacion(
                venta["comprador_id"],
                venta_id,
                "Contratación completada",
                "La contratación fue completada correctamente. Ya puedes dejar una valoración.",
                "success"
            )

        # print("DEBUG UPDATE RESPONSE:", update_resp.data)

        flash("Estado actualizado correctamente.", "success")

    except Exception as e:
        print("ERROR CAMBIANDO ESTADO:", e)
        flash(f"No se pudo actualizar el estado: {str(e)}", "error")

    return redirect(url_for("estudiante.solicitudes_recibidas"))

@estudiante_bp.route("/freelancer/<estudiante_id>")
def perfil_publico_freelancer(estudiante_id):
    try:
        perfil = (
            supabase.table("perfiles")
            .select("*")
            .eq("id", estudiante_id)
            .single()
            .execute()
        )

        trabajos = (
            supabase.table("portafolio")
            .select("*")
            .eq("estudiante_id", estudiante_id)
            .order("created_at", desc=True)
            .execute()
        )

        servicios = (
            supabase.table("productos")
            .select("id")
            .eq("vendedor_id", estudiante_id)
            .eq("estado", "activo")
            .execute()
        )
        valoraciones = (
            supabase.table("valoraciones")
            .select("calificacion, comentario, fecha, producto:productos(titulo)")
            .eq("vendedor_id", estudiante_id)
            .order("fecha", desc=True)
            .execute()
        )

        reviews = valoraciones.data or []

        promedio = 0
        if reviews:
            promedio = round(
                sum(r["calificacion"] for r in reviews if r.get("calificacion")) / len(reviews),
                1
            )

        return render_template(
            "freelancer/perfil_publico.html",
            perfil=perfil.data,
            trabajos=trabajos.data or [],
            servicios_count=len(servicios.data or []),
            reviews=reviews,
            promedio=promedio,
            total_reviews=len(reviews),
            estudiante_id=estudiante_id
        )

    except Exception as e:  
        print("ERROR PERFIL PUBLICO:", e)
        flash("No se pudo cargar el perfil del freelancer", "error")
        return redirect(url_for("servicios.explorar_productos"))
    
@estudiante_bp.route("/freelancer/<estudiante_id>/servicios")
def servicios_publicos_freelancer(estudiante_id):
    try:
        perfil = (
            supabase.table("perfiles")
            .select("*")
            .eq("id", estudiante_id)
            .single()
            .execute()
        )

        servicios = (
            supabase.table("productos")
            .select("*")
            .eq("vendedor_id", estudiante_id)
            .eq("estado", "activo")
            .order("fecha_publicacion", desc=True)
            .execute()
        )

        return render_template(
            "freelancer/servicios_publicos.html",
            perfil=perfil.data,
            servicios=servicios.data,
            estudiante_id=estudiante_id
        )

    except Exception as e:
        print("ERROR SERVICIOS FREELANCER:", e)
        flash("No se pudieron cargar los servicios del freelancer", "error")
        return redirect(url_for("servicios.explorar_productos"))