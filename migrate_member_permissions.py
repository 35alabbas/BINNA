#!/usr/bin/env python3
"""
One-time migration: backfill ProjectMember.permissions.

Stamps every existing ProjectMember with a per-module view/edit permission map
set to exactly what that member's current project role already grants under
today's _get_membership / _requires_role / _check_access rules.

  * VIEW is granted for every module — no module hides itself today, so no
    existing member is ever migrated into an all-false (hidden) state.
  * EDIT is granted only where the member's role meets the module's current edit
    threshold (see app.models._MODULE_EDIT_MIN_ROLE). Viewers therefore stay
    read-only everywhere, including financial / gantt / uploads (which don't yet
    enforce that at the route layer) — current viewers are NOT upgraded to edit.

Idempotent: only rows whose permissions is NULL / '' / '{}' are backfilled, so
re-running changes nothing already set.

Default mode is a DRY RUN — reads only, writes nothing, alters nothing.

    python migrate_member_permissions.py            # dry run + samples
    python migrate_member_permissions.py --apply    # add column + backfill

Run once per environment (local dev DB and Render production DB).
"""
import json
import os
import sys

from sqlalchemy import inspect, text

from app import create_app, db
from app.models import default_permissions_for_role, PERMISSION_MODULES


def _fetch_members(conn):
    """Existing memberships joined to user/project for readable output.

    Raw SQL on purpose: it does not reference the new `permissions` column, so it
    works whether or not that column exists yet (dry run on a pre-migration DB).
    """
    return conn.execute(text(
        "SELECT pm.id AS id, pm.project_id AS project_id, pm.user_id AS user_id, "
        "       pm.role AS role, u.username AS username, p.name AS project_name "
        "FROM project_members pm "
        "LEFT JOIN users u    ON u.id = pm.user_id "
        "LEFT JOIN projects p ON p.id = pm.project_id "
        "ORDER BY pm.id"
    )).mappings().all()


def _column_exists(table, column):
    return column in [c['name'] for c in inspect(db.engine).get_columns(table)]


def _print_policy():
    print("Permission policy per role (view = ALL modules; edit listed):")
    for role in ('viewer', 'member', 'admin', 'owner'):
        perms = default_permissions_for_role(role)
        edits = [m for m, f in perms.items() if f['edit']]
        print(f"  {role:7} -> edit: {', '.join(edits) if edits else '(none — view only)'}")
    print()


def dry_run():
    with db.engine.connect() as conn:
        members = _fetch_members(conn)

    by_role = {}
    for m in members:
        by_role[m['role']] = by_role.get(m['role'], 0) + 1

    print("DRY RUN — nothing written, no column added.\n")
    print(f"project_members rows: {len(members)}")
    print(f"by role: {by_role or '(none)'}\n")
    _print_policy()

    sample = members[:3]
    if not sample:
        print("No existing members in this DB to sample.")
        return
    print(f"Sample of {len(sample)} member(s) with resulting permissions:")
    for m in sample:
        perms = default_permissions_for_role(m['role'])
        print(f"\n  member id={m['id']}  user={m['username']!r}  "
              f"project={m['project_name']!r}  role={m['role']}")
        for mod in PERMISSION_MODULES:
            f = perms[mod]
            print(f"      {mod:15} view={str(f['view']):5} edit={f['edit']}")


def apply():
    # 1. Ensure the column exists (idempotent ALTER — same DDL as _ensure_schema).
    if _column_exists('project_members', 'permissions'):
        print("Column project_members.permissions already present.")
    else:
        with db.engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE project_members ADD COLUMN permissions TEXT DEFAULT '{}'"
            ))
        print("Added column project_members.permissions.")

    # 2. Backfill only un-provisioned rows.
    updated, skipped = 0, 0
    with db.engine.begin() as conn:
        members = _fetch_members(conn)
        current = {
            r['id']: (r['permissions'] or '').strip()
            for r in conn.execute(text(
                "SELECT id, permissions FROM project_members"
            )).mappings().all()
        }
        for m in members:
            if current.get(m['id'], '') not in ('', '{}'):
                skipped += 1
                continue
            perms = default_permissions_for_role(m['role'])
            conn.execute(
                text("UPDATE project_members SET permissions = :p WHERE id = :id"),
                {'p': json.dumps(perms), 'id': m['id']},
            )
            updated += 1
    print(f"Backfill complete — {updated} updated, {skipped} already set.")

    # 3. Invariant check: no member may be hidden (both flags false) anywhere.
    hidden = []
    with db.engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, permissions FROM project_members"
        )).mappings().all()
    for r in rows:
        try:
            perms = json.loads(r['permissions']) if r['permissions'] else {}
        except (ValueError, TypeError):
            perms = {}
        for mod, f in perms.items():
            if not f.get('view') and not f.get('edit'):
                hidden.append((r['id'], mod))
    if hidden:
        print(f"WARNING: {len(hidden)} module(s) ended up hidden: {hidden[:5]}")
    else:
        print("Invariant OK: no member is hidden from any module.")


def main():
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        if '--apply' in sys.argv:
            apply()
        else:
            dry_run()


if __name__ == '__main__':
    main()
