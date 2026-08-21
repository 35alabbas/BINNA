#!/usr/bin/env python3
r"""Focused Phase 1B-1 business-role and project-manager regression test.

Refuses to run unless DATABASE_URL points to a newly-created empty SQLite file
outside C:\BINNA\instance.  It never imports run.py or applies migrations.
"""
import json
import os
import sys
from datetime import timedelta
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
from app.models import Company, FinancialData, Project, ProjectMember, User, _now  # noqa: E402


app = create_app('development')
client = app.test_client()


def headers(user_id):
    with app.app_context():
        token = create_access_token(identity=str(user_id))
    return {'Authorization': 'Bearer ' + token}


with app.app_context():
    db.create_all()
    alpha = Company(
        name='Alpha', slug='alpha', status='trial',
        trial_ends_at=_now() + timedelta(days=14),
    )
    beta = Company(
        name='Beta', slug='beta', status='trial',
        trial_ends_at=_now() + timedelta(days=14),
    )
    db.session.add_all([alpha, beta])
    db.session.flush()

    owner = User(
        username='owner', email='owner@alpha.test', password_hash='unused',
        company_id=alpha.id, company_role='owner', email_verified=True,
    )
    portfolio = User(
        username='portfolio', email='portfolio@alpha.test', password_hash='unused',
        company_id=alpha.id, company_role='member', email_verified=True,
    )
    employee = User(
        username='employee', email='employee@alpha.test', password_hash='unused',
        company_id=alpha.id, company_role='member', email_verified=True,
    )
    explicit_pm = User(
        username='pm', email='pm@alpha.test', password_hash='unused',
        company_id=alpha.id, company_role='member', email_verified=True,
    )
    outsider = User(
        username='outsider', email='outsider@beta.test', password_hash='unused',
        company_id=beta.id, company_role='owner', email_verified=True,
    )
    db.session.add_all([owner, portfolio, employee, explicit_pm, outsider])
    db.session.flush()

    # A legacy project deliberately has no Phase 1B manager assignment.
    legacy = Project(
        company_id=alpha.id, code='OLD', name='Legacy project', created_by=owner.id,
    )
    db.session.add(legacy)
    db.session.flush()
    legacy_member = ProjectMember(
        company_id=alpha.id, project_id=legacy.id, user_id=employee.id,
        role='member', permissions=json.dumps({
            'financial': {'view': True, 'edit': True},
        }),
    )
    db.session.add(legacy_member)
    db.session.add(FinancialData(
        company_id=alpha.id, project_id=legacy.id, updated_by=owner.id,
        data=json.dumps({'payments': [], 'income': [], 'expenses': []}),
    ))
    db.session.commit()

    ids = {
        'alpha': alpha.id, 'beta': beta.id, 'owner': owner.id,
        'portfolio': portfolio.id, 'employee': employee.id,
        'explicit_pm': explicit_pm.id, 'outsider': outsider.id,
        'legacy': legacy.id, 'legacy_member': legacy_member.id,
    }


owner_h = headers(ids['owner'])
portfolio_h = headers(ids['portfolio'])
employee_h = headers(ids['employee'])
pm_h = headers(ids['explicit_pm'])
outsider_h = headers(ids['outsider'])

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
print('Phase 1B-1 business roles')

# Existing owner is a company manager without rewriting the user row.
owner_as_portfolio = client.put(
    '/api/v1/company/projects-manager',
    json={'user_id': ids['owner']}, headers=owner_h,
)
check('company manager may also serve as projects manager',
      owner_as_portfolio.status_code == 200)
assign_portfolio = client.put(
    '/api/v1/company/projects-manager',
    json={'user_id': ids['portfolio']}, headers=owner_h,
)
check('legacy company owner can designate projects manager', assign_portfolio.status_code == 200)
with app.app_context():
    owner_row = db.session.get(User, ids['owner'])
    check('legacy owner row is not rewritten',
          getattr(owner_row, 'is_company_manager', None) is False)

# Employee cannot create; portfolio manager can create with automatic interim PM.
denied_create = client.post(
    '/api/v1/projects', json={'code': 'NO', 'name': 'Denied'}, headers=employee_h,
)
check('ordinary employee cannot create projects', denied_create.status_code == 403)

interim_create = client.post(
    '/api/v1/projects', json={'code': 'INT', 'name': 'Interim'}, headers=portfolio_h,
)
check('projects manager can create a project', interim_create.status_code == 201)
interim_body = interim_create.get_json() or {}
interim_id = (interim_body.get('project') or {}).get('id')
with app.app_context():
    interim = db.session.get(Project, interim_id) if interim_id else None
    check('projects manager becomes interim project manager',
          interim is not None and
          getattr(interim, 'project_manager_user_id', None) == ids['portfolio'])

