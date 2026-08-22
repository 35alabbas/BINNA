#!/usr/bin/env python3
"""Focused paid-payment and project financial-category regression tests."""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path


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
    Company, FinancialData, GlobalParty, Project, ProjectMember,
    Subcontract, SupplyAgreement, User, _now,
)

app = create_app('development')
client = app.test_client()


def headers(user_id):
    with app.app_context():
        token = create_access_token(identity=str(user_id))
    return {'Authorization': 'Bearer ' + token}


with app.app_context():
    db.create_all()
    alpha = Company(name='Alpha', slug='alpha-sync', status='trial',
                    trial_ends_at=_now() + timedelta(days=14))
    beta = Company(name='Beta', slug='beta-sync', status='trial',
                   trial_ends_at=_now() + timedelta(days=14))
    db.session.add_all([alpha, beta]); db.session.flush()
    pm = User(username='sync-pm', email='sync-pm@test', password_hash='unused',
              company_id=alpha.id, company_role='member', email_verified=True)
    outsider = User(username='sync-out', email='sync-out@test', password_hash='unused',
                    company_id=beta.id, company_role='owner', email_verified=True)
    db.session.add_all([pm, outsider]); db.session.flush()
    project = Project(company_id=alpha.id, code='SYNC', name='Sync project',
                      created_by=pm.id, project_manager_user_id=pm.id)
    db.session.add(project); db.session.flush()
    db.session.add(ProjectMember(
        company_id=alpha.id, project_id=project.id, user_id=pm.id, role='viewer',
        permissions=json.dumps({'financial': {'view': True, 'edit': True},
                                'subcontracts': {'view': True, 'edit': True}}),
    ))
    party = GlobalParty(company_id=alpha.id, project_id=project.id,
                        name_en='Supplier A', role='supplier')
    db.session.add(party); db.session.flush()
    supply = SupplyAgreement(
        company_id=alpha.id, project_id=project.id, global_party_id=party.id,
        ref='SYNC-PO-001', description='Steel', po_value=500, currency='USD',
        date_issued='2026-08-01', status='open', data=json.dumps({'payments': []}),
    )
    historical = SupplyAgreement(
        company_id=alpha.id, project_id=project.id, global_party_id=party.id,
        ref='SYNC-PO-002', description='Historical', po_value=100, currency='IQD',
        date_issued='2026-07-01', status='closed',
        data=json.dumps({'payments': [{'id': 'historical-paid', 'date': '2026-07-02', 'amount': 100}]}),
    )
    db.session.add_all([supply, historical]); db.session.commit()
    ids = {'project': project.id, 'supply': supply.id, 'historical': historical.id,
           'pm': pm.id, 'outsider': outsider.id}


pm_h = headers(ids['pm'])
outsider_h = headers(ids['outsider'])
passed = failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1; print('  ok   ' + name)
    else:
        failed += 1; print('  FAIL ' + name)


print(f'ISOLATED_DATABASE={TEST_DB_PATH}')
print('Payment-expense synchronization')

categories = client.get(f"/api/v1/projects/{ids['project']}/financial/categories", headers=pm_h)
check('project exposes distinct income and expense category lists',
      categories.status_code == 200 and
      set((categories.get_json() or {}).keys()) >= {'income_categories', 'expense_categories'})

paid_blob = {'payments': [{'id': 'supplier-pay-1', 'date': '2026-08-10',
                           'amount': 100, 'exchangeRate': 1310}]}
paid = client.put(
    f"/api/v1/projects/{ids['project']}/supply-agreements/{ids['supply']}",
    json={'data': paid_blob}, headers=pm_h,
)
check('new non-IQD paid supplier payment is accepted with an exchange rate', paid.status_code == 200)
with app.app_context():
    fd = FinancialData.query.filter_by(project_id=ids['project']).first()
    financial = json.loads(fd.data) if fd and fd.data else {}
    generated = [row for row in financial.get('expenses', []) if row.get('system_generated')]
    check('paid supplier payment creates one IQD-valued linked expense',
          len(generated) == 1 and generated[0].get('amount') == 100 and
          generated[0].get('rate') == 1310 and generated[0].get('source', {}).get('payment_uuid') == 'supplier-pay-1')

