#!/usr/bin/env python3
"""
Reset the password of a Postgres role (kills the old/leaked password).

Connects with a CURRENTLY-WORKING credential and runs
    ALTER ROLE <user> WITH PASSWORD <new>;
which changes the role's password at the Postgres level — the old password
stops authenticating immediately for any NEW connection.

All secrets come from env vars in YOUR terminal; none are printed.
    DB_USER              role to alter (default: binna_db_user)
    CURRENT_DB_PASSWORD  a password that works RIGHT NOW (used only to log in)
    NEW_DB_PASSWORD      the new password to set
    DB_EXTERNAL_HOST     dpg-xxxx-a.<region>-postgres.render.com
    DB_NAME              binna_xxxx

Usage:  python reset_password.py
"""
import os
import sys
import urllib.parse

try:
    import psycopg
    from psycopg import sql
except ImportError:
    sys.exit('ABORT: psycopg (psycopg3) is not installed.')

user = os.environ.get('DB_USER', 'binna_db_user')
cur_pw = os.environ.get('CURRENT_DB_PASSWORD')
new_pw = os.environ.get('NEW_DB_PASSWORD')
host = os.environ.get('DB_EXTERNAL_HOST')
db = os.environ.get('DB_NAME')

missing = [k for k, v in [('CURRENT_DB_PASSWORD', cur_pw), ('NEW_DB_PASSWORD', new_pw),
                          ('DB_EXTERNAL_HOST', host), ('DB_NAME', db)] if not v]
if missing:
    sys.exit('ABORT: set these env vars first: ' + ', '.join(missing))

if new_pw == cur_pw:
    sys.exit('ABORT: NEW_DB_PASSWORD is identical to CURRENT_DB_PASSWORD — pick a new one.')

login_url = 'postgresql://{u}:{p}@{h}/{d}?sslmode=require'.format(
    u=user, p=urllib.parse.quote(cur_pw, safe=''), h=host, d=db)

print('Connecting as "%s" to reset its password...' % user)
try:
    with psycopg.connect(login_url, autocommit=True, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT current_user')
            who = cur.fetchone()[0]
            # ALTER ROLE cannot bind the password as a parameter; sql.Literal
            # safely quotes/escapes it. sql.Identifier safely quotes the role.
            cur.execute(sql.SQL('ALTER ROLE {} WITH PASSWORD {}').format(
                sql.Identifier(user), sql.Literal(new_pw)))
    print('  logged in as   :', who)
    print('  RESULT: PASSWORD RESET for role "%s".' % user)
    print('  Next: verify the NEW password works and the OLD one now FAILS,')
    print('        using check_credential.py — BEFORE touching DATABASE_URL.')
except psycopg.OperationalError as e:
    sys.exit('FAIL: could not connect with CURRENT_DB_PASSWORD.\n  %s: %s'
             % (type(e).__name__, str(e).splitlines()[0] if str(e) else ''))
except Exception as e:
    sys.exit('FAIL: %s: %s' % (type(e).__name__, str(e).splitlines()[0] if str(e) else ''))
