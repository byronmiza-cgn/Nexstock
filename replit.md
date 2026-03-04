# AquaStock - Control de Inventario para Acuarios

## Overview
Aplicacion web multi-tienda para acuarios con asistente financiero proactivo. Controla inventario de animales vivos (peces, corales, invertebrados, plantas) y ayuda a tomar decisiones de negocio con alertas y calculos automaticos.

## Tech Stack
- **Backend**: Python 3.11 + Flask
- **Database**: SQLite (via Flask-SQLAlchemy)
- **Frontend**: HTML + Bootstrap 5 + Bootstrap Icons
- **ORM**: SQLAlchemy
- **Auth**: Session-based with werkzeug password hashing

## Project Structure
```
app.py                          - Main application (models, routes, auth, logic, API)
templates/
  base.html                     - Base template with navbar and auth-aware layout
  login.html                    - Login form
  registro.html                 - Registration form
  dashboard.html                - Dashboard with alerts, top 3, stats (mobile-first)
  especies.html                 - Species list
  nueva_especie.html            - New species form
  _especies_dropdown.html       - Shared species dropdown with search and smart ordering
  lotes.html                    - Entry lots list
  nuevo_lote.html               - New lot form
  ventas.html                   - Sales list
  nueva_venta.html              - Sale form with live financial assistant
  muertes.html                  - Deaths list
  nueva_muerte.html             - New death form
static/
  style.css                     - Custom styles with mobile-first responsive design
```

## Features
- Multi-tenant: each store registers and sees only their own data
- User registration and login with password hashing
- Register species with smart dropdown (most-used first, with search)
- Register entry lots, sales (with stock validation), deaths
- **Proactive financial assistant on sale form:**
  - Shows cost per unit, stock, and min recommended price (20% margin)
  - Live margin/unit, margin %, and total profit calculation
  - Red alert when selling below cost
- **Dashboard alerts:**
  - High mortality warning (>25%)
  - Negative margin warning
  - Top 3 most profitable species
- Mobile-first design: card layout on mobile, table on desktop

## Key Business Logic
- Stock = total entered - total sold - total dead (never negative)
- Mortality % = (total dead / total entered) * 100
- Adjusted cost/unit = total cost / (total entered - total dead)
- Min recommended price = adjusted cost * 1.20
- Adjusted margin = (sales revenue - (adjusted cost * sold)) / (adjusted cost * sold) * 100

## API Endpoints
- GET /api/especie/<id>/stats - Returns species financial stats (JSON)

## Running
The app runs on port 5000 with `python app.py`. Database is auto-created on first run.
