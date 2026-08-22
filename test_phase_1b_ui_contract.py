#!/usr/bin/env python3
"""Phase 1B-3 UI response contract on an isolated SQLite database."""
import os
import sys
import json
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
from app.models import Company, FinancialData, Project, ProjectMember, User  # noqa: E402


app = create_app('development')
with app.app_context():
    db.create_all()
    company = Company(name='UI Contract Co', slug='ui-contract', status='trial')
    db.session.add(company)
    db.session.flush()
    owner = User(username='owner', email='owner@ui.test', password_hash='x',
                 company_id=company.id, company_role='owner', email_verified=True)
    portfolio = User(username='portfolio', email='portfolio@ui.test', password_hash='x',
                     company_id=company.id, company_role='member', email_verified=True)
    pm = User(username='pm', email='pm@ui.test', password_hash='x',
              company_id=company.id, company_role='member', email_verified=True)
    employee = User(username='employee', email='employee@ui.test', password_hash='x',
                    company_id=company.id, company_role='member', email_verified=True)
    db.session.add_all([owner, portfolio, pm, employee])
    db.session.flush()
    company.projects_manager_user_id = portfolio.id
    project = Project(company_id=company.id, code='UI', name='UI Project', status='completed',
                      created_by=owner.id, project_manager_user_id=pm.id,
                      is_closed=True, closed_by_user_id=owner.id)
    db.session.add(project)
    db.session.flush()
    db.session.add_all([
        ProjectMember(company_id=company.id, project_id=project.id, user_id=owner.id,
                      role='owner', permissions='{}'),
        ProjectMember(company_id=company.id, project_id=project.id, user_id=pm.id,
                      role='viewer', permissions='{}'),
        ProjectMember(company_id=company.id, project_id=project.id, user_id=employee.id,
                      role='member', permissions=json.dumps({
                          'financial': {'view': False, 'edit': False},
                      })),
        FinancialData(company_id=company.id, project_id=project.id, updated_by=owner.id,
                      data=json.dumps({
                          'currency': 'IQD',
                          'contractDetails': {
                              'contract-value': '1250000000',
                              'date': '2026-01-15',
                              'contract-end': '2027-03-31',
                              'period': '440',
                          },
                          'cashflowSummary': {
                              'totalCertified': 240000000,
                              'totalReceived': 180000000,
                          },
                      })),
    ])
    db.session.commit()
    ids = {'owner': owner.id, 'portfolio': portfolio.id, 'pm': pm.id,
           'employee': employee.id, 'project': project.id}
    tokens = {name: create_access_token(identity=str(ids[name]))
              for name in ('owner', 'portfolio', 'pm', 'employee')}


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
print('Phase 1B-3 UI API contract')

owner_me = (client.get('/api/v1/auth/me', headers=headers['owner']).get_json() or {})
portfolio_me = (client.get('/api/v1/auth/me', headers=headers['portfolio']).get_json() or {})
check('auth response identifies effective company manager',
      owner_me.get('user', {}).get('is_company_manager') is True)
check('auth response identifies designated projects manager',
      portfolio_me.get('user', {}).get('is_projects_manager') is True)

company_data = (client.get('/api/v1/company', headers=headers['owner']).get_json() or {})
check('company response exposes designated projects manager',
      company_data.get('company', {}).get('projects_manager_user_id') == ids['portfolio'])
check('company response exposes migration readiness',
      company_data.get('phase_1b_ready') is True and company_data.get('phase_1b_2_ready') is True)

members_data = (client.get('/api/v1/company/members', headers=headers['owner']).get_json() or {})
member_by_id = {row['id']: row for row in members_data.get('members', [])}
check('company member rows expose effective business roles',
      member_by_id.get(ids['owner'], {}).get('is_company_manager') is True and
      member_by_id.get(ids['portfolio'], {}).get('is_projects_manager') is True)

portfolio_projects = (client.get('/api/v1/projects', headers=headers['portfolio']).get_json() or {})
portfolio_row = (portfolio_projects.get('projects') or [{}])[0]
check('project list exposes manager and independent lifecycle state',
      portfolio_row.get('project_manager_user_id') == ids['pm'] and
      portfolio_row.get('status') == 'completed' and portfolio_row.get('is_closed') is True)
check('projects manager receives lifecycle and assignment capabilities',
      portfolio_row.get('capabilities', {}).get('manage_lifecycle') is True and
      portfolio_row.get('capabilities', {}).get('manage_assignments') is True and
      portfolio_row.get('capabilities', {}).get('add_monitoring_comment') is True)

pm_project = (client.get(f"/api/v1/projects/{ids['project']}", headers=headers['pm']).get_json() or {})
pm_caps = pm_project.get('project', {}).get('capabilities', {})
check('designated project manager can read management records but not lifecycle controls',
      pm_caps.get('read_management_records') is True and
      pm_caps.get('manage_lifecycle') is False and
      pm_caps.get('add_monitoring_comment') is False)
check('closed project disables operational edits in UI metadata',
      pm_caps.get('edit_operational') is False)

closed_permissions = client.get(
    f"/api/v1/projects/{ids['project']}/permissions", headers=headers['portfolio'],
)
check('authorized manager can still read permissions on a closed project',
      closed_permissions.status_code == 200 and
      len((closed_permissions.get_json() or {}).get('members', [])) == 3)

employee_project = (client.get(f"/api/v1/projects/{ids['project']}", headers=headers['employee']).get_json() or {})
employee_caps = employee_project.get('project', {}).get('capabilities', {})
check('ordinary employee receives no management-record capability',
      employee_caps.get('read_management_records') is False)

pm_overview_response = client.get(
    f"/api/v1/projects/{ids['project']}/overview", headers=headers['pm'],
)
pm_overview = (pm_overview_response.get_json() or {}).get('overview', {})
check('overview exposes only authoritative recorded project values',
      pm_overview_response.status_code == 200 and
      pm_overview.get('contract_value') == 1250000000 and
      pm_overview.get('currency') == 'IQD' and
      pm_overview.get('contract_date') == '2026-01-15' and
      pm_overview.get('contract_completion_date') == '2027-03-31' and
      pm_overview.get('contract_duration_days') == 440 and
      pm_overview.get('received_owner_payments') == 180000000 and
      pm_overview.get('employee_count') == 3)
check('undefined progress cash and alerts remain explicitly unavailable',
      pm_overview.get('financial_progress') is None and
      pm_overview.get('schedule_progress') is None and
      pm_overview.get('project_cash_position') is None and
      pm_overview.get('alert_count') is None)

employee_overview = (client.get(
    f"/api/v1/projects/{ids['project']}/overview", headers=headers['employee'],
).get_json() or {}).get('overview', {})
check('financial overview values follow existing module permissions',
      employee_overview.get('contract_value') is None and
      employee_overview.get('received_owner_payments') is None and
      employee_overview.get('employee_count') == 3)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
