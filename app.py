import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, url_for, flash, session
from config.supabase import supabase
from werkzeug.utils import secure_filename
from flask import Flask, render_template, redirect, request, url_for, flash, session, jsonify
from functools import wraps

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Configuración para subir archivos
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Crear carpeta si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Inicia sesión', 'error')
            return redirect(url_for('home'))
        if session['user'].get('rol') != 'admin':
            flash('Acceso no autorizado', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

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
        "options": {"redirect_to": "http://127.0.0.1:5000/callback"}
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
        
        # Asegurar que exista perfil
        perfil = supabase.table('perfiles').select('id').eq('id', usuario.id).execute()
        if not perfil.data:
            supabase.table('perfiles').insert({'id': usuario.id}).execute()
        
        # Obtener el rol
        respuesta = supabase.table('perfiles').select('rol').eq('id', usuario.id).execute()
        rol = respuesta.data[0]['rol'] if respuesta.data and respuesta.data[0].get('rol') else None
        
        # Guardar en sesión
        session['user'] = {
            'id': usuario.id,
            'email': usuario.email,
            'name': usuario.user_metadata.get('name', 'Usuario'),
            'avatar': usuario.user_metadata.get('avatar_url', 'https://via.placeholder.com/40'),
            'rol': rol
        }
        
        if rol:
            flash(f'Bienvenido {usuario.user_metadata.get("name", "Usuario")}', 'success')
            if rol == 'estudiante':
                return redirect(url_for('dashboard_estudiante', user_id=usuario.id))
            elif rol == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard_comprador', user_id=usuario.id))
        else:
            return redirect(url_for('elegir_rol', user_id=usuario.id))

    except Exception as e:
        flash(f'Error en callback: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    supabase.auth.sign_out()
    session.clear()
    flash('Sesión cerrada', 'success')
    return redirect(url_for('home'))

@app.route('/elegir-rol')
def elegir_rol():
    user_id = request.args.get('user_id')
    if not user_id:
        flash('Error: ID no encontrado', 'error')
        return redirect(url_for('home'))
    return render_template('elegir_rol.html', user_id=user_id)

@app.route('/guardar-rol')
def guardar_rol():
    rol = request.args.get('rol')
    user_id = request.args.get('user_id')
    if not user_id or not rol:
        flash('Faltan datos', 'error')
        return redirect(url_for('home'))
    
    # Validar que el rol esté permitido
    if rol not in ['estudiante', 'comprador', 'admin']:
        flash('Rol no válido', 'error')
        return redirect(url_for('elegir_rol', user_id=user_id))
    
    try:
        supabase.table('perfiles').upsert({"id": user_id, "rol": rol}).execute()
        if 'user' in session:
            session['user']['rol'] = rol
        
        flash(f'Perfil creado: {rol}', 'success')
        
        # Redirección según el rol
        if rol == 'estudiante':
            return redirect(url_for('dashboard_estudiante', user_id=user_id))
        elif rol == 'comprador':
            return redirect(url_for('dashboard_comprador', user_id=user_id))
        elif rol == 'admin':
            return redirect(url_for('admin_dashboard'))  # Asegúrate de tener esta ruta
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('elegir_rol', user_id=user_id))
# ==================== VENDEDOR ====================
@app.route('/dashboard/estudiante')
def dashboard_estudiante():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    
    user_id = request.args.get('user_id')
    
    # VERIFICACIÓN DE ROL - SOLO ESTUDIANTES
    respuesta_rol = supabase.table('perfiles').select('rol').eq('id', session['user']['id']).execute()
    rol = respuesta_rol.data[0]['rol'] if respuesta_rol.data else None
    
    if rol != 'estudiante':
        flash('Acceso no autorizado. Esta sección es solo para vendedores.', 'error')
        if rol == 'comprador':
            return redirect(url_for('dashboard_comprador', user_id=session['user']['id']))
        elif rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('home'))
    
    # Resto del código existente...
    if not user_id or session['user']['id'] != user_id:
        flash('Acceso no autorizado', 'error')
        return redirect(url_for('home'))
    
    try:
        productos_count = supabase.table('productos').select('id', count='exact').eq('vendedor_id', user_id).eq('estado', 'activo').execute()
        total_productos = productos_count.count or 0
        ventas_count = supabase.table('ventas').select('id', count='exact').eq('vendedor_id', user_id).execute()
        total_ventas = ventas_count.count or 0
        ventas = supabase.table('ventas').select('id').eq('vendedor_id', user_id).execute()
        calificacion = '—'
        if ventas.data:
            ids = [v['id'] for v in ventas.data]
            vals = supabase.table('valoraciones').select('calificacion').in_('venta_id', ids).execute()
            if vals.data:
                calificacion = round(sum(v['calificacion'] for v in vals.data) / len(vals.data), 1)
        clientes = supabase.table('ventas').select('comprador_id').eq('vendedor_id', user_id).execute()
        clientes_unicos = len(set(c['comprador_id'] for c in clientes.data)) if clientes.data else 0
        stats = {'ventas': total_ventas, 'productos': total_productos, 'calificacion': calificacion, 'clientes': clientes_unicos}
        usuario_data = session['user']
        class UsuarioMock:
            def __init__(self, data):
                self.id = data['id']
                self.email = data['email']
                self.user_metadata = {'name': data['name'], 'avatar_url': data['avatar']}
        usuario = UsuarioMock(usuario_data)
        return render_template('dashboard_estudiante.html', usuario=usuario, stats=stats)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/publicar-producto')
def publicar_producto():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    
    # VERIFICAR QUE SEA ESTUDIANTE
    respuesta_rol = supabase.table('perfiles').select('rol').eq('id', session['user']['id']).execute()
    rol = respuesta_rol.data[0]['rol'] if respuesta_rol.data else None
    
    if rol != 'estudiante':
        flash('Solo los vendedores pueden publicar productos', 'error')
        if rol == 'comprador':
            return redirect(url_for('dashboard_comprador', user_id=session['user']['id']))
        elif rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('home'))
    
    return render_template('publicar_producto.html')

@app.route('/guardar-producto', methods=['POST'])
def guardar_producto():
    if 'user' not in session:
        flash('No autorizado', 'error')
        return redirect(url_for('home'))
    
    titulo = request.form.get('titulo')
    descripcion = request.form.get('descripcion')
    precio = request.form.get('precio')
    categoria_id = request.form.get('categoria')
    
    if not titulo or not precio:
        flash('Título y precio son obligatorios', 'error')
        return redirect(url_for('publicar_producto'))
    
    # Datos básicos del producto
    data = {
        'vendedor_id': session['user']['id'],
        'titulo': titulo,
        'descripcion': descripcion,
        'precio': float(precio),
        'categoria_id': int(categoria_id) if categoria_id and categoria_id.isdigit() else None,
        'estado': 'pendiente'
    }
    
    # Manejar la imagen
    if 'imagen' in request.files:
        file = request.files['imagen']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{session['user']['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            data['imagen_url'] = f"/static/uploads/{filename}"
    
    # Manejar archivo
    if 'archivo' in request.files:
        file = request.files['archivo']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{session['user']['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            data['archivo_url'] = f"/static/uploads/{filename}"
    
    try:
        supabase.table('productos').insert(data).execute()
        flash('Producto publicado exitosamente!', 'success')
        return redirect(url_for('dashboard_estudiante', user_id=session['user']['id']))
    except Exception as e:
        flash(f'Error al publicar: {str(e)}', 'error')
        return redirect(url_for('publicar_producto'))

@app.route('/mis-productos')
def mis_productos():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    
    # VERIFICAR QUE SEA ESTUDIANTE
    respuesta_rol = supabase.table('perfiles').select('rol').eq('id', session['user']['id']).execute()
    rol = respuesta_rol.data[0]['rol'] if respuesta_rol.data else None
    
    if rol != 'estudiante':
        flash('Acceso no autorizado', 'error')
        return redirect(url_for('home'))
    
    productos = supabase.table('productos').select('*, categorias(nombre)').eq('vendedor_id', session['user']['id']).order('fecha_publicacion', desc=True).execute()
    return render_template('mis_productos.html', productos=productos.data)

@app.route('/estadisticas')
def estadisticas():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    
    # VERIFICAR QUE SEA ESTUDIANTE
    respuesta_rol = supabase.table('perfiles').select('rol').eq('id', session['user']['id']).execute()
    rol = respuesta_rol.data[0]['rol'] if respuesta_rol.data else None
    
    if rol != 'estudiante':
        flash('Acceso no autorizado', 'error')
        return redirect(url_for('home'))
    
    user_id = session['user']['id']
    try:
        # resto del código igual...
        ventas_count = supabase.table('ventas').select('id', count='exact').eq('vendedor_id', user_id).execute()
        total_ventas = ventas_count.count or 0
        ingresos_data = supabase.table('ventas').select('monto').eq('vendedor_id', user_id).execute()
        ingresos = sum(v['monto'] for v in ingresos_data.data) if ingresos_data.data else 0
        prod_vendidos = supabase.table('ventas').select('producto_id').eq('vendedor_id', user_id).execute()
        productos_unicos = len(set(p['producto_id'] for p in prod_vendidos.data)) if prod_vendidos.data else 0
        ventas = supabase.table('ventas').select('id').eq('vendedor_id', user_id).execute()
        promedio = '—'
        if ventas.data:
            ids = [v['id'] for v in ventas.data]
            vals = supabase.table('valoraciones').select('calificacion').in_('venta_id', ids).execute()
            if vals.data:
                promedio = round(sum(v['calificacion'] for v in vals.data) / len(vals.data), 1)
        stats = {'total_ventas': total_ventas, 'ingresos': ingresos, 'productos_vendidos': productos_unicos, 'calificacion': promedio}
        return render_template('estadisticas.html', stats=stats)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('dashboard_estudiante', user_id=user_id))

@app.route('/configuracion')
def configuracion():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    return render_template('configuracion.html', user=session['user'])

# ==================== COMPRADOR ====================
@app.route('/dashboard/comprador')
def dashboard_comprador():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    
    user_id = request.args.get('user_id')
    
    # VERIFICACIÓN DE ROL - SOLO COMPRADORES
    respuesta_rol = supabase.table('perfiles').select('rol').eq('id', session['user']['id']).execute()
    rol = respuesta_rol.data[0]['rol'] if respuesta_rol.data else None
    
    if rol != 'comprador':
        flash('Acceso no autorizado. Esta sección es solo para compradores.', 'error')
        if rol == 'estudiante':
            return redirect(url_for('dashboard_estudiante', user_id=session['user']['id']))
        elif rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('home'))
    
    # Resto del código existente...
    if not user_id or session['user']['id'] != user_id:
        flash('Acceso no autorizado', 'error')
        return redirect(url_for('home'))
    
    try:
        compras = supabase.table('ventas').select('id', count='exact').eq('comprador_id', user_id).execute()
        favs = supabase.table('favoritos').select('id', count='exact').eq('usuario_id', user_id).execute()
        ventas = supabase.table('ventas').select('id').eq('comprador_id', user_id).execute()
        resenas = 0
        if ventas.data:
            ids = [v['id'] for v in ventas.data]
            res = supabase.table('valoraciones').select('id', count='exact').in_('venta_id', ids).execute()
            resenas = res.count or 0
        stats = {'compras': compras.count or 0, 'favoritos': favs.count or 0, 'resenas': resenas, 'ofertas': 0}
        usuario_data = session['user']
        class UsuarioMock:
            def __init__(self, data):
                self.id = data['id']
                self.email = data['email']
                self.user_metadata = {'name': data['name'], 'avatar_url': data['avatar']}
        usuario = UsuarioMock(usuario_data)
        return render_template('dashboard_comprador.html', usuario=usuario, stats=stats)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/explorar')
def explorar_productos():
    if 'user' not in session:
        flash('Inicia sesión para explorar', 'error')
        return redirect(url_for('home'))
    categoria = request.args.get('categoria')
    query = supabase.table('productos').select('*').eq('estado', 'activo')
    if categoria and categoria != 'todos':
        query = query.eq('categoria_id', int(categoria))
    productos = query.execute()
    return render_template('explorar_productos.html', productos=productos.data)

@app.route('/comprar/<int:producto_id>', methods=['POST'])
def comprar_producto(producto_id):
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    # VERIFICAR QUE NO SEA ADMIN
    if session['user'].get('rol') == 'admin':
        flash('Los administradores no pueden realizar compras', 'error')
        return redirect(url_for('admin_dashboard'))
    comprador_id = session['user']['id']
    try:
        prod = supabase.table('productos').select('*').eq('id', producto_id).single().execute()
        if not prod.data:
            flash('Producto no encontrado', 'error')
            return redirect(url_for('explorar_productos'))
        if prod.data['vendedor_id'] == comprador_id:
            flash('No puedes comprar tus propios productos', 'error')
            return redirect(url_for('explorar_productos'))
        venta = {
            'producto_id': producto_id,
            'comprador_id': comprador_id,
            'vendedor_id': prod.data['vendedor_id'],
            'monto': prod.data['precio']
        }
        supabase.table('ventas').insert(venta).execute()
        flash('Compra exitosa', 'success')
        return redirect(url_for('mis_compras'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('explorar_productos'))

@app.route('/mis-compras')
def mis_compras():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    compras = supabase.table('ventas')\
        .select('*, producto:productos(*)')\
        .eq('comprador_id', session['user']['id'])\
        .order('fecha_venta', desc=True)\
        .execute()
    return render_template('mis_compras.html', compras=compras.data)

@app.route('/favoritos')
def favoritos():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))

    favs = supabase.table('favoritos')\
        .select('*, producto:productos(*)')\
        .eq('usuario_id', session['user']['id'])\
        .execute()
    return render_template('favoritos.html', favoritos=favs.data)

    user_id = session['user']['id']
    # Obtener ids de productos favoritos
    favs = supabase.table('favoritos').select('producto_id').eq('usuario_id', user_id).execute()
    if not favs.data:
        return render_template('favoritos.html', favoritos=[])
    
    producto_ids = [f['producto_id'] for f in favs.data]
    # Obtener datos completos de esos productos
    productos = supabase.table('productos').select('*, categorias(nombre)').in_('id', producto_ids).execute()
    
    # Estructurar como espera la plantilla
    favoritos_data = [{'producto': p} for p in productos.data]
    return render_template('favoritos.html', favoritos=favoritos_data)


@app.route('/agregar-favorito/<int:producto_id>', methods=['POST'])
def agregar_favorito(producto_id):
    if 'user' not in session:
        return {'error': 'No autorizado'}, 401
    try:
        supabase.table('favoritos').insert({'usuario_id': session['user']['id'], 'producto_id': producto_id}).execute()
        return {'success': True}, 200
    except:
        return {'error': 'Ya existe'}, 400

@app.route('/quitar-favorito/<int:producto_id>', methods=['POST'])
def quitar_favorito(producto_id):
    if 'user' not in session:
        return {'error': 'No autorizado'}, 401
    supabase.table('favoritos').delete().eq('usuario_id', session['user']['id']).eq('producto_id', producto_id).execute()
    return {'success': True}, 200

@app.route('/mis-resenas')
def mis_resenas():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    ventas = supabase.table('ventas')\
        .select('*, producto:productos(*), valoraciones(*)')\
        .eq('comprador_id', session['user']['id'])\
        .execute()
    con_resena = [v for v in ventas.data if v.get('valoraciones') and len(v['valoraciones']) > 0]
    return render_template('mis_resenas.html', resenas=con_resena)

@app.route('/dejar-resena/<int:venta_id>', methods=['POST'])
def dejar_resena(venta_id):
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    calif = request.form.get('calificacion')
    coment = request.form.get('comentario')
    if not calif:
        flash('Calificación requerida', 'error')
        return redirect(url_for('mis_compras'))
    try:
        supabase.table('valoraciones').insert({'venta_id': venta_id, 'calificacion': int(calif), 'comentario': coment}).execute()
        flash('Reseña guardada', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('mis_compras'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    
    user_id = session['user']['id']
    respuesta = supabase.table('perfiles').select('rol').eq('id', user_id).execute()
    if respuesta.data and respuesta.data[0].get('rol'):
        rol = respuesta.data[0]['rol']
        if rol == 'estudiante':
            return redirect(url_for('dashboard_estudiante', user_id=user_id))
        elif rol == 'comprador':
            return redirect(url_for('dashboard_comprador', user_id=user_id))
        elif rol == 'admin':
            return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('elegir_rol', user_id=user_id))

@app.route('/productos')
def productos():
    return render_template('productos.html')

@app.route('/checkout/<int:producto_id>')
def checkout(producto_id):
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    
    # Obtener producto
    prod = supabase.table('productos').select('*').eq('id', producto_id).single().execute()
    if not prod.data:
        flash('Producto no encontrado', 'error')
        return redirect(url_for('explorar_productos'))
    
    return render_template('checkout.html', producto=prod.data)

@app.route('/procesar-pago/<int:producto_id>', methods=['POST'])
def procesar_pago(producto_id):
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    
    comprador_id = session['user']['id']
    try:
        prod = supabase.table('productos').select('*').eq('id', producto_id).single().execute()
        if not prod.data:
            flash('Producto no encontrado', 'error')
            return redirect(url_for('explorar_productos'))
        
        if prod.data['vendedor_id'] == comprador_id:
            flash('No puedes comprar tus propios productos', 'error')
            return redirect(url_for('explorar_productos'))
        
        # Crear venta
        venta_data = {
            'producto_id': producto_id,
            'comprador_id': comprador_id,
            'vendedor_id': prod.data['vendedor_id'],
            'monto': prod.data['precio'],
            'estado': 'pendiente'
        }
        supabase.table('ventas').insert(venta_data).execute()
        flash('¡Pago exitoso! Compra realizada', 'success')
        return redirect(url_for('mis_compras'))
    except Exception as e:
        flash(f'Error en pago: {str(e)}', 'error')
        return redirect(url_for('checkout', producto_id=producto_id))


# ==================== CARRITO DE COMPRAS ====================

# ==================== CARRITO DE COMPRAS ====================

@app.route('/carrito')
def ver_carrito():
    """Muestra la página del carrito"""
    if 'user' not in session:
        flash('Inicia sesión para ver tu carrito', 'error')
        return redirect(url_for('home'))
    return render_template('carrito.html')

@app.route('/checkout-carrito', methods=['GET', 'POST'])
def checkout_carrito():
    if 'user' not in session:
        flash('Inicia sesión para continuar', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        items = request.json.get('items', [])
        session['carrito_items'] = items
        return jsonify({'success': True})
    else:
        items = session.get('carrito_items', [])
        if not items:
            flash('No hay productos en el carrito', 'warning')
            return redirect(url_for('ver_carrito'))
        total = sum(item['precio'] * item['cantidad'] for item in items)
        # 👇 AHORA USA checkout.html
        return render_template('checkout.html', items=items, total=total)

@app.route('/procesar-pago-carrito', methods=['POST'])
def procesar_pago_carrito():
    """Registra las ventas de todos los productos del carrito"""
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    
    items = session.get('carrito_items', [])
    if not items:
        flash('No hay productos en el carrito', 'error')
        return redirect(url_for('ver_carrito'))
    
    comprador_id = session['user']['id']
    try:
        for item in items:
            # Verificar que el producto existe y está activo
            prod = supabase.table('productos').select('vendedor_id, precio, estado').eq('id', item['id']).single().execute()
            if not prod.data or prod.data.get('estado') != 'activo':
                flash(f'El producto "{item["titulo"]}" ya no está disponible', 'error')
                return redirect(url_for('ver_carrito'))
            
            # Crear la venta
            venta_data = {
                'producto_id': item['id'],
                'comprador_id': comprador_id,
                'vendedor_id': prod.data['vendedor_id'],
                'monto': item['precio'] * item['cantidad'],
                'estado': 'pendiente'
            }
            # Si tu tabla ventas tiene columna 'cantidad', descomenta la línea siguiente:
            # venta_data['cantidad'] = item['cantidad']
            supabase.table('ventas').insert(venta_data).execute()
        
        # Limpiar sesión
        session.pop('carrito_items', None)
        flash('¡Compra realizada con éxito!', 'success')
        return redirect(url_for('mis_compras'))
    except Exception as e:
        flash(f'Error al procesar pago: {str(e)}', 'error')
        return redirect(url_for('ver_carrito'))
    
@app.route('/productos-destacados')
def productos_destacados():
    try:
        # Obtener productos activos, ordenados por fecha (los más nuevos primero)
        # Si tu tabla tiene 'fecha_publicacion' úsala; si no, usa 'created_at' o 'id' descendente
        response = supabase.table('productos')\
            .select('*')\
            .eq('estado', 'activo')\
            .order('fecha_publicacion', desc=True)\
            .limit(8)\
            .execute()
        
        return jsonify({'productos': response.data})
    except Exception as e:
        print(f"Error en productos-destacados: {e}")
        return jsonify({'productos': []})

@app.route('/eliminar-producto/<int:producto_id>', methods=['DELETE'])
def eliminar_producto(producto_id):
    # Verificar que el usuario esté logueado
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    
    user_id = session['user']['id']
    
    try:
        # Buscar el producto y verificar que pertenezca al usuario actual
        producto = supabase.table('productos').select('*').eq('id', producto_id).single().execute()
        
        if not producto.data:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        if producto.data['vendedor_id'] != user_id:
            return jsonify({'success': False, 'error': 'No tienes permiso para eliminar este producto'}), 403
        
        # Opción 1: Eliminación física (borra el registro)
        supabase.table('productos').delete().eq('id', producto_id).execute()
        
        # Opción 2: Eliminación lógica (cambiar estado a 'eliminado') - recomendado
        # supabase.table('productos').update({'estado': 'eliminado'}).eq('id', producto_id).execute()
        
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Error eliminando producto: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500    
    
# ROL ADMI
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # Estadísticas: total productos pendientes, ventas pendientes, etc.
    try:
        productos_pendientes = supabase.table('productos').select('id', count='exact').eq('estado', 'pendiente').execute()
        ventas_pendientes = supabase.table('ventas').select('id', count='exact').eq('estado', 'pendiente').execute()
        total_categorias = supabase.table('categorias').select('id', count='exact').execute()
        stats = {
            'productos_pendientes': productos_pendientes.count or 0,
            'ventas_pendientes': ventas_pendientes.count or 0,
            'total_categorias': total_categorias.count or 0
        }
    except Exception as e:
        stats = {}
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/categorias')
@admin_required
def admin_categorias():
    categorias = supabase.table('categorias').select('*').order('id').execute()
    return render_template('admin/categorias.html', categorias=categorias.data)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Inicia sesión', 'error')
            return redirect(url_for('home'))
        
        user_id = session['user']['id']
        respuesta = supabase.table('perfiles').select('rol').eq('id', user_id).execute()
        rol = respuesta.data[0]['rol'] if respuesta.data else None
        
        if rol != 'admin':
            flash('Acceso no autorizado. Se requieren permisos de administrador.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/usuarios')
@admin_required
def admin_usuarios():
    usuarios = supabase.table('perfiles').select('*').execute()
    return render_template('admin/usuarios.html', usuarios=usuarios.data)

@app.route('/admin/productos')
@admin_required
def admin_productos():
    productos = supabase.table('productos').select('*, perfiles(nombre)').order('fecha_publicacion', desc=True).execute()
    return render_template('admin/productos.html', productos=productos.data)

@app.route('/admin/ventas')
@admin_required
def admin_ventas():
    ventas = supabase.table('ventas').select('*, producto:productos(titulo), comprador:perfiles!comprador_id(nombre), vendedor:perfiles!vendedor_id(nombre)').order('fecha_venta', desc=True).execute()
    return render_template('admin/ventas.html', ventas=ventas.data)

@app.route('/admin/categoria/crear', methods=['POST'])
@admin_required
def admin_categoria_crear():
    nombre = request.form.get('nombre')
    descripcion = request.form.get('descripcion')
    if not nombre:
        flash('El nombre es obligatorio', 'error')
        return redirect(url_for('admin_categorias'))
    supabase.table('categorias').insert({'nombre': nombre, 'descripcion': descripcion}).execute()
    flash('Categoría creada', 'success')
    return redirect(url_for('admin_categorias'))

@app.route('/admin/categoria/editar/<int:categoria_id>', methods=['POST'])
@admin_required
def admin_categoria_editar(categoria_id):
    nombre = request.form.get('nombre')
    descripcion = request.form.get('descripcion')
    supabase.table('categorias').update({'nombre': nombre, 'descripcion': descripcion}).eq('id', categoria_id).execute()
    flash('Categoría actualizada', 'success')
    return redirect(url_for('admin_categorias'))

@app.route('/admin/categoria/eliminar/<int:categoria_id>', methods=['DELETE'])
@admin_required
def admin_categoria_eliminar(categoria_id):
    try:
        supabase.table('categorias').delete().eq('id', categoria_id).execute()
        return jsonify({'success': True})
    except:
        return jsonify({'success': False, 'error': 'No se puede eliminar si tiene productos asociados'}), 400
    
@app.route('/admin/publicaciones')
@admin_required
def admin_publicaciones():
    productos = supabase.table('productos')\
        .select('*, perfiles(nombre)')\
        .in_('estado', ['pendiente', 'activo', 'rechazado'])\
        .order('fecha_publicacion', desc=True)\
        .execute()
    return render_template('admin/publicaciones.html', productos=productos.data)

@app.route('/admin/publicacion/aprobar/<int:producto_id>', methods=['POST'])
@admin_required
def admin_aprobar_producto(producto_id):
    supabase.table('productos').update({'estado': 'activo'}).eq('id', producto_id).execute()
    flash('Producto aprobado y visible para los compradores', 'success')
    return redirect(url_for('admin_publicaciones'))

@app.route('/admin/publicacion/rechazar/<int:producto_id>', methods=['POST'])
@admin_required
def admin_rechazar_producto(producto_id):
    supabase.table('productos').update({'estado': 'rechazado'}).eq('id', producto_id).execute()
    flash('Producto rechazado. El vendedor deberá modificar o volver a publicar', 'warning')
    return redirect(url_for('admin_publicaciones'))

@app.route('/admin/transacciones')
@admin_required
def admin_transacciones():
    ventas = supabase.table('ventas')\
        .select('*, producto:productos(titulo), comprador:perfiles!comprador_id(nombre), vendedor:perfiles!vendedor_id(nombre)')\
        .order('fecha_venta', desc=True)\
        .execute()
    return render_template('admin/transacciones.html', ventas=ventas.data)

@app.route('/admin/transaccion/aprobar/<int:venta_id>', methods=['POST'])
@admin_required
def admin_aprobar_transaccion(venta_id):
    supabase.table('ventas').update({'estado': 'completado'}).eq('id', venta_id).execute()
    flash('Transacción aprobada. El vendedor recibirá el pago', 'success')
    return redirect(url_for('admin_transacciones'))

@app.route('/admin/transaccion/cancelar/<int:venta_id>', methods=['POST'])
@admin_required
def admin_cancelar_transaccion(venta_id):
    supabase.table('ventas').update({'estado': 'cancelado'}).eq('id', venta_id).execute()
    flash('Transacción cancelada. El comprador no será cobrado', 'warning')
    return redirect(url_for('admin_transacciones'))

@app.route('/producto/<int:producto_id>')
def detalle_producto(producto_id):
    try:
        producto = supabase.table('productos').select('*').eq('id', producto_id).single().execute()
        if not producto.data:
            flash('Producto no encontrado', 'error')
            return redirect(url_for('explorar_productos'))
        
        # Obtener nombre del vendedor
        vendedor = supabase.table('perfiles').select('nombre').eq('id', producto.data['vendedor_id']).execute()
        vendedor_nombre = vendedor.data[0]['nombre'] if vendedor.data else 'Vendedor'
        
        return render_template('detalle_producto.html', producto=producto.data, vendedor_nombre=vendedor_nombre)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('explorar_productos'))

@app.route('/admin/todas-publicaciones')
@admin_required
def admin_todas_publicaciones():
    """Admin puede ver y gestionar TODAS las publicaciones"""
    try:
        # Obtener todos los productos, ordenados por fecha
        productos = supabase.table('productos')\
            .select('*, perfiles(nombre)')\
            .order('fecha_publicacion', desc=True)\
            .execute()
        return render_template('admin/todas_publicaciones.html', productos=productos.data)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/eliminar-publicacion/<int:producto_id>', methods=['DELETE'])
@admin_required
def admin_eliminar_publicacion(producto_id):
    """Admin puede eliminar CUALQUIER publicación permanentemente"""
    try:
        # Verificar que el producto existe
        producto = supabase.table('productos').select('*').eq('id', producto_id).single().execute()
        if not producto.data:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        # Eliminar archivos físicos si existen
        if producto.data.get('imagen_url'):
            file_path = producto.data['imagen_url'].replace('/static/', 'static/')
            if os.path.exists(file_path):
                os.remove(file_path)
        
        if producto.data.get('archivo_url'):
            file_path = producto.data['archivo_url'].replace('/static/', 'static/')
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Eliminar de la base de datos
        supabase.table('productos').delete().eq('id', producto_id).execute()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route('/como-funciona')
def como_funciona():
    return render_template('como_funciona.html')

@app.route('/contacto')
def contacto():
    return render_template('contacto.html')

@app.route('/terminos-uso')
def terminos_uso():
    return render_template('terminos_uso.html')

@app.route('/politica-privacidad')
def politica_privacidad():
    return render_template('politica_privacidad.html')

@app.route('/ayuda')
def ayuda():
    return render_template('ayuda.html')
if __name__ == '__main__':
    app.run(debug=True, port=5000)