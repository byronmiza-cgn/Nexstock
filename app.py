import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///acuario.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_tienda = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
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
    fecha = db.Column(db.Date, nullable=False, default=date.today)


class Muerte(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    especie_id = db.Column(db.Integer, db.ForeignKey('especie.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    nota = db.Column(db.String(200))


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
    costo_unitario_ajustado = (costo_total / unidades_vendibles) if unidades_vendibles > 0 else 0

    precio_minimo_recomendado = round(costo_unitario_ajustado * 1.20, 2)

    if total_vendido > 0 and costo_unitario_ajustado > 0:
        costo_de_vendidos = costo_unitario_ajustado * total_vendido
        margen = ((ingreso_ventas - costo_de_vendidos) / costo_de_vendidos) * 100
    elif costo_total > 0 and unidades_vendibles <= 0:
        margen = -100.0
    else:
        margen = 0

    return {
        'total_ingresado': total_ingresado,
        'total_vendido': total_vendido,
        'total_muerto': total_muerto,
        'stock': stock,
        'costo_total': costo_total,
        'costo_unitario_ajustado': round(costo_unitario_ajustado, 2),
        'precio_minimo_recomendado': precio_minimo_recomendado,
        'ingreso_ventas': ingreso_ventas,
        'mortalidad': round(mortalidad, 1),
        'margen': round(margen, 1),
    }


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
        db.session.add(usuario)
        db.session.commit()
        session['usuario_id'] = usuario.id
        session['nombre_tienda'] = usuario.nombre_tienda
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


@app.route('/')
@login_required
def dashboard():
    especies = Especie.query.filter_by(usuario_id=session['usuario_id']).order_by(Especie.nombre).all()
    datos = []
    alertas = []
    for esp in especies:
        stats = calcular_estadisticas(esp)
        datos.append({'especie': esp, **stats})
        if stats['mortalidad'] > 25 and stats['total_ingresado'] > 0:
            alertas.append({
                'tipo': 'mortalidad',
                'especie': esp.nombre,
                'valor': stats['mortalidad'],
            })
        if stats['margen'] < 0 and stats['total_vendido'] > 0:
            alertas.append({
                'tipo': 'margen_negativo',
                'especie': esp.nombre,
                'valor': stats['margen'],
            })

    top_rentables = sorted(
        [d for d in datos if d['margen'] > 0 and d['total_vendido'] > 0],
        key=lambda x: -x['margen']
    )[:3]

    usuario = get_usuario()
    return render_template(
        'dashboard.html',
        datos=datos,
        alertas=alertas,
        top_rentables=top_rentables,
        usuario=usuario,
    )


@app.route('/especies')
@login_required
def lista_especies():
    especies = Especie.query.filter_by(usuario_id=session['usuario_id']).order_by(Especie.nombre).all()
    return render_template('especies.html', especies=especies)


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
        venta = Venta(especie_id=especie.id, cantidad=cantidad, precio_unidad=precio_unidad, fecha=fecha)
        incrementar_uso(especie)
        db.session.add(venta)
        db.session.commit()
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
        muerte = Muerte(especie_id=especie.id, cantidad=cantidad, fecha=fecha, nota=nota)
        incrementar_uso(especie)
        db.session.add(muerte)
        db.session.commit()
        flash('Muerte registrada.', 'success')
        return redirect(url_for('lista_muertes'))
    frecuentes, resto = get_especies_usuario()
    return render_template('nueva_muerte.html', frecuentes=frecuentes, resto=resto, hoy=date.today().isoformat())


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
