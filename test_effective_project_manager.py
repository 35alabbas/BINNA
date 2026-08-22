#!/usr/bin/env python3
"""Effective operational project-manager hierarchy regression tests."""
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
from app.models import (  # noqa: E402
    Company, PERMISSION_MODULES, Project, ProjectMember, User, _now,
)
from app.tenancy import (  # noqa: E402
    ProjectClosedError, authorize_project_access, phase_1b_2_schema_status,
    phase_1b_schema_status,
)


app = create_app('development')
client = app.test_client()


def headers(user_id):
    with app.app_context():
        token = create_access_token(identity=str(user_id))
    return {'Authorization': 'Bearer ' + token}


with app.app_context():
    db.create_all()
    phase_1b_schema_status.cache_clear()
    phase_1b_2_schema_status.cache_clear()
    companies = [
        Company(name=name, slug=name.lower(), status='trial',
                trial_ends_at=_now() + timedelta(days=14))
        for name in ('Fallback', 'Portfolio', 'Explicit', 'Foreign')
    ]
    db.session.add_all(companies)
    db.session.flush()
    fallback_company, portfolio_company, explicit_company, foreign_company = companies

    fallback_manager = User(
        username='fallback-manager', email='fallback@test', password_hash='unused',
        company_id=fallback_company.id, company_role='owner', email_verified=True,
    )
    portfolio_owner = User(
        username='portfolio-owner', email='portfolio-owner@test', password_hash='unused',
        company_id=portfolio_company.id, company_role='owner', email_verified=True,
    )
    projects_manager = User(
        username='projects-manager', email='projects@test', password_hash='unused',
        company_id=portfolio_company.id, company_role='member', email_verified=True,
    )
    explicit_owner = User(
        username='explicit-owner', email='explicit-owner@test', password_hash='unused',
        company_id=explicit_company.id, company_role='owner', email_verified=True,
    )
    explicit_manager = User(
        username='explicit-manager', email='explicit-manager@test', password_hash='unused',
        company_id=explicit_company.id, company_role='member', email_verified=True,
    )
    employee = User(
        username='employee', email='employee@test', password_hash='unused',
        company_id=fallback_company.id, company_role='member', email_verified=True,
    )
    outsider = User(
        username='outsider', email='outsider@test', password_hash='unused',
        company_id=foreign_company.id, company_role='owner', email_verified=True,
    )
    db.session.add_all([
        fallback_manager, portfolio_owner, projects_manager, explicit_owner,
        explicit_manager, employee, outsider,
    ])
    db.session.flush()
    portfolio_company.projects_manager_user_id = projects_manager.id

    fallback_project = Project(
        company_id=fallback_company.id, code='FALL', name='Fallback project',
        created_by=fallback_manager.id,
    )
    portfolio_project = Project(
        company_id=portfolio_company.id, code='PORT', name='Portfolio project',
        created_by=portfolio_owner.id,
    )
    explicit_project = Project(
        company_id=explicit_company.id, code='EXPL', name='Explicit project',
        created_by=explicit_owner.id, project_manager_user_id=explicit_manager.id,
    )
    closed_project = Project(
        company_id=fallback_company.id, code='CLOS', name='Closed project',
        created_by=fallback_manager.id, is_closed=True,
    )
    db.session.add_all([fallback_project, portfolio_project, explicit_project, closed_project])
    db.session.flush()
    employee_permissions = {
        module: {'view': True, 'edit': False} for module in PERMISSION_MODULES
    }
    employee_permissions['financial'] = {'view': True, 'edit': True}
    db.session.add(ProjectMember(
        company_id=fallback_company.id, project_id=fallback_project.id,
        user_id=employee.id, role='member', permissions=json.dumps(employee_permissions),
    ))
    db.session.commit()
    ids = {
        'fallback_manager': fallback_manager.id,
        'projects_manager': projects_manager.id,
        'explicit_manager': explicit_manager.id,
        'employee': employee.id,
        'outsider': outsider.id,
        'fallback_project': fallback_project.id,
        'portfolio_project': portfolio_project.id,
        'explicit_project': explicit_project.id,
        'closed_project': closed_project.id,
    }


passed = failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print('  ok   ' + name)
    else:
        failed += 1
        print('  FAIL ' + name)


def create_letter(project_id, user_id, subject):
    return client.post(
        f'/api/v1/projects/{project_id}/dc', headers=headers(user_id),
        json={
            'direction': 'incoming', 'subject': subject,
            'from_party': 'Client', 'to_party': 'Contractor',
            'letter_date': '2026-08-22',
        },
    )


def edit_financial(project_id, user_id):
    return client.put(
        f'/api/v1/projects/{project_id}/financial', headers=headers(user_id),
        json={'data': {'payments': [], 'income': [], 'expenses': []}},
    )


print(f'ISOLATED_DATABASE={TEST_DB_PATH}')
print('Effective operational project manager')

fallback_letter = create_letter(ids['fallback_project'], ids['fallback_manager'], 'Fallback authority')
check('company manager without higher assignment creates Document Control letter',
      fallback_letter.status_code == 201)
check('company manager without higher assignment edits another operational module',
      edit_financial(ids['fallback_project'], ids['fallback_manager']).status_code == 200)

portfolio_letter = create_letter(ids['portfolio_project'], ids['projects_manager'], 'Interim authority')
check('assigned projects manager is interim operational manager', portfolio_letter.status_code == 201)
check('interim projects manager edits another operational module',
      edit_financial(ids['portfolio_project'], ids['projects_manager']).status_code == 200)

explicit_letter = create_letter(ids['explicit_project'], ids['explicit_manager'], 'Explicit authority')
check('explicit project manager creates Document Control letter', explicit_letter.status_code == 201)
check('explicit project manager edits another operational module',
      edit_financial(ids['explicit_project'], ids['explicit_manager']).status_code == 200)

with app.app_context():
    all_modules_allowed = all(
        authorize_project_access(
            ids['fallback_project'], ids['fallback_manager'], module, 'edit', 'member'
        )[2]
        for module in PERMISSION_MODULES
    )
check('effective manager has edit authorization for every project module', all_modules_allowed)

check('ordinary employee keeps granted financial edit permission',
      edit_financial(ids['fallback_project'], ids['employee']).status_code == 200)
check('ordinary employee remains blocked from ungranted Document Control editing',
      create_letter(ids['fallback_project'], ids['employee'], 'Denied').status_code == 403)
check('cross-company operational access remains hidden',
      create_letter(ids['fallback_project'], ids['outsider'], 'Foreign').status_code == 404)
check('closed project blocks effective manager operational edits',
      edit_financial(ids['closed_project'], ids['fallback_manager']).status_code == 409)

project_response = client.get(
    f'/api/v1/projects/{ids["fallback_project"]}', headers=headers(ids['fallback_manager']),
)
project_data = (project_response.get_json() or {}).get('project') or {}
check('frontend capability metadata grants effective operational editing',
      project_response.status_code == 200 and
      project_data.get('capabilities', {}).get('edit_operational') is True and
      all(p.get('edit') is True for p in project_data.get('my_permissions', {}).values()))

closed_response = client.get(
    f'/api/v1/projects/{ids["closed_project"]}', headers=headers(ids['fallback_manager']),
)
closed_data = (closed_response.get_json() or {}).get('project') or {}
check('frontend capability metadata marks closed project read-only',
      closed_response.status_code == 200 and
      closed_data.get('capabilities', {}).get('edit_operational') is False and
      all(p.get('edit') is False for p in closed_data.get('my_permissions', {}).values()))

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
