import os
from dotenv import load_dotenv
from flask import Flask, render_template, session
from routes.auth import auth_bp
from routes.estudiante import estudiante_bp
from routes.comprador import comprador_bp
from routes.admin import admin_bp
from routes.servicios import servicios_bp
from routes.pagos import pagos_bp
from routes.notificaciones import notificaciones_bp
from routes.chat import chat_bp

load_dotenv(override=True)

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

app.register_blueprint(auth_bp)
app.register_blueprint(estudiante_bp)
app.register_blueprint(comprador_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(servicios_bp)
app.register_blueprint(pagos_bp)
app.register_blueprint(notificaciones_bp)
app.register_blueprint(chat_bp)


@app.context_processor
def inject_user():
    user = session.get("user") if "user" in session else None
    return dict(session_user=user)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return render_template("home.html")

    rol = session["user"].get("rol")

    if rol == "estudiante":
        from flask import redirect, url_for
        return redirect(url_for("estudiante.dashboard_estudiante"))

    if rol == "comprador":
        from flask import redirect, url_for
        return redirect(url_for("comprador.dashboard_comprador"))

    if rol == "admin":
        from flask import redirect, url_for
        return redirect(url_for("admin.admin_dashboard"))

    from flask import redirect, url_for
    return redirect(url_for("elegir_rol"))

@app.route("/explorar")
def explorar_productos():
    return render_template("servicios/explorar_productos.html", productos=[])


@app.route("/productos")
def productos():
    return render_template("productos.html")



@app.route("/como-funciona")
def como_funciona():
    return render_template("como_funciona.html")


@app.route("/contacto")
def contacto():
    return render_template("contacto.html")


@app.route("/ayuda")
def ayuda():
    return render_template("ayuda.html")


@app.route("/terminos-uso")
def terminos_uso():
    return render_template("terminos_uso.html")


@app.route("/politica-privacidad")
def politica_privacidad():
    return render_template("politica_privacidad.html")




if __name__ == "__main__":
    app.run(debug=True, port=5000)