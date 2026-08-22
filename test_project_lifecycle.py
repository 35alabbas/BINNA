#!/usr/bin/env python3
"""Phase 1B-2 lifecycle regression tests on an isolated SQLite database."""
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
from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402
from app.models import Company, FinancialData, Project, ProjectMember, User  # noqa: E402


app = create_app('development')
with app.app_context():
    db.create_all()
    alpha = Company(name='Alpha', slug='alpha', status='trial')
    beta = Company(name='Beta', slug='beta', status='trial')
    db.session.add_all([alpha, beta])
    db.session.flush()

    owner = User(username='owner', email='owner@alpha.test', password_hash='unused',
                 company_id=alpha.id, company_role='owner', email_verified=True)
    portfolio = User(username='portfolio', email='portfolio@alpha.test', password_hash='unused',
                     company_id=alpha.id, company_role='member', email_verified=True)
    pm = User(username='pm', email='pm@alpha.test', password_hash='unused',
              company_id=alpha.id, company_role='member', email_verified=True)
    employee = User(username='employee', email='employee@alpha.test', password_hash='unused',
                    company_id=alpha.id, company_role='member', email_verified=True)
    foreign = User(username='foreign', email='foreign@beta.test', password_hash='unused',
                   company_id=beta.id, company_role='owner', email_verified=True)
    db.session.add_all([owner, portfolio, pm, employee, foreign])
    db.session.flush()
    alpha.projects_manager_user_id = portfolio.id

    project = Project(company_id=alpha.id, code='LC', name='Lifecycle', status='on-hold',
                      created_by=owner.id, project_manager_user_id=pm.id)
    db.session.add(project)
    db.session.flush()
    db.session.add_all([
        ProjectMember(company_id=alpha.id, project_id=project.id, user_id=owner.id,
                      role='owner', permissions='{}'),
        ProjectMember(company_id=alpha.id, project_id=project.id, user_id=pm.id,
                      role='viewer', permissions='{}'),
        ProjectMember(company_id=alpha.id, project_id=project.id, user_id=employee.id,
                      role='member', permissions='{}'),
        FinancialData(company_id=alpha.id, project_id=project.id, data=json.dumps({}),
                      updated_by=owner.id),
    ])
    db.session.commit()
    ids = {name: obj.id for name, obj in {
        'owner': owner, 'portfolio': portfolio, 'pm': pm,
        'employee': employee, 'foreign': foreign, 'project': project,
    }.items()}
    tokens = {name: create_access_token(identity=str(ids[name]))
              for name in ('owner', 'portfolio', 'pm', 'employee', 'foreign')}


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


pid = ids['project']
print(f'ISOLATED_DATABASE={TEST_DB_PATH}')
print('Phase 1B-2 project lifecycle')

check('project manager cannot close project', client.post(
    f'/api/v1/projects/{pid}/close', headers=headers['pm'],
).status_code == 403)
check('foreign company cannot close project', client.post(
    f'/api/v1/projects/{pid}/close', headers=headers['foreign'],
).status_code == 404)
closed = client.post(f'/api/v1/projects/{pid}/close', headers=headers['portfolio'])
check('projects manager can close project', closed.status_code == 200)
check('closure leaves operational status unchanged',
      closed.status_code == 200 and closed.get_json()['project']['status'] == 'on-hold')
check('closed project remains readable by member', client.get(
    f'/api/v1/projects/{pid}', headers=headers['employee'],
).status_code == 200)
blocked = client.put(
    f'/api/v1/projects/{pid}/financial', json={'data': {'income': [1]}},
    headers=headers['employee'],
)
check('closed project blocks operational financial write',
      blocked.status_code == 409 and (blocked.get_json() or {}).get('code') == 'project_closed')
check('closed project blocks membership changes', client.post(
    f'/api/v1/projects/{pid}/members', json={'email': 'portfolio@alpha.test'},
    headers=headers['portfolio'],
).status_code == 409)
check('project deletion is permanently disabled', client.delete(
    f'/api/v1/projects/{pid}', headers=headers['owner'],
).status_code == 409)

check('employee cannot add monitoring comment', client.post(
    f'/api/v1/projects/{pid}/monitoring-comments', json={'body': 'Employee note'},
    headers=headers['employee'],
).status_code == 403)
comment = client.post(
    f'/api/v1/projects/{pid}/monitoring-comments', json={'body': '  Closure reviewed.  '},
    headers=headers['owner'],
)
check('company manager can comment on closed project', comment.status_code == 201)
check('monitoring comment body is normalized', comment.status_code == 201 and
      comment.get_json()['comment']['body'] == 'Closure reviewed.')
