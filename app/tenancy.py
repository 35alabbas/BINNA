"""
BINNA — Tenant isolation (Phase 2)

This module is the single chokepoint for multi-tenant access control. Every data
endpoint in the app resolves access through a project-membership helper before
touching data; those helpers now delegate here, so tenant isolation is enforced
in exactly one place.

The rule: a request may only reach a project (and therefore any row hanging off
that project) when the project belongs to the *caller's own company*. A
`ProjectMember` row is necessary but NOT sufficient — the company_id on the
project must match the company_id on the user. This blocks both:
  • a route that forgets to scope its own query (the gate already 404'd), and
  • a stale/forged cross-company ProjectMember row (company_id mismatch → 404).

Legacy note: pre-Phase-2 rows carry company_id = NULL. Python's `None == None`
is True, so a legacy user (company_id NULL) still reaches legacy projects
(company_id NULL) — single-tenant dev data keeps working. Every account created
through the Phase 2 signup/invite flow has a real company_id, so two real
tenants are always strictly isolated.
"""
from functools import lru_cache, wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import inspect

from app import db
from app.models import PERMISSION_MODULES, Project, ProjectMember, User

# Tenant role hierarchy (distinct from project-membership roles, though they
# share the same ladder of names).
_COMPANY_ROLE_ORDER = {'viewer': 0, 'member': 1, 'admin': 2, 'owner': 3}


def current_user():
    """Load the User behind the current JWT identity, or None."""
    uid = get_jwt_identity()
    if uid is None:
        return None
    try:
        return User.query.get(int(uid))
    except (TypeError, ValueError):
        return None


def same_company(project, user) -> bool:
    """True when `project` belongs to `user`'s company (the isolation predicate)."""
    if project is None or user is None:
        return False
    return project.company_id == user.company_id


def membership_or_none(project_id, user_id):
    """The company-aware project gate.

    Returns (project, member) ONLY when:
      • the user exists, and
      • the project exists, and
      • the project belongs to the user's company  (TENANT ISOLATION), and
      • the user has a ProjectMember row on that project.
    Otherwise returns (None, None). Every route helper delegates here.
    """
    user = User.query.get(int(user_id)) if user_id is not None else None
    if user is None:
        return None, None

    project = Project.query.get(project_id)
    if project is None:
        return None, None

    # ── TENANT ISOLATION — the make-or-break check ──────────────────────────────
    if not same_company(project, user):
        return None, None

    member = ProjectMember.query.filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    if member is None:
        return None, None

    return project, member


_PHASE_1B_COLUMNS = {
    'users': {'is_company_manager'},
    'companies': {'projects_manager_user_id'},
    'projects': {'project_manager_user_id'},
}

_PHASE_1B_2_COLUMNS = {
    'projects': {'is_closed', 'closed_at', 'closed_by_user_id'},
}
_PHASE_1B_2_TABLES = {'project_monitoring_comments', 'audit_logs'}


class ProjectClosedError(Exception):
    """Raised only after tenant access is established for a closed project."""


@lru_cache(maxsize=1)
def phase_1b_2_schema_status() -> dict:
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    missing = {}
    for table, required in _PHASE_1B_2_COLUMNS.items():
        present = ({c['name'] for c in inspector.get_columns(table)}
                   if table in tables else set())
        absent = sorted(required - present)
        if absent:
            missing[table] = absent
    absent_tables = sorted(_PHASE_1B_2_TABLES - tables)
    if absent_tables:
        missing['tables'] = absent_tables
    return {'ready': not missing, 'missing': missing}


def is_project_closed(project) -> bool:
    """Pre-migration projects are treated as open for legacy compatibility."""
    return bool(phase_1b_2_schema_status()['ready'] and project.is_closed)


@lru_cache(maxsize=1)
def phase_1b_schema_status() -> dict:
    """Read-only Phase 1B schema check, cached for this app process.

    Applying the explicit migration requires an application restart, which also
    refreshes this cache. The function itself never creates or alters anything.
    """
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    missing = {}
    for table, required in _PHASE_1B_COLUMNS.items():
        present = ({c['name'] for c in inspector.get_columns(table)}
                   if table in tables else set())
        absent = sorted(required - present)
        if absent:
            missing[table] = absent
    return {'ready': not missing, 'missing': missing}


def is_company_manager(user) -> bool:
    """Business company manager, with legacy owner compatibility."""
    if user is None or user.company_id is None:
        return False
    if user.company_role == 'owner':
        return True
    if not phase_1b_schema_status()['ready']:
        return False
    return bool(user.is_company_manager)


def is_projects_manager(user) -> bool:
    """The one designated portfolio manager for the user's company."""
    if user is None or user.company_id is None:
        return False
    if not phase_1b_schema_status()['ready'] or user.company is None:
        return False
    return user.company.projects_manager_user_id == user.id


