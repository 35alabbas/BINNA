#!/usr/bin/env python3
"""Phase 1B-1 additive business-role schema migration.

Default mode is a read-only DRY RUN. No rows are rewritten and no existing
project receives a project manager. Explicit application requires both flags:

    python migrate_phase_1b_roles.py
    python migrate_phase_1b_roles.py --apply --confirm-phase-1b

Deploy the schema before deploying code that enables Phase 1B write endpoints.
Legacy application reads remain compatible because the new ORM columns are
deferred and Phase 1B endpoints fail closed while these columns are absent.
"""
import argparse
import os

from sqlalchemy import inspect, text

from app import create_app, db


COLUMNS = (
    ('users', 'is_company_manager', 'BOOLEAN NOT NULL DEFAULT FALSE'),
    ('companies', 'projects_manager_user_id', 'INTEGER'),
    ('projects', 'project_manager_user_id', 'INTEGER'),
)

INDEXES = (
    ('ix_companies_projects_manager_user_id', 'companies', 'projects_manager_user_id'),
    ('ix_projects_project_manager_user_id', 'projects', 'project_manager_user_id'),
)


def _tables_and_columns():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    columns = {
        table: {c['name'] for c in inspector.get_columns(table)}
        for table in tables
    }
    return tables, columns


def _candidate_summary(conn):
    """Report likely legacy managers without assigning or updating anything."""
    rows = conn.execute(text(
        "SELECT p.id, p.name, "
        "       SUM(CASE WHEN pm.role = 'owner' THEN 1 ELSE 0 END) AS owner_count, "
        "       MIN(CASE WHEN pm.role = 'owner' THEN pm.user_id END) AS candidate_user_id "
        "FROM projects p "
        "LEFT JOIN project_members pm ON pm.project_id = p.id "
        "GROUP BY p.id, p.name ORDER BY p.id"
    )).mappings().all()
    unique = [r for r in rows if r['owner_count'] == 1]
    ambiguous = [r for r in rows if r['owner_count'] != 1]
    print(f"Existing projects: {len(rows)}")
    print(f"Potential managers (one legacy owner): {len(unique)}")
    print(f"Needs manual review (zero/multiple owners): {len(ambiguous)}")
    for row in rows[:10]:
        candidate = row['candidate_user_id'] if row['owner_count'] == 1 else 'manual review'
        print(f"  project={row['id']} name={row['name']!r} candidate={candidate}")
    print("No project-manager assignments are written by this migration.")


def dry_run():
    tables, columns = _tables_and_columns()
    missing = []
    for table, column, ddl in COLUMNS:
        if table not in tables:
            print(f"MISSING TABLE: {table} (migration cannot proceed)")
        elif column in columns[table]:
            print(f"PRESENT: {table}.{column}")
        else:
            print(f"WOULD ADD: {table}.{column} {ddl}")
            missing.append((table, column))
    print(f"DRY RUN: {len(missing)} column(s) missing; nothing written.")
    if 'projects' in tables and 'project_members' in tables:
        with db.engine.connect() as conn:
            _candidate_summary(conn)


def apply_migration():
    tables, columns = _tables_and_columns()
    absent_tables = sorted({table for table, _, _ in COLUMNS if table not in tables})
    if absent_tables:
        raise RuntimeError(f"Required tables missing: {', '.join(absent_tables)}")

    added = []
    with db.engine.begin() as conn:
        for table, column, ddl in COLUMNS:
            if column in columns[table]:
                print(f"PRESENT: {table}.{column}")
                continue
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'))
            added.append(f'{table}.{column}')
            print(f"ADDED: {table}.{column}")
        for name, table, column in INDEXES:
            conn.execute(text(
                f'CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})'
            ))
            print(f"INDEX READY: {name}")

    print(f"APPLY COMPLETE: {len(added)} column(s) added; no rows rewritten.")
    print("Existing projects remain unassigned for later manual confirmation.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-phase-1b', action='store_true')
    args = parser.parse_args()
    if args.apply and not args.confirm_phase_1b:
        parser.error('--apply requires --confirm-phase-1b')

    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        if args.apply:
            apply_migration()
        else:
            dry_run()


if __name__ == '__main__':
    main()
