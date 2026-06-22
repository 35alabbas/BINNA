"""
BINNA — billing lifecycle (Phase 4): trial -> grace -> locked.

Decisions (Mohammed, 2026-06-22):
  • locked == READ-ONLY (view your data, can't edit) — not a full block.
  • grace == 7 days after the trial lapses.
  • evaluation is LAZY / request-time — no cron job (avoids the extra Render cost
    and any drift window between stored state and enforced state).

compute_status() is pure (no writes). refresh_status() persists transitions
(stamps grace_ends_at on entering grace) and is safe to call on every request.
A before_request guard makes a `locked` company read-only: mutating API calls get
403, reads always pass. ALL deadline checks go through models.is_past(), so a NULL
trial_ends_at/grace_ends_at NEVER locks an account.

Manual billing: a company becomes `active` only when the super-admin marks an
invoice paid (admin panel — later phase). `active` is exempt from the auto-lock
lifecycle here.
"""
from datetime import timedelta

from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request

from app import db
from app.models import as_aware, is_past

GRACE_DAYS = 7

_WRITE_METHODS   = {'POST', 'PUT', 'PATCH', 'DELETE'}     # safe methods always pass
_EXEMPT_PREFIXES = ('/api/v1/auth/',)                     # login/verify/reset must work when locked


def compute_status(company):
    """Pure effective status from stored state — no DB writes.

    'active' (manually marked paid) is exempt from the auto-lock lifecycle. For the
    unpaid lifecycle: a future OR NULL trial_ends_at ⇒ trial; once the trial is
    past, a future OR NULL grace_ends_at ⇒ grace; a past grace_ends_at ⇒ locked.
    Because is_past(None) is False, a company with no deadlines never locks.
    """
    if company.status == 'active':
        return 'active'
    if not is_past(company.trial_ends_at):
        return 'trial'
    if not is_past(company.grace_ends_at):
        return 'grace'
    return 'locked'


def refresh_status(company):
    """compute_status + persist transitions. Stamps grace_ends_at the first time the
    trial lapses (so grace is a real 7-day window, not open-ended). Commits only when
    something changed. Returns the effective status."""
    changed = False
    if (company.status != 'active'
            and company.trial_ends_at is not None and is_past(company.trial_ends_at)
            and company.grace_ends_at is None):
        company.grace_ends_at = as_aware(company.trial_ends_at) + timedelta(days=GRACE_DAYS)
        changed = True

    eff = compute_status(company)
    if company.status != eff:
        company.status = eff
        changed = True
    if changed:
        db.session.commit()
    return eff


def init_app(app):
    """Register the read-only-lock guard. Runs before each request; only acts on
    mutating API calls from an authenticated, non-super-admin, locked tenant."""
    # Imported here to avoid a circular import at module load.
    from app.tenancy import current_user

    @app.before_request
    def _enforce_company_lock():
        if request.method not in _WRITE_METHODS:
            return                                   # reads/HEAD/OPTIONS always allowed
        path = request.path
        if not path.startswith('/api/'):
            return
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return                                   # auth flows exempt
        try:
            verify_jwt_in_request(optional=True)
        except Exception:
            return                                   # bad/expired token → let the route's auth 401
        user = current_user()
        if not user or user.company_id is None:
            return                                   # unauthenticated / no tenant
        if user.role == 'admin':
            return                                   # platform super-admin is never locked out
        company = user.company
        if company is None:
            return
        if refresh_status(company) == 'locked':
            # `code` makes this unambiguously distinguishable from the role-gate
            # 403s ({'error': 'Insufficient permissions...'}) — a future
            # "why can't I edit" is diagnosed by the field, not by guessing
            # which check fired or substring-matching the message.
            return jsonify({
                'code':  'account_locked',
                'error': 'Your BINNA account is locked pending payment. It is '
                         'read-only — you can view your data but cannot make changes '
                         'until the account is reactivated.'
            }), 403
