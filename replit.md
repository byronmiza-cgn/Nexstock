# NexStock - Control Financiero para Negocios con Inventario

## Overview
Plataforma SaaS multi-tienda para control financiero de negocios con inventario vivo (acuarios, viveros, etc.). Asistente financiero proactivo que ayuda a tomar decisiones de negocio con alertas inteligentes y calculos automaticos.

## Tech Stack
- **Backend**: Python 3.11 + Flask
- **Database**: SQLite (via Flask-SQLAlchemy)
- **Frontend**: HTML + Bootstrap 5 + Bootstrap Icons
- **ORM**: SQLAlchemy
- **Auth**: Session-based with werkzeug password hashing
- **Design**: Mobile-first, SaaS financiero minimalista

## Brand Identity
- **Name**: NexStock
- **Tagline**: "Decisiones inteligentes para negocios con inventario"
- **Color Palette**:
  - Primary: #1E3A8A (navy blue)
  - Secondary: #3B82F6 (blue)
  - Success: #16A34A (green)
  - Warning: #F59E0B (amber)
  - Danger: #DC2626 (red)
  - Background: #F3F4F6
  - Text: #111827 / #6B7280
- **Typography**: system-ui font stack
- **Visual Hierarchy**: Ganancia Neta is the hero metric (largest, colored background, own row on mobile)

## Project Structure
```
app.py                          - Main application (models, routes, auth, logic, API)
templates/
  base.html                     - Base template with navbar and auth-aware layout
  login.html                    - Login with aspirational positioning narrative
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
  style.css                     - Custom styles with NexStock palette, visual hierarchy, mobile-first
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
  - Resumen Financiero: Ganancia Neta (hero metric), Invertido, Recuperado, Valor Inventario
  - Ganancia Neta visually dominates: full-width on mobile, 50% on desktop, colored background
  - Smart suggestions (max 2): high mortality, below-cost sales, low margin
  - "Negocio saludable" message when no issues detected
  - Ganancia real (money) per species alongside margin %
  - Top 3 most profitable species
- Mobile-first design: card layout on mobile, table on desktop

## Key Business Logic

### Immutable Historical Costs
- `costo_unitario_momento` is stored on every Venta and Muerte at registration time
- This captures the adjusted cost/unit at the exact moment of the transaction
- All historical financial calculations (ganancia, margen, balance) use this stored value
- New lotes do NOT change historical profits — only future transactions reflect updated costs
- On app startup, a backfill runs for any NULL records using per-date historical reconstruction
- Fallback to current cost exists only as temporary protection; after backfill no NULLs remain

### Formulas
- Stock = total entered - total sold - total dead
- Mortality % = (total dead / total entered) * 100
- Adjusted cost/unit (current) = total cost / (total entered - total dead)
- Min recommended price = adjusted cost * 1.20
- Costo de vendidos = sum of (venta.cantidad * venta.costo_unitario_momento) per venta
- Costo de muertos = sum of (muerte.cantidad * muerte.costo_unitario_momento) per muerte
- Ganancia real per species = ingreso_ventas - costo_de_vendidos - costo_de_muertos
- Adjusted margin = (ingreso_ventas - costo_de_vendidos) / costo_de_vendidos * 100
- **Valor Inventario** = stock * costo_unitario_ajustado (uses LIVE cost for current valuation)

### Balance por Periodo
- Total Invertido = sum of lote.costo_total in date range
- Total Recuperado = sum of venta revenue in date range
- Costo Vendido = sum of (venta.costo_unitario_momento * cantidad) per venta in range
- Costo Muertes = sum of (muerte.costo_unitario_momento * cantidad) per muerte in range
- Ganancia Neta = Recuperado - Costo Vendido - Costo Muertes

### Smart Alerts (max 2)
- Mortality >25%
- Negative margin (sales below cost)
- Average margin <10%

## Database Migration
- `migrate_add_costo_momento()` runs on startup to add columns if missing (SQLite ALTER TABLE)
- Backfill runs after migration for any NULL costo_unitario_momento records
- Both are idempotent and safe to run multiple times

## API Endpoints
- GET /api/especie/<id>/stats - Returns species financial stats (JSON)

## Running
The app runs on port 5000 with `python app.py`. Database is auto-created on first run.
