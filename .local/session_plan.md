# Objective
Add edit and delete functionality for all record types (Ventas, Lotes, Muertes, Especies) so users can correct data entry mistakes. Each list table gets action buttons (edit/delete) per row. Delete requires a confirmation modal. Edit opens a pre-filled form. Stock validation prevents inconsistent states (e.g., can't delete a lot if its units were already sold). Immutable `costo_unitario_momento` is preserved on venta/muerte edits. Follows existing NexStock design language.

# Tasks

### T001: Add delete routes with stock validation
- **Blocked By**: []
- **Details**:
  - Add POST routes: `/ventas/<id>/eliminar`, `/lotes/<id>/eliminar`, `/muertes/<id>/eliminar`, `/especies/<id>/eliminar`
  - Each route verifies the record belongs to the current user (via especie.usuario_id)
  - **Lote delete**: check that removing the lot's quantity wouldn't make stock negative for that especie (stock = sum(lotes.cantidad) - sum(ventas.cantidad) - sum(muertes.cantidad)). If removing the lot would cause negative stock, flash error and deny
  - **Especie delete**: only allowed if species has zero lotes, ventas, and muertes. Otherwise flash error explaining why
  - **Venta delete**: always safe (frees stock). Delete and redirect to `/ventas`
  - **Muerte delete**: always safe (frees stock). Delete and redirect to `/muertes`
  - Flash confirmation message on success (e.g., "Venta eliminada.")
  - Files: `app.py`
  - Acceptance: All 4 delete routes work, stock validation prevents inconsistent data, proper flash messages

### T002: Add edit routes with pre-filled forms
- **Blocked By**: []
- **Details**:
  - Add GET/POST routes: `/ventas/<id>/editar`, `/lotes/<id>/editar`, `/muertes/<id>/editar`, `/especies/<id>/editar`
  - GET renders the same creation form template but in edit mode (pre-filled with current values, submit button says "Guardar Cambios")
  - POST validates and saves changes
  - **Venta edit**: can change cantidad, precio_unidad, fecha. Validate new cantidad against available stock (current stock + original venta cantidad = available). Do NOT change costo_unitario_momento (immutable)
  - **Lote edit**: can change cantidad, costo_total, fecha. Validate that reducing cantidad wouldn't make stock negative
  - **Muerte edit**: can change cantidad, fecha, nota. Validate new cantidad against available stock (current stock + original muerte cantidad = available). Do NOT change costo_unitario_momento (immutable)
  - **Especie edit**: can change nombre, categoria, descripcion. Validate unique name (excluding self)
  - Templates receive an `editando` object when in edit mode; forms use its values for pre-fill
  - Files: `app.py`, `templates/nueva_venta.html`, `templates/nuevo_lote.html`, `templates/nueva_muerte.html`, `templates/nueva_especie.html`
  - Acceptance: All 4 edit forms load with current data, save changes correctly, validate properly

### T003: Add action buttons to list tables + delete confirmation modal
- **Blocked By**: []
- **Details**:
  - Add "Acciones" column to each list table (especies, lotes, ventas, muertes)
  - Each row gets an edit icon-button (bi-pencil) linking to the edit route and a delete icon-button (bi-trash) that triggers a confirmation modal
  - Add a single reusable Bootstrap modal per list page: "Estas seguro de eliminar este registro?" with Cancel and Eliminar (red) buttons
  - Delete button in modal submits a hidden POST form to the delete route (set via JS on click)
  - Small icon buttons styled subtly (btn-outline-secondary btn-sm for edit, btn-outline-danger btn-sm for delete)
  - Files: `templates/ventas.html`, `templates/lotes.html`, `templates/muertes.html`, `templates/especies.html`
  - Acceptance: All list pages show edit/delete buttons per row, modal confirmation works, delete executes correctly

### T004: Update replit.md documentation
- **Blocked By**: [T001, T002, T003]
- **Details**:
  - Add edit/delete functionality to Features section
  - Document stock validation rules for deletions and edits
  - Note that costo_unitario_momento is never changed on edits (immutable historical cost)
  - Files: `replit.md`
  - Acceptance: Documentation reflects new edit/delete capabilities and validation rules
