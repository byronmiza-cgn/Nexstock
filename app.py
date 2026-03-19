import os
import logging
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from threading import Thread

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')

# Support PostgreSQL in production (Railway), SQLite locally
database_url = os.environ.get('DATABASE_URL', 'sqlite:///acuario.db')
# Railway/Heroku provide postgres:// but SQLAlchemy requires postgresql://
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask-Mail config (uses env vars set in Railway)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

db = SQLAlchemy(app)
mail = Mail(app)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_tienda = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='GTQ')
    creado = db.Column(db.DateTime, default=datetime.utcnow)
    especies = db.relationship('Especie', backref='usuario', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Especie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), nullable=False, default='Pez')
    descripcion = db.Column(db.String(200))
    usage_count = db.Column(db.Integer, nullable=False, default=0)
    lotes = db.relationship('Lote', backref='especie', lazy=True)
    ventas = db.relationship('Venta', backref='especie', lazy=True)
    muertes = db.relationship('Muerte', backref='especie', lazy=True)
    __table_args__ = (db.UniqueConstraint('usuario_id', 'nombre', name='uq_usuario_especie'),)


class Lote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    especie_id = db.Column(db.Integer, db.ForeignKey('especie.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    costo_total = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)


class Venta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    especie_id = db.Column(db.Integer, db.ForeignKey('especie.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unidad = db.Column(db.Float, nullable=False)
    costo_unitario_momento = db.Column(db.Float, nullable=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)


class Muerte(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    especie_id = db.Column(db.Integer, db.ForeignKey('especie.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    costo_unitario_momento = db.Column(db.Float, nullable=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    nota = db.Column(db.String(200))


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    token = db.Column(db.String(100), nullable=False, unique=True)
    expira = db.Column(db.DateTime, nullable=False)
    usado = db.Column(db.Boolean, default=False)

    def is_valid(self):
        return not self.usado and datetime.utcnow() < self.expira


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Inicia sesion para continuar.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_usuario():
    return Usuario.query.get(session['usuario_id'])


def get_especies_usuario():
    todas = Especie.query.filter_by(usuario_id=session['usuario_id']).all()
    frecuentes = sorted([e for e in todas if e.usage_count > 0], key=lambda e: -e.usage_count)[:10]
    frecuentes_ids = {e.id for e in frecuentes}
    resto = sorted([e for e in todas if e.id not in frecuentes_ids], key=lambda e: e.nombre.lower())
    return frecuentes, resto


def incrementar_uso(especie):
    especie.usage_count += 1


def calcular_estadisticas(especie):
    total_ingresado = sum(l.cantidad for l in especie.lotes)
    total_vendido = sum(v.cantidad for v in especie.ventas)
    total_muerto = sum(m.cantidad for m in especie.muertes)
    stock = total_ingresado - total_vendido - total_muerto

    costo_total = sum(l.costo_total for l in especie.lotes)
    ingreso_ventas = sum(v.cantidad * v.precio_unidad for v in especie.ventas)

    mortalidad = (total_muerto / total_ingresado * 100) if total_ingresado > 0 else 0

    unidades_vendibles = total_ingresado - total_muerto
    if unidades_vendibles > 0:
        costo_unitario_ajustado = costo_total / unidades_vendibles
    elif total_ingresado > 0:
        costo_unitario_ajustado = costo_total / total_ingresado
    else:
        costo_unitario_ajustado = 0

    precio_minimo_recomendado = round(costo_unitario_ajustado * 1.20, 2)

    costo_de_vendidos = sum(
        v.cantidad * (v.costo_unitario_momento if v.costo_unitario_momento is not None else costo_unitario_ajustado)
        for v in especie.ventas
    )
    costo_de_muertos = sum(
        m.cantidad * (m.costo_unitario_momento if m.costo_unitario_momento is not None else costo_unitario_ajustado)
        for m in especie.muertes
    )
    if unidades_vendibles <= 0 and total_muerto > 0 and costo_de_muertos == 0:
        costo_de_muertos = costo_total - costo_de_vendidos
    ganancia_real = ingreso_ventas - costo_de_vendidos - costo_de_muertos

    if total_vendido > 0 and costo_de_vendidos > 0:
        # Margen real: incluye el costo de las muertes para reflejar la rentabilidad total
        costo_total_real = costo_de_vendidos + costo_de_muertos
        margen = ((ingreso_ventas - costo_total_real) / costo_de_vendidos) * 100
    elif costo_total > 0 and unidades_vendibles <= 0:
        margen = -100.0
    else:
        margen = 0

    valor_inventario = max(stock, 0) * costo_unitario_ajustado

    return {
        'total_ingresado': total_ingresado,
        'total_vendido': total_vendido,
        'total_muerto': total_muerto,
        'stock': stock,
        'costo_total': costo_total,
        'costo_unitario_ajustado': round(costo_unitario_ajustado, 2),
        'precio_minimo_recomendado': precio_minimo_recomendado,
        'ingreso_ventas': round(ingreso_ventas, 2),
        'costo_de_vendidos': round(costo_de_vendidos, 2),
        'costo_de_muertos': round(costo_de_muertos, 2),
        'ganancia_real': round(ganancia_real, 2),
        'valor_inventario': round(valor_inventario, 2),
        'mortalidad': round(mortalidad, 1),
        'margen': round(margen, 1),
    }


def obtener_rango_fechas(periodo, desde_str, hasta_str):
    hoy = date.today()
    if periodo == 'hoy':
        return hoy, hoy
    elif periodo == 'semana':
        inicio = hoy - timedelta(days=hoy.weekday())
        return inicio, hoy
    elif periodo == 'mes':
        return hoy.replace(day=1), hoy
    elif periodo == 'custom' and desde_str and hasta_str:
        try:
            desde = datetime.strptime(desde_str, '%Y-%m-%d').date()
            hasta = datetime.strptime(hasta_str, '%Y-%m-%d').date()
            return desde, hasta
        except ValueError:
            return None, None
    return None, None


def calcular_balance_periodo(usuario_id, fecha_inicio, fecha_fin):
    especies = Especie.query.filter_by(usuario_id=usuario_id).all()

    total_invertido = 0
    total_recuperado = 0
    total_costo_vendido = 0
    total_costo_muertes = 0

    for esp in especies:
        stats = calcular_estadisticas(esp)
        costo_u_fallback = stats['costo_unitario_ajustado']

        lotes_periodo = [l for l in esp.lotes if fecha_inicio <= l.fecha <= fecha_fin]
        total_invertido += sum(l.costo_total for l in lotes_periodo)

        ventas_periodo = [v for v in esp.ventas if fecha_inicio <= v.fecha <= fecha_fin]
        ingreso_periodo = sum(v.cantidad * v.precio_unidad for v in ventas_periodo)
        total_recuperado += ingreso_periodo
        total_costo_vendido += sum(
            v.cantidad * (v.costo_unitario_momento if v.costo_unitario_momento is not None else costo_u_fallback)
            for v in ventas_periodo
        )

        muertes_periodo = [m for m in esp.muertes if fecha_inicio <= m.fecha <= fecha_fin]
        total_costo_muertes += sum(
            m.cantidad * (m.costo_unitario_momento if m.costo_unitario_momento is not None else costo_u_fallback)
            for m in muertes_periodo
        )

    ganancia_neta = total_recuperado - total_costo_vendido - total_costo_muertes

    return {
        'total_invertido': round(total_invertido, 2),
        'total_recuperado': round(total_recuperado, 2),
        'costo_vendido': round(total_costo_vendido, 2),
        'costo_muertes': round(total_costo_muertes, 2),
        'ganancia_neta': round(ganancia_neta, 2),
    }


def generar_sugerencias(datos, balance):
    sugerencias = []

    especies_alta_mortalidad = [d for d in datos if d['mortalidad'] > 25 and d['total_ingresado'] > 0]
    if especies_alta_mortalidad:
        nombres = ', '.join(d['especie'].nombre for d in especies_alta_mortalidad[:2])
        sugerencias.append({
            'tipo': 'danger',
            'icono': 'bi-heartbreak',
            'texto': f'Alta mortalidad en {nombres}. Revisa las condiciones del acuario.',
        })

    especies_bajo_costo = [d for d in datos if d['margen'] < 0 and d['total_vendido'] > 0]
    if especies_bajo_costo:
        nombres = ', '.join(d['especie'].nombre for d in especies_bajo_costo[:2])
        sugerencias.append({
            'tipo': 'warning',
            'icono': 'bi-graph-down-arrow',
            'texto': f'Ventas por debajo del costo en {nombres}. Ajusta los precios.',
        })

    if len(sugerencias) < 2:
        especies_con_ventas = [d for d in datos if d['total_vendido'] > 0 and d['margen'] > 0]
        if especies_con_ventas:
            margen_promedio = sum(d['margen'] for d in especies_con_ventas) / len(especies_con_ventas)
            if margen_promedio < 10:
                sugerencias.append({
                    'tipo': 'warning',
                    'icono': 'bi-exclamation-circle',
                    'texto': f'Margen promedio bajo ({margen_promedio:.1f}%). Considera aumentar precios.',
                })

    return sugerencias[:2]


@app.route('/api/especie/<int:especie_id>/stats')
@login_required
def api_especie_stats(especie_id):
    especie = Especie.query.filter_by(
        id=especie_id, usuario_id=session['usuario_id']
    ).first_or_404()
    stats = calcular_estadisticas(especie)
    return jsonify({
        'nombre': especie.nombre,
        'stock': stats['stock'],
        'costo_unitario_ajustado': stats['costo_unitario_ajustado'],
        'precio_minimo_recomendado': stats['precio_minimo_recomendado'],
    })


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        nombre_tienda = request.form['nombre_tienda'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        password2 = request.form['password2']
        currency = request.form.get('currency', 'GTQ')
        if not nombre_tienda or not email or not password:
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('registro'))
        if password != password2:
            flash('Las contrasenas no coinciden.', 'danger')
            return redirect(url_for('registro'))
        if len(password) < 6:
            flash('La contrasena debe tener al menos 6 caracteres.', 'danger')
            return redirect(url_for('registro'))
        existente = Usuario.query.filter_by(email=email).first()
        if existente:
            flash('Ya existe una cuenta con ese email.', 'danger')
            return redirect(url_for('registro'))
        usuario = Usuario(nombre_tienda=nombre_tienda, email=email)
        usuario.set_password(password)
        usuario.currency = currency if currency in ('GTQ', 'USD') else 'GTQ'
        db.session.add(usuario)
        db.session.commit()
        session['usuario_id'] = usuario.id
        session['nombre_tienda'] = usuario.nombre_tienda
        session['currency'] = usuario.currency
        flash(f'Bienvenido, {nombre_tienda}!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('registro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.check_password(password):
            session['usuario_id'] = usuario.id
            session['nombre_tienda'] = usuario.nombre_tienda
            session['currency'] = usuario.currency
            flash(f'Bienvenido, {usuario.nombre_tienda}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Email o contrasena incorrectos.', 'danger')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesion cerrada.', 'info')
    return redirect(url_for('login'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()
        # Always show the same message to avoid user enumeration
        if usuario:
            token = secrets.token_urlsafe(32)
            expira = datetime.utcnow() + timedelta(hours=1)
            reset = PasswordResetToken(
                usuario_id=usuario.id,
                token=token,
                expira=expira
            )
            db.session.add(reset)
            db.session.commit()
            reset_url = url_for('reset_password', token=token, _external=True)
            try:
                # build both plain text and simple HTML body
                text_body = f"""Hola {usuario.nombre_tienda},

Recibimos una solicitud para restablecer la contraseña de tu cuenta NexStock.

Haz clic en el siguiente enlace para crear una nueva contraseña (válido por 1 hora):

{reset_url}

Si no solicitaste esto, ignora este correo. Tu contraseña no cambiará.

— El equipo de NexStock
"""
                html_body = f"""
                <p>Hola <strong>{usuario.nombre_tienda}</strong>,</p>
                <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta NexStock.</p>
                <p>Haz clic en el siguiente enlace para crear una nueva contraseña (válido por 1 hora):</p>
                <p><a href=\"{reset_url}\">Restablecer contraseña</a></p>
                <p>Si no solicitaste esto, ignora este correo. Tu contraseña no cambiará.</p>
                <p style=\"color:#6b7280;font-size:0.9rem;\">— El equipo de NexStock</p>
                """

                msg = Message(subject='Restablecer contraseña - NexStock', recipients=[email])
                msg.body = text_body
                msg.html = html_body
                # Log the reset link so it's visible in Railway logs (helpful if SMTP isn't configured)
                app.logger.info('Password reset link for %s: %s', email, reset_url)

                # Send email asynchronously so a slow SMTP connection doesn't block the request
                def _send_async(message):
                    try:
                        with app.app_context():
                            mail.send(message)
                        app.logger.info('Password reset email sent to %s (background)', email)
                    except Exception:
                        app.logger.exception('Error sending password reset email to %s (background)', email)

                Thread(target=_send_async, args=(msg,), daemon=True).start()
                app.logger.info('Password reset email scheduled for %s', email)
            except Exception as e:
                # Log the error and the URL so you can still retrieve the link from logs
                app.logger.exception("Error enviando email de reset: %s", e)
                app.logger.info('Password reset link (fallback) for %s: %s', email, reset_url)
        flash('Si ese email está registrado, recibirás un enlace en tu correo.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    reset = PasswordResetToken.query.filter_by(token=token).first()
    if not reset or not reset.is_valid():
        flash('El enlace no es válido o ya expiró. Solicita uno nuevo.', 'danger')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        password = request.form['password']
        password2 = request.form['password2']
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            return redirect(url_for('reset_password', token=token))
        if password != password2:
            flash('Las contraseñas no coinciden.', 'danger')
            return redirect(url_for('reset_password', token=token))
        usuario = Usuario.query.get(reset.usuario_id)
        usuario.set_password(password)
        reset.usado = True
        db.session.commit()
        flash('¡Contraseña actualizada! Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)


@app.route('/')
@login_required
def dashboard():
    periodo = request.args.get('periodo', 'mes')
    desde_str = request.args.get('desde', '')
    hasta_str = request.args.get('hasta', '')

    fecha_inicio, fecha_fin = obtener_rango_fechas(periodo, desde_str, hasta_str)
    if fecha_inicio is None:
        periodo = 'mes'
        hoy = date.today()
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy

    uid = session['usuario_id']
    especies = Especie.query.filter_by(usuario_id=uid).order_by(Especie.nombre).all()

    tiene_especies = len(especies) > 0
    tiene_lotes = Lote.query.join(Especie).filter(Especie.usuario_id == uid).first() is not None if tiene_especies else False
    tiene_ventas = Venta.query.join(Especie).filter(Especie.usuario_id == uid).first() is not None if tiene_lotes else False
    onboarding = not (tiene_especies and tiene_lotes and tiene_ventas)

    datos = []
    valor_inventario_total = 0
    for esp in especies:
        stats = calcular_estadisticas(esp)
        datos.append({'especie': esp, **stats})
        valor_inventario_total += stats['valor_inventario']

    balance = calcular_balance_periodo(uid, fecha_inicio, fecha_fin)

    sugerencias = generar_sugerencias(datos, balance)

    top_rentables = sorted(
        [d for d in datos if d['margen'] > 0 and d['total_vendido'] > 0],
        key=lambda x: -x['margen']
    )[:3]

    usuario = get_usuario()
    return render_template(
        'dashboard.html',
        datos=datos,
        balance=balance,
        valor_inventario_total=round(valor_inventario_total, 2),
        sugerencias=sugerencias,
        top_rentables=top_rentables,
        usuario=usuario,
        periodo=periodo,
        fecha_inicio=fecha_inicio.isoformat(),
        fecha_fin=fecha_fin.isoformat(),
        hoy=date.today().isoformat(),
        onboarding=onboarding,
        tiene_especies=tiene_especies,
        tiene_lotes=tiene_lotes,
        tiene_ventas=tiene_ventas,
    )


@app.route('/especies')
@login_required
def lista_especies():
    especies = Especie.query.filter_by(usuario_id=session['usuario_id']).order_by(Especie.nombre).all()
    datos = [{'especie': e, **calcular_estadisticas(e)} for e in especies]
    return render_template('especies.html', datos=datos)


@app.route('/especies/nueva', methods=['GET', 'POST'])
@login_required
def nueva_especie():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        categoria = request.form['categoria']
        descripcion = request.form.get('descripcion', '').strip()
        if not nombre:
            flash('El nombre es obligatorio.', 'danger')
            return redirect(url_for('nueva_especie'))
        existente = Especie.query.filter_by(
            usuario_id=session['usuario_id'], nombre=nombre
        ).first()
        if existente:
            flash('Ya existe una especie con ese nombre.', 'danger')
            return redirect(url_for('nueva_especie'))
        especie = Especie(
            usuario_id=session['usuario_id'],
            nombre=nombre,
            categoria=categoria,
            descripcion=descripcion
        )
        db.session.add(especie)
        db.session.commit()
        tiene_lotes = Lote.query.join(Especie).filter(Especie.usuario_id == session['usuario_id']).first()
        if not tiene_lotes:
            flash(f'Especie "{nombre}" registrada. Ahora registra tu primer lote.', 'success')
            return redirect(url_for('nuevo_lote'))
        flash(f'Especie "{nombre}" registrada.', 'success')
        return redirect(url_for('lista_especies'))
    return render_template('nueva_especie.html')


@app.route('/lotes')
@login_required
def lista_lotes():
    lotes = Lote.query.join(Especie).filter(
        Especie.usuario_id == session['usuario_id']
    ).order_by(Lote.fecha.desc()).all()
    return render_template('lotes.html', lotes=lotes)


@app.route('/lotes/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_lote():
    if request.method == 'POST':
        especie_id = request.form['especie_id']
        especie = Especie.query.filter_by(
            id=especie_id, usuario_id=session['usuario_id']
        ).first_or_404()
        cantidad = int(request.form['cantidad'])
        costo_total = float(request.form['costo_total'])
        fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        if cantidad < 1 or costo_total < 0:
            flash('Cantidad debe ser al menos 1 y costo no puede ser negativo.', 'danger')
            return redirect(url_for('nuevo_lote'))
        lote = Lote(especie_id=especie.id, cantidad=cantidad, costo_total=costo_total, fecha=fecha)
        incrementar_uso(especie)
        db.session.add(lote)
        db.session.commit()
        tiene_ventas = Venta.query.join(Especie).filter(Especie.usuario_id == session['usuario_id']).first()
        if not tiene_ventas:
            flash('Lote registrado. Ahora registra tu primera venta.', 'success')
            return redirect(url_for('nueva_venta'))
        flash('Lote registrado.', 'success')
        return redirect(url_for('lista_lotes'))
    frecuentes, resto = get_especies_usuario()
    return render_template('nuevo_lote.html', frecuentes=frecuentes, resto=resto, hoy=date.today().isoformat())


@app.route('/ventas')
@login_required
def lista_ventas():
    ventas = Venta.query.join(Especie).filter(
        Especie.usuario_id == session['usuario_id']
    ).order_by(Venta.fecha.desc()).all()
    return render_template('ventas.html', ventas=ventas)


@app.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_venta():
    if request.method == 'POST':
        especie_id = request.form['especie_id']
        especie = Especie.query.filter_by(
            id=especie_id, usuario_id=session['usuario_id']
        ).first_or_404()
        cantidad = int(request.form['cantidad'])
        precio_unidad = float(request.form['precio_unidad'])
        fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        if cantidad < 1 or precio_unidad < 0:
            flash('Cantidad debe ser al menos 1 y precio no puede ser negativo.', 'danger')
            return redirect(url_for('nueva_venta'))
        stats = calcular_estadisticas(especie)
        if cantidad > stats['stock']:
            flash(f'Stock insuficiente. Disponible: {stats["stock"]}', 'danger')
            return redirect(url_for('nueva_venta'))
        es_primera_venta = not Venta.query.join(Especie).filter(Especie.usuario_id == session['usuario_id']).first()
        venta = Venta(
            especie_id=especie.id, cantidad=cantidad, precio_unidad=precio_unidad,
            costo_unitario_momento=stats['costo_unitario_ajustado'], fecha=fecha
        )
        incrementar_uso(especie)
        db.session.add(venta)
        db.session.commit()
        if es_primera_venta:
            flash('Ya estas viendo tus numeros reales. NexStock ahora esta trabajando para ti.', 'success')
            return redirect(url_for('dashboard'))
        flash('Venta registrada.', 'success')
        return redirect(url_for('lista_ventas'))
    frecuentes, resto = get_especies_usuario()
    return render_template('nueva_venta.html', frecuentes=frecuentes, resto=resto, hoy=date.today().isoformat())


@app.route('/muertes')
@login_required
def lista_muertes():
    muertes = Muerte.query.join(Especie).filter(
        Especie.usuario_id == session['usuario_id']
    ).order_by(Muerte.fecha.desc()).all()
    return render_template('muertes.html', muertes=muertes)


@app.route('/muertes/nueva', methods=['GET', 'POST'])
@login_required
def nueva_muerte():
    if request.method == 'POST':
        especie_id = request.form['especie_id']
        especie = Especie.query.filter_by(
            id=especie_id, usuario_id=session['usuario_id']
        ).first_or_404()
        cantidad = int(request.form['cantidad'])
        fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        nota = request.form.get('nota', '').strip()
        if cantidad < 1:
            flash('Cantidad debe ser al menos 1.', 'danger')
            return redirect(url_for('nueva_muerte'))
        stats = calcular_estadisticas(especie)
        if cantidad > stats['stock']:
            flash(f'No puedes registrar mas muertes que el stock disponible ({stats["stock"]}).', 'danger')
            return redirect(url_for('nueva_muerte'))
        muerte = Muerte(
            especie_id=especie.id, cantidad=cantidad,
            costo_unitario_momento=stats['costo_unitario_ajustado'], fecha=fecha, nota=nota
        )
        incrementar_uso(especie)
        db.session.add(muerte)
        db.session.commit()
        flash('Muerte registrada.', 'success')
        return redirect(url_for('lista_muertes'))
    frecuentes, resto = get_especies_usuario()
    return render_template('nueva_muerte.html', frecuentes=frecuentes, resto=resto, hoy=date.today().isoformat())


@app.route('/especies/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_especie(id):
    especie = Especie.query.filter_by(id=id, usuario_id=session['usuario_id']).first_or_404()
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        categoria = request.form['categoria']
        descripcion = request.form.get('descripcion', '').strip()
        if not nombre:
            flash('El nombre es obligatorio.', 'danger')
            return redirect(url_for('editar_especie', id=id))
        existente = Especie.query.filter(
            Especie.usuario_id == session['usuario_id'],
            Especie.nombre == nombre,
            Especie.id != id
        ).first()
        if existente:
            flash('Ya existe otra especie con ese nombre.', 'danger')
            return redirect(url_for('editar_especie', id=id))
        especie.nombre = nombre
        especie.categoria = categoria
        especie.descripcion = descripcion
        db.session.commit()
        flash(f'Especie "{nombre}" actualizada.', 'success')
        return redirect(url_for('lista_especies'))
    return render_template('nueva_especie.html', editando=especie)


@app.route('/especies/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_especie(id):
    especie = Especie.query.filter_by(id=id, usuario_id=session['usuario_id']).first_or_404()
    if especie.lotes or especie.ventas or especie.muertes:
        flash('No se puede eliminar una especie que tiene lotes, ventas o muertes asociadas.', 'danger')
        return redirect(url_for('lista_especies'))
    db.session.delete(especie)
    db.session.commit()
    flash(f'Especie "{especie.nombre}" eliminada.', 'success')
    return redirect(url_for('lista_especies'))


@app.route('/lotes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_lote(id):
    lote = Lote.query.get_or_404(id)
    especie = Especie.query.filter_by(id=lote.especie_id, usuario_id=session['usuario_id']).first_or_404()
    if request.method == 'POST':
        nueva_cantidad = int(request.form['cantidad'])
        nuevo_costo = float(request.form['costo_total'])
        nueva_fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        if nueva_cantidad < 1 or nuevo_costo < 0:
            flash('Cantidad debe ser al menos 1 y costo no puede ser negativo.', 'danger')
            return redirect(url_for('editar_lote', id=id))
        total_consumido = sum(v.cantidad for v in especie.ventas) + sum(m.cantidad for m in especie.muertes)
        total_otros_lotes = sum(l.cantidad for l in especie.lotes if l.id != id)
        if total_otros_lotes + nueva_cantidad < total_consumido:
            flash(f'No puedes reducir la cantidad a {nueva_cantidad}. Ya se han consumido {total_consumido} unidades.', 'danger')
            return redirect(url_for('editar_lote', id=id))
        lote.cantidad = nueva_cantidad
        lote.costo_total = nuevo_costo
        lote.fecha = nueva_fecha
        db.session.commit()
        flash('Lote actualizado.', 'success')
        return redirect(url_for('lista_lotes'))
    frecuentes, resto = get_especies_usuario()
    return render_template('nuevo_lote.html', editando=lote, frecuentes=frecuentes, resto=resto, hoy=date.today().isoformat())


@app.route('/lotes/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_lote(id):
    lote = Lote.query.get_or_404(id)
    especie = Especie.query.filter_by(id=lote.especie_id, usuario_id=session['usuario_id']).first_or_404()
    total_otros_lotes = sum(l.cantidad for l in especie.lotes if l.id != id)
    total_consumido = sum(v.cantidad for v in especie.ventas) + sum(m.cantidad for m in especie.muertes)
    if total_otros_lotes < total_consumido:
        flash(f'No se puede eliminar este lote. Se han vendido/muerto {total_consumido} unidades y solo quedarian {total_otros_lotes} en otros lotes.', 'danger')
        return redirect(url_for('lista_lotes'))
    db.session.delete(lote)
    db.session.commit()
    flash('Lote eliminado.', 'success')
    return redirect(url_for('lista_lotes'))


@app.route('/ventas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_venta(id):
    venta = Venta.query.get_or_404(id)
    especie = Especie.query.filter_by(id=venta.especie_id, usuario_id=session['usuario_id']).first_or_404()
    if request.method == 'POST':
        nueva_cantidad = int(request.form['cantidad'])
        nuevo_precio = float(request.form['precio_unidad'])
        nueva_fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        if nueva_cantidad < 1 or nuevo_precio < 0:
            flash('Cantidad debe ser al menos 1 y precio no puede ser negativo.', 'danger')
            return redirect(url_for('editar_venta', id=id))
        stats = calcular_estadisticas(especie)
        stock_disponible = stats['stock'] + venta.cantidad
        if nueva_cantidad > stock_disponible:
            flash(f'Stock insuficiente. Disponible: {stock_disponible}', 'danger')
            return redirect(url_for('editar_venta', id=id))
        venta.cantidad = nueva_cantidad
        venta.precio_unidad = nuevo_precio
        venta.fecha = nueva_fecha
        db.session.commit()
        flash('Venta actualizada.', 'success')
        return redirect(url_for('lista_ventas'))
    frecuentes, resto = get_especies_usuario()
    return render_template('nueva_venta.html', editando=venta, frecuentes=frecuentes, resto=resto, hoy=date.today().isoformat())


@app.route('/ventas/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_venta(id):
    venta = Venta.query.get_or_404(id)
    Especie.query.filter_by(id=venta.especie_id, usuario_id=session['usuario_id']).first_or_404()
    db.session.delete(venta)
    db.session.commit()
    flash('Venta eliminada.', 'success')
    return redirect(url_for('lista_ventas'))


@app.route('/muertes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_muerte(id):
    muerte = Muerte.query.get_or_404(id)
    especie = Especie.query.filter_by(id=muerte.especie_id, usuario_id=session['usuario_id']).first_or_404()
    if request.method == 'POST':
        nueva_cantidad = int(request.form['cantidad'])
        nueva_fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        nota = request.form.get('nota', '').strip()
        if nueva_cantidad < 1:
            flash('Cantidad debe ser al menos 1.', 'danger')
            return redirect(url_for('editar_muerte', id=id))
        stats = calcular_estadisticas(especie)
        stock_disponible = stats['stock'] + muerte.cantidad
        if nueva_cantidad > stock_disponible:
            flash(f'No puedes registrar mas muertes que el stock disponible ({stock_disponible}).', 'danger')
            return redirect(url_for('editar_muerte', id=id))
        muerte.cantidad = nueva_cantidad
        muerte.fecha = nueva_fecha
        muerte.nota = nota
        db.session.commit()
        flash('Muerte actualizada.', 'success')
        return redirect(url_for('lista_muertes'))
    frecuentes, resto = get_especies_usuario()
    return render_template('nueva_muerte.html', editando=muerte, frecuentes=frecuentes, resto=resto, hoy=date.today().isoformat())


@app.route('/muertes/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_muerte(id):
    muerte = Muerte.query.get_or_404(id)
    Especie.query.filter_by(id=muerte.especie_id, usuario_id=session['usuario_id']).first_or_404()
    db.session.delete(muerte)
    db.session.commit()
    flash('Muerte eliminada.', 'success')
    return redirect(url_for('lista_muertes'))


def migrate_add_costo_momento():
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    if 'venta' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('venta')]
        if 'costo_unitario_momento' not in cols:
            db.session.execute(text('ALTER TABLE venta ADD COLUMN costo_unitario_momento FLOAT'))
            db.session.commit()
    if 'muerte' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('muerte')]
        if 'costo_unitario_momento' not in cols:
            db.session.execute(text('ALTER TABLE muerte ADD COLUMN costo_unitario_momento FLOAT'))
            db.session.commit()


def migrate_add_usuario_currency():
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    if 'usuario' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('usuario')]
        if 'currency' not in cols:
            # SQLite accepts adding a column with a default
            try:
                db.session.execute(text("ALTER TABLE usuario ADD COLUMN currency VARCHAR(3) DEFAULT 'GTQ' NOT NULL"))
                db.session.commit()
            except Exception:
                # Fallback: try without NOT NULL/default (older sqlite)
                try:
                    db.session.execute(text("ALTER TABLE usuario ADD COLUMN currency VARCHAR(3)"))
                    db.session.commit()
                except Exception:
                    pass


with app.app_context():
    migrate_add_costo_momento()
    migrate_add_usuario_currency()
    db.create_all()

    def calcular_costo_historico(especie, hasta_fecha):
        lotes_hasta = [l for l in especie.lotes if l.fecha <= hasta_fecha]
        muertes_hasta = [m for m in especie.muertes if m.fecha <= hasta_fecha]
        total_ingresado = sum(l.cantidad for l in lotes_hasta)
        costo_total = sum(l.costo_total for l in lotes_hasta)
        total_muerto = sum(m.cantidad for m in muertes_hasta)
        unidades_vendibles = total_ingresado - total_muerto
        if unidades_vendibles > 0:
            return round(costo_total / unidades_vendibles, 2)
        elif total_ingresado > 0:
            return round(costo_total / total_ingresado, 2)
        return 0

    ventas_null = Venta.query.filter(Venta.costo_unitario_momento.is_(None)).all()
    muertes_null = Muerte.query.filter(Muerte.costo_unitario_momento.is_(None)).all()

    if ventas_null or muertes_null:
        for v in ventas_null:
            v.costo_unitario_momento = calcular_costo_historico(v.especie, v.fecha)

        for m in muertes_null:
            m.costo_unitario_momento = calcular_costo_historico(m.especie, m.fecha)

        db.session.commit()
        print(f'Backfill: {len(ventas_null)} ventas, {len(muertes_null)} muertes actualizadas')
    else:
        print('Backfill: no hay registros pendientes')
@app.context_processor
def utility_processor():
    def formato_moneda(valor):
        # Usa la moneda guardada en sesión si existe: 'GTQ' (Quetzal) o 'USD' (Dólar)
        moneda = session.get('currency', 'GTQ')
        try:
            cantidad = float(valor)
        except (TypeError, ValueError):
            cantidad = 0.0
        if moneda == 'USD':
            simbolo = '$'
        else:
            simbolo = 'Q'
        return f"{simbolo} {cantidad:,.2f}"
    def currency_symbol():
        return '$' if session.get('currency', 'GTQ') == 'USD' else 'Q'

    return dict(formato_moneda=formato_moneda, currency_symbol=currency_symbol())


@app.route('/set_currency', methods=['POST'])
def set_currency():
    """Guarda la preferencia de moneda en la sesión y vuelve a la página anterior."""
    moneda = request.form.get('currency')
    if moneda in ('GTQ', 'USD'):
        session['currency'] = moneda
        # Si el usuario está logueado, persiste la preferencia en la BD
        if 'usuario_id' in session:
            try:
                usuario = Usuario.query.get(session['usuario_id'])
                if usuario:
                    usuario.currency = moneda
                    db.session.commit()
            except Exception:
                db.session.rollback()
    # redirigir a la página anterior si existe, sino al dashboard
    return redirect(request.referrer or url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.exception("500 error: %s", error)
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def unhandled_exception(e):
    db.session.rollback()
    app.logger.exception("Unhandled exception: %s", e)
    return render_template('500.html'), 500
