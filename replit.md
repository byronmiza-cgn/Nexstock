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
  dashboard.html                - Financial dashboard with period filter, balance, suggestions
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
- **Financial Dashboard:**
  - Period filter: Hoy / Semana / Mes / Personalizado (custom date range)
  - Resumen Financiero: Invertido, Recuperado, Ganancia Neta, Valor Inventario
  - Smart suggestions (max 2): high mortality, below-cost sales, low margin
  - "Negocio saludable" message when no issues detected
  - Ganancia real (money) per species alongside margin %
  - Top 3 most profitable species
- Mobile-first design: card layout on mobile, table on desktop

## Key Business Logic
- Stock = total entered - total sold - total dead (never negative)
- Mortality % = (total dead / total entered) * 100
- Adjusted cost/unit = total cost / (total entered - total dead)
- Min recommended price = adjusted cost * 1.20
- Adjusted margin = (sales revenue - (adjusted cost * sold)) / (adjusted cost * sold) * 100
- **Ganancia real per species** = ingreso_ventas - (costo_unitario_ajustado * total_vendido) - (costo_unitario_ajustado * total_muerto)
- **Balance periodo:**
  - Total Invertido = sum of lote.costo_total in date range
  - Total Recuperado = sum of venta revenue in date range
  - Costo Vendido = sum of (costo_unitario_ajustado * cantidad vendida) per species in range
  - Costo Muertes = sum of (costo_unitario_ajustado * cantidad muerta) per species in range
  - Ganancia Neta = Recuperado - Costo Vendido - Costo Muertes
- **Valor Inventario** = sum of (stock * costo_unitario_ajustado) per species (always calculated, no period filter)
- **Smart alerts (max 2):** mortality >25%, negative margin sales, average margin <10%

## API Endpoints
- GET /api/especie/<id>/stats - Returns species financial stats (JSON)

## Running
The app runs on port 5000 with `python app.py`. Database is auto-created on first run.
