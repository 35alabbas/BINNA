#!/usr/bin/env python3
r"""Phase 1B-1 compatibility test for a pre-migration database schema.

Uses only a newly-created empty SQLite file outside C:\BINNA\instance.
"""
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
from migrate_phase_1b_roles import apply_migration, dry_run  # noqa: E402


app = create_app('development')

with app.app_context():
    # Deliberately reproduce only the legacy columns needed for an authenticated
    # project-list request. New Phase 1B columns are intentionally absent.
    statements = (
        "CREATE TABLE companies (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, "
        "slug VARCHAR(120) NOT NULL, plan VARCHAR(20), max_users INTEGER, "
        "trial_ends_at DATETIME, grace_ends_at DATETIME, paid_until DATETIME, "
        "status VARCHAR(20), created_at DATETIME)",
        "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(80) NOT NULL, "
        "email VARCHAR(120) NOT NULL, password_hash VARCHAR(255) NOT NULL, "
        "role VARCHAR(20), is_active BOOLEAN, created_at DATETIME, company_id INTEGER, "
        "company_role VARCHAR(20), email_verified BOOLEAN, email_verification_token VARCHAR(255), "
        "pending_company_name VARCHAR(200), invite_pending BOOLEAN, "
        "password_reset_token VARCHAR(255), password_reset_expires DATETIME)",
        "CREATE TABLE projects (id INTEGER PRIMARY KEY, company_id INTEGER, code VARCHAR(20) NOT NULL, "
        "name VARCHAR(200) NOT NULL, client VARCHAR(200), consultant VARCHAR(200), "
        "contractor VARCHAR(200), description TEXT, status VARCHAR(20), "
        "created_by INTEGER NOT NULL, created_at DATETIME, updated_at DATETIME)",
        "CREATE TABLE project_members (id INTEGER PRIMARY KEY, company_id INTEGER, "
        "project_id INTEGER NOT NULL, user_id INTEGER NOT NULL, role VARCHAR(20), "
        "joined_at DATETIME, permissions TEXT)",
    )
    with db.engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(text(
            "INSERT INTO companies (id,name,slug,plan,max_users,status) "
            "VALUES (1,'Legacy','legacy','trial',999,'trial')"
        ))
        conn.execute(text(
            "INSERT INTO users (id,username,email,password_hash,role,is_active,company_id,"
            "company_role,email_verified,invite_pending) "
            "VALUES (1,'owner','owner@legacy.test','unused','user',1,1,'owner',1,0)"
        ))
        conn.execute(text(
            "INSERT INTO projects (id,company_id,code,name,status,created_by) "
            "VALUES (1,1,'OLD','Legacy project','active',1)"
        ))
        conn.execute(text(
            "INSERT INTO project_members (id,company_id,project_id,user_id,role,permissions) "
            "VALUES (1,1,1,1,'owner','{}')"
        ))
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
print('Phase 1B-1 pre-migration compatibility')

legacy_list = client.get('/api/v1/projects', headers=headers)
check('legacy project reads still work before migration', legacy_list.status_code == 200)
check('legacy project remains visible',
      legacy_list.status_code == 200 and legacy_list.get_json()['total'] == 1)

new_write = client.post(
    '/api/v1/projects', json={'code': 'NEW', 'name': 'New project'}, headers=headers,
)
check('Phase 1B write fails closed before migration', new_write.status_code == 503)
check('migration-required response is explicit',
      (new_write.get_json() or {}).get('code') == 'phase_1b_migration_required')

with app.app_context():
    before = {
        table: {c['name'] for c in inspect(db.engine).get_columns(table)}
        for table in ('users', 'companies', 'projects')
    }
    dry_run()
    after = {
        table: {c['name'] for c in inspect(db.engine).get_columns(table)}
        for table in ('users', 'companies', 'projects')
    }
check('migration defaults to read-only dry-run', before == after)
check('dry-run did not add Phase 1B columns',
      'is_company_manager' not in after['users'] and
      'projects_manager_user_id' not in after['companies'] and
      'project_manager_user_id' not in after['projects'])

with app.app_context():
    apply_migration()
    apply_migration()  # idempotence: a second explicit run adds nothing
    migrated = {
        table: {c['name'] for c in inspect(db.engine).get_columns(table)}
        for table in ('users', 'companies', 'projects')
    }
    legacy_state = db.session.execute(text(
        "SELECT is_company_manager FROM users WHERE id=1"
    )).scalar_one()
    manager_state = db.session.execute(text(
        "SELECT project_manager_user_id FROM projects WHERE id=1"
    )).scalar_one()
check('explicit apply adds only the three Phase 1B columns',
      'is_company_manager' in migrated['users'] and
      'projects_manager_user_id' in migrated['companies'] and
      'project_manager_user_id' in migrated['projects'])
check('explicit apply does not rewrite legacy company owner', legacy_state in (0, False))
check('explicit apply does not assign legacy project manager', manager_state is None)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
