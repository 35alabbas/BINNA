#!/usr/bin/env python3
"""
BINNA — Phase 5 item 3: per-module permission management API.

Covers the two new project endpoints that back the CEO permissions grid:

  GET  /api/v1/projects/<id>/permissions                     (project admin/owner)
  PUT  /api/v1/projects/<id>/members/<member_id>/permissions (project admin/owner)

Asserted behaviour:
  * admin/owner can read every member's effective per-module map (all 10 modules)
  * a project VIEWER cannot read or write the map (insufficient role)
  * PUT persists a member's grants; a re-read reflects them
  * edit=True forces view=True (you can't grant edit without view)
  * the project OWNER's grants are immutable (always full access) → 403
  * unknown module keys are ignored; a missing "permissions" object → 400

Runs offline against a throwaway SQLite DB (RESEND_API_KEY unset → email logged,
not sent). Exit 0 only when every assertion holds.
"""
import os, sys, tempfile

_TMP = os.path.join(tempfile.gettempdir(), 'binna_permissions_test.db')
if os.path.exists(_TMP):
    os.remove(_TMP)
os.environ['DATABASE_URL'] = 'sqlite:///' + _TMP
os.environ['FLASK_ENV']    = 'development'
os.environ.pop('RESEND_API_KEY', None)
os.environ['APP_BASE_URL'] = 'http://localhost:5000'

from app import create_app, db                       # noqa: E402
from app.models import User, PERMISSION_MODULES      # noqa: E402

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


def invited_member(owner_hdr, email, pw, company_role='member'):
    """Owner invites into the company; invitee accepts → verified login header."""
    inv = client.post('/api/v1/company/invite',
                      json={'email': email, 'company_role': company_role}, headers=owner_hdr)
    assert inv.status_code == 201, inv.get_json()
    with app.app_context():
        itok = User.query.filter_by(email=email).first().email_verification_token
    acc = client.post('/api/v1/company/accept-invite', json={'token': itok, 'password': pw})
    assert acc.status_code == 200, acc.get_json()
    rl = client.post('/api/v1/auth/login', json={'email': email, 'password': pw})
    return {'Authorization': 'Bearer ' + rl.get_json()['access_token']}


def add_to_project(owner_hdr, pid, email, role):
    am = client.post(f'/api/v1/projects/{pid}/members',
                     json={'email': email, 'role': role}, headers=owner_hdr)
    assert am.status_code == 201, am.get_json()
    return am.get_json()['member']['id']


print('═' * 70)
print('  PHASE 5 item 3 — per-module permission management API')
print('═' * 70)

# ── Setup ──────────────────────────────────────────────────────────────────────
owner_hdr = signup_owner('ceo', 'ceo@acme.test', 'ownerpass', 'Acme')
pr = client.post('/api/v1/projects', json={'code': 'ACM', 'name': 'Acme Tower'},
                 headers=owner_hdr)
pid = pr.get_json()['project']['id']

mem_hdr = invited_member(owner_hdr, 'pm@acme.test', 'memberpass', 'member')
mem_id  = add_to_project(owner_hdr, pid, 'pm@acme.test', 'member')

viewer_hdr = invited_member(owner_hdr, 'eyes@acme.test', 'viewerpass', 'viewer')
add_to_project(owner_hdr, pid, 'eyes@acme.test', 'viewer')

# ── GET permissions — owner sees the whole grid ────────────────────────────────
print('\n[A] GET /permissions')
g = client.get(f'/api/v1/projects/{pid}/permissions', headers=owner_hdr)
check(f'[{g.status_code}] owner reads permissions (200)', g.status_code == 200)
body = g.get_json()
check('all 10 modules returned', set(body.get('modules', [])) == set(PERMISSION_MODULES))
check('3 members listed', body.get('total') == 3)
rows = {m['member_id']: m for m in body['members']}
member_row = rows[mem_id]
check("member row carries a full permission map",
      set(member_row['permissions'].keys()) == set(PERMISSION_MODULES))
check("member (role 'member') has edit on financial by default",
      member_row['permissions']['financial']['edit'] is True)
check("member (role 'member') has NO edit on projects by default",
      member_row['permissions']['projects']['edit'] is False)

# ── GET permissions — a project viewer is blocked ──────────────────────────────
gv = client.get(f'/api/v1/projects/{pid}/permissions', headers=viewer_hdr)
check(f'[{gv.status_code}] viewer CANNOT read permissions (403/404)',
      gv.status_code in (403, 404))

# ── PUT — set the member read-only on financial ────────────────────────────────
print('\n[B] PUT member permissions')
put = client.put(f'/api/v1/projects/{pid}/members/{mem_id}/permissions',
                 json={'permissions': {'financial': {'view': True, 'edit': False}}},
                 headers=owner_hdr)
check(f'[{put.status_code}] owner sets member perms (200)', put.status_code == 200)
check('response shows financial edit now False',
      put.get_json()['permissions']['financial']['edit'] is False)
# re-read confirms persistence
g2 = client.get(f'/api/v1/projects/{pid}/permissions', headers=owner_hdr).get_json()
fin2 = {m['member_id']: m for m in g2['members']}[mem_id]['permissions']['financial']
check('re-read: financial edit stayed False', fin2['edit'] is False and fin2['view'] is True)

# ── PUT — edit=True forces view=True ───────────────────────────────────────────
put2 = client.put(f'/api/v1/projects/{pid}/members/{mem_id}/permissions',
                  json={'permissions': {'gantt': {'view': False, 'edit': True}}},
                  headers=owner_hdr)
gantt = put2.get_json()['permissions']['gantt']
check('edit=True forced view=True on gantt', gantt['view'] is True and gantt['edit'] is True)

# ── PUT — unknown module ignored, known modules preserved ──────────────────────
put3 = client.put(f'/api/v1/projects/{pid}/members/{mem_id}/permissions',
                  json={'permissions': {'not_a_module': {'view': True, 'edit': True}}},
                  headers=owner_hdr)
check(f'[{put3.status_code}] unknown module accepted+ignored (200)', put3.status_code == 200)
check('unknown module NOT in saved map', 'not_a_module' not in put3.get_json()['permissions'])
check('prior gantt grant preserved through partial PUT',
      put3.get_json()['permissions']['gantt']['edit'] is True)

# ── PUT — owner grants are immutable ───────────────────────────────────────────
print('\n[C] guards')
owner_member_id = {m['username']: m['member_id'] for m in g2['members']}.get('ceo')
puto = client.put(f'/api/v1/projects/{pid}/members/{owner_member_id}/permissions',
                  json={'permissions': {'financial': {'view': False, 'edit': False}}},
                  headers=owner_hdr)
check(f'[{puto.status_code}] cannot edit OWNER permissions (403)', puto.status_code == 403)

# ── PUT — viewer cannot write, and a bad body 400 ──────────────────────────────
putv = client.put(f'/api/v1/projects/{pid}/members/{mem_id}/permissions',
                  json={'permissions': {'financial': {'view': True, 'edit': True}}},
                  headers=viewer_hdr)
check(f'[{putv.status_code}] viewer CANNOT write permissions (403/404)',
      putv.status_code in (403, 404))
putb = client.put(f'/api/v1/projects/{pid}/members/{mem_id}/permissions',
                  json={'nope': 1}, headers=owner_hdr)
check(f'[{putb.status_code}] missing "permissions" object → 400', putb.status_code == 400)

# ── Verdict ────────────────────────────────────────────────────────────────────
print('\n' + '═' * 70)
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(1 if _FAIL else 0)
