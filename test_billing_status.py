#!/usr/bin/env python3
"""
BINNA — Phase 4 billing lifecycle: status computation + read-only lock enforcement.

Decisions under test: locked == read-only, grace == 7 days, lazy request-time eval.
Crucially asserts a companies-1-&-2-style account (status=trial, trial_ends_at =
created_at + 14d, grace_ends_at NULL) is computed as 'trial' and is NOT locked —
and stays writable — so deploying this layer cannot silently lock real users.

Offline, throwaway SQLite. Exit 0 = all assertions hold.
"""
import os, sys, tempfile
from datetime import timedelta

_TMP = os.path.join(tempfile.gettempdir(), 'binna_billing_test.db')
if os.path.exists(_TMP):
    os.remove(_TMP)
os.environ['DATABASE_URL'] = 'sqlite:///' + _TMP
os.environ['FLASK_ENV']    = 'development'
os.environ.pop('RESEND_API_KEY', None)
os.environ['APP_BASE_URL'] = 'http://localhost:5000'

from app import create_app, db                                   # noqa: E402
from app.models import Company, User, _now                       # noqa: E402
from app import billing                                          # noqa: E402

app = create_app('development')
import run                                                        # noqa: E402,F401
with app.app_context():
    db.create_all(); run._ensure_schema()
client = app.test_client()

_PASS = _FAIL = 0
def check(name, cond):
    global _PASS, _FAIL
    _PASS += bool(cond); _FAIL += (not cond)
    print(('  ok   ' if cond else '  FAIL ') + name)

_n = [0]
def make_company(status='trial', trial_off=None, grace_off=None):
    """Insert a Company with deadlines at now±offset days (None ⇒ NULL). Returns id."""
    _n[0] += 1
    with app.app_context():
        c = Company(
            name=f'C{_n[0]}', slug=f'c{_n[0]}', plan='trial', status=status,
            trial_ends_at=(_now() + timedelta(days=trial_off)) if trial_off is not None else None,
            grace_ends_at=(_now() + timedelta(days=grace_off)) if grace_off is not None else None,
        )
        db.session.add(c); db.session.commit()
        return c.id

def status_of(cid):
    with app.app_context():
        return db.session.get(Company, cid).status


print('═' * 70)
print('  PHASE 4 — BILLING STATUS + READ-ONLY LOCK')
print('═' * 70)

# ── 1. compute_status (pure) ──────────────────────────────────────────────────
print('\n[1] compute_status() — pure lifecycle from stored deadlines')
cases = {
    'like-1-2 (trial +14d, grace NULL)':   (make_company('trial', 14, None),  'trial'),
    'active/paid (trial -100d)':           (make_company('active', -100, None),'active'),
    'in grace (trial -1d, grace +5d)':     (make_company('trial', -1, 5),     'grace'),
    'lapsed (trial -30d, grace -1d)':      (make_company('trial', -30, -1),   'locked'),
    'no deadlines (trial NULL)':           (make_company('trial', None, None),'trial'),
}
with app.app_context():
    for label, (cid, expected) in cases.items():
        got = billing.compute_status(db.session.get(Company, cid))
        check(f"{label} -> '{got}' (expect '{expected}')", got == expected)

# ── 2. refresh_status (persists transitions) ──────────────────────────────────
print('\n[2] refresh_status() — stamps grace, persists, NULL-safe')
cid_lapse = make_company('trial', trial_off=-1, grace_off=None)
with app.app_context():
    c = db.session.get(Company, cid_lapse)
    eff = billing.refresh_status(c)
    check("just-lapsed trial -> 'grace'", eff == 'grace')
    delta = (c.grace_ends_at.replace(tzinfo=None)
             - (c.trial_ends_at.replace(tzinfo=None) + timedelta(days=billing.GRACE_DAYS)))
    check('grace_ends_at stamped to trial_ends_at + 7d', abs(delta.total_seconds()) < 2)
check("persisted: just-lapsed company is now 'grace'", status_of(cid_lapse) == 'grace')

cid_stay = make_company('trial', trial_off=14, grace_off=None)   # companies 1 & 2 shape
with app.app_context():
    c = db.session.get(Company, cid_stay)
    eff = billing.refresh_status(c)
    check('refresh keeps trial-active at trial and does NOT stamp grace',
          eff == 'trial' and c.grace_ends_at is None)

# ── 3. Enforcement: locked == read-only; trial writable; super-admin bypass ───
print('\n[3] enforcement (lazy, request-time)')

def signup(username, email, company):
    r = client.post('/api/v1/auth/register', json={
        'username': username, 'email': email, 'password': 'password1', 'company_name': company})
    assert r.status_code == 201, r.get_json()
    with app.app_context():
        tok = User.query.filter_by(email=email).first().email_verification_token
    client.get(f'/api/v1/auth/verify/{tok}')
    rl = client.post('/api/v1/auth/login', json={'email': email, 'password': 'password1'})
    return {'Authorization': 'Bearer ' + rl.get_json()['access_token']}, rl.get_json()['user']['id']

def newproj(hdr, code):
    return client.post('/api/v1/projects', json={'code': code, 'name': code,
                       'client': 'C', 'consultant': 'K', 'contractor': 'T'}, headers=hdr)

hdr_admin, uid_admin = signup('boss', 'boss@acme.test', 'Acme')      # FIRST user → platform super-admin
hdr_user,  uid_user  = signup('staff', 'staff@beta.test', 'Beta')    # platform role 'user'

check('[3a] trial-active company CAN create a project (201)', newproj(hdr_user, 'P1').status_code == 201)

# lock the non-admin company; a write then triggers the lazy transition → 403
with app.app_context():
    cu = db.session.get(User, uid_user).company
    cu.status = 'trial'; cu.trial_ends_at = _now() - timedelta(days=30); cu.grace_ends_at = None
    db.session.commit(); cu_id = cu.id
_blocked = newproj(hdr_user, 'P2')
check('[3b] locked company write BLOCKED (403)', _blocked.status_code == 403)
check("[3b'] lock 403 carries code='account_locked' (distinct from role-gate 403s)",
      _blocked.get_json().get('code') == 'account_locked')
check('[3c] locked company read ALLOWED (200)', client.get('/api/v1/projects', headers=hdr_user).status_code == 200)
check('[3d] status lazily persisted to locked', status_of(cu_id) == 'locked')

# platform super-admin is never locked out, even with an expired company
with app.app_context():
    ca = db.session.get(User, uid_admin).company
    ca.status = 'locked'; ca.trial_ends_at = _now() - timedelta(days=30)
    ca.grace_ends_at = _now() - timedelta(days=1); db.session.commit()
check('[3e] platform super-admin bypasses the lock (201)', newproj(hdr_admin, 'P3').status_code == 201)

print('\n' + '═' * 70)
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(1 if _FAIL else 0)
