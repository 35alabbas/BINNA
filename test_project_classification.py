#!/usr/bin/env python3
"""Stage 1 project classification and warning behavior on isolated SQLite."""
import json
import os
import sys
from pathlib import Path


def _verified_test_database() -> Path:
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
    AuditLog, Company, FinancialData, Project, ProjectMember,
    ProjectWarningDismissal, User,
)
from app.tenancy import project_classification_schema_status  # noqa: E402


app = create_app('development')
with app.app_context():
    db.create_all()
    alpha = Company(name='Alpha', slug='alpha-classification', status='trial')
    beta = Company(name='Beta', slug='beta-classification', status='trial')
    db.session.add_all([alpha, beta])
    db.session.flush()
    manager = User(username='manager', email='manager@class.test', password_hash='x',
                   company_id=alpha.id, company_role='owner', email_verified=True)
    portfolio = User(username='portfolio', email='portfolio@class.test', password_hash='x',
                     company_id=alpha.id, company_role='member', email_verified=True)
    pm = User(username='pm', email='pm@class.test', password_hash='x',
              company_id=alpha.id, company_role='member', email_verified=True)
    editor = User(username='editor', email='editor@class.test', password_hash='x',
                  company_id=alpha.id, company_role='member', email_verified=True)
    employee = User(username='employee', email='employee@class.test', password_hash='x',
                    company_id=alpha.id, company_role='member', email_verified=True)
    foreign = User(username='foreign', email='foreign@class.test', password_hash='x',
                   company_id=beta.id, company_role='owner', email_verified=True)
    db.session.add_all([manager, portfolio, pm, editor, employee, foreign])
    db.session.flush()
    alpha.projects_manager_user_id = portfolio.id
    project = Project(company_id=alpha.id, code='HOUSE', name='Small House', status='active',
                      created_by=manager.id, project_manager_user_id=pm.id)
    closed = Project(company_id=alpha.id, code='CLOSED', name='Closed', status='completed',
                     created_by=manager.id, project_manager_user_id=pm.id, is_closed=True,
                     closed_by_user_id=manager.id)
    db.session.add_all([project, closed])
    db.session.flush()
    settings_edit = json.dumps({'projects': {'view': True, 'edit': True}})
    settings_view = json.dumps({'projects': {'view': True, 'edit': False}})
    for target in (project, closed):
        db.session.add(ProjectMember(company_id=alpha.id, project_id=target.id,
                                     user_id=manager.id, role='owner', permissions='{}'))
        db.session.add(ProjectMember(company_id=alpha.id, project_id=target.id,
                                     user_id=pm.id, role='viewer', permissions='{}'))
    db.session.add_all([
        ProjectMember(company_id=alpha.id, project_id=project.id, user_id=editor.id,
                      role='member', permissions=settings_edit),
        ProjectMember(company_id=alpha.id, project_id=project.id, user_id=employee.id,
                      role='member', permissions=settings_view),
        FinancialData(company_id=alpha.id, project_id=project.id, updated_by=manager.id,
                      data=json.dumps({'contractDetails': {}, 'boq': [], 'vo': [], 'payments': []})),
    ])
    db.session.commit()
    ids = {name: user.id for name, user in {
        'manager': manager, 'portfolio': portfolio, 'pm': pm, 'editor': editor,
        'employee': employee, 'foreign': foreign,
    }.items()}
    ids.update(project=project.id, closed=closed.id)
    tokens = {name: create_access_token(identity=str(uid))
              for name, uid in ids.items() if name not in ('project', 'closed')}


client = app.test_client()
headers = {name: {'Authorization': 'Bearer ' + token} for name, token in tokens.items()}
passed = failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print('  ok   ' + name)
    else:
        failed += 1
        print('  FAIL ' + name)


print(f'ISOLATED_DATABASE={TEST_DB_PATH}')
print('Stage 1 classification, generated codes, and warnings')

with app.app_context():
    check('fresh schema exposes Stage 1 structures', project_classification_schema_status()['ready'])

created_one = client.post('/api/v1/projects', json={
    'name': 'Private Villa', 'project_manager_user_id': ids['pm'],
}, headers=headers['manager'])
created_two = client.post('/api/v1/projects', json={
    'name': 'Second Villa', 'project_manager_user_id': ids['pm'],
}, headers=headers['manager'])
one = (created_one.get_json() or {}).get('project', {})
two = (created_two.get_json() or {}).get('project', {})
check('project creation generates a company-scoped code when omitted',
      created_one.status_code == 201 and one.get('code') == 'PRJ-0001')
check('generated project codes advance without collisions',
      created_two.status_code == 201 and two.get('code') == 'PRJ-0002')

manual = client.post('/api/v1/projects', json={
    'code': 'VILLA-A', 'name': 'Named Villa', 'project_manager_user_id': ids['pm'],
}, headers=headers['manager'])
duplicate = client.post('/api/v1/projects', json={
    'code': 'VILLA-A', 'name': 'Duplicate', 'project_manager_user_id': ids['pm'],
}, headers=headers['manager'])
check('manual project code remains supported',
      manual.status_code == 201 and (manual.get_json() or {}).get('project', {}).get('code') == 'VILLA-A')
check('duplicate project code is rejected within the company', duplicate.status_code == 409)
duplicate_edit = client.put(f"/api/v1/projects/{ids['project']}",
                            json={'code': 'VILLA-A'}, headers=headers['pm'])
