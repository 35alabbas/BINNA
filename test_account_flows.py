#!/usr/bin/env python3
"""Phase 2 — invite + password-reset flow check (offline, throwaway DB)."""
import os, sys, tempfile

_TMP = os.path.join(tempfile.gettempdir(), 'binna_flows_test.db')
if os.path.exists(_TMP):
    os.remove(_TMP)
os.environ['DATABASE_URL'] = 'sqlite:///' + _TMP
os.environ.pop('RESEND_API_KEY', None)
os.environ['APP_BASE_URL'] = 'http://localhost:5000'

from app import create_app, db
from app.models import User

app = create_app('development')
import run
with app.app_context():
    db.create_all(); run._ensure_schema()
c = app.test_client()
P = F = 0
def ck(n, cond):
    global P, F
    P += cond; F += (not cond)
    print(('  ok   ' if cond else '  FAIL ') + n)

def verify_owner(username, email, pw, comp):
    c.post('/api/v1/auth/register', json={'username':username,'email':email,'password':pw,'company_name':comp})
    with app.app_context():
        t = User.query.filter_by(email=email).first().email_verification_token
    c.get(f'/api/v1/auth/verify/{t}')
    r = c.post('/api/v1/auth/login', json={'email':email,'password':pw})
    return {'Authorization': 'Bearer ' + r.get_json()['access_token']}

print('── INVITE FLOW ──')
owner = verify_owner('boss', 'boss@acme.test', 'password1', 'Acme')
inv = c.post('/api/v1/company/invite', json={'email':'staff@acme.test','company_role':'member'}, headers=owner)
ck('owner can invite (201)', inv.status_code == 201)
with app.app_context():
    invitee = User.query.filter_by(email='staff@acme.test').first()
    ck('invitee created in owner company', invitee.company_id is not None)
    ck('invitee is pending + unverified', invitee.invite_pending and not invitee.email_verified)
    itok = invitee.email_verification_token
# Invited member cannot log in until they accept (no password yet)
acc = c.post('/api/v1/company/accept-invite', json={'token':itok,'password':'staffpass'})
ck('accept-invite succeeds (200)', acc.status_code == 200)
ck('accept-invite returns a token', bool(acc.get_json().get('access_token')))
with app.app_context():
    invitee = User.query.filter_by(email='staff@acme.test').first()
    ck('invitee now verified + not pending', invitee.email_verified and not invitee.invite_pending)
    ck('invitee role is member', invitee.company_role == 'member')
# Invited member now appears in the company directory, scoped to same company
mem = c.post('/api/v1/auth/login', json={'email':'staff@acme.test','password':'staffpass'})
ck('invited member can now log in (200)', mem.status_code == 200)

print('\n── NON-PRIVILEGED INVITE IS BLOCKED ──')
mem_hdr = {'Authorization': 'Bearer ' + mem.get_json()['access_token']}
blocked = c.post('/api/v1/company/invite', json={'email':'x@acme.test','company_role':'member'}, headers=mem_hdr)
ck('member (viewer-level) cannot invite (403)', blocked.status_code == 403)

print('\n── PASSWORD RESET FLOW ──')
fp = c.post('/api/v1/auth/forgot-password', json={'email':'boss@acme.test'})
ck('forgot-password returns generic 200', fp.status_code == 200)
with app.app_context():
    rtok = User.query.filter_by(email='boss@acme.test').first().password_reset_token
    ck('reset token issued', bool(rtok))
rp = c.post('/api/v1/auth/reset-password', json={'token':rtok,'new_password':'newpass99'})
ck('reset-password succeeds (200)', rp.status_code == 200)
old = c.post('/api/v1/auth/login', json={'email':'boss@acme.test','password':'password1'})
ck('old password rejected (401)', old.status_code == 401)
new = c.post('/api/v1/auth/login', json={'email':'boss@acme.test','password':'newpass99'})
ck('new password works (200)', new.status_code == 200)
# Unknown email still returns generic success (no enumeration)
fp2 = c.post('/api/v1/auth/forgot-password', json={'email':'nobody@nowhere.test'})
ck('unknown email → generic 200 (no enumeration)', fp2.status_code == 200)

print('\n── UNVERIFIED LOGIN IS BLOCKED ──')
c.post('/api/v1/auth/register', json={'username':'pending','email':'pending@acme.test','password':'pendpass','company_name':'Pend'})
pl = c.post('/api/v1/auth/login', json={'email':'pending@acme.test','password':'pendpass'})
ck('unverified user cannot log in (403)', pl.status_code == 403)

print(f'\nRESULT: {P} passed, {F} failed')
sys.exit(1 if F else 0)
