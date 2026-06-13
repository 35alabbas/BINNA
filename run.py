#!/usr/bin/env python3
"""
BINNA — Construction PM
Usage:  python run.py
"""
import os
import sys

# Ensure UTF-8 I/O on Windows (no-op on other platforms)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

from sqlalchemy import inspect, text

from app import create_app, db

app = create_app(os.environ.get('FLASK_ENV', 'development'))


def _ensure_schema():
    """Lightweight, non-destructive auto-migration.

    db.create_all() only creates missing *tables* — it never adds a new *column*
    to a table that already exists. When a model gains a column, every SELECT
    SQLAlchemy emits will reference it and fail on a DB that predates it (the
    existing rows are still there, just unreadable). This adds any such missing
    columns in place via ALTER TABLE — no data is dropped. Idempotent: each
    column is checked before being added, so it is safe to run on every boot.
    """
    insp = inspect(db.engine)
    tables = insp.get_table_names()
    # (table, column, DDL type/default) — extend this list when models gain columns.
    additions = [
        ('gantt_data', 'stoppages', "TEXT DEFAULT '[]'"),
        ('global_parties', 'role',          "VARCHAR(20) NOT NULL DEFAULT 'other'"),
        ('global_parties', 'logo_filename', "VARCHAR(500)"),
        ('global_parties', 'notes',         "TEXT"),
        ('global_parties', 'is_seeded',     "BOOLEAN NOT NULL DEFAULT 0"),
    ]
    for table, column, ddl in additions:
        if table not in tables:
            continue  # create_all() will build the whole table fresh
        existing = [c['name'] for c in insp.get_columns(table)]
        if column in existing:
            continue
        with db.engine.begin() as conn:
            conn.execute(text('ALTER TABLE {} ADD COLUMN {} {}'.format(table, column, ddl)))

    # Pre-Phase-1 `global_parties` tables carry a NOT NULL `type` column (now
    # `role`) and a `logo` column (now `logo_filename`). Fold their data into
    # the new columns, then drop them — otherwise every insert from the current
    # model (which never sets `type`) violates that NOT NULL constraint and
    # rolls back project creation entirely.
    if 'global_parties' in tables:
        legacy_cols = [c['name'] for c in inspect(db.engine).get_columns('global_parties')]
        if 'type' in legacy_cols:
            with db.engine.begin() as conn:
                conn.execute(text(
                    "UPDATE global_parties SET role = type WHERE type IS NOT NULL AND type <> ''"
                ))
                conn.execute(text(
                    "UPDATE global_parties SET is_seeded = 1 "
                    "WHERE role IN ('client', 'consultant', 'contractor')"
                ))
                if 'logo' in legacy_cols:
                    conn.execute(text(
                        "UPDATE global_parties SET logo_filename = logo "
                        "WHERE logo_filename IS NULL AND logo IS NOT NULL"
                    ))
                conn.execute(text('ALTER TABLE global_parties DROP COLUMN type'))
                if 'logo' in legacy_cols:
                    conn.execute(text('ALTER TABLE global_parties DROP COLUMN logo'))


# Create tables on startup — runs for both gunicorn and direct python run.py
with app.app_context():
    db.create_all()
    _ensure_schema()


@app.cli.command('init-db')
def init_db():
    """Create all database tables."""
    db.create_all()
    _ensure_schema()
    print('[OK] Database tables created.')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print('-' * 50)
    print('  BINNA Construction PM')
    print(f'  http://localhost:{port}')
    print('-' * 50)
    app.run(debug=True, host='0.0.0.0', port=port)
