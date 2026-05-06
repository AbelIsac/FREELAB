import os
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, url_for, flash
from config.supabase import supabase

# Cargar variables de entorno
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            "redirect_to": "http://127.0.0.1:5000/callback"
        }
    })
    return redirect(res.url)

@app.route('/callback')
def callback():
    codigo = request.args.get('code')
    if not codigo:
        flash('No se recibió código de Google', 'error')
        return redirect(url_for('home'))

    try:
        sesion = supabase.auth.exchange_code_for_session({"auth_code": codigo})
        usuario = sesion.user
        
        # Verificar si tiene rol asignado
        respuesta = supabase.table('perfiles').select('rol').eq('id', usuario.id).execute()
        
        if respuesta.data and respuesta.data[0].get('rol'):
            flash(f'Bienvenido {usuario.user_metadata.get("name", "Usuario")}', 'success')
            return render_template('dashboard.html', usuario=usuario, rol=respuesta.data[0]['rol'])
        else:
            return redirect(url_for('elegir_rol', user_id=usuario.id))

    except Exception as e:
        flash(f'Error en el callback: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/elegir-rol')
def elegir_rol():
    user_id = request.args.get('user_id')
    if not user_id:
        flash('Error: No se encontró el ID de usuario', 'error')
        return redirect(url_for('home'))
    
    return render_template('elegir_rol.html', user_id=user_id)

@app.route('/guardar-rol')
def guardar_rol():
    rol = request.args.get('rol')
    user_id = request.args.get('user_id')
    
    if not user_id or not rol:
        flash('Error: Faltan datos requeridos', 'error')
        return redirect(url_for('home'))
        
    try:
        datos_a_guardar = {"id": user_id, "rol": rol}
        respuesta = supabase.table('perfiles').upsert(datos_a_guardar).execute()
        
        if respuesta.data:
            flash(f'¡Perfil creado! Tu rol es: {rol}', 'success')
            
            # 🔥 CAMBIO IMPORTANTE: Redirigir según el rol
            if rol == 'estudiante':
                return redirect(url_for('dashboard_estudiante', user_id=user_id))
            else:
                return redirect(url_for('dashboard_comprador', user_id=user_id))
        else:
            flash('Error al guardar el perfil', 'error')
            return redirect(url_for('elegir_rol', user_id=user_id))
             
    except Exception as e:
        flash(f'Error técnico: {str(e)}', 'error')
        return redirect(url_for('elegir_rol', user_id=user_id))

@app.route('/dashboard/estudiante')
def dashboard_estudiante():
    user_id = request.args.get('user_id')
    if not user_id:
        return redirect(url_for('home'))
    
    # Obtener usuario
    try:
        usuario = supabase.auth.admin.get_user_by_id(user_id)
        return render_template('dashboard_estudiante.html', usuario=usuario.user, rol='estudiante')
    except:
        flash('Error al cargar usuario', 'error')
        return redirect(url_for('home'))

@app.route('/dashboard/comprador')
def dashboard_comprador():
    user_id = request.args.get('user_id')
    if not user_id:
        return redirect(url_for('home'))
    
    try:
        usuario = supabase.auth.admin.get_user_by_id(user_id)
        return render_template('dashboard_comprador.html', usuario=usuario.user, rol='comprador')
    except:
        flash('Error al cargar usuario', 'error')
        return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)