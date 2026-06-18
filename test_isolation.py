#!/usr/bin/env python3
"""
BINNA — Phase 2 tenant-isolation test  (the make-or-break check)

Creates TWO real companies through the full signup→verify flow, has each create
a project plus data in every module, then proves Company A cannot reach Company
B's data through ANY project-scoped endpoint — not just the obvious ones. The
endpoint sweep is generated from the live URL map, so new routes are covered
automatically.

Runs entirely offline against a throwaway SQLite DB (RESEND_API_KEY unset → the
email module logs links instead of sending). Exit code 0 = isolation holds.
"""
import os
import sys
import tempfile

# Throwaway DB + dev config BEFORE importing the app.
_TMP_DB = os.path.join(tempfile.gettempdir(), 'binna_isolation_test.db')
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ['DATABASE_URL'] = 'sqlite:///' + _TMP_DB
os.environ['FLASK_ENV']    = 'development'
os.environ.pop('RESEND_API_KEY', None)        # force dev email fallback
os.environ['APP_BASE_URL'] = 'http://localhost:5000'

from app import create_app, db                                    # noqa: E402
from app.models import User                                       # noqa: E402

app = create_app('development')

# Build schema exactly like run.py does.
import run                                                        # noqa: E402,F401
with app.app_context():
    db.create_all()
    run._ensure_schema()

client = app.test_client()

_PASS = 0
_FAIL = 0


def check(name, condition):
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f'  ok   {name}')
    else:
        _FAIL += 1
        print(f'  FAIL {name}')


def signup_and_login(username, email, password, company):
    """Full self-signup → verify → login. Returns (auth_headers, user_id)."""
    r = client.post('/api/v1/auth/register', json={
        'username': username, 'email': email, 'password': password,
        'company_name': company,
    })
    assert r.status_code == 201, f'register failed: {r.status_code} {r.get_json()}'

    # Pull the verification token straight from the DB (the email is logged, not sent).
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        token = u.email_verification_token
        assert token, 'no verification token issued'

    rv = client.get(f'/api/v1/auth/verify/{token}')
    assert rv.status_code in (302, 200), f'verify failed: {rv.status_code}'

    rl = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert rl.status_code == 200, f'login failed: {rl.status_code} {rl.get_json()}'
    tok = rl.get_json()['access_token']
    uid = rl.get_json()['user']['id']
    return {'Authorization': f'Bearer {tok}'}, uid


def create_project(headers, code, name):
    r = client.post('/api/v1/projects', json={'code': code, 'name': name,
                                              'client': 'C', 'consultant': 'K',
                                              'contractor': 'T'}, headers=headers)
    assert r.status_code == 201, f'create project failed: {r.status_code} {r.get_json()}'
    return r.get_json()['project']['id']


def seed_data(headers, pid):
    """Create at least one row in each module so reads have something to leak."""
    client.post(f'/api/v1/projects/{pid}/dc',
                json={'direction': 'incoming', 'subject': 'secret letter'}, headers=headers)
    client.post(f'/api/v1/projects/{pid}/submittals/dwg',
                json={'title': 'secret dwg'}, headers=headers)
    client.post(f'/api/v1/projects/{pid}/dr',
                json={'report_date': '2026-01-01', 'weather': 'sunny'}, headers=headers)
    client.post(f'/api/v1/projects/{pid}/lbt',
                json={'direction': 'out', 'test_type': 'concrete'}, headers=headers)
    client.put(f'/api/v1/projects/{pid}/financial',
               json={'data': {'secret': 'B-money'}}, headers=headers)
    client.put(f'/api/v1/projects/{pid}/gantt',
               json={'tasks': [{'name': 'secret task'}]}, headers=headers)


print('═' * 70)
print('  PHASE 2 TENANT-ISOLATION TEST')
print('═' * 70)

with app.app_context():
    pass

# ── Two real tenants ────────────────────────────────────────────────────────────
print('\n[setup] creating Company A and Company B via full signup flow…')
hdr_a, uid_a = signup_and_login('owner_a', 'a@aco.test', 'passwordA', 'Alpha Co')
hdr_b, uid_b = signup_and_login('owner_b', 'b@bco.test', 'passwordB', 'Beta Co')

