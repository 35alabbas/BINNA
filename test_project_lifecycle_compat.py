#!/usr/bin/env python3
"""Phase 1B-2 pre/post migration compatibility on isolated SQLite."""
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
from app.tenancy import phase_1b_2_schema_status  # noqa: E402
from migrate_phase_1b_2_lifecycle import apply_migration, dry_run  # noqa: E402


app = create_app('development')
with app.app_context():
    statements = (
        "CREATE TABLE companies (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, "
        "slug VARCHAR(120) NOT NULL, plan VARCHAR(20), max_users INTEGER, trial_ends_at DATETIME, "
        "grace_ends_at DATETIME, paid_until DATETIME, status VARCHAR(20), created_at DATETIME, "
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
        "created_at DATETIME, updated_at DATETIME, project_manager_user_id INTEGER)",
        "CREATE TABLE project_members (id INTEGER PRIMARY KEY, company_id INTEGER, project_id INTEGER, "
        "user_id INTEGER, role VARCHAR(20), joined_at DATETIME, permissions TEXT)",
    )
    with db.engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(text("INSERT INTO companies (id,name,slug,plan,max_users,status,projects_manager_user_id) "
                          "VALUES (1,'Legacy','legacy','trial',999,'trial',2)"))
        conn.execute(text("INSERT INTO users (id,username,email,password_hash,role,is_active,company_id," 
                          "company_role,is_company_manager,email_verified,invite_pending) VALUES "
                          "(1,'owner','owner@legacy.test','x','user',1,1,'owner',0,1,0),"
                          "(2,'portfolio','portfolio@legacy.test','x','user',1,1,'member',0,1,0),"
                          "(3,'pm','pm@legacy.test','x','user',1,1,'member',0,1,0)"))
        conn.execute(text("INSERT INTO projects (id,company_id,code,name,status,created_by,project_manager_user_id) "
                          "VALUES (1,1,'OLD','Legacy project','active',1,2)"))
        conn.execute(text("INSERT INTO project_members (id,company_id,project_id,user_id,role,permissions) "
                          "VALUES (1,1,1,1,'owner','{}'),(2,1,1,2,'viewer','{}')"))
    token = create_access_token(identity='2')


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
print('Phase 1B-2 migration compatibility')

legacy_write = client.put('/api/v1/projects/1/project-manager', json={'user_id': 3}, headers=headers)
check('Phase 1B-1 manager assignment continues before migration', legacy_write.status_code == 200)
check('lifecycle endpoint fails explicitly before migration', client.post(
    '/api/v1/projects/1/close', headers=headers,
).status_code == 503)
with app.app_context():
    tables_before = set(inspect(db.engine).get_table_names())
    columns_before = {c['name'] for c in inspect(db.engine).get_columns('projects')}
    dry_run()
    tables_after_dry = set(inspect(db.engine).get_table_names())
    columns_after_dry = {c['name'] for c in inspect(db.engine).get_columns('projects')}
check('dry-run changes no tables', tables_before == tables_after_dry)
check('dry-run changes no columns', columns_before == columns_after_dry)
check('audit table remains absent before explicit migration', 'audit_logs' not in tables_before)

with app.app_context():
    apply_migration()
    apply_migration()
    migrated_tables = set(inspect(db.engine).get_table_names())
    migrated_columns = {c['name'] for c in inspect(db.engine).get_columns('projects')}
    legacy_manager = db.session.execute(text(
        'SELECT project_manager_user_id FROM projects WHERE id=1')).scalar_one()
    closed = db.session.execute(text('SELECT is_closed FROM projects WHERE id=1')).scalar_one()
check('explicit migration creates only additive lifecycle structures',
      {'audit_logs', 'project_monitoring_comments'} <= migrated_tables and
      {'is_closed', 'closed_at', 'closed_by_user_id'} <= migrated_columns)
check('migration does not rewrite existing manager assignment', legacy_manager == 3)
check('existing project defaults to open', closed in (0, False))

audited_write = client.put('/api/v1/projects/1/project-manager', json={'user_id': 2}, headers=headers)
check('manager assignment continues after migration', audited_write.status_code == 200)
with app.app_context():
    audit_count = db.session.execute(text(
        "SELECT COUNT(*) FROM audit_logs WHERE action_type='project.manager_assigned' "
        "AND project_id=1 AND actor_user_id=2")).scalar_one()
check('post-migration manager assignment is audited', audit_count == 1)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
