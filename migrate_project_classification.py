#!/usr/bin/env python3
"""Stage 1 additive project-classification migration; dry-run is default."""
import argparse
import os

from sqlalchemy import inspect, text

from app import create_app, db
from app.tenancy import project_classification_schema_status


COLUMNS = (
    ('projects', 'project_regime', 'VARCHAR(30)'),
    ('projects', 'investment_subtype', 'VARCHAR(30)'),
    ('projects', 'work_nature', 'VARCHAR(40)'),
    ('projects', 'contract_structure', 'VARCHAR(40)'),
    ('projects', 'optional_field_states', 'TEXT'),
)

INDEXES = (
    ('uq_projects_company_code', 'projects', 'company_id, code', True),
    ('ix_project_warning_dismissals_company_id', 'project_warning_dismissals', 'company_id', False),
    ('ix_project_warning_dismissals_project_id', 'project_warning_dismissals', 'project_id', False),
)


def _schema():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    columns = {table: {c['name'] for c in inspector.get_columns(table)} for table in tables}
    indexes = {table: {i['name'] for i in inspector.get_indexes(table)} for table in tables}
    return tables, columns, indexes


def _duplicate_codes(conn):
    return conn.execute(text(
        "SELECT company_id, code, COUNT(*) AS duplicate_count FROM projects "
        "WHERE company_id IS NOT NULL GROUP BY company_id, code HAVING COUNT(*) > 1"
    )).mappings().all()


def dry_run():
    tables, columns, _indexes = _schema()
    changes = 0
    for table, column, ddl in COLUMNS:
        if table not in tables:
            print(f'MISSING TABLE: {table} (migration cannot proceed)')
        elif column in columns[table]:
            print(f'PRESENT: {table}.{column}')
        else:
            print(f'WOULD ADD: {table}.{column} {ddl}')
            changes += 1
    if 'project_warning_dismissals' in tables:
        print('PRESENT: table project_warning_dismissals')
    else:
        print('WOULD CREATE: table project_warning_dismissals')
        changes += 1
    if 'projects' in tables:
        with db.engine.connect() as conn:
            duplicates = _duplicate_codes(conn)
        print(f'DUPLICATE COMPANY PROJECT CODES: {len(duplicates)}')
        if duplicates:
            print('BLOCKED: resolve duplicate company-scoped project codes before explicit apply.')
    print(f'DRY RUN: {changes} additive change(s) pending; nothing written.')


def apply_migration():
    tables, columns, _indexes = _schema()
    if 'projects' not in tables:
        raise RuntimeError('Required table missing: projects')
    with db.engine.connect() as conn:
        duplicates = _duplicate_codes(conn)
    if duplicates:
        raise RuntimeError('Duplicate company-scoped project codes block the unique index')

    added = 0
    with db.engine.begin() as conn:
        for table, column, ddl in COLUMNS:
            if column in columns.get(table, set()):
                print(f'PRESENT: {table}.{column}')
                continue
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'))
            print(f'ADDED: {table}.{column}')
            added += 1

    from app.models import ProjectWarningDismissal
    if 'project_warning_dismissals' not in tables:
        ProjectWarningDismissal.__table__.create(bind=db.engine, checkfirst=True)
        print('CREATED: table project_warning_dismissals')
        added += 1

    tables, columns, indexes = _schema()
    with db.engine.begin() as conn:
        for name, table, expression, unique in INDEXES:
            if name in indexes.get(table, set()):
                print(f'PRESENT: index {name}')
                continue
            keyword = 'UNIQUE ' if unique else ''
            conn.execute(text(
                f'CREATE {keyword}INDEX IF NOT EXISTS {name} ON {table} ({expression})'
            ))
            print(f'INDEX READY: {name}')

    project_classification_schema_status.cache_clear()
    print(f'APPLY COMPLETE: {added} additive change(s); no existing rows rewritten.')
    print('Existing projects remain unclassified until explicitly updated.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-project-classification', action='store_true')
    args = parser.parse_args()
    if args.apply and not args.confirm_project_classification:
        parser.error('--apply requires --confirm-project-classification')
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        apply_migration() if args.apply else dry_run()


if __name__ == '__main__':
    main()
