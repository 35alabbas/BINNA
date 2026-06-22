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

Manual billing: a company becomes `active` only when the super-admin records a
payment (record_payment, surfaced via the admin panel). `active` is exempt from
the auto-lock lifecycle ONLY while inside its paid window — once paid_until
lapses, the company auto-downgrades active→grace(7d)→locked, exactly like a
trial. A manually-activated company with paid_until NULL stays active (sticky).
"""
from datetime import timedelta

from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request

from app import db
from app.models import Payment, add_months, as_aware, is_past, _now

GRACE_DAYS = 7

_WRITE_METHODS   = {'POST', 'PUT', 'PATCH', 'DELETE'}     # safe methods always pass
_EXEMPT_PREFIXES = ('/api/v1/auth/',)                     # login/verify/reset must work when locked


def _in_paid_window(company):
    """True when the company has a paid period that has NOT yet lapsed.

    A NULL paid_until means 'no paid period recorded' (e.g. a company an admin
    flipped active by hand) — is_past(None) is False, so that account stays
    active and is never auto-downgraded. A paid_until in the past means the paid
    month lapsed: the account re-enters the trial→grace→locked lifecycle."""
    return not is_past(company.paid_until)


def _lapse_anchor(company):
    """The deadline the 7-day grace window runs from, once a company is no longer
    in a valid paid/trial window. A lapsed paid period takes precedence over the
    (always-past, once paid) trial date; otherwise grace runs from trial_ends_at.
    Returns None when nothing has lapsed yet (so grace is never stamped early)."""
    if company.paid_until is not None and is_past(company.paid_until):
        return company.paid_until
    if company.trial_ends_at is not None and is_past(company.trial_ends_at):
        return company.trial_ends_at
    return None


def compute_status(company):
    """Pure effective status from stored state — no DB writes.

    `active` is exempt from the auto-lock lifecycle ONLY while inside its paid
    window (paid_until in the future, or NULL = manually activated → sticky).
    A stored `locked` is sticky — once locked (auto OR manual admin suspend) an
    account only leaves via an explicit reactivation (record_payment / activate),
    which set status directly; it never auto-recovers to trial/grace. Otherwise
    the unpaid lifecycle drives it: a future OR NULL trial_ends_at ⇒ trial; once
    that is past, a future OR NULL grace_ends_at ⇒ grace; a past grace_ends_at ⇒
    locked. Because is_past(None) is False, a company with no deadlines never locks.
    """
    if company.status == 'active' and _in_paid_window(company):
        return 'active'
    if company.status == 'locked':
        return 'locked'
    if not is_past(company.trial_ends_at):
        return 'trial'
    if not is_past(company.grace_ends_at):
        return 'grace'
    return 'locked'


def refresh_status(company):
    """compute_status + persist transitions. Stamps grace_ends_at the first time the
    company lapses out of its trial OR its paid period (so grace is a real 7-day
    window, not open-ended). Commits only when something changed. Returns the
    effective status."""
    changed = False
    in_active = company.status == 'active' and _in_paid_window(company)
    # Don't stamp grace for an account that's active (still paid) or already
    # locked (sticky) — only for one that has just lapsed out of trial/paid.
    if not in_active and company.status != 'locked':
        anchor = _lapse_anchor(company)
        if anchor is not None and company.grace_ends_at is None:
            company.grace_ends_at = as_aware(anchor) + timedelta(days=GRACE_DAYS)
            changed = True

    eff = compute_status(company)
    if company.status != eff:
        company.status = eff
        changed = True
    if changed:
        db.session.commit()
    return eff


def record_payment(company, amount_iqd, method, months, recorded_by, note=None, paid_at=None):
    """Log a manual subscription payment and (re)activate the company.

    Extends the paid window: if the company is still inside a paid period, the
    new months stack on top of the existing paid_until (early renewal doesn't
    lose remaining days); otherwise the window starts now. Resets grace_ends_at
    so a future lapse re-stamps grace cleanly from the NEW paid_until rather than
    a stale trial-era value. Returns the persisted Payment row.
    """
    now = _now()
    base = as_aware(company.paid_until) if (company.paid_until and not is_past(company.paid_until)) else now
    new_paid_until = add_months(base, months)

    payment = Payment(
        company_id   = company.id,
        amount_iqd   = amount_iqd,
        method       = method,
        months       = months,
        period_start = base,
        period_end   = new_paid_until,
        note         = note,
        recorded_by  = recorded_by,
        paid_at      = paid_at or now,
    )
    company.status        = 'active'
    company.paid_until    = new_paid_until
    company.grace_ends_at = None            # clean slate: re-stamp grace from the new paid_until on a future lapse
    db.session.add(payment)
    db.session.commit()
    return payment


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
