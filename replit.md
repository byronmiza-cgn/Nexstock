# AquaStock - Control de Inventario para Acuarios

## Overview
Aplicación web para tiendas de acuarios que permite controlar el inventario de animales vivos (peces, corales, invertebrados, plantas).

## Tech Stack
- **Backend**: Python 3.11 + Flask
- **Database**: SQLite (via Flask-SQLAlchemy)
- **Frontend**: HTML + Bootstrap 5 + Bootstrap Icons
- **ORM**: SQLAlchemy

## Project Structure
```
app.py              - Main application (models, routes, logic)
templates/
  base.html         - Base template with navbar and layout
  dashboard.html    - Main dashboard with stats per species
  especies.html     - Species list
  nueva_especie.html - New species form
  lotes.html        - Entry lots list
  nuevo_lote.html   - New lot form
  ventas.html       - Sales list
  nueva_venta.html  - New sale form
  muertes.html      - Deaths list
  nueva_muerte.html - New death form
static/
  style.css         - Custom styles
```

## Features
- Register species (name, category, description)
- Register entry lots (species, quantity, total cost, date)
- Register sales (species, quantity, unit price, date)
- Register deaths (species, quantity, date, optional note)
- Dashboard with automatic calculations:
  - Current stock per species (entries - sales - deaths)
  - Mortality percentage per species
  - Adjusted margin considering losses

## Running
The app runs on port 5000 with `python app.py`. Database is auto-created on first run.
