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

Runs offline against a caller-provided, newly created SQLite database outside
C:\\BINNA\\instance. It never imports run.py. Exit 0 only when every assertion holds.
"""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def _verified_test_database():
    url = os.environ.get('DATABASE_URL', '')
    if os.environ.get('BINNA_ISOLATED_TEST_DB') != '1' or not url.startswith('sqlite:///'):
        raise RuntimeError('Refusing to run without an explicitly isolated SQLite database')
    path = Path(url[len('sqlite:///'):]).resolve()
    instance = (Path(__file__).resolve().parent / 'instance').resolve()
    try:
        path.relative_to(instance)
    except ValueError:
        pass
    else:
        raise RuntimeError('Refusing to use a database inside C:\\BINNA\\instance')
    if not path.is_file() or path.stat().st_size != 0:
        raise RuntimeError('Test database must be a newly created empty file')
    return path


TEST_DB_PATH = _verified_test_database()

from flask_jwt_extended import create_access_token  # noqa: E402
from app import create_app, db  # noqa: E402
from app.models import (  # noqa: E402
    Company, FinancialData, PERMISSION_MODULES, Project, ProjectMember, User, _now,
)

app = create_app('development')
client = app.test_client()


def headers(user_id):
    with app.app_context():
        token = create_access_token(identity=str(user_id))
    return {'Authorization': 'Bearer ' + token}


with app.app_context():
    db.create_all()
    alpha = Company(name='Acme', slug='permissions-acme', status='trial',
                    trial_ends_at=_now() + timedelta(days=14))
    beta = Company(name='Beta', slug='permissions-beta', status='trial',
                   trial_ends_at=_now() + timedelta(days=14))
    db.session.add_all([alpha, beta])
    db.session.flush()
    manager = User(username='ceo', email='ceo@acme.test', password_hash='unused',
                   company_id=alpha.id, company_role='owner',
                   is_company_manager=True, email_verified=True)
    member = User(username='pm', email='pm@acme.test', password_hash='unused',
                  company_id=alpha.id, company_role='member', email_verified=True)
    viewer = User(username='eyes', email='eyes@acme.test', password_hash='unused',
                  company_id=alpha.id, company_role='viewer', email_verified=True)
    outsider = User(username='outside', email='outside@beta.test', password_hash='unused',
                    company_id=beta.id, company_role='owner',
                    is_company_manager=True, email_verified=True)
    db.session.add_all([manager, member, viewer, outsider])
    db.session.flush()
    alpha.projects_manager_user_id = manager.id
    # The company manager also serves as projects manager and explicit project
    # manager; the other users exercise legacy project roles and module grants.
    project = Project(company_id=alpha.id, code='ACM', name='Acme Tower',
                      created_by=manager.id, project_manager_user_id=manager.id)
    db.session.add(project)
    db.session.flush()
    owner_membership = ProjectMember(company_id=alpha.id, project_id=project.id,
                                     user_id=manager.id, role='owner', permissions='{}')
    member_membership = ProjectMember(company_id=alpha.id, project_id=project.id,
                                      user_id=member.id, role='member', permissions='{}')
    viewer_membership = ProjectMember(company_id=alpha.id, project_id=project.id,
                                      user_id=viewer.id, role='viewer', permissions='{}')
    db.session.add_all([owner_membership, member_membership, viewer_membership])
    db.session.add(FinancialData(company_id=alpha.id, project_id=project.id,
                                 updated_by=manager.id,
                                 data=json.dumps({'income': [], 'expenses': []})))
    db.session.commit()
    ids = {'project': project.id, 'manager': manager.id, 'member': member.id,
           'viewer': viewer.id, 'outsider': outsider.id,
           'member_membership': member_membership.id}

owner_hdr = headers(ids['manager'])
mem_hdr = headers(ids['member'])
viewer_hdr = headers(ids['viewer'])
outsider_hdr = headers(ids['outsider'])
pid = ids['project']
mem_id = ids['member_membership']

_PASS = _FAIL = 0
def check(name, cond):
    global _PASS, _FAIL
    _PASS += bool(cond); _FAIL += (not cond)
    print(('  ok   ' if cond else '  FAIL ') + name)


print('═' * 70)
print('  PHASE 5 item 3 — per-module permission management API')
print('═' * 70)

# ── Setup ──────────────────────────────────────────────────────────────────────
print(f'ISOLATED_DATABASE={TEST_DB_PATH}')

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
foreign = client.get(f'/api/v1/projects/{pid}/permissions', headers=outsider_hdr)
check(f'[{foreign.status_code}] cross-company permissions stay hidden (404)',
      foreign.status_code == 404)

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

# ── ENFORCEMENT — the map now gates real module routes ─────────────────────────
# Proves can() is wired in, not just stored. A member with financial fully granted
# can read+write; revoking view hides the module (404); revoking edit makes it
# read-only (403). A group-2 module (dc) confirms the read gate there too. An
# un-provisioned viewer still reads (role default view=True) — no lock-out.
print('\n[D] route enforcement')
FIN = f'/api/v1/projects/{pid}/financial'
DC  = f'/api/v1/projects/{pid}/dc'

def set_perms(mid, perms):
    r = client.put(f'/api/v1/projects/{pid}/members/{mid}/permissions',
                   json={'permissions': perms}, headers=owner_hdr)
    assert r.status_code == 200, r.get_json()

# full grant → member can read and write financial
set_perms(mem_id, {'financial': {'view': True, 'edit': True}})
check(f'[{client.get(FIN, headers=mem_hdr).status_code}] member reads financial when granted (200)',
      client.get(FIN, headers=mem_hdr).status_code == 200)
check(f'[{client.put(FIN, json={"data": {}}, headers=mem_hdr).status_code}] member writes financial when granted (200)',
      client.put(FIN, json={'data': {}}, headers=mem_hdr).status_code == 200)

# revoke view+edit → module hidden (read 404, write 403)
set_perms(mem_id, {'financial': {'view': False, 'edit': False}})
check(f'[{client.get(FIN, headers=mem_hdr).status_code}] view revoked → member read financial 404',
      client.get(FIN, headers=mem_hdr).status_code == 404)
check(f'[{client.put(FIN, json={"data": {}}, headers=mem_hdr).status_code}] view revoked → member write financial 403/404',
      client.put(FIN, json={'data': {}}, headers=mem_hdr).status_code in (403, 404))

# view-only → can read, cannot write
set_perms(mem_id, {'financial': {'view': True, 'edit': False}})
check(f'[{client.get(FIN, headers=mem_hdr).status_code}] view-only → member reads financial (200)',
      client.get(FIN, headers=mem_hdr).status_code == 200)
check(f'[{client.put(FIN, json={"data": {}}, headers=mem_hdr).status_code}] view-only → member write financial 403',
      client.put(FIN, json={'data': {}}, headers=mem_hdr).status_code == 403)

# group-2 module read gate (dc): hide it → member list 404
set_perms(mem_id, {'dc': {'view': False, 'edit': False}})
check(f'[{client.get(DC, headers=mem_hdr).status_code}] dc view revoked → member list 404',
      client.get(DC, headers=mem_hdr).status_code == 404)
set_perms(mem_id, {'dc': {'view': True, 'edit': True}})
check(f'[{client.get(DC, headers=mem_hdr).status_code}] dc view restored → member list 200',
      client.get(DC, headers=mem_hdr).status_code == 200)

# un-provisioned viewer is NOT locked out of reads (role default view=True)
check(f'[{client.get(FIN, headers=viewer_hdr).status_code}] un-provisioned viewer still reads financial (200)',
      client.get(FIN, headers=viewer_hdr).status_code == 200)

# ── Verdict ────────────────────────────────────────────────────────────────────
print('\n' + '═' * 70)
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(1 if _FAIL else 0)
