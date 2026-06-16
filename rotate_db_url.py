#!/usr/bin/env python3
"""
Phase 0 DB credential rotation helper — binna_db_user -> binna_users.

Verifies the NEW credential actually connects BEFORE you swap it onto the live
web service, then emits the Internal Database URL to paste into Render.

Why two hosts:
- Render's INTERNAL host (e.g. dpg-xxxx-a) only resolves inside Render's
  network — it cannot be tested from a laptop. So we VERIFY the credential
  against the EXTERNAL host (public, needs sslmode=require), then BUILD the
  INTERNAL url (no ssl) for the web service to use.

Secrets:
- The new password is read from the env var NEW_DB_PASSWORD (set it in YOUR
  terminal, e.g.  $env:NEW_DB_PASSWORD = '...').  It is NEVER printed.
- The final URL contains the password, so it is printed ONLY to your local
  terminal under a clear banner. Do NOT paste that line back into chat — paste
  back only the 'current_user / current_database / server' confirmation lines.

Set these env vars first (host/db values are NOT secret — copy from Render's
database "Connections" panel):
    NEW_DB_PASSWORD   the binna_users password
    DB_EXTERNAL_HOST  e.g. dpg-xxxxxxxxxxxx-a.oregon-postgres.render.com
    DB_INTERNAL_HOST  e.g. dpg-xxxxxxxxxxxx-a
    DB_NAME           e.g. binna_xxxx
    DB_USER           optional, defaults to binna_users

Usage:  python rotate_db_url.py
"""
import os
import sys
import urllib.parse

try:
    import psycopg
except ImportError:
    sys.exit('ABORT: psycopg (psycopg3) is not installed in this environment.')

user = os.environ.get('DB_USER', 'binna_users')
pw = os.environ.get('NEW_DB_PASSWORD')
ext_host = os.environ.get('DB_EXTERNAL_HOST')
int_host = os.environ.get('DB_INTERNAL_HOST')
dbname = os.environ.get('DB_NAME')

missing = [k for k, v in [
    ('NEW_DB_PASSWORD', pw), ('DB_EXTERNAL_HOST', ext_host),
    ('DB_INTERNAL_HOST', int_host), ('DB_NAME', dbname),
] if not v]
if missing:
    sys.exit('ABORT: set these env vars first: ' + ', '.join(missing))

enc_pw = urllib.parse.quote(pw, safe='')

# Build both URLs. External for verifying from here; Internal for Render.
external_url = 'postgresql://{u}:{p}@{h}/{d}?sslmode=require'.format(
    u=user, p=enc_pw, h=ext_host, d=dbname)
internal_url = 'postgresql://{u}:{p}@{h}/{d}'.format(
    u=user, p=enc_pw, h=int_host, d=dbname)

# --- Verify the NEW credential actually works (against the external host) ---
print('Verifying the new credential against the external host...')
try:
    with psycopg.connect(external_url, autocommit=True, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT current_user, current_database(), version()')
            cu, cdb, ver = cur.fetchone()
except Exception as e:
    # Print the error type/message but NOT the URL/password.
    sys.exit('FAIL: could not connect as the new credential.\n  %s: %s'
             % (type(e).__name__, str(e).splitlines()[0] if str(e) else ''))

print('\nCONNECTION OK (safe to paste these lines back):')
print('  current_user     :', cu)
print('  current_database :', cdb)
print('  server           :', ver.split(' on ')[0])
if cu != user:
    print('  WARNING: connected as "%s", expected "%s".' % (cu, user))
    print('  RESULT: FAIL — wrong user. Do NOT swap the live service.')
    sys.exit(1)
print('  CONFIRMED: authenticating as "%s".' % user)

print('\nRESULT: PASS — new credential is valid.')
print('\n' + '=' * 70)
print('NEW INTERNAL DATABASE URL  (SECRET — paste into Render DATABASE_URL,')
print('do NOT paste this line into chat):')
print('=' * 70)
print(internal_url)
print('=' * 70)
