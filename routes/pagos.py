from flask import Blueprint, redirect, url_for, flash
from utils.decorators import login_required, role_required

pagos_bp = Blueprint("pagos", __name__)


@pagos_bp.route("/checkout/<int:producto_id>")
@login_required
@role_required("comprador")
def checkout(producto_id):
    flash("El checkout ahora se gestiona desde la solicitud del servicio.", "info")
    return redirect(url_for("servicios.detalle_producto", producto_id=producto_id))


@pagos_bp.route("/procesar-pago/<int:producto_id>", methods=["POST"])
@login_required
@role_required("comprador")
def procesar_pago(producto_id):
    return redirect(url_for("comprador.solicitar_servicio", producto_id=producto_id))