check('project manager can read monitoring comments', client.get(
    f'/api/v1/projects/{pid}/monitoring-comments', headers=headers['pm'],
).status_code == 200)
check('ordinary employee cannot read monitoring comments', client.get(
    f'/api/v1/projects/{pid}/monitoring-comments', headers=headers['employee'],
).status_code == 403)
check('monitoring comments expose no update endpoint', client.put(
    f'/api/v1/projects/{pid}/monitoring-comments/1', json={'body': 'changed'},
    headers=headers['owner'],
).status_code in (404, 405))
check('monitoring comments expose no delete endpoint', client.delete(
    f'/api/v1/projects/{pid}/monitoring-comments/1', headers=headers['owner'],
).status_code in (404, 405))

audit = client.get(f'/api/v1/projects/{pid}/audit-logs', headers=headers['pm'])
check('project manager can read project audit', audit.status_code == 200)
actions = [row['action_type'] for row in (audit.get_json() or {}).get('audit_logs', [])]
check('closure audit is recorded', 'project.closed' in actions)
check('monitoring comment audit is not required', 'monitoring_comment.created' not in actions)
check('ordinary employee cannot read audit', client.get(
    f'/api/v1/projects/{pid}/audit-logs', headers=headers['employee'],
).status_code == 403)
company_audit = client.get('/api/v1/company/audit-logs', headers=headers['owner'])
check('company manager can read company-wide audit feed', company_audit.status_code == 200)
check('ordinary employee cannot read company-wide audit feed', client.get(
    '/api/v1/company/audit-logs', headers=headers['employee'],
).status_code == 403)
check('audit logs expose no update endpoint', client.put(
    f'/api/v1/projects/{pid}/audit-logs/1', json={}, headers=headers['owner'],
).status_code in (404, 405))
check('audit logs expose no delete endpoint', client.delete(
    f'/api/v1/projects/{pid}/audit-logs/1', headers=headers['owner'],
).status_code in (404, 405))

reopened = client.post(f'/api/v1/projects/{pid}/reopen', headers=headers['owner'])
check('company manager can reopen project', reopened.status_code == 200)
check('reopening preserves operational status', reopened.status_code == 200 and
      reopened.get_json()['project']['status'] == 'on-hold')
check('operational write works again after reopen', client.put(
    f'/api/v1/projects/{pid}/financial', json={'data': {'income': []}},
    headers=headers['employee'],
).status_code == 200)

manager_change = client.put(
    f'/api/v1/projects/{pid}/project-manager', json={'user_id': ids['employee']},
    headers=headers['portfolio'],
)
check('project manager replacement succeeds after reopen', manager_change.status_code == 200)
added = client.post(
    f'/api/v1/projects/{pid}/members',
    json={'email': 'portfolio@alpha.test', 'role': 'member'},
    headers=headers['portfolio'],
)
added_id = ((added.get_json() or {}).get('member') or {}).get('id')
check('project employee addition succeeds after reopen', added.status_code == 201)
permissions = client.put(
    f'/api/v1/projects/{pid}/members/{added_id}/permissions',
    json={'permissions': {'financial': {'view': True, 'edit': True}}},
    headers=headers['portfolio'],
) if added_id else None
check('project permission change succeeds after reopen',
      permissions is not None and permissions.status_code == 200)
removed = client.delete(
    f'/api/v1/projects/{pid}/members/{added_id}', headers=headers['portfolio'],
) if added_id else None
check('project employee removal succeeds after reopen',
      removed is not None and removed.status_code == 200)

created = client.post(
    '/api/v1/projects', json={'code': 'AUD', 'name': 'Audited creation'},
    headers=headers['owner'],
)
check('new project creation succeeds with audit schema', created.status_code == 201)
check('projects manager replacement succeeds with audit schema', client.put(
    '/api/v1/company/projects-manager', json={'user_id': ids['portfolio']},
    headers=headers['owner'],
).status_code == 200)

project_actions = [row['action_type'] for row in (client.get(
    f'/api/v1/projects/{pid}/audit-logs', headers=headers['owner'],
).get_json() or {}).get('audit_logs', [])]
check('manager replacement is audited', 'project.manager_assigned' in project_actions)
check('employee addition is audited', 'project.member_added' in project_actions)
check('employee removal is audited', 'project.member_removed' in project_actions)
check('permission change is audited', 'project.permissions_changed' in project_actions)
company_actions = [row['action_type'] for row in (client.get(
    '/api/v1/company/audit-logs', headers=headers['owner'],
).get_json() or {}).get('audit_logs', [])]
check('project creation is audited', 'project.created' in company_actions)
check('projects manager replacement is audited',
      'company.projects_manager_assigned' in company_actions)

with app.app_context():
    project_count = db.session.execute(text('SELECT COUNT(*) FROM projects WHERE id=:id'),
                                       {'id': pid}).scalar_one()
    member_count = db.session.execute(text(
        'SELECT COUNT(*) FROM project_members WHERE project_id=:id'), {'id': pid}).scalar_one()
check('closure and deletion endpoint preserve project record', project_count == 1)
check('closure preserves memberships', member_count == 3)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
