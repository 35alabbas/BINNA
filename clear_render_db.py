#!/usr/bin/env python3
"""
Phase 0 — Render PRODUCTION clear (dummy data only).

Empties all 14 BINNA tables and resets identity sequences on the production
PostgreSQL database WITHOUT dropping or recreating the schema, using a single
TRUNCATE ... RESTART IDENTITY CASCADE.

Robustness (rewrite — the previous version self-deadlocked):
- NO Flask, NO app-context, NO db.create_all(). Exactly ONE psycopg connection
  does everything, so there is no second idle-in-transaction connection holding
  ACCESS SHARE locks while TRUNCATE waits for ACCESS EXCLUSIVE.
- autocommit=True, so each statement commits immediately (no lingering locks).
- SET statement_timeout = '30s' so a stuck TRUNCATE aborts instead of hanging.
- Terminates every other backend on this database first, so no other session
  can hold a conflicting lock.

Safety:
- Reads the connection string from os.environ['DATABASE_URL]. NEVER printed.
- Only table names, row counts, and status lines are emitted.

Usage:  python clear_render_db.py
"""
import os
import sys

try:
    import psycopg
except ImportError:
    sys.exit('ABORT: psycopg (psycopg3) is not installed in this environment.')

raw = os.environ.get('DATABASE_URL')
if not raw:
    sys.exit('ABORT: DATABASE_URL is not set in this environment.')

# Normalize to a conninfo string psycopg understands (strip SQLAlchemy's
# "+psycopg" dialect suffix; leave postgresql:// as-is).
url = raw.replace('postgresql+psycopg://', 'postgresql://')
url = url.replace('postgres://', 'postgresql://', 1)

TABLES = [
    'archives', 'daily_reports', 'dc_letters', 'financial_data', 'gantt_data',
    'global_parties', 'lab_tests', 'parties', 'project_members', 'projects',
    'subcontracts', 'submittals', 'supply_agreements', 'users',
]

# Single connection, autocommit — no wrapping transaction to hold locks.
with psycopg.connect(url, autocommit=True, connect_timeout=10) as conn:
    with conn.cursor() as cur:
        # 1) Bound every statement so nothing can hang indefinitely.
        cur.execute("SET statement_timeout = '30s'")
        cur.execute("SET lock_timeout = '15s'")

        # 2) Terminate every OTHER backend on this database (suspended web
        #    service, restarted-DB ghosts, the previous hung run) so none of
        #    them can hold a conflicting lock against the TRUNCATE.
        cur.execute(
            "SELECT pg_terminate_backend(pid) "
            "FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid()"
        )
        killed = sum(1 for (ok,) in cur.fetchall() if ok)
        print('Terminated %d other backend(s) on this database.' % killed)

        # BEFORE snapshot (autocommit → each SELECT releases its lock at once).
        print('\nBEFORE:')
        total_before = 0
        for t in TABLES:
            cur.execute('SELECT COUNT(*) FROM "%s"' % t)
            n = cur.fetchone()[0]
            total_before += n
            print('%8d  %s' % (n, t))
        print('TOTAL ROWS BEFORE: %d' % total_before)

        # 3) One TRUNCATE for all 14 tables — RESTART IDENTITY resets sequences,
        #    CASCADE follows FKs so order doesn't matter.
        print('\nTruncating all 14 tables (RESTART IDENTITY CASCADE)...')
        cur.execute(
            'TRUNCATE archives, daily_reports, dc_letters, financial_data, '
            'gantt_data, global_parties, lab_tests, parties, project_members, '
            'projects, subcontracts, submittals, supply_agreements, users '
            'RESTART IDENTITY CASCADE'
        )
        print('TRUNCATE complete.')

        # 4) AFTER counts.
        print('\nAFTER:')
        total_after = 0
        for t in TABLES:
            cur.execute('SELECT COUNT(*) FROM "%s"' % t)
            n = cur.fetchone()[0]
            total_after += n
            print('%8d  %s' % (n, t))
        print('TOTAL ROWS AFTER: %d' % total_after)

        print('\nRESULT:', 'PASS — production database is clean'
              if total_after == 0 else 'FAIL — rows remain')

print('\nConnection closed cleanly.')
