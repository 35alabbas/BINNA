#!/usr/bin/env python3
"""
Check whether a given user+password still authenticates against the DB.

Use it to answer the only question that matters for rotation:
"Does the OLD exposed password still work?"
  - AUTH FAILED  -> the old secret is dead. Rotation worked.
  - AUTH OK      -> the old secret is still live. Rotation did nothing yet.

Reads everything from env (nothing secret in chat). Connects via the EXTERNAL
host (the internal host won't resolve from a laptop) with sslmode=require.

Set, then run:
    $env:DB_USER          = 'binna_db_user'      # the role to test
    $env:DB_PASSWORD      = '<password to test>' # e.g. the OLD password
    $env:DB_EXTERNAL_HOST = 'dpg-xxxx-a.<region>-postgres.render.com'
    $env:DB_NAME          = 'binna_xxxx'
    python check_credential.py

Prints only: AUTH OK/FAILED, current_user, current_database. Never the password.
"""
import os
import sys
import urllib.parse

try:
    import psycopg
except ImportError:
    sys.exit('ABORT: psycopg (psycopg3) is not installed.')

user = os.environ.get('DB_USER')
pw = os.environ.get('DB_PASSWORD')
host = os.environ.get('DB_EXTERNAL_HOST')
db = os.environ.get('DB_NAME')

missing = [k for k, v in [('DB_USER', user), ('DB_PASSWORD', pw),
                          ('DB_EXTERNAL_HOST', host), ('DB_NAME', db)] if not v]
if missing:
    sys.exit('ABORT: set these env vars first: ' + ', '.join(missing))

url = 'postgresql://{u}:{p}@{h}/{d}?sslmode=require'.format(
    u=user, p=urllib.parse.quote(pw, safe=''), h=host, d=db)

print('Testing login for role "%s"...' % user)
try:
    with psycopg.connect(url, autocommit=True, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT current_user, current_database()')
            cu, cdb = cur.fetchone()
    print('  RESULT: AUTH OK  (this password STILL WORKS)')
    print('  current_user     :', cu)
    print('  current_database :', cdb)
except psycopg.OperationalError as e:
    msg = (str(e).splitlines()[0] if str(e) else '').lower()
    if 'password authentication failed' in msg or 'authentication' in msg:
        print('  RESULT: AUTH FAILED  (password rejected — this secret is DEAD)')
    else:
        print('  RESULT: connection error (NOT an auth result):')
        print('  %s: %s' % (type(e).__name__, str(e).splitlines()[0]))
except Exception as e:
    print('  RESULT: unexpected error:')
    print('  %s: %s' % (type(e).__name__, str(e).splitlines()[0] if str(e) else ''))
