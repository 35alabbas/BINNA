#!/usr/bin/env python3
"""Focused Phase 1A backend permission regression test.

This script refuses to run unless DATABASE_URL names a pre-created temporary
SQLite file outside the repository's real ``instance`` directory.
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path


def _verified_test_database() -> Path:
    url = os.environ.get('DATABASE_URL', '')
    marker = os.environ.get('BINNA_ISOLATED_TEST_DB')
    if marker != '1' or not url.startswith('sqlite:///'):
        raise RuntimeError('Refusing to run without an explicitly isolated SQLite database')

    db_path = Path(url[len('sqlite:///'):]).resolve()
    instance_dir = (Path(__file__).resolve().parent / 'instance').resolve()
    try:
        db_path.relative_to(instance_dir)
    except ValueError:
        pass
    else:
        raise RuntimeError('Refusing to use a database inside C:\\BINNA\\instance')

    if not db_path.is_file() or db_path.stat().st_size != 0:
        raise RuntimeError('Test database must be a newly created empty file')
    return db_path


TEST_DB_PATH = _verified_test_database()

from flask_jwt_extended import create_access_token  # noqa: E402

from app import create_app, db  # noqa: E402
from app.models import (  # noqa: E402
    Company,
    DCLetter,
    FinancialData,
    PERMISSION_MODULES,
    Project,
    ProjectMember,
    User,
    _now,
)


app = create_app('development')
client = app.test_client()


def permission_map(**overrides):
    result = {module: {'view': True, 'edit': True} for module in PERMISSION_MODULES}
    result.update(overrides)
    return json.dumps(result)


with app.app_context():
    db.create_all()

    company_a = Company(
        name='Alpha', slug='alpha', status='trial',
        trial_ends_at=_now() + timedelta(days=14),
    )
    company_b = Company(
        name='Beta', slug='beta', status='trial',
        trial_ends_at=_now() + timedelta(days=14),
    )
    db.session.add_all([company_a, company_b])
    db.session.flush()

    owner = User(
        username='owner', email='owner@alpha.test', password_hash='unused',
        company_id=company_a.id, company_role='owner', email_verified=True,
    )
    employee = User(
        username='employee', email='employee@alpha.test', password_hash='unused',
        company_id=company_a.id, company_role='member', email_verified=True,
    )
    outsider = User(
        username='outsider', email='outsider@beta.test', password_hash='unused',
        company_id=company_b.id, company_role='owner', email_verified=True,
    )
    db.session.add_all([owner, employee, outsider])
    db.session.flush()

    editable = Project(company_id=company_a.id, code='EDIT', name='Editable', created_by=owner.id)
    readonly = Project(company_id=company_a.id, code='READ', name='Read only', created_by=owner.id)
    hidden = Project(company_id=company_a.id, code='HIDE', name='Hidden project', created_by=owner.id)
    legacy = Project(company_id=company_a.id, code='OLD', name='Legacy permissions', created_by=owner.id)
    foreign = Project(company_id=company_b.id, code='BETA', name='Beta project', created_by=outsider.id)
    db.session.add_all([editable, readonly, hidden, legacy, foreign])
    db.session.flush()

    db.session.add_all([
        ProjectMember(company_id=company_a.id, project_id=editable.id, user_id=owner.id, role='owner'),
        ProjectMember(company_id=company_a.id, project_id=readonly.id, user_id=owner.id, role='owner'),
        ProjectMember(company_id=company_a.id, project_id=hidden.id, user_id=owner.id, role='owner'),
        ProjectMember(company_id=company_a.id, project_id=legacy.id, user_id=owner.id, role='owner'),
        ProjectMember(company_id=company_b.id, project_id=foreign.id, user_id=outsider.id, role='owner'),
        ProjectMember(
            company_id=company_a.id, project_id=editable.id, user_id=employee.id, role='member',
            permissions=permission_map(),
        ),
        ProjectMember(
            company_id=company_a.id, project_id=readonly.id, user_id=employee.id, role='member',
            permissions=permission_map(
                financial={'view': True, 'edit': False},
                dc={'view': False, 'edit': False},
            ),
        ),
        ProjectMember(
            company_id=company_a.id, project_id=hidden.id, user_id=employee.id, role='member',
            permissions=permission_map(projects={'view': False, 'edit': False}),
        ),
        ProjectMember(
            company_id=company_a.id, project_id=legacy.id, user_id=employee.id, role='member',
            permissions='{}',
        ),
    ])
    db.session.add_all([
        FinancialData(
            company_id=company_a.id, project_id=editable.id, updated_by=owner.id,
            data=json.dumps({'payments': [{'id': 1}], 'income': [], 'expenses': []}),
        ),
        FinancialData(
            company_id=company_a.id, project_id=readonly.id, updated_by=owner.id,
            data=json.dumps({'payments': [{'id': 2}], 'income': [], 'expenses': []}),
        ),
        DCLetter(
            company_id=company_a.id, project_id=readonly.id, created_by=owner.id,
            code='READ-LetterIN-001', direction='incoming', subject='private count',
            from_party='Client', to_party='Contractor', letter_date=date(2026, 1, 1),
        ),
    ])
    db.session.commit()

    employee_headers = {'Authorization': 'Bearer ' + create_access_token(identity=str(employee.id))}
    owner_headers = {'Authorization': 'Bearer ' + create_access_token(identity=str(owner.id))}
    outsider_headers = {'Authorization': 'Bearer ' + create_access_token(identity=str(outsider.id))}
    editable_id, readonly_id, hidden_id, legacy_id, foreign_id = (
        editable.id, readonly.id, hidden.id, legacy.id, foreign.id,
    )


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
print('Phase 1A module access')

# Permitted viewing and editing in project 1.
financial_1 = f'/api/v1/projects/{editable_id}/financial'
check('permitted viewing returns 200', client.get(financial_1, headers=employee_headers).status_code == 200)
check('permitted editing returns 200', client.put(
    financial_1, json={'data': {'payments': []}}, headers=employee_headers,
).status_code == 200)

# Same employee, different permissions in project 2.
financial_2 = f'/api/v1/projects/{readonly_id}/financial'
check('view-only permission still returns 200', client.get(financial_2, headers=employee_headers).status_code == 200)
check('view-only permission blocks editing', client.put(
    financial_2, json={'data': {'payments': []}}, headers=employee_headers,
).status_code == 403)
check('blocked module view returns 404', client.get(
    f'/api/v1/projects/{readonly_id}/dc', headers=employee_headers,
).status_code == 404)

# Project-module view applies to list and direct project metadata.
listed = client.get('/api/v1/projects', headers=employee_headers).get_json()['projects']
listed_ids = {row['id'] for row in listed}
check('project without projects.view is hidden from project list', hidden_id not in listed_ids)
check('project without projects.view blocks direct project metadata', client.get(
    f'/api/v1/projects/{hidden_id}', headers=employee_headers,
).status_code == 404)
check('legacy empty permission map keeps role-default project access', legacy_id in listed_ids)
check('project owner keeps full access despite stored restrictions', client.get(
    f'/api/v1/projects/{hidden_id}', headers=owner_headers,
).status_code == 200)

# Dashboard response keeps its keys but masks values from modules without view.
stats_response = client.get(f'/api/v1/projects/{readonly_id}/stats', headers=employee_headers)
stats = stats_response.get_json()['stats'] if stats_response.status_code == 200 else {}
check('dashboard stats response remains available', stats_response.status_code == 200)
check('dashboard preserves all established statistic keys', set(stats) == {
    'dc', 'dr', 'lbt', 'dwg', 'fir', 'mir', 'ms', 'rfi',
    'financial', 'cashflow', 'certified', 'received', 'gantt', 'subcontracts',
})
check('dashboard keeps existing dc key while masking its value', 'dc' in stats and stats['dc'] == 0)
check('dashboard keeps visible financial stats', stats.get('financial') == 1)

# A second tenant cannot use its token against either project in company A.
check('cross-company viewing is blocked', client.get(
    financial_1, headers=outsider_headers,
).status_code in (403, 404))
check('cross-company editing is blocked', client.put(
    financial_1, json={'data': {}}, headers=outsider_headers,
).status_code in (403, 404))
check('second company can access its own project', client.get(
    f'/api/v1/projects/{foreign_id}', headers=outsider_headers,
).status_code == 200)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