same = client.put(
    f"/api/v1/projects/{ids['project']}/supply-agreements/{ids['supply']}",
    json={'data': paid_blob}, headers=pm_h,
)
with app.app_context():
    fd = FinancialData.query.filter_by(project_id=ids['project']).first()
    financial = json.loads(fd.data) if fd and fd.data else {}
    generated = [row for row in financial.get('expenses', []) if row.get('system_generated') and row.get('amount', 0) > 0]
    check('repeating the same paid save is idempotent', same.status_code == 200 and len(generated) == 1)

manual_overwrite = client.put(
    f"/api/v1/projects/{ids['project']}/financial/income",
    json={'expenses': [{'id': 'manual-1', 'desc': 'Manual', 'amount': 5, 'cur': 'IQD'}]},
    headers=pm_h,
)
with app.app_context():
    payload = json.loads(FinancialData.query.filter_by(project_id=ids['project']).first().data)
    check('financial saves preserve linked expenses against manual alteration or removal',
          manual_overwrite.status_code == 200 and
          len([r for r in payload['expenses'] if r.get('system_generated')]) == 1 and
          len([r for r in payload['expenses'] if r.get('id') == 'manual-1']) == 1)

reversed_response = client.put(
    f"/api/v1/projects/{ids['project']}/supply-agreements/{ids['supply']}",
    json={'data': {'payments': []}}, headers=pm_h,
)
with app.app_context():
    payload = json.loads(FinancialData.query.filter_by(project_id=ids['project']).first().data)
    linked_rows = [r for r in payload['expenses'] if r.get('source', {}).get('payment_uuid') == 'supplier-pay-1']
    check('removing a paid payment appends one linked negative reversal',
          reversed_response.status_code == 200 and len(linked_rows) == 2 and
          sorted(r.get('amount') for r in linked_rows) == [-100, 100])

category_create = client.post(
    f"/api/v1/projects/{ids['project']}/financial/categories",
    json={'kind': 'expense', 'name': 'Equipment'}, headers=pm_h,
)
category = (category_create.get_json() or {}).get('category') or {}
category_archive = client.put(
    f"/api/v1/projects/{ids['project']}/financial/categories/expense/{category.get('id')}",
    json={'archived': True}, headers=pm_h,
)
check('ordinary project category has a stable id and may be safely archived',
      category_create.status_code == 201 and category.get('id') and category_archive.status_code == 200 and
      (category_archive.get_json() or {}).get('category', {}).get('archived') is True)

missing_rate = client.put(
    f"/api/v1/projects/{ids['project']}/supply-agreements/{ids['supply']}",
    json={'data': {'payments': [{'id': 'supplier-pay-2', 'date': '2026-08-11', 'amount': 25}]}},
    headers=pm_h,
)
check('new non-IQD payment without exchange rate is rejected', missing_rate.status_code == 400)

historical_body = {'payments': [{'id': 'historical-paid', 'date': '2026-07-02', 'amount': 100}]}
historical_save = client.put(
    f"/api/v1/projects/{ids['project']}/supply-agreements/{ids['historical']}",
    json={'data': historical_body}, headers=pm_h,
)
with app.app_context():
    fd = FinancialData.query.filter_by(project_id=ids['project']).first()
    rows = json.loads(fd.data).get('expenses', []) if fd and fd.data else []
    check('historical paid rows are not backfilled',
          historical_save.status_code == 200 and
          not any(r.get('source', {}).get('payment_uuid') == 'historical-paid' for r in rows))

cross = client.get(f"/api/v1/projects/{ids['project']}/financial/categories", headers=outsider_h)
check('cross-company category access remains denied', cross.status_code == 404)

with app.app_context():
    project_row = db.session.get(Project, ids['project'])
    project_row.is_closed = True
    db.session.commit()
closed_write = client.put(
    f"/api/v1/projects/{ids['project']}/supply-agreements/{ids['supply']}",
    json={'data': {'payments': []}}, headers=pm_h,
)
check('closed project payment modifications remain denied', closed_write.status_code == 409)
with app.app_context():
    project_row = db.session.get(Project, ids['project'])
    project_row.is_closed = False
    db.session.commit()

with app.app_context():
    from app.models import PaymentExpenseLink
    PaymentExpenseLink.__table__.drop(bind=db.engine)
legacy_without_link_schema = client.put(
    f"/api/v1/projects/{ids['project']}/supply-agreements/{ids['supply']}",
    json={'data': {'payments': [{'id': 'pre-migration-new', 'date': '2026-08-20', 'amount': 10}]}},
    headers=pm_h,
)
check('before the additive migration legacy payment saves continue without synchronization',
      legacy_without_link_schema.status_code == 200)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
