#!/usr/bin/env python3
"""Stage 1 pre/post migration compatibility on isolated SQLite."""
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
from sqlalchemy import inspect, text  # noqa: E402

from app import create_app, db  # noqa: E402
from app.tenancy import project_classification_schema_status  # noqa: E402
from migrate_project_classification import apply_migration, dry_run  # noqa: E402


app = create_app('development')
with app.app_context():
    statements = (
        "CREATE TABLE companies (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, "
        "slug VARCHAR(120) NOT NULL, plan VARCHAR(20), max_users INTEGER, status VARCHAR(20), "
        "trial_ends_at DATETIME, grace_ends_at DATETIME, paid_until DATETIME, created_at DATETIME, "
        "projects_manager_user_id INTEGER)",
        "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(80) NOT NULL, "
        "email VARCHAR(120) NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(20), "
        "is_active BOOLEAN, created_at DATETIME, company_id INTEGER, company_role VARCHAR(20), "
        "is_company_manager BOOLEAN NOT NULL DEFAULT FALSE, email_verified BOOLEAN, "
        "email_verification_token VARCHAR(255), pending_company_name VARCHAR(200), "
        "invite_pending BOOLEAN, password_reset_token VARCHAR(255), password_reset_expires DATETIME)",
        "CREATE TABLE projects (id INTEGER PRIMARY KEY, company_id INTEGER, code VARCHAR(20) NOT NULL, "
        "name VARCHAR(200) NOT NULL, client VARCHAR(200), consultant VARCHAR(200), "
        "contractor VARCHAR(200), description TEXT, status VARCHAR(20), created_by INTEGER NOT NULL, "
        "created_at DATETIME, updated_at DATETIME, project_manager_user_id INTEGER, "
        "is_closed BOOLEAN NOT NULL DEFAULT FALSE, closed_at DATETIME, closed_by_user_id INTEGER)",
        "CREATE TABLE project_members (id INTEGER PRIMARY KEY, company_id INTEGER, project_id INTEGER, "
        "user_id INTEGER, role VARCHAR(20), joined_at DATETIME, permissions TEXT)",
        "CREATE TABLE financial_data (id INTEGER PRIMARY KEY, company_id INTEGER, project_id INTEGER UNIQUE, "
        "data TEXT, updated_by INTEGER, updated_at DATETIME)",
        "CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, project_id INTEGER, "
        "actor_user_id INTEGER NOT NULL, action_type VARCHAR(80) NOT NULL, previous_values TEXT, "
        "new_values TEXT, created_at DATETIME)",
        "CREATE TABLE project_monitoring_comments (id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, "
        "project_id INTEGER NOT NULL, author_user_id INTEGER NOT NULL, body TEXT NOT NULL, created_at DATETIME)",
    )
    with db.engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(text("INSERT INTO companies (id,name,slug,plan,max_users,status,projects_manager_user_id) "
                          "VALUES (1,'Legacy','legacy-stage1','trial',999,'trial',1)"))
        conn.execute(text("INSERT INTO users (id,username,email,password_hash,role,is_active,company_id,"
                          "company_role,is_company_manager,email_verified,invite_pending) VALUES "
                          "(1,'owner','owner@legacy.test','x','user',1,1,'owner',0,1,0)"))
        conn.execute(text("INSERT INTO projects (id,company_id,code,name,status,created_by,"
                          "project_manager_user_id,is_closed) VALUES "
                          "(1,1,'OLD','Legacy project','active',1,1,0)"))
        conn.execute(text("INSERT INTO project_members (id,company_id,project_id,user_id,role,permissions) "
                          "VALUES (1,1,1,1,'owner','{}')"))
    token = create_access_token(identity='1')

client = app.test_client()
headers = {'Authorization': 'Bearer ' + token}
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
print('Stage 1 migration compatibility')

legacy_list = client.get('/api/v1/projects', headers=headers)
legacy_read = client.get('/api/v1/projects/1', headers=headers)
check('existing project list remains readable before Stage 1 migration', legacy_list.status_code == 200)
check('existing project detail remains readable before Stage 1 migration', legacy_read.status_code == 200)
check('legacy project serializes as unclassified without touching absent columns',
      (legacy_read.get_json() or {}).get('project', {}).get('classification_complete') is False)

created = client.post('/api/v1/projects', json={'name': 'Pre-migration new project'}, headers=headers)
check('existing project creation continues before Stage 1 migration', created.status_code == 201)
check('pre-migration creation can still generate a project code',
      (created.get_json() or {}).get('project', {}).get('code') == 'PRJ-0001')

classification = client.put('/api/v1/projects/1/classification', json={
    'project_regime': 'private', 'work_nature': 'construction',
    'contract_structure': 'independent',
}, headers=headers)
warnings = client.get('/api/v1/projects/1/warnings', headers=headers)
check('classification write reports migration required before migration',
      classification.status_code == 503 and
      (classification.get_json() or {}).get('code') == 'project_classification_migration_required')
check('classification warnings report migration required before migration', warnings.status_code == 503)

with app.app_context():
    tables_before = set(inspect(db.engine).get_table_names())
    columns_before = {c['name'] for c in inspect(db.engine).get_columns('projects')}
    old_row_before = db.session.execute(text(
        'SELECT code,name,client FROM projects WHERE id=1')).one()
    dry_run()
    tables_after = set(inspect(db.engine).get_table_names())
    columns_after = {c['name'] for c in inspect(db.engine).get_columns('projects')}
check('migration defaults to a read-only dry-run',
      tables_before == tables_after and columns_before == columns_after)

with app.app_context():
    apply_migration()
    apply_migration()
    migrated_tables = set(inspect(db.engine).get_table_names())
    migrated_columns = {c['name'] for c in inspect(db.engine).get_columns('projects')}
    old_row_after = db.session.execute(text(
        'SELECT code,name,client FROM projects WHERE id=1')).one()
    legacy_classification = db.session.execute(text(
        'SELECT project_regime,investment_subtype,work_nature,contract_structure '
        'FROM projects WHERE id=1')).one()
check('explicit migration creates only additive Stage 1 structures',
      'project_warning_dismissals' in migrated_tables and
      {'project_regime', 'investment_subtype', 'work_nature', 'contract_structure',
       'optional_field_states'} <= migrated_columns)
check('explicit migration is idempotent and rewrites no existing project fields',
      old_row_before == old_row_after)
check('legacy projects remain explicitly unclassified after migration',
      all(value is None for value in legacy_classification))
with app.app_context():
    project_classification_schema_status.cache_clear()
    schema_ready_after_migration = project_classification_schema_status()['ready']
check('schema readiness becomes available after explicit isolated migration',
      schema_ready_after_migration)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
