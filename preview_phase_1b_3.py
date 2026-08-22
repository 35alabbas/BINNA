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
    AuditLog, Company, FinancialData, GanttData, GlobalParty, Party, Project,
    ProjectMember, ProjectMonitoringComment, Subcontract, SupplyAgreement, User,
)
from migrate_phase_1b_roles import apply_migration as apply_phase_1b_1
from migrate_phase_1b_2_lifecycle import apply_migration as apply_phase_1b_2
from migrate_payment_expense_links import apply_migration as apply_payment_expense_links
from app.payment_expenses import (
    SUBCONTRACT_CATEGORY_ID, SUPPLIER_CATEGORY_ID, sync_paid_payment_log,
)

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
    apply_payment_expense_links()
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
    overview_payloads = {
        active.id: {
            'currency': 'IQD',
            'contractDetails': {'contract-value': '2850000000', 'date': '2026-02-01',
                                'contract-end': '2027-07-15', 'period': '530',
                                'actual-finish': '',
                                'extensions': [{'days': '14', 'note': 'Approved variation order VO-03'}]},
            'boq': [
                {'num': 'C-01', 'desc': 'Reinforced concrete foundations', 'unit': 'm³', 'qty': '420', 'price': '550000'},
                {'num': 'A-12', 'desc': 'أعمال إنهاء الواجهات الخارجية', 'unit': 'm²', 'qty': '1850', 'price': '95000'},
            ],
            'vo': [], 'payments': [],
            'income': [{'id': 'demo-income-1', 'desc': 'Company project funding',
                        'cat': 'demo-income-funding', 'date': '2026-02-01',
                        'cur': 'IQD', 'amount': 350000000, 'rate': 1}],
            'expenses': [{'id': 'demo-expense-1', 'desc': 'Site setup',
                          'cat': 'demo-expense-site', 'date': '2026-02-03',
                          'cur': 'IQD', 'amount': 48000000, 'rate': 1}],
            'incomeCategories': [{'id': 'demo-income-funding', 'name': 'Company funding', 'archived': False}],
            'expenseCategories': [{'id': 'demo-expense-site', 'name': 'Site setup', 'archived': False}],
            'cashflowSummary': {'totalCertified': 740000000, 'totalReceived': 610000000},
        },
        closed.id: {
            'currency': 'IQD',
            'contractDetails': {'contract-value': '920000000', 'date': '2024-04-10',
                                'contract-end': '2025-06-30', 'period': '446'},
            'cashflowSummary': {'totalCertified': 920000000, 'totalReceived': 920000000},
        },
    }
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
                                     data=json.dumps(overview_payloads[project.id]),
                                     updated_by=manager.id))

    db.session.add(GanttData(
        company_id=company.id, project_id=active.id, updated_by=project_manager.id,
        tasks=json.dumps([{
            'id': 'demo-task-1', 'name': 'Foundation works', 'type': 'task', 'level': 0,
            'start': '2026-02-01', 'end': '2026-03-15', 'pct': 65, 'preds': [],
        }]),
        stoppages=json.dumps([{
            'id': 'demo-stop-1', 'name': 'Heavy rainfall', 'start': '2026-02-18',
            'end': '2026-02-21', 'type': 'weather',
            'notes': 'Site access was suspended for safety.', 'reference': 'SITE-INS-014',
        }]),
    ))

    subcontractor = Party(company_id=company.id, project_id=active.id,
                          name='Tigris Civil Works', role='subcontractor')
    supplier = GlobalParty(company_id=company.id, project_id=active.id,
                           name_en='Mesopotamia Steel', name_ar='حديد بلاد الرافدين',
                           role='supplier')
    db.session.add_all([subcontractor, supplier])
    db.session.flush()
    subcontract = Subcontract(
        company_id=company.id, project_id=active.id, party_id=subcontractor.id,
        ref='DEMO-A-SUB-001', title='Foundation concrete works', kind='monthly',
        status='active', data=json.dumps({'currency': 'IQD', 'payments': [
            {'id': 'demo-sub-paid', 'date': '2026-03-10', '_net': 72000000,
             'paid': True, 'paidDate': '2026-03-10', 'exchangeRate': 1},
            {'id': 'demo-sub-unpaid', 'date': '2026-04-10', '_net': 31000000,
             'paid': False, 'paidDate': ''},
        ]}), documents='[]')
    supply = SupplyAgreement(
        company_id=company.id, project_id=active.id, global_party_id=supplier.id,
        ref='DEMO-A-PO-001', description='Reinforcement steel', po_value=185000,
        currency='USD', date_issued='2026-02-05', status='partially_paid',
        data=json.dumps({'payments': [
            {'id': 'demo-supplier-paid', 'date': '2026-03-05', 'amount': 65000,
             'exchangeRate': 1310, 'invoiceRef': 'MS-104'},
        ]}),
    )
    db.session.add_all([subcontract, supply])
    db.session.flush()
    sync_paid_payment_log(
        project=active, actor_user_id=project_manager.id,
        source_type='subcontract_payment', agreement_id=subcontract.id,
        party_name=subcontractor.name, currency='IQD', old_payments=[],
        new_payments=[{'id': 'demo-sub-paid', 'date': '2026-03-10', 'amount': 72000000,
                       'exchangeRate': 1}], category_id=SUBCONTRACT_CATEGORY_ID,
        category_name='Subcontractors')
    sync_paid_payment_log(
        project=active, actor_user_id=project_manager.id,
        source_type='supply_agreement_payment', agreement_id=supply.id,
        party_name=supplier.name_en, currency='USD', old_payments=[],
        new_payments=[{'id': 'demo-supplier-paid', 'date': '2026-03-05', 'amount': 65000,
                       'exchangeRate': 1310}], category_id=SUPPLIER_CATEGORY_ID,
        category_name='Suppliers')

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
