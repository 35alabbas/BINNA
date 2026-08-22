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

Runs offline against a caller-provided, newly created SQLite database outside
C:\\BINNA\\instance. It never imports run.py. Exit 0 only when every assertion holds.
"""
import io
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
    Company, FinancialData, Project, ProjectMember, User, _now,
)

app = create_app('development')
upload_dir = TEST_DB_PATH.with_name(TEST_DB_PATH.name + '.uploads')
app.config.update(UPLOAD_FOLDER=str(upload_dir), R2_ACCESS_KEY_ID='',
                  R2_SECRET_ACCESS_KEY='', R2_BUCKET='', R2_ENDPOINT='')
client = app.test_client()


def headers(user_id):
    with app.app_context():
        token = create_access_token(identity=str(user_id))
    return {'Authorization': 'Bearer ' + token}


with app.app_context():
    db.create_all()
    alpha = Company(name='Acme', slug='viewer-acme', status='trial',
                    trial_ends_at=_now() + timedelta(days=14))
    beta = Company(name='Beta', slug='viewer-beta', status='trial',
                   trial_ends_at=_now() + timedelta(days=14))
    db.session.add_all([alpha, beta])
    db.session.flush()
    manager = User(username='boss', email='boss@acme.test', password_hash='unused',
                   company_id=alpha.id, company_role='owner',
                   is_company_manager=True, email_verified=True)
    viewer = User(username='eyes', email='eyes@acme.test', password_hash='unused',
                  company_id=alpha.id, company_role='viewer', email_verified=True)
    outsider = User(username='outside', email='outside@beta.test', password_hash='unused',
                    company_id=beta.id, company_role='owner',
                    is_company_manager=True, email_verified=True)
    db.session.add_all([manager, viewer, outsider])
    db.session.flush()
    alpha.projects_manager_user_id = manager.id
    # One user deliberately holds the company-manager, projects-manager, and
    # explicit project-manager authorities; the viewer receives no edit grant.
    project = Project(company_id=alpha.id, code='ACM', name='Acme Tower',
                      client='C', consultant='K', contractor='T',
                      created_by=manager.id, project_manager_user_id=manager.id)
    db.session.add(project)
    db.session.flush()
    db.session.add_all([
        ProjectMember(company_id=alpha.id, project_id=project.id,
                      user_id=manager.id, role='owner', permissions='{}'),
        ProjectMember(company_id=alpha.id, project_id=project.id,
                      user_id=viewer.id, role='viewer', permissions='{}'),
    ])
    db.session.add(FinancialData(company_id=alpha.id, project_id=project.id,
                                 updated_by=manager.id,
                                 data=json.dumps({'income': [], 'expenses': []})))
    db.session.commit()
    ids = {'project': project.id, 'manager': manager.id,
           'viewer': viewer.id, 'outsider': outsider.id}

owner_hdr = headers(ids['manager'])
viewer_hdr = headers(ids['viewer'])
outsider_hdr = headers(ids['outsider'])
pid = ids['project']

_PASS = _FAIL = 0
def check(name, cond):
    global _PASS, _FAIL
    _PASS += bool(cond); _FAIL += (not cond)
    print(('  ok   ' if cond else '  FAIL ') + name)


print('═' * 70)
print('  ITEM (d) — VIEWER cannot edit, OWNER can')
print('═' * 70)

# ── Setup ────────────────────────────────────────────────────────────────────
print(f'ISOLATED_DATABASE={TEST_DB_PATH}')
with app.app_context():
    viewer_membership = ProjectMember.query.filter_by(
        project_id=pid, user_id=ids['viewer']).first()
    check("setup: viewer is a project member with role 'viewer'",
          viewer_membership is not None and viewer_membership.role == 'viewer')

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
cross_edit = client.put(f'/api/v1/projects/{pid}',
                        json={'name': 'FOREIGN EDIT'}, headers=outsider_hdr)
check(f'[{cross_edit.status_code}] cross-company project edit is hidden (404)',
      cross_edit.status_code == 404)

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
                 data={'file': (io.BytesIO(b'viewer file'), 'v.pdf')},
                 content_type='multipart/form-data', headers=viewer_hdr)
ou = client.post(f'/api/v1/projects/{pid}/uploads',
                 data={'file': (io.BytesIO(b'owner file'), 'o.pdf')},
                 content_type='multipart/form-data', headers=owner_hdr)
check(f'    [{vu.status_code}] viewer upload BLOCKED (403)', vu.status_code == 403)
check(f'    [{ou.status_code}] owner  upload OK (201)',      ou.status_code == 201)

# ── Verdict ──────────────────────────────────────────────────────────────────
print('\n' + '═' * 70)
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(1 if _FAIL else 0)