pid_a = create_project(hdr_a, 'APA', 'Alpha Project')
pid_b = create_project(hdr_b, 'BPB', 'Beta Project')
seed_data(hdr_a, pid_a)
seed_data(hdr_b, pid_b)
print(f'[setup] A: user={uid_a} project={pid_a}   B: user={uid_b} project={pid_b}')

# Sanity: each tenant lives in its own company.
with app.app_context():
    ua = User.query.get(uid_a)
    ub = User.query.get(uid_b)
    check('A and B are in different companies', ua.company_id != ub.company_id)
    check('A is owner of its company', ua.company_role == 'owner')

# ── 1. Listing never crosses tenants ────────────────────────────────────────────
print('\n[1] project listing is company-scoped')
la = client.get('/api/v1/projects', headers=hdr_a).get_json()['projects']
lb = client.get('/api/v1/projects', headers=hdr_b).get_json()['projects']
a_ids = {p['id'] for p in la}
b_ids = {p['id'] for p in lb}
check('A sees its own project',      pid_a in a_ids)
check('A does NOT see B project',    pid_b not in a_ids)
check('B does NOT see A project',    pid_a not in b_ids)

# ── 2. THE SWEEP: A hits every project-scoped GET against B's project ────────────
print("\n[2] endpoint sweep — A's token vs B's project_id on EVERY route")
import re as _re
swept = 0
for rule in app.url_map.iter_rules():
    # Only the JSON API carries tenant data. Page routes (e.g. /project/<id>)
    # serve a static SPA shell with no data — the JS then calls the gated API —
    # so they are intentionally out of scope for the data-isolation sweep.
    if not rule.rule.startswith('/api/'):
        continue
    if '<int:project_id>' not in rule.rule or 'GET' not in (rule.methods or set()):
        continue
    # Build a concrete path: B's project, a VALID module_type, dummy ints elsewhere.
    path = rule.rule.replace('<int:project_id>', str(pid_b))
    path = path.replace('<module_type>', 'dwg')
    path = _re.sub(r'<[^>]*?:([^>]+)>', '1', path)   # typed converters → 1
    path = _re.sub(r'<([^>]+)>', '1', path)          # bare converters → 1
    if '<' in path:
        continue
    resp = client.get(path, headers=hdr_a)
    swept += 1
    # Cross-tenant access must be refused. 403/404 = gate denied; 400 = request
    # rejected before any data. The ONLY failure is a 2xx leaking B's data.
    ok = resp.status_code in (400, 403, 404)
    check(f'[{resp.status_code}] {rule.rule}', ok)

print(f'\n    swept {swept} project-scoped GET endpoints')

# ── 3. Direct data endpoints return B's secrets to B, nothing to A ──────────────
print('\n[3] spot-check sensitive payloads do not leak')
fa = client.get(f'/api/v1/projects/{pid_b}/financial', headers=hdr_a)
check('A cannot read B financial (404/403)', fa.status_code in (403, 404))
fb = client.get(f'/api/v1/projects/{pid_b}/financial', headers=hdr_b)
check('B CAN read its own financial',        fb.status_code == 200)

# ── 4. Mutations across tenants are refused ─────────────────────────────────────
print('\n[4] cross-tenant writes are refused')
wr = client.post(f'/api/v1/projects/{pid_b}/dc',
                 json={'direction': 'incoming', 'subject': 'hijack'}, headers=hdr_a)
check('A cannot create DC under B project', wr.status_code in (403, 404))
de = client.delete(f'/api/v1/projects/{pid_b}', headers=hdr_a)
check('A cannot delete B project',          de.status_code in (403, 404))

# ── 5. A cannot add itself / others to B via the project member endpoint ────────
print('\n[5] membership endpoints are isolated')
am = client.post(f'/api/v1/projects/{pid_b}/members',
                 json={'email': 'a@aco.test', 'role': 'admin'}, headers=hdr_a)
check('A cannot add members to B project', am.status_code in (403, 404))

# ── 6. Company member listing is scoped ─────────────────────────────────────────
print('\n[6] company member directory is scoped')
ma = client.get('/api/v1/company/members', headers=hdr_a).get_json()['members']
emails_a = {m['email'] for m in ma}
check('A company directory has A owner',     'a@aco.test' in emails_a)
check('A company directory excludes B owner', 'b@bco.test' not in emails_a)

# ── Verdict ─────────────────────────────────────────────────────────────────────
print('\n' + '═' * 70)
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(1 if _FAIL else 0)
