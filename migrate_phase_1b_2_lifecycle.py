#!/usr/bin/env python3
"""Phase 1B-2 additive lifecycle/audit migration; dry-run is the default."""
import argparse
import os

from sqlalchemy import inspect, text

from app import create_app, db
from app.tenancy import phase_1b_2_schema_status


COLUMNS = (
    ('projects', 'is_closed', 'BOOLEAN NOT NULL DEFAULT FALSE'),
    ('projects', 'closed_at', 'DATETIME'),
    ('projects', 'closed_by_user_id', 'INTEGER'),
)

TABLES = ('project_monitoring_comments', 'audit_logs')

INDEXES = (
    ('ix_projects_closed_by_user_id', 'projects', 'closed_by_user_id'),
    ('ix_project_monitoring_comments_company_id', 'project_monitoring_comments', 'company_id'),
    ('ix_project_monitoring_comments_project_id', 'project_monitoring_comments', 'project_id'),
    ('ix_project_monitoring_comments_created_at', 'project_monitoring_comments', 'created_at'),
    ('ix_audit_logs_company_id', 'audit_logs', 'company_id'),
    ('ix_audit_logs_project_id', 'audit_logs', 'project_id'),
    ('ix_audit_logs_action_type', 'audit_logs', 'action_type'),
    ('ix_audit_logs_created_at', 'audit_logs', 'created_at'),
)


def _schema():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    columns = {table: {c['name'] for c in inspector.get_columns(table)} for table in tables}
    return tables, columns


def dry_run():
    tables, columns = _schema()
    changes = 0
    for table, column, ddl in COLUMNS:
        if table not in tables:
            print(f'MISSING TABLE: {table} (migration cannot proceed)')
        elif column in columns[table]:
            print(f'PRESENT: {table}.{column}')
        else:
            print(f'WOULD ADD: {table}.{column} {ddl}')
            changes += 1
    for table in TABLES:
        if table in tables:
            print(f'PRESENT: table {table}')
        else:
            print(f'WOULD CREATE: table {table}')
            changes += 1
    print(f'DRY RUN: {changes} additive change(s) pending; nothing written.')


def apply_migration():
    tables, columns = _schema()
    if 'projects' not in tables:
        raise RuntimeError('Required table missing: projects')
    added = 0
    with db.engine.begin() as conn:
        for table, column, ddl in COLUMNS:
            if column in columns.get(table, set()):
                print(f'PRESENT: {table}.{column}')
                continue
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'))
            print(f'ADDED: {table}.{column}')
            added += 1
    from app.models import AuditLog, ProjectMonitoringComment
    for model in (ProjectMonitoringComment, AuditLog):
        if model.__tablename__ not in tables:
            model.__table__.create(bind=db.engine, checkfirst=True)
            print(f'CREATED: table {model.__tablename__}')
            added += 1
    with db.engine.begin() as conn:
        for name, table, column in INDEXES:
            conn.execute(text(f'CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})'))
            print(f'INDEX READY: {name}')
    phase_1b_2_schema_status.cache_clear()
    print(f'APPLY COMPLETE: {added} additive change(s); no existing rows rewritten.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-phase-1b-2', action='store_true')
    args = parser.parse_args()
    if args.apply and not args.confirm_phase_1b_2:
        parser.error('--apply requires --confirm-phase-1b-2')
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        apply_migration() if args.apply else dry_run()


if __name__ == '__main__':
    main()
