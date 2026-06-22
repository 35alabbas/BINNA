"""
BINNA — Platform admin panel (Phase 4)

The single BINNA super-admin (users.role == 'admin', the first-ever signup)
manages every customer company from here. Manual billing only — no payment API:
the admin records payments made via Zain Cash / Asia Hawala / Qi Card / NBI and
flips company state by hand. Currency is IQD throughout.

GET  /api/v1/admin/companies                 list every company (effective status, deadlines, members, paid total)
POST /api/v1/admin/companies/<id>/activate   manually mark a company active (sticky — no paid period)
POST /api/v1/admin/companies/<id>/suspend    manually lock a company (read-only) until reactivated
POST /api/v1/admin/companies/<id>/mark-paid   record a payment → active + extend paid_until
GET  /api/v1/admin/revenue                    payment log + totals (the revenue tracker)

Every route is gated by require_platform_admin (PLATFORM role, distinct from the
tenant company_role). All state transitions go through app.billing so the lazy
lock lifecycle stays the single source of truth.
"""
from flask import Blueprint, request, jsonify
from sqlalchemy import func

from app import db, billing
from app.models import Company, User, Payment, PAYMENT_METHODS
from app.tenancy import require_platform_admin

admin_bp = Blueprint('admin', __name__, url_prefix='/api/v1/admin')


def _company_row(company, member_counts, owner_emails, paid_totals):
    """Build one admin-list row. `status` is the EFFECTIVE status (pure compute,
    no write) so the admin sees reality even before a tenant's next request
    lazily persists a transition."""
    return {
        'id':            company.id,
        'name':          company.name,
        'slug':          company.slug,
        'plan':          company.plan,
        'status':        billing.compute_status(company),
        'stored_status': company.status,
        'trial_ends_at': company.trial_ends_at.isoformat() if company.trial_ends_at else None,
        'grace_ends_at': company.grace_ends_at.isoformat() if company.grace_ends_at else None,
        'paid_until':    company.paid_until.isoformat() if company.paid_until else None,
        'created_at':    company.created_at.isoformat() if company.created_at else None,
        'member_count':  member_counts.get(company.id, 0),
        'owner_email':   owner_emails.get(company.id),
        'total_paid_iqd': paid_totals.get(company.id, 0),
    }


@admin_bp.route('/companies', methods=['GET'])
@require_platform_admin
def list_companies(user):
    companies = Company.query.order_by(Company.created_at.desc()).all()

    # One aggregate query each — avoids an N+1 across the company list.
    member_counts = dict(
        db.session.query(User.company_id, func.count(User.id))
        .filter(User.company_id.isnot(None), User.is_active.is_(True))
        .group_by(User.company_id).all()
    )
    owner_emails = dict(
        db.session.query(User.company_id, User.email)
        .filter(User.company_id.isnot(None), User.company_role == 'owner').all()
    )
    paid_totals = dict(
        db.session.query(Payment.company_id, func.coalesce(func.sum(Payment.amount_iqd), 0))
        .group_by(Payment.company_id).all()
    )

    rows = [_company_row(c, member_counts, owner_emails, paid_totals) for c in companies]
    return jsonify({'companies': rows, 'total': len(rows)})


def _get_company_or_404(company_id):
    return db.session.get(Company, company_id)


@admin_bp.route('/companies/<int:company_id>/activate', methods=['POST'])
@require_platform_admin
def activate_company(user, company_id):
    """Manual activation — sticky `active` with NO paid period (paid_until stays
    NULL). Use mark-paid instead to activate AND extend a paid window. Clears a
    stale grace deadline so a future lapse re-stamps cleanly."""
    company = _get_company_or_404(company_id)
    if company is None:
        return jsonify({'error': 'Company not found'}), 404
    company.status        = 'active'
    company.grace_ends_at = None
    db.session.commit()
    return jsonify({'company': company.to_dict(), 'message': f'{company.name} activated.'})


@admin_bp.route('/companies/<int:company_id>/suspend', methods=['POST'])
@require_platform_admin
def suspend_company(user, company_id):
    """Manual suspend — set status=locked (read-only). Locked is sticky in the
    billing lifecycle, so this holds until an explicit reactivation."""
    company = _get_company_or_404(company_id)
    if company is None:
        return jsonify({'error': 'Company not found'}), 404
    company.status = 'locked'
    db.session.commit()
    return jsonify({'company': company.to_dict(), 'message': f'{company.name} suspended (read-only).'})


@admin_bp.route('/companies/<int:company_id>/mark-paid', methods=['POST'])
@require_platform_admin
def mark_paid(user, company_id):
    """Record a manual payment → activate + extend the paid window.

    Body: { amount_iqd: int>0, method: <PAYMENT_METHODS key>, months: int>=1
            (default 1), note?: str }.
    """
    company = _get_company_or_404(company_id)
    if company is None:
        return jsonify({'error': 'Company not found'}), 404

    data = request.get_json(silent=True) or {}

    # amount — whole IQD, strictly positive.
    try:
        amount = int(data.get('amount_iqd'))
    except (TypeError, ValueError):
        return jsonify({'error': 'amount_iqd must be a whole number of IQD'}), 400
    if amount <= 0:
        return jsonify({'error': 'amount_iqd must be greater than zero'}), 400

    method = (data.get('method') or '').strip()
    if method not in PAYMENT_METHODS:
        return jsonify({
            'error': f'method must be one of: {", ".join(sorted(PAYMENT_METHODS))}'
        }), 400

    # months — paid-period length, default 1, at least 1.
    try:
        months = int(data.get('months', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'months must be a whole number'}), 400
    if months < 1:
        return jsonify({'error': 'months must be at least 1'}), 400

    note = (data.get('note') or '').strip() or None

    payment = billing.record_payment(
        company, amount_iqd=amount, method=method, months=months,
        recorded_by=user.id, note=note,
    )
    return jsonify({
        'message': f'Payment recorded. {company.name} is active until '
                   f'{company.paid_until.date().isoformat()}.',
        'company': company.to_dict(),
        'payment': payment.to_dict(),
    }), 201


@admin_bp.route('/revenue', methods=['GET'])
@require_platform_admin
def revenue(user):
    """The revenue tracker — full payment log (most recent first) plus totals and
    a per-method breakdown. All amounts in IQD."""
    payments = Payment.query.order_by(Payment.paid_at.desc()).all()

    by_method = {k: 0 for k in PAYMENT_METHODS}
    total = 0
    for p in payments:
        total += p.amount_iqd or 0
        by_method[p.method] = by_method.get(p.method, 0) + (p.amount_iqd or 0)

    return jsonify({
        'payments':   [p.to_dict() for p in payments],
        'count':      len(payments),
        'total_iqd':  total,
        'by_method':  by_method,
        'methods':    PAYMENT_METHODS,   # key → label, for the UI's method picker
    })