# Company manager may select an explicit manager, including safe membership creation.
explicit_create = client.post(
    '/api/v1/projects',
    json={'code': 'EXP', 'name': 'Explicit', 'project_manager_user_id': ids['explicit_pm']},
    headers=owner_h,
)
check('company manager can create with explicit project manager', explicit_create.status_code == 201)
explicit_id = ((explicit_create.get_json() or {}).get('project') or {}).get('id')
with app.app_context():
    explicit = db.session.get(Project, explicit_id) if explicit_id else None
    pm_membership = ProjectMember.query.filter_by(
        project_id=explicit_id, user_id=ids['explicit_pm'],
    ).first() if explicit_id else None
    check('explicit project manager is stored once',
          explicit is not None and
          getattr(explicit, 'project_manager_user_id', None) == ids['explicit_pm'])
    check('manager receives a safe membership when absent',
          pm_membership is not None and pm_membership.role == 'viewer')

# Tenant isolation applies to assignment and reassignment.
foreign_assignment = client.put(
    f'/api/v1/projects/{explicit_id}/project-manager',
    json={'user_id': ids['outsider']}, headers=portfolio_h,
)
check('cross-company manager assignment is rejected', foreign_assignment.status_code == 404)

reassign = client.put(
    f'/api/v1/projects/{explicit_id}/project-manager',
    json={'user_id': ids['employee']}, headers=portfolio_h,
)
check('projects manager can safely replace project manager', reassign.status_code == 200)
with app.app_context():
    explicit = db.session.get(Project, explicit_id)
    old_pm = ProjectMember.query.filter_by(
        project_id=explicit_id, user_id=ids['explicit_pm'],
    ).first()
    check('reassignment changes only the designated manager',
          getattr(explicit, 'project_manager_user_id', None) == ids['employee'])
    check('previous manager membership is preserved',
          old_pm is not None and old_pm.role == 'viewer')

# Portfolio managers monitor but cannot edit operations; assigned manager can.
check('projects manager can monitor project financial data', client.get(
    f'/api/v1/projects/{explicit_id}/financial', headers=portfolio_h,
).status_code == 200)
check('projects manager cannot edit project financial data', client.put(
    f'/api/v1/projects/{explicit_id}/financial', json={'data': {}}, headers=portfolio_h,
).status_code == 403)
check('assigned project manager can edit project financial data', client.put(
    f'/api/v1/projects/{explicit_id}/financial', json={'data': {}}, headers=employee_h,
).status_code == 200)

portfolio_membership = client.post(
    f'/api/v1/projects/{explicit_id}/members',
    json={'email': 'portfolio@alpha.test', 'role': 'member'}, headers=portfolio_h,
)
portfolio_member_id = ((portfolio_membership.get_json() or {}).get('member') or {}).get('id')
grant_portfolio = client.put(
    f'/api/v1/projects/{explicit_id}/members/{portfolio_member_id}/permissions',
    json={'permissions': {'financial': {'view': True, 'edit': True}}},
    headers=portfolio_h,
) if portfolio_member_id else None
check('projects manager can receive explicit operational permission',
      portfolio_membership.status_code == 201 and
      grant_portfolio is not None and grant_portfolio.status_code == 200)
check('explicit permission allows projects manager operational editing', client.put(
    f'/api/v1/projects/{explicit_id}/financial', json={'data': {}}, headers=portfolio_h,
).status_code == 200)

# Explicit legacy operational permissions remain effective and legacy manager stays NULL.
check('legacy member keeps explicit operational editing', client.put(
    f'/api/v1/projects/{ids["legacy"]}/financial', json={'data': {}}, headers=employee_h,
).status_code == 200)
with app.app_context():
    legacy = db.session.get(Project, ids['legacy'])
    check('legacy project is not silently assigned a manager',
          getattr(legacy, 'project_manager_user_id', None) is None)

# Outsider remains isolated; platform role is untouched.
check('cross-company project monitoring is denied', client.get(
    f'/api/v1/projects/{explicit_id}/financial', headers=outsider_h,
).status_code in (403, 404))
with app.app_context():
    check('platform roles remain unchanged',
          db.session.get(User, ids['owner']).role == 'user' and
          db.session.get(User, ids['outsider']).role == 'user')

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
