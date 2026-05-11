import os
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, url_for, flash, session
from config.supabase import supabase

# Cargar variables de entorno
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Context processor para inyectar usuario en todos los templates
@app.context_processor
def inject_user():
    user = session.get('user') if 'user' in session else None
    return dict(session_user=user)

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
        
        # Guardar usuario en session de Flask
        session['user'] = {
            'id': usuario.id,
            'email': usuario.email,
            'name': usuario.user_metadata.get('name', 'Usuario'),
            'avatar': usuario.user_metadata.get('avatar_url', 'https://via.placeholder.com/40')
        }
        
        # Verificar si tiene rol asignado
        respuesta = supabase.table('perfiles').select('rol').eq('id', usuario.id).execute()
        
        if respuesta.data and respuesta.data[0].get('rol'):
            rol = respuesta.data[0]['rol']
            flash(f'Bienvenido {usuario.user_metadata.get("name", "Usuario")}', 'success')
            
            # 🔥 REDIRIGIR SEGÚN EL ROL A LAS NUEVAS PANTALLAS
            if rol == 'estudiante':
                return redirect(url_for('dashboard_estudiante', user_id=usuario.id))
            else:
                return redirect(url_for('dashboard_comprador', user_id=usuario.id))
        else:
            return redirect(url_for('elegir_rol', user_id=usuario.id))

    except Exception as e:
        flash(f'Error en el callback: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    try:
        # Cerrar sesión en Supabase
        supabase.auth.sign_out()
        # Limpiar sesión de Flask
        session.clear()
        flash('Has cerrado sesión exitosamente', 'success')
    except Exception as e:
        flash(f'Error al cerrar sesión: {str(e)}', 'error')
    
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
            
            # 🔥 REDIRIGIR SEGÚN EL ROL
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
        flash('Error: No se encontró usuario', 'error')
        return redirect(url_for('home'))
    
    try:
        # Obtener usuario de la sesión en lugar de llamar a admin
        if 'user' in session and session['user']['id'] == user_id:
            usuario_data = session['user']
            # Crear un objeto similar al de supabase
            class UsuarioMock:
                def __init__(self, data):
                    self.id = data['id']
                    self.email = data['email']
                    self.user_metadata = {'name': data['name'], 'avatar_url': data['avatar']}
            
            usuario = UsuarioMock(usuario_data)
            return render_template('dashboard_estudiante.html', usuario=usuario, rol='estudiante')
        else:
            flash('Sesión expirada, inicia sesión nuevamente', 'error')
            return redirect(url_for('home'))
    except Exception as e:
        flash(f'Error al cargar usuario: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/dashboard/comprador')
def dashboard_comprador():
    user_id = request.args.get('user_id')
    if not user_id:
        flash('Error: No se encontró usuario', 'error')
        return redirect(url_for('home'))
    
    try:
        # Obtener usuario de la sesión
        if 'user' in session and session['user']['id'] == user_id:
            usuario_data = session['user']
            # Crear un objeto similar al de supabase
            class UsuarioMock:
                def __init__(self, data):
                    self.id = data['id']
                    self.email = data['email']
                    self.user_metadata = {'name': data['name'], 'avatar_url': data['avatar']}
            
            usuario = UsuarioMock(usuario_data)
            return render_template('dashboard_comprador.html', usuario=usuario, rol='comprador')
        else:
            flash('Sesión expirada, inicia sesión nuevamente', 'error')
            return redirect(url_for('home'))
    except Exception as e:
        flash(f'Error al cargar usuario: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash('Por favor inicia sesión primero', 'error')
        return redirect(url_for('home'))
    
    # Verificar rol del usuario
    user_id = session['user']['id']
    respuesta = supabase.table('perfiles').select('rol').eq('id', user_id).execute()
    
    if respuesta.data and respuesta.data[0].get('rol'):
        rol = respuesta.data[0]['rol']
        if rol == 'estudiante':
            return redirect(url_for('dashboard_estudiante', user_id=user_id))
        else:
            return redirect(url_for('dashboard_comprador', user_id=user_id))
    else:
        return redirect(url_for('elegir_rol', user_id=user_id))

@app.route('/productos')
def productos():
    return render_template('productos.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)