import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///acuario.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Especie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    categoria = db.Column(db.String(50), nullable=False, default='Pez')
    descripcion = db.Column(db.String(200))
    lotes = db.relationship('Lote', backref='especie', lazy=True)
    ventas = db.relationship('Venta', backref='especie', lazy=True)
    muertes = db.relationship('Muerte', backref='especie', lazy=True)


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


def calcular_estadisticas(especie):
    total_ingresado = sum(l.cantidad for l in especie.lotes)
    total_vendido = sum(v.cantidad for v in especie.ventas)
    total_muerto = sum(m.cantidad for m in especie.muertes)
    stock = total_ingresado - total_vendido - total_muerto

    costo_total = sum(l.costo_total for l in especie.lotes)
    ingreso_ventas = sum(v.cantidad * v.precio_unidad for v in especie.ventas)

    mortalidad = (total_muerto / total_ingresado * 100) if total_ingresado > 0 else 0

    costo_unitario = (costo_total / total_ingresado) if total_ingresado > 0 else 0
    costo_muertos = costo_unitario * total_muerto
    costo_vendidos = costo_unitario * total_vendido

    if costo_vendidos > 0:
        margen = ((ingreso_ventas - costo_vendidos - costo_muertos) / costo_vendidos) * 100
    elif costo_total > 0:
        margen = -100.0
    else:
        margen = 0

    return {
        'total_ingresado': total_ingresado,
        'total_vendido': total_vendido,
        'total_muerto': total_muerto,
        'stock': stock,
        'costo_total': costo_total,
        'costo_muertos': round(costo_muertos, 2),
        'ingreso_ventas': ingreso_ventas,
        'mortalidad': round(mortalidad, 1),
        'margen': round(margen, 1),
    }


@app.route('/')
def dashboard():
    especies = Especie.query.order_by(Especie.nombre).all()
    datos = []
    for esp in especies:
        stats = calcular_estadisticas(esp)
        datos.append({'especie': esp, **stats})
    return render_template('dashboard.html', datos=datos)


@app.route('/especies')
def lista_especies():
    especies = Especie.query.order_by(Especie.nombre).all()
    return render_template('especies.html', especies=especies)


@app.route('/especies/nueva', methods=['GET', 'POST'])
def nueva_especie():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        categoria = request.form['categoria']
        descripcion = request.form.get('descripcion', '').strip()
        if not nombre:
            flash('El nombre es obligatorio.', 'danger')
            return redirect(url_for('nueva_especie'))
        existente = Especie.query.filter_by(nombre=nombre).first()
        if existente:
            flash('Ya existe una especie con ese nombre.', 'danger')
            return redirect(url_for('nueva_especie'))
        especie = Especie(nombre=nombre, categoria=categoria, descripcion=descripcion)
        db.session.add(especie)
        db.session.commit()
        flash(f'Especie "{nombre}" registrada.', 'success')
        return redirect(url_for('lista_especies'))
    return render_template('nueva_especie.html')


@app.route('/lotes')
def lista_lotes():
    lotes = Lote.query.order_by(Lote.fecha.desc()).all()
    return render_template('lotes.html', lotes=lotes)


@app.route('/lotes/nuevo', methods=['GET', 'POST'])
def nuevo_lote():
    if request.method == 'POST':
        especie_id = request.form['especie_id']
        cantidad = int(request.form['cantidad'])
        costo_total = float(request.form['costo_total'])
        fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        if cantidad < 1 or costo_total < 0:
            flash('Cantidad debe ser al menos 1 y costo no puede ser negativo.', 'danger')
            return redirect(url_for('nuevo_lote'))
        lote = Lote(especie_id=especie_id, cantidad=cantidad, costo_total=costo_total, fecha=fecha)
        db.session.add(lote)
        db.session.commit()
        flash('Lote registrado.', 'success')
        return redirect(url_for('lista_lotes'))
    especies = Especie.query.order_by(Especie.nombre).all()
    return render_template('nuevo_lote.html', especies=especies, hoy=date.today().isoformat())


@app.route('/ventas')
def lista_ventas():
    ventas = Venta.query.order_by(Venta.fecha.desc()).all()
    return render_template('ventas.html', ventas=ventas)


@app.route('/ventas/nueva', methods=['GET', 'POST'])
def nueva_venta():
    if request.method == 'POST':
        especie_id = request.form['especie_id']
        cantidad = int(request.form['cantidad'])
        precio_unidad = float(request.form['precio_unidad'])
        fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        if cantidad < 1 or precio_unidad < 0:
            flash('Cantidad debe ser al menos 1 y precio no puede ser negativo.', 'danger')
            return redirect(url_for('nueva_venta'))
        especie = Especie.query.get(especie_id)
        stats = calcular_estadisticas(especie)
        if cantidad > stats['stock']:
            flash(f'Stock insuficiente. Disponible: {stats["stock"]}', 'danger')
            return redirect(url_for('nueva_venta'))
        venta = Venta(especie_id=especie_id, cantidad=cantidad, precio_unidad=precio_unidad, fecha=fecha)
        db.session.add(venta)
        db.session.commit()
        flash('Venta registrada.', 'success')
        return redirect(url_for('lista_ventas'))
    especies = Especie.query.order_by(Especie.nombre).all()
    return render_template('nueva_venta.html', especies=especies, hoy=date.today().isoformat())


@app.route('/muertes')
def lista_muertes():
    muertes = Muerte.query.order_by(Muerte.fecha.desc()).all()
    return render_template('muertes.html', muertes=muertes)


@app.route('/muertes/nueva', methods=['GET', 'POST'])
def nueva_muerte():
    if request.method == 'POST':
        especie_id = request.form['especie_id']
        cantidad = int(request.form['cantidad'])
        fecha = datetime.strptime(request.form['fecha'], '%Y-%m-%d').date()
        nota = request.form.get('nota', '').strip()
        especie = Especie.query.get(especie_id)
        stats = calcular_estadisticas(especie)
        if cantidad > stats['stock']:
            flash(f'No puedes registrar más muertes que el stock disponible ({stats["stock"]}).', 'danger')
            return redirect(url_for('nueva_muerte'))
        muerte = Muerte(especie_id=especie_id, cantidad=cantidad, fecha=fecha, nota=nota)
        db.session.add(muerte)
        db.session.commit()
        flash('Muerte registrada.', 'success')
        return redirect(url_for('lista_muertes'))
    especies = Especie.query.order_by(Especie.nombre).all()
    return render_template('nueva_muerte.html', especies=especies, hoy=date.today().isoformat())


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
