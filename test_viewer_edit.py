#!/usr/bin/env python3
"""
BINNA — Phase 2 checklist item (d), LITERALLY:
  a VIEWER attempting a content-EDIT action is blocked,
  while an OWNER performing the SAME edit succeeds.

Not invite permissions — actual content edits across the modules that were the
authorization gap (financial, gantt, uploads) plus a project-field edit:

  [A] PROJECT-FIELD  PUT  /projects/<id>            (projects.py: 'admin'; viewer 404 by design)
  [B] FINANCIAL      PUT  /projects/<id>/financial  (gated 'member' → viewer 403, owner 200)
      GANTT          PUT  /projects/<id>/gantt       (gated 'member' → viewer 403, owner 200)
      UPLOADS        POST /projects/<id>/uploads     (gated 'member' → viewer 403, owner 201)

Runs offline against a throwaway SQLite DB (RESEND_API_KEY unset → email logged,
not sent). Exit 0 only when every assertion holds.
"""
import io, os, sys, tempfile

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

# ── A. PROJECT-FIELD edit — PUT /projects/<id> ────────────────────────────────
# projects.py collapses "insufficient role" into 404 (it won't disclose the
# project exists), so a blocked viewer here is 403 OR 404 — both mean "blocked".
print('\n[A] content edit: rename the project (PUT /projects/<id>)')
v_edit = client.put(f'/api/v1/projects/{pid}',
                    json={'name': 'HACKED BY VIEWER'}, headers=viewer_hdr)
check(f'[{v_edit.status_code}] VIEWER edit is BLOCKED (403/404)',
      v_edit.status_code in (403, 404))
o_edit = client.put(f'/api/v1/projects/{pid}',
                    json={'name': 'Acme Tower (renamed by owner)'}, headers=owner_hdr)
check(f'[{o_edit.status_code}] OWNER edit SUCCEEDS (200)', o_edit.status_code == 200)
after = client.get(f'/api/v1/projects/{pid}', headers=owner_hdr).get_json()['project']
check("project name reflects OWNER's edit, not the viewer's",
      after['name'] == 'Acme Tower (renamed by owner)')

# ── B. MODULE edits — the patched gap: viewer 403, owner success ──────────────
# financial / gantt / uploads were membership-only (any member, incl. a viewer,
# could write). Each must now require 'member': viewer → 403, owner → success.
print('\n[B] module content edits: VIEWER blocked (403), OWNER succeeds')

print('  financial  (PUT /projects/<id>/financial)')
vf = client.put(f'/api/v1/projects/{pid}/financial', json={'data': {'x': 'viewer'}}, headers=viewer_hdr)
of = client.put(f'/api/v1/projects/{pid}/financial', json={'data': {'x': 'owner'}},  headers=owner_hdr)
check(f'    [{vf.status_code}] viewer financial edit BLOCKED (403)', vf.status_code == 403)
check(f'    [{of.status_code}] owner  financial edit OK (200)',      of.status_code == 200)

print('  financial/income  (PUT /projects/<id>/financial/income)')
vfi = client.put(f'/api/v1/projects/{pid}/financial/income', json={'income': []}, headers=viewer_hdr)
ofi = client.put(f'/api/v1/projects/{pid}/financial/income', json={'income': []}, headers=owner_hdr)
check(f'    [{vfi.status_code}] viewer income edit BLOCKED (403)', vfi.status_code == 403)
check(f'    [{ofi.status_code}] owner  income edit OK (200)',      ofi.status_code == 200)

print('  gantt      (PUT /projects/<id>/gantt)')
vg = client.put(f'/api/v1/projects/{pid}/gantt', json={'tasks': [{'name': 'viewer task'}]}, headers=viewer_hdr)
og = client.put(f'/api/v1/projects/{pid}/gantt', json={'tasks': [{'name': 'owner task'}]},  headers=owner_hdr)
check(f'    [{vg.status_code}] viewer gantt edit BLOCKED (403)', vg.status_code == 403)
check(f'    [{og.status_code}] owner  gantt edit OK (200)',      og.status_code == 200)

print('  uploads    (POST /projects/<id>/uploads)')
vu = client.post(f'/api/v1/projects/{pid}/uploads',
                 data={'file': (io.BytesIO(b'viewer file'), 'v.txt')},
                 content_type='multipart/form-data', headers=viewer_hdr)
ou = client.post(f'/api/v1/projects/{pid}/uploads',
                 data={'file': (io.BytesIO(b'owner file'), 'o.txt')},
                 content_type='multipart/form-data', headers=owner_hdr)
check(f'    [{vu.status_code}] viewer upload BLOCKED (403)', vu.status_code == 403)
check(f'    [{ou.status_code}] owner  upload OK (201)',      ou.status_code == 201)

# ── Verdict ──────────────────────────────────────────────────────────────────
print('\n' + '═' * 70)
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(1 if _FAIL else 0)
