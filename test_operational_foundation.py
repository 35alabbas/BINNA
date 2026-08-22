#!/usr/bin/env python3
"""Operational shell foundation API tests on an isolated SQLite database."""
import io
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
from app.models import Company, GanttData, Project, ProjectMember, User  # noqa: E402


app = create_app('development')
with app.app_context():
    db.create_all()
    alpha = Company(name='Alpha', slug='alpha-ops', status='trial')
    beta = Company(name='Beta', slug='beta-ops', status='trial')
    db.session.add_all([alpha, beta])
    db.session.flush()
    owner = User(username='owner', email='owner@ops.test', password_hash='x',
                 company_id=alpha.id, company_role='owner', email_verified=True)
    editor = User(username='editor', email='editor@ops.test', password_hash='x',
                  company_id=alpha.id, company_role='member', email_verified=True)
    viewer = User(username='viewer', email='viewer@ops.test', password_hash='x',
                  company_id=alpha.id, company_role='member', email_verified=True)
    foreign = User(username='foreign', email='foreign@ops.test', password_hash='x',
                   company_id=beta.id, company_role='owner', email_verified=True)
    db.session.add_all([owner, editor, viewer, foreign])
    db.session.flush()
    project = Project(company_id=alpha.id, code='OPS', name='Operations', status='active',
                      created_by=owner.id, project_manager_user_id=owner.id)
    closed = Project(company_id=alpha.id, code='CLS', name='Closed', status='completed',
                     created_by=owner.id, project_manager_user_id=owner.id, is_closed=True,
                     closed_by_user_id=owner.id)
    db.session.add_all([project, closed])
    db.session.flush()
    edit_permissions = json.dumps({
        'financial': {'view': True, 'edit': True},
        'gantt': {'view': True, 'edit': True},
    })
    view_permissions = json.dumps({
        'financial': {'view': True, 'edit': False},
        'gantt': {'view': True, 'edit': False},
    })
    db.session.add_all([
        ProjectMember(company_id=alpha.id, project_id=project.id, user_id=owner.id,
                      role='owner', permissions='{}'),
        ProjectMember(company_id=alpha.id, project_id=project.id, user_id=editor.id,
                      role='member', permissions=edit_permissions),
        ProjectMember(company_id=alpha.id, project_id=project.id, user_id=viewer.id,
                      role='member', permissions=view_permissions),
        ProjectMember(company_id=alpha.id, project_id=closed.id, user_id=owner.id,
                      role='owner', permissions='{}'),
        GanttData(company_id=alpha.id, project_id=project.id, updated_by=owner.id,
                  tasks=json.dumps([{'id': 't1', 'name': 'Foundation', 'start': '2026-01-01',
                                    'end': '2026-01-05', 'preds': []}]),
                  stoppages=json.dumps([{'id': 's1', 'name': 'Weather',
                                         'start': '2026-01-02', 'end': '2026-01-03',
                                         'type': 'weather'}])),
    ])
    db.session.commit()
    ids = {'owner': owner.id, 'editor': editor.id, 'viewer': viewer.id,
           'foreign': foreign.id, 'project': project.id, 'closed': closed.id}
    tokens = {name: create_access_token(identity=str(ids[name]))
              for name in ('owner', 'editor', 'viewer', 'foreign')}


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
print('Operational localization, stoppages, and BOQ import')

stoppage_list = client.get(f'/api/v1/projects/{pid}/gantt/stoppages', headers=headers['viewer'])
check('gantt viewers can read authoritative stoppages',
      stoppage_list.status_code == 200 and
      (stoppage_list.get_json() or {}).get('stoppages', [{}])[0].get('id') == 's1')

replacement = [{
    'id': 's2', 'name': 'Client instruction', 'start': '2026-02-10', 'end': '2026-02-12',
    'type': 'decision', 'notes': 'Work paused safely', 'reference': 'LTR-17',
}]
saved = client.put(f'/api/v1/projects/{pid}/gantt/stoppages', json={'stoppages': replacement},
                   headers=headers['editor'])
check('gantt editors can update stoppages without a task payload', saved.status_code == 200)
with app.app_context():
    persisted = GanttData.query.filter_by(project_id=pid).first()
    persisted_tasks = json.loads(persisted.tasks)
    persisted_stoppages = json.loads(persisted.stoppages)
check('stoppage-only update preserves every gantt task',
      persisted_tasks == [{'id': 't1', 'name': 'Foundation', 'start': '2026-01-01',
                           'end': '2026-01-05', 'preds': []}])