def can_manage_project_portfolio(user) -> bool:
    return is_company_manager(user) or is_projects_manager(user)


def is_project_manager(user, project) -> bool:
    """True only for the explicitly assigned project manager."""
    if user is None or project is None or not same_company(project, user):
        return False
    if not phase_1b_schema_status()['ready']:
        return False
    return project.project_manager_user_id == user.id


def is_effective_project_manager(user, project) -> bool:
    """Resolve explicit PM, projects-manager fallback, then company manager."""
    if user is None or project is None or not same_company(project, user):
        return False
    if not phase_1b_schema_status()['ready']:
        return False
    if project.project_manager_user_id is not None:
        return project.project_manager_user_id == user.id
    company = user.company
    if company is not None and company.projects_manager_user_id is not None:
        return company.projects_manager_user_id == user.id
    return is_company_manager(user)


class _EffectiveManagerAccess:
    """Non-persistent adapter for legacy routes that expect a member object."""

    role = 'owner'
    id = None

    def __init__(self, project_id, user_id):
        self.project_id = project_id
        self.user_id = user_id

    @staticmethod
    def can(_module, _action='view'):
        return True

    @staticmethod
    def effective_permissions():
        return {
            module: {'view': True, 'edit': True}
            for module in PERMISSION_MODULES
        }


def authorize_project_access(project_id, user_id, module, action='view', min_role='viewer'):
    """Central Phase 1B project authorization.

    Returns ``(project, member, allowed)``. Tenant isolation is always first.
    Portfolio managers receive company-wide read access. The effective project
    manager receives full operational access without requiring a legacy
    ProjectMember row. Everyone else keeps the exact legacy ProjectMember role
    + per-module permission behavior.
    """
    user = User.query.get(int(user_id)) if user_id is not None else None
    project = Project.query.get(project_id)
    if user is None or project is None or not same_company(project, user):
        return None, None, False

    member = ProjectMember.query.filter_by(
        project_id=project_id, user_id=user_id,
    ).first()

    if is_effective_project_manager(user, project):
        if action == 'edit' and is_project_closed(project):
            raise ProjectClosedError()
        return project, (member or _EffectiveManagerAccess(project.id, user.id)), True
    if action == 'view' and can_manage_project_portfolio(user):
        return project, member, True
    if member is None:
        return project, None, False

    from app.models import _ROLE_ORDER
    if _ROLE_ORDER.get(member.role, 0) < _ROLE_ORDER.get(min_role, 0):
        return project, member, False
    allowed = member.can(module, action)
    if allowed and action == 'edit' and is_project_closed(project):
        raise ProjectClosedError()
    return project, member, allowed


def can_manage_project_assignments(user, project) -> bool:
    """Portfolio managers and the effective PM manage project staffing."""
    return (user is not None and project is not None and same_company(project, user)
            and (can_manage_project_portfolio(user)
                 or is_effective_project_manager(user, project)))


def can_read_project_management_records(user, project) -> bool:
    """Portfolio managers or the effective PM may read comments/audit."""
    return (user is not None and project is not None and same_company(project, user)
            and (can_manage_project_portfolio(user)
                 or is_effective_project_manager(user, project)))


def company_role_at_least(user, min_role: str) -> bool:
    """True when the user's TENANT role meets or exceeds `min_role`."""
    if user is None or user.company_id is None:
        return False
    return _COMPANY_ROLE_ORDER.get(user.company_role, 0) >= _COMPANY_ROLE_ORDER.get(min_role, 0)


def require_platform_admin(fn):
    """Decorator for platform-admin routes (the admin panel).

    Gates on the PLATFORM role (users.role == 'admin') — the single BINNA
    super-admin (first-ever signup) — NOT the tenant company_role. This is a
    different axis from require_company_role: a company owner is the top of their
    tenant but has no platform-admin access. Injects the loaded User as `user`.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = current_user()
        if user is None:
            return jsonify({'error': 'User not found'}), 404
        if user.role != 'admin':
            return jsonify({'error': 'Platform administrator access required'}), 403
        kwargs['user'] = user
        return fn(*args, **kwargs)
    return wrapper


def require_company_role(min_role: str):
    """Decorator for company-management routes (invites, member admin).

    Verifies a valid JWT, loads the user, and requires their tenant company_role
    to be >= `min_role`. Injects the loaded User as the `user` kwarg. Keeps the
    PLATFORM role (users.role) entirely separate — this checks ONLY tenant role.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = current_user()
            if user is None:
                return jsonify({'error': 'User not found'}), 404
            if user.company_id is None:
                return jsonify({'error': 'Your account is not attached to a company'}), 403
            if not company_role_at_least(user, min_role):
                return jsonify({'error': 'Insufficient company permissions'}), 403
            kwargs['user'] = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator
