# AquaStock - Control de Inventario para Acuarios

## Overview
Aplicacion web multi-tienda para acuarios que permite controlar el inventario de animales vivos (peces, corales, invertebrados, plantas). Cada tienda tiene su propia cuenta con datos aislados.

## Tech Stack
- **Backend**: Python 3.11 + Flask
- **Database**: SQLite (via Flask-SQLAlchemy)
- **Frontend**: HTML + Bootstrap 5 + Bootstrap Icons
- **ORM**: SQLAlchemy
- **Auth**: Session-based with werkzeug password hashing

## Project Structure
```
app.py                          - Main application (models, routes, auth, logic)
templates/
  base.html                     - Base template with navbar and auth-aware layout
  login.html                    - Login form
  registro.html                 - Registration form
  dashboard.html                - Main dashboard with stats per species
  especies.html                 - Species list
  nueva_especie.html            - New species form
  _especies_dropdown.html       - Shared species dropdown with search and smart ordering
  lotes.html                    - Entry lots list
  nuevo_lote.html               - New lot form
  ventas.html                   - Sales list
  nueva_venta.html              - New sale form
  muertes.html                  - Deaths list
  nueva_muerte.html             - New death form
static/
  style.css                     - Custom styles
```

## Features
- Multi-tenant: each store registers and sees only their own data
- User registration and login with password hashing
- Register species (name, category, description) per store
- Smart species dropdown: most-used species shown first, with search filter
- usage_count field tracks how often each species is used in transactions
- Register entry lots (species, quantity, total cost, date)
- Register sales (species, quantity, unit price, date) with stock validation
- Register deaths (species, quantity, date, optional note) with stock validation
- Dashboard with automatic calculations:
  - Current stock per species (entries - sales - deaths)
  - Mortality percentage per species (deaths / total entered)
  - Adjusted cost per unit (total cost / surviving units)
  - Adjusted margin considering mortality losses

## Key Business Logic
- Stock = total entered - total sold - total dead (never goes negative due to validation)
- Mortality % = (total dead / total entered) * 100
- Adjusted cost/unit = total cost / (total entered - total dead)
- Adjusted margin = (sales revenue - (adjusted cost * sold)) / (adjusted cost * sold) * 100
- All data queries are filtered by the logged-in user's ID
- Species usage_count incremented on each lot, sale, or death registration

## Running
The app runs on port 5000 with `python app.py`. Database is auto-created on first run.
