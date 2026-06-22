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
        ('lab_tests', 'lab_party_id', 'INTEGER'),
        ('global_parties', 'role',          "VARCHAR(20) NOT NULL DEFAULT 'other'"),
        ('global_parties', 'logo_filename', "VARCHAR(500)"),
        ('global_parties', 'notes',         "TEXT"),
        ('global_parties', 'is_seeded',     "BOOLEAN NOT NULL DEFAULT 0"),
        # ── Phase 1: multi-tenant structure ────────────────────────────────────
        # `company_id` on every tenant-scoped table — plain INTEGER (matching the
        # lab_party_id precedent). The model declares the ForeignKey + index;
        # create_all() materializes those on a fresh DB, and these ALTERs add the
        # bare column in place on a DB that predates Phase 1. The `companies`
        # table itself is NOT here — new tables are built by create_all().
        ('users',             'company_id', 'INTEGER'),
        ('projects',          'company_id', 'INTEGER'),
        ('project_members',   'company_id', 'INTEGER'),
        ('dc_letters',        'company_id', 'INTEGER'),
        ('archives',          'company_id', 'INTEGER'),
        ('submittals',        'company_id', 'INTEGER'),
        ('daily_reports',     'company_id', 'INTEGER'),
        ('lab_tests',         'company_id', 'INTEGER'),
        ('financial_data',    'company_id', 'INTEGER'),
        ('gantt_data',        'company_id', 'INTEGER'),
        ('parties',           'company_id', 'INTEGER'),
        ('subcontracts',      'company_id', 'INTEGER'),
        ('global_parties',    'company_id', 'INTEGER'),
        ('supply_agreements', 'company_id', 'INTEGER'),
        # users: TENANT role + email-verification columns (verification *logic*
        # is wired in Phase 2; the columns are built now). DEFAULT FALSE — not
        # DEFAULT 0 — so the boolean DDL is valid on PostgreSQL as well as SQLite.
        ('users', 'company_role',             "VARCHAR(20) DEFAULT 'viewer'"),
        ('users', 'email_verified',           'BOOLEAN NOT NULL DEFAULT FALSE'),
        ('users', 'email_verification_token', 'VARCHAR(255)'),
        # ── Phase 2: account-flow columns ──────────────────────────────────────
        ('users', 'pending_company_name',     'VARCHAR(200)'),
        ('users', 'invite_pending',           'BOOLEAN NOT NULL DEFAULT FALSE'),
        ('users', 'password_reset_token',     'VARCHAR(255)'),
        ('users', 'password_reset_expires',   'TIMESTAMP'),
        # ── Per-member module permissions ──────────────────────────────────────
        # JSON map {module: {view, edit}} on each membership. Column is added here
        # so existing DBs can read the new model field on boot; the one-time
        # role-based backfill lives in migrate_member_permissions.py (run once).
        ('project_members', 'permissions',     "TEXT DEFAULT '{}'"),
        # ── Phase 4: manual billing ────────────────────────────────────────────
        # companies.paid_until — end of the current paid period; set when an
        # invoice is marked paid, drives the active→grace→locked auto-downgrade.
        # uploads.size_bytes — byte size captured at upload, feeds the per-company
        # storage usage indicator. Both nullable; existing rows read as NULL/0.
        # The `payments` table itself is NOT here — new tables build via create_all().
        ('companies', 'paid_until', 'TIMESTAMP'),
        ('uploads',   'size_bytes', 'INTEGER'),
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

    # ── Phase 2: legacy-account backfill ───────────────────────────────────────
    # Login now requires email_verified=TRUE. Accounts that predate Phase 2 were
    # created with the column DEFAULT FALSE and would be locked out. Backfill them
    # to verified — but ONLY rows with no verification token, i.e. genuine legacy
    # users. A real pending self-signup/invite always carries a token, so those
    # correctly stay unverified. Idempotent: re-running re-matches nothing new.
    if 'users' in tables:
        ucols = [c['name'] for c in inspect(db.engine).get_columns('users')]
        if 'email_verified' in ucols and 'email_verification_token' in ucols:
            with db.engine.begin() as conn:
                conn.execute(text(
                    "UPDATE users SET email_verified = TRUE "
                    "WHERE email_verified = FALSE AND email_verification_token IS NULL"
                ))


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