check('editing cannot introduce a duplicate company project code', duplicate_edit.status_code == 409)

invalid_create = client.post('/api/v1/projects', json={
    'name': 'Invalid classification', 'project_manager_user_id': ids['pm'],
    'project_regime': 'private', 'investment_subtype': 'private',
}, headers=headers['manager'])
check('creation validates classification dimensions before writing',
      invalid_create.status_code == 400)

classification = {
    'project_regime': 'investment',
    'investment_subtype': 'private',
    'work_nature': 'construction',
    'contract_structure': 'investment_no_main_employer',
    'optional_field_states': {'client': 'not_applicable'},
}
for actor in ('manager', 'portfolio', 'pm', 'editor'):
    response = client.put(f"/api/v1/projects/{ids['project']}/classification",
                          json=classification, headers=headers[actor])
    check(f'{actor} may update project classification', response.status_code == 200)

readback = (client.get(f"/api/v1/projects/{ids['project']}", headers=headers['employee'])
            .get_json() or {}).get('project', {})
check('classification serializes independently and marks completion',
      readback.get('project_regime') == 'investment' and
      readback.get('investment_subtype') == 'private' and
      readback.get('work_nature') == 'construction' and
      readback.get('contract_structure') == 'investment_no_main_employer' and
      readback.get('classification_complete') is True)
check('explicit not-applicable employer state round-trips',
      readback.get('optional_field_states', {}).get('client') == 'not_applicable')

unauthorized = client.put(f"/api/v1/projects/{ids['project']}/classification",
                          json=classification, headers=headers['employee'])
foreign = client.put(f"/api/v1/projects/{ids['project']}/classification",
                     json=classification, headers=headers['foreign'])
closed = client.put(f"/api/v1/projects/{ids['closed']}/classification",
                    json=classification, headers=headers['manager'])
check('ordinary employees cannot update classification', unauthorized.status_code == 403)
check('cross-company classification updates are hidden', foreign.status_code == 404)
check('closed projects reject classification updates', closed.status_code == 409)

invalid = client.put(f"/api/v1/projects/{ids['project']}/classification", json={
    'project_regime': 'private', 'investment_subtype': 'private',
    'work_nature': 'construction', 'contract_structure': 'independent',
}, headers=headers['manager'])
check('investment subtype is rejected outside investment regime', invalid.status_code == 400)

warnings = client.get(f"/api/v1/projects/{ids['project']}/warnings", headers=headers['employee'])
warning_keys = {row['key'] for row in (warnings.get_json() or {}).get('warnings', [])}
check('not-applicable employer suppresses the employer warning',
      warnings.status_code == 200 and 'missing_client' not in warning_keys)

client.put(f"/api/v1/projects/{ids['project']}/classification", json={
    **classification, 'optional_field_states': {'client': 'missing'},
}, headers=headers['manager'])
warnings = client.get(f"/api/v1/projects/{ids['project']}/warnings", headers=headers['employee'])
warning_keys = {row['key'] for row in (warnings.get_json() or {}).get('warnings', [])}
check('missing employer produces a contextual project warning', 'missing_client' in warning_keys)

dismissed = client.put(f"/api/v1/projects/{ids['project']}/warnings/missing_client/dismiss",
                       headers=headers['pm'])
after_dismiss = client.get(f"/api/v1/projects/{ids['project']}/warnings",
                           headers=headers['employee'])
check('effective project manager may dismiss a project-wide warning', dismissed.status_code == 200)
check('dismissed warning stays hidden project-wide',
      'missing_client' not in {r['key'] for r in (after_dismiss.get_json() or {}).get('warnings', [])})
same_classification = client.put(f"/api/v1/projects/{ids['project']}/classification", json={
    **classification, 'optional_field_states': {'client': 'missing'},
}, headers=headers['manager'])
after_same_save = client.get(f"/api/v1/projects/{ids['project']}/warnings",
                             headers=headers['employee'])
check('unchanged classification does not resurface a dismissed warning',
      same_classification.status_code == 200 and
      'missing_client' not in {r['key'] for r in (after_same_save.get_json() or {}).get('warnings', [])})
check('ordinary employee cannot dismiss project warnings', client.put(
    f"/api/v1/projects/{ids['project']}/warnings/missing_client/dismiss",
    headers=headers['employee']).status_code == 403)

client.put(f"/api/v1/projects/{ids['project']}", json={'client': 'Home owner'},
           headers=headers['pm'])
client.put(f"/api/v1/projects/{ids['project']}", json={'client': ''},
           headers=headers['pm'])
resurfaced = client.get(f"/api/v1/projects/{ids['project']}/warnings",
                        headers=headers['employee'])
check('warning resurfaces after the relevant condition genuinely changes',
      'missing_client' in {r['key'] for r in (resurfaced.get_json() or {}).get('warnings', [])})

with app.app_context():
    actions = {row.action_type for row in AuditLog.query.filter_by(project_id=ids['project']).all()}
    check('classification and warning dismissal are audited',
          {'project.classification_updated', 'project.warning_dismissed'} <= actions)
    check('warning dismissal remains tenant and project scoped',
          ProjectWarningDismissal.query.filter_by(project_id=ids['project'],
                                                   warning_key='missing_client').count() == 0)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
