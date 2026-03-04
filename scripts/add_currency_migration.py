#!/usr/bin/env python3
"""
Small migration script to add a `currency` column to the `usuario` table and backfill values.
Run from the project root with the same python environment used for the app:

    python scripts/add_currency_migration.py

This script imports the `app` and `db` from the application and runs inside the app context.
"""
from app import app, db
from sqlalchemy import inspect, text

def main():
    with app.app_context():
        inspector = inspect(db.engine)
        if 'usuario' not in inspector.get_table_names():
            print('Table `usuario` not found in the database. Nothing to do.')
            return

        cols = [c['name'] for c in inspector.get_columns('usuario')]
        if 'currency' in cols:
            print('Column `currency` already exists. Backfilling null/empty values...')
        else:
            try:
                # Try to add the column without constraints for maximum compatibility across sqlite versions
                db.session.execute(text("ALTER TABLE usuario ADD COLUMN currency VARCHAR(3)"))
                db.session.commit()
                print('Added column `currency` to `usuario`.')
            except Exception as e:
                db.session.rollback()
                print('Failed to add column `currency` via ALTER TABLE:', e)
                print('If ALTER TABLE is not supported in your SQLite version you may need to migrate the table manually.')

        # Backfill existing rows (set GTQ by default for any NULL/empty)
        try:
            db.session.execute(text("UPDATE usuario SET currency = 'GTQ' WHERE currency IS NULL OR currency = ''"))
            db.session.commit()
            print('Backfilled existing rows to currency=GTQ where needed.')
        except Exception as e:
            db.session.rollback()
            print('Failed to backfill currency values:', e)

        # Quick sanity: show counts per currency
        try:
            res = db.session.execute(text("SELECT currency, COUNT(*) as cnt FROM usuario GROUP BY currency"))
            print('Counts by currency:')
            # SQLAlchemy Core returns Row objects that support both index and key access
            for row in res:
                try:
                    # Try name-based access first, fall back to positional
                    currency = row['currency']
                    cnt = row['cnt']
                except Exception:
                    currency = row[0]
                    cnt = row[1]
                print(f"  {currency}: {cnt}")
        except Exception as e:
            print('Failed to query counts:', e)

if __name__ == '__main__':
    main()
