#!/usr/bin/env python3
"""
Phase 1 verification — boot the app against the configured database and confirm
the multi-tenant schema is present. Writes NO data.

Run it with DATABASE_URL pointing at binna-db's EXTERNAL url to confirm the app
boots against PostgreSQL:

    $env:DATABASE_URL = 'postgresql://binna_db_user:<pw>@<EXTERNAL-host>/<db>?sslmode=require'
    python verify_phase1.py

Importing run.py boots the app (create_all() + _ensure_schema()) against that
DB. On a fresh Postgres this CREATES the empty Phase-1 tables there (idempotent,
no rows) — which is the production schema we want anyway. The URL is never
printed.
"""
import os
import sys

if not os.environ.get('DATABASE_URL'):
    sys.exit('ABORT: DATABASE_URL is not set. Set it to binna-db EXTERNAL url '
             '(…?sslmode=require) to boot against PostgreSQL.')

import run  # boots: create_all() + _ensure_schema() against DATABASE_URL
from app import db
from sqlalchemy import inspect

DATA_TABLES = [
    'users', 'projects', 'project_members', 'dc_letters', 'archives',
    'submittals', 'daily_reports', 'lab_tests', 'financial_data', 'gantt_data',
    'parties', 'subcontracts', 'global_parties', 'supply_agreements',
]
USER_NEW_COLS = ['company_id', 'company_role', 'email_verified', 'email_verification_token']

with run.app.app_context():
    dialect = db.engine.dialect.name
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    print('Booted OK. dialect:', dialect, '| tables:', len(tables))

    ok = True

    if 'companies' not in tables:
        ok = False
        print('  FAIL: companies table missing')
    else:
        cols = [c['name'] for c in insp.get_columns('companies')]
        need = ['id', 'name', 'slug', 'plan', 'max_users', 'trial_ends_at',
                'grace_ends_at', 'status', 'created_at']
        missing = [c for c in need if c not in cols]
        print('  companies columns:', 'all present' if not missing else 'MISSING ' + str(missing))
        ok = ok and not missing

    missing_cid = [t for t in DATA_TABLES
                   if t in tables and 'company_id' not in [c['name'] for c in insp.get_columns(t)]]
    print('  company_id on all data tables:', 'YES' if not missing_cid else 'MISSING on ' + str(missing_cid))
    ok = ok and not missing_cid

    ucols = [c['name'] for c in insp.get_columns('users')] if 'users' in tables else []
    missing_u = [c for c in USER_NEW_COLS if c not in ucols]
    print('  users new columns:', 'all present' if not missing_u else 'MISSING ' + str(missing_u))
    print('  users.role (platform admin|user) preserved:', 'role' in ucols)
    ok = ok and not missing_u and 'role' in ucols

    print('\nRESULT:', 'PASS — Phase 1 schema present on ' + dialect if ok else 'FAIL')
