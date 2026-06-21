#!/usr/bin/env python3
"""
BINNA — Phase 2 checklist item (d), LITERALLY:
  a VIEWER attempting a content-EDIT action is blocked (403),
  while an OWNER performing the SAME edit succeeds (200).

Not invite permissions — an actual content edit. Two edit surfaces are probed:
  • PROJECT-FIELD edit  →  PUT /api/v1/projects/<id>            (role-gated 'admin')
  • FINANCIAL edit      →  PUT /api/v1/projects/<id>/financial  (membership-only?)

Runs offline against a throwaway SQLite DB (RESEND_API_KEY unset → email logged,
not sent). Exit 0 only if item (d) holds on the project-field edit.
"""
import os, sys, tempfile

_TMP = os.path.join(tempfile.gettempdir(), 'binna_viewer_edit_test.db')
if os.path.exists(_TMP):
    os.remove(_TMP)
os.environ['DATABASE_URL'] = 'sqlite:///' + _TMP
os.environ['FLASK_ENV']    = 'development'
os.environ.pop('RESEND_API_KEY', None)
os.environ['APP_BASE_URL'] = 'http://localhost:5000'

from app import create_app, db                       # noqa: E402
from app.models import User                          # noqa: E402

app = create_app('development')
import run                                            # noqa: E402,F401
with app.app_context():
    db.create_all()
    run._ensure_schema()
client = app.test_client()

_PASS = _FAIL = 0
def check(name, cond):
    global _PASS, _FAIL
    _PASS += bool(cond); _FAIL += (not cond)
    print(('  ok   ' if cond else '  FAIL ') + name)


def signup_owner(username, email, pw, company):
    r = client.post('/api/v1/auth/register', json={
        'username': username, 'email': email, 'password': pw, 'company_name': company})
    assert r.status_code == 201, r.get_json()
    with app.app_context():
        tok = User.query.filter_by(email=email).first().email_verification_token
    client.get(f'/api/v1/auth/verify/{tok}')
    rl = client.post('/api/v1/auth/login', json={'email': email, 'password': pw})
    return {'Authorization': 'Bearer ' + rl.get_json()['access_token']}


def make_viewer_in_company(owner_hdr, email, pw):
    """Owner invites a VIEWER into the company; invitee accepts → verified login."""
    inv = client.post('/api/v1/company/invite',
                      json={'email': email, 'company_role': 'viewer'}, headers=owner_hdr)
    assert inv.status_code == 201, inv.get_json()
    with app.app_context():
        itok = User.query.filter_by(email=email).first().email_verification_token
    acc = client.post('/api/v1/company/accept-invite', json={'token': itok, 'password': pw})
    assert acc.status_code == 200, acc.get_json()
    rl = client.post('/api/v1/auth/login', json={'email': email, 'password': pw})
    return {'Authorization': 'Bearer ' + rl.get_json()['access_token']}


print('═' * 70)
print('  ITEM (d) — VIEWER cannot edit, OWNER can')
print('═' * 70)

# ── Setup ────────────────────────────────────────────────────────────────────
owner_hdr = signup_owner('boss', 'boss@acme.test', 'ownerpass', 'Acme')
pr = client.post('/api/v1/projects', json={'code': 'ACM', 'name': 'Acme Tower',
                 'client': 'C', 'consultant': 'K', 'contractor': 'T'}, headers=owner_hdr)
pid = pr.get_json()['project']['id']

viewer_hdr = make_viewer_in_company(owner_hdr, 'eyes@acme.test', 'viewerpass')
# Owner adds the viewer onto the project with PROJECT-role 'viewer'.
am = client.post(f'/api/v1/projects/{pid}/members',
                 json={'email': 'eyes@acme.test', 'role': 'viewer'}, headers=owner_hdr)
assert am.status_code == 201, am.get_json()
check("setup: viewer is a project member with role 'viewer'",
      am.get_json()['member']['role'] == 'viewer')

# ── A. PROJECT-FIELD edit — PUT /projects/<id> (the literal item (d)) ──────────
print('\n[A] content edit: rename the project (PUT /projects/<id>)')
v_edit = client.put(f'/api/v1/projects/{pid}',
                    json={'name': 'HACKED BY VIEWER'}, headers=viewer_hdr)
check(f'[{v_edit.status_code}] VIEWER edit is BLOCKED (expect 403)',
      v_edit.status_code == 403)

o_edit = client.put(f'/api/v1/projects/{pid}',
                    json={'name': 'Acme Tower (renamed by owner)'}, headers=owner_hdr)
check(f'[{o_edit.status_code}] OWNER edit SUCCEEDS (expect 200)',
      o_edit.status_code == 200)

# Prove the write actually took / was actually rejected.
after = client.get(f'/api/v1/projects/{pid}', headers=owner_hdr).get_json()['project']
check("project name reflects OWNER's edit, not the viewer's",
      after['name'] == 'Acme Tower (renamed by owner)')

ITEM_D_OK = (v_edit.status_code == 403 and o_edit.status_code == 200
             and after['name'] == 'Acme Tower (renamed by owner)')

# ── B. FINANCIAL edit — PUT /projects/<id>/financial (honest probe) ───────────
print('\n[B] content edit: financial blob (PUT /projects/<id>/financial)')
vf = client.put(f'/api/v1/projects/{pid}/financial',
                json={'data': {'secret': 'viewer-was-here'}}, headers=viewer_hdr)
print(f'      VIEWER financial PUT → HTTP {vf.status_code}')
of = client.put(f'/api/v1/projects/{pid}/financial',
                json={'data': {'secret': 'owner-value'}}, headers=owner_hdr)
print(f'      OWNER  financial PUT → HTTP {of.status_code}')
fin_gated = vf.status_code == 403
if fin_gated:
    print('      → financial edit IS role-gated against viewers.')
else:
    print(f'      → ⚠ financial edit is NOT role-gated: a viewer got HTTP {vf.status_code} '
          '(membership-only access, no role check). REAL GAP.')

# ── Verdict ──────────────────────────────────────────────────────────────────
print('\n' + '═' * 70)
print(f'  ITEM (d) [project-field edit]: {"PASS" if ITEM_D_OK else "FAIL"}')
print(f'  financial edit role-gated:     {"yes" if fin_gated else "NO (gap)"}')
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(0 if ITEM_D_OK else 1)
