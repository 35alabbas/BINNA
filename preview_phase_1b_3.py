"""Safe local Phase 1B-3 demonstration server.

Requires an explicit SQLite DATABASE_URL outside the repository instance folder.
The database is recreated and seeded for demonstration use only.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


def _safe_database_path():
    url = os.environ.get('DATABASE_URL', '')
    if not url.startswith('sqlite:///'):
        raise SystemExit('DATABASE_URL must be an explicit sqlite:/// URL')
    parsed = urlparse(url)
    raw = unquote(parsed.path)
    if os.name == 'nt' and raw.startswith('/'):
        raw = raw[1:]
    target = Path(raw).resolve()
    protected = (Path(__file__).resolve().parent / 'instance').resolve()
    try:
        target.relative_to(protected)
        raise SystemExit('Refusing to use a database inside C:\\BINNA\\instance')
    except ValueError:
        pass
    if target.exists() and target.stat().st_size:
        raise SystemExit('Preview database must be a new empty file')
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


DB_PATH = _safe_database_path()
if os.environ.get('BINNA_ISOLATED_TEST_DB') != '1':
    raise SystemExit('Set BINNA_ISOLATED_TEST_DB=1 for the local preview')

from app import create_app, db
from app.models import (
    AuditLog, Company, FinancialData, Project, ProjectMember,
    ProjectMonitoringComment, User,
)
from migrate_phase_1b_roles import apply_migration as apply_phase_1b_1
from migrate_phase_1b_2_lifecycle import apply_migration as apply_phase_1b_2

app = create_app('production')
app.config.update(DEBUG=False, TESTING=False)


def _user(company, username, email, company_role='member', company_manager=False):
    user = User(username=username, email=email, role='user', company=company,
                company_role=company_role, is_company_manager=company_manager,
                email_verified=True, is_active=True)
    user.set_password('BinnaDemo!2026')
    db.session.add(user)
    return user


def seed_demo():
    db.create_all()
    # Run the same additive migration entrypoints used in deployment. On a new
    # demo schema they verify columns/tables and create the required indexes.
    apply_phase_1b_1()
    apply_phase_1b_2()
    company = Company(name='BINNA Demo Contracting', slug='binna-demo',
                      status='active', plan='trial')
    db.session.add(company)
    db.session.flush()
    manager = _user(company, 'demo_manager', 'manager@demo.binna', 'owner', True)
    portfolio = _user(company, 'demo_projects', 'projects@demo.binna', 'admin')
    project_manager = _user(company, 'demo_pm', 'pm@demo.binna', 'member')
    engineer = _user(company, 'demo_engineer', 'engineer@demo.binna', 'member')
    document_controller = _user(company, 'demo_dc', 'dc@demo.binna', 'member')
    db.session.flush()
    company.projects_manager_user_id = portfolio.id

    active = Project(company_id=company.id, code='DEMO-A', name='Al-Nahrain Office Complex',
                     client='Demo Client', contractor='BINNA Demo Contracting', status='active',
                     created_by=manager.id, project_manager_user_id=project_manager.id,
                     is_closed=False)
    closed = Project(company_id=company.id, code='DEMO-C', name='Completed School Rehabilitation',
                     client='Demo Directorate', contractor='BINNA Demo Contracting', status='completed',
                     created_by=manager.id, project_manager_user_id=project_manager.id,
                     is_closed=True, closed_at=datetime.now(timezone.utc),
                     closed_by_user_id=portfolio.id)
    db.session.add_all([active, closed])
    db.session.flush()

    engineer_permissions = {'gantt': {'view': True, 'edit': True},
                            'dr': {'view': True, 'edit': True},
                            'financial': {'view': True, 'edit': False}}
    dc_permissions = {'dc': {'view': True, 'edit': True},
                      'uploads': {'view': True, 'edit': True},
                      'financial': {'view': False, 'edit': False}}
    for project in (active, closed):
        db.session.add_all([
            ProjectMember(company_id=company.id, project_id=project.id,
                          user_id=project_manager.id, role='owner', permissions='{}'),
            ProjectMember(company_id=company.id, project_id=project.id,
                          user_id=engineer.id, role='member',
                          permissions=json.dumps(engineer_permissions)),
            ProjectMember(company_id=company.id, project_id=project.id,
                          user_id=document_controller.id, role='member',
                          permissions=json.dumps(dc_permissions)),
        ])
        db.session.add(FinancialData(company_id=company.id, project_id=project.id,
                                     data='{}', updated_by=manager.id))

    db.session.add_all([
        ProjectMonitoringComment(company_id=company.id, project_id=active.id,
                                 author_user_id=portfolio.id,
                                 body='Weekly review: procurement is on track; monitor the concrete delivery date.'),
        ProjectMonitoringComment(company_id=company.id, project_id=closed.id,
                                 author_user_id=manager.id,
                                 body='Final management review completed. Records retained for reference.'),
        AuditLog(company_id=company.id, project_id=active.id, actor_user_id=manager.id,
                 action_type='project.created', new_values=json.dumps({'code': active.code})),
        AuditLog(company_id=company.id, project_id=active.id, actor_user_id=portfolio.id,
                 action_type='project.manager_assigned',
                 new_values=json.dumps({'project_manager_user_id': project_manager.id})),
        AuditLog(company_id=company.id, project_id=closed.id, actor_user_id=portfolio.id,
                 action_type='project.closed', previous_values=json.dumps({'is_closed': False}),
                 new_values=json.dumps({'is_closed': True})),
    ])
    db.session.commit()


with app.app_context():
    seed_demo()

if __name__ == '__main__':
    print(f'PREVIEW_DATABASE={DB_PATH}', flush=True)
    print('PREVIEW_URL=http://127.0.0.1:5055/login', flush=True)
    app.run(host='127.0.0.1', port=5055, debug=False, use_reloader=False)