check('stoppage notes and references round-trip',
      persisted_stoppages[0].get('notes') == 'Work paused safely' and
      persisted_stoppages[0].get('reference') == 'LTR-17')
check('gantt viewer cannot update stoppages', client.put(
    f'/api/v1/projects/{pid}/gantt/stoppages', json={'stoppages': []},
    headers=headers['viewer'],
).status_code == 403)
check('foreign tenant cannot read stoppages', client.get(
    f'/api/v1/projects/{pid}/gantt/stoppages', headers=headers['foreign'],
).status_code == 404)
check('closed project blocks stoppage modification', client.put(
    f"/api/v1/projects/{ids['closed']}/gantt/stoppages", json={'stoppages': []},
    headers=headers['owner'],
).status_code == 409)
invalid_stop = client.put(
    f'/api/v1/projects/{pid}/gantt/stoppages',
    json={'stoppages': [{'name': 'Missing dates'}]}, headers=headers['editor'],
)
check('malformed stoppages are rejected without replacing saved records',
      invalid_stop.status_code == 400)

csv_bytes = (
    'Item Number,Description,Unit,Quantity,Unit Price,Total\n'
    'A-1,أعمال خرسانية,m3,١٢٫٥,2000,25000\n'
    'A-2,Malformed,m,not-a-number,100,0\n'
).encode('utf-8-sig')
mapping = json.dumps({'num': 'Item Number', 'desc': 'Description', 'unit': 'Unit',
                      'qty': 'Quantity', 'price': 'Unit Price', 'total': 'Total'})


def import_csv(auth='editor', project_id=pid):
    return client.post(
        f'/api/v1/projects/{project_id}/financial/boq-import/preview',
        data={'file': (io.BytesIO(csv_bytes), 'boq.csv'), 'mapping': mapping},
        headers=headers[auth], content_type='multipart/form-data',
    )


csv_preview = import_csv()
csv_payload = csv_preview.get_json() or {}
check('csv import preview preserves Arabic and normalizes Arabic-Indic numbers',
      csv_preview.status_code == 200 and csv_payload.get('valid_rows', [{}])[0].get('desc') == 'أعمال خرسانية' and
      csv_payload.get('valid_rows', [{}])[0].get('qty') == 12.5 and
      csv_payload.get('valid_rows', [{}])[0].get('num') == 'A-1')
check('source totals are references while authoritative totals are recalculated',
      csv_payload.get('valid_rows', [{}])[0].get('source_total') == 25000 and
      csv_payload.get('valid_rows', [{}])[0].get('calculated_total') == 25000)
check('malformed csv rows are explained and excluded',
      len(csv_payload.get('valid_rows', [])) == 1 and
      len(csv_payload.get('rejected_rows', [])) == 1 and
      'quantity' in csv_payload.get('rejected_rows', [{}])[0].get('errors', []))
check('financial viewer cannot preview a BOQ import', import_csv('viewer').status_code == 403)
check('foreign tenant cannot preview a BOQ import', import_csv('foreign').status_code == 404)
check('closed project blocks BOQ import preview', import_csv('owner', ids['closed']).status_code == 409)

try:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(['Item Number', 'Description', 'Unit', 'Quantity', 'Unit Price', 'Total'])
    ws.append(['X-1', 'Formula must not execute', 'm', '=2+3', 100, '=D2*E2'])
    xlsx = io.BytesIO()
    wb.save(xlsx)
    xlsx.seek(0)
    xlsx_preview = client.post(
        f'/api/v1/projects/{pid}/financial/boq-import/preview',
        data={'file': (xlsx, 'boq.xlsx'), 'mapping': mapping},
        headers=headers['editor'], content_type='multipart/form-data',
    )
    xlsx_payload = xlsx_preview.get_json() or {}
    check('xlsx formulas are never evaluated as import values',
          xlsx_preview.status_code == 200 and not xlsx_payload.get('valid_rows') and
          len(xlsx_payload.get('rejected_rows', [])) == 1)
    malformed_xlsx = client.post(
        f'/api/v1/projects/{pid}/financial/boq-import/preview',
        data={'file': (io.BytesIO(b'not-a-workbook'), 'broken.xlsx'), 'mapping': mapping},
        headers=headers['editor'], content_type='multipart/form-data',
    )
    check('malformed xlsx files return a controlled validation error',
          malformed_xlsx.status_code == 400 and (malformed_xlsx.get_json() or {}).get('error'))
except ImportError:
    check('openpyxl is installed in the project environment', False)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
