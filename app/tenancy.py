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
from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.models import Project, ProjectMember, User

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


def company_role_at_least(user, min_role: str) -> bool:
    """True when the user's TENANT role meets or exceeds `min_role`."""
    if user is None or user.company_id is None:
        return False
    return _COMPANY_ROLE_ORDER.get(user.company_role, 0) >= _COMPANY_ROLE_ORDER.get(min_role, 0)


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
