import os
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, url_for, flash, session
from config.supabase import supabase

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

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
        
        session['user'] = {
            'id': usuario.id,
            'email': usuario.email,
            'name': usuario.user_metadata.get('name', 'Usuario'),
            'avatar': usuario.user_metadata.get('avatar_url', 'https://via.placeholder.com/40')
        }
        
        # Asegurar que exista perfil
        perfil = supabase.table('perfiles').select('id').eq('id', usuario.id).execute()
        if not perfil.data:
            supabase.table('perfiles').insert({'id': usuario.id}).execute()
        
        respuesta = supabase.table('perfiles').select('rol').eq('id', usuario.id).execute()
        if respuesta.data and respuesta.data[0].get('rol'):
            rol = respuesta.data[0]['rol']
            flash(f'Bienvenido {usuario.user_metadata.get("name", "Usuario")}', 'success')
            if rol == 'estudiante':
                return redirect(url_for('dashboard_estudiante', user_id=usuario.id))
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
    try:
        supabase.table('perfiles').upsert({"id": user_id, "rol": rol}).execute()
        flash(f'Perfil creado: {rol}', 'success')
        if rol == 'estudiante':
            return redirect(url_for('dashboard_estudiante', user_id=user_id))
        else:
            return redirect(url_for('dashboard_comprador', user_id=user_id))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('elegir_rol', user_id=user_id))

# ==================== VENDEDOR ====================
@app.route('/dashboard/estudiante')
def dashboard_estudiante():
    user_id = request.args.get('user_id')
    if not user_id or 'user' not in session or session['user']['id'] != user_id:
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
    try:
        data = {
            'vendedor_id': session['user']['id'],
            'titulo': titulo,
            'descripcion': descripcion,
            'precio': float(precio),
            'categoria_id': int(categoria_id) if categoria_id and categoria_id.isdigit() else None,
            'estado': 'activo'
        }
        supabase.table('productos').insert(data).execute()
        flash('Producto publicado', 'success')
        return redirect(url_for('dashboard_estudiante', user_id=session['user']['id']))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('publicar_producto'))

@app.route('/mis-productos')
def mis_productos():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    productos = supabase.table('productos').select('*, categorias(nombre)').eq('vendedor_id', session['user']['id']).order('fecha_publicacion', desc=True).execute()
    return render_template('mis_productos.html', productos=productos.data)

@app.route('/estadisticas')
def estadisticas():
    if 'user' not in session:
        flash('Inicia sesión', 'error')
        return redirect(url_for('home'))
    user_id = session['user']['id']
    try:
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
    user_id = request.args.get('user_id')
    if not user_id or 'user' not in session or session['user']['id'] != user_id:
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
    categoria = request.args.get('categoria', type=int)
    query = supabase.table('productos').select('*, categorias(nombre)').eq('estado', 'activo')
    if categoria:
        query = query.eq('categoria_id', categoria)
    productos = query.execute()
    # No intentamos obtener email del vendedor porque perfiles no tiene email
    return render_template('explorar_productos.html', productos=productos.data)

@app.route('/comprar/<int:producto_id>', methods=['POST'])
def comprar_producto(producto_id):
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
        .select('*, producto:productos(*, categorias(nombre))')\
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
        .select('*, producto:productos(*, categorias(nombre))')\
        .eq('usuario_id', session['user']['id'])\
        .execute()
    return render_template('favoritos.html', favoritos=favs.data)

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
        else:
            return redirect(url_for('dashboard_comprador', user_id=user_id))
    else:
        return redirect(url_for('elegir_rol', user_id=user_id))

@app.route('/productos')
def productos():
    return render_template('productos.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)