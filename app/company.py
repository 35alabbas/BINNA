"""
BINNA — Company (tenant) management blueprint  (Phase 2)

GET    /api/v1/company                     current company + trial info
GET    /api/v1/company/members             list members (any member)
POST   /api/v1/company/invite              invite by email + role (owner/admin)
POST   /api/v1/company/accept-invite       set password → activate (public)
PUT    /api/v1/company/members/<id>        change a member's company_role (owner/admin)
DELETE /api/v1/company/members/<id>        deactivate a member (owner/admin)

Tenant role (users.company_role) governs these routes via require_company_role —
strictly separate from the platform role (users.role). All reads are implicitly
company-scoped: every query filters on the caller's own company_id.
"""
import re
import secrets

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, get_jwt_identity,
)
from sqlalchemy import func

from app import db
from app.models import User, Upload
from app.tenancy import current_user, require_company_role
from app.email import send_invite_email

company_bp = Blueprint('company', __name__, url_prefix='/api/v1/company')

_VALID_COMPANY_ROLES = {'admin', 'member', 'viewer'}   # 'owner' is not assignable via invite


def _token() -> str:
    return secrets.token_urlsafe(32)


def _derive_username(email: str) -> str:
    """Build a unique username from an email local-part."""
    base = re.sub(r'[^a-zA-Z0-9_]+', '', email.split('@', 1)[0]) or 'user'
    if len(base) < 3:
        base = f'{base}usr'
    candidate = base
    n = 2
    while User.query.filter_by(username=candidate).first():
        candidate = f'{base}{n}'
        n += 1
    return candidate


# ── Current company ─────────────────────────────────────────────────────────────

@company_bp.route('', methods=['GET'])
@jwt_required()
def get_company():
    user = current_user()
    if not user or not user.company:
        return jsonify({'error': 'No company attached to this account'}), 404
    return jsonify({'company': user.company.to_dict(), 'my_role': user.company_role})


# ── Storage usage (company-scoped R2 indicator) ──────────────────────────────────

@company_bp.route('/storage', methods=['GET'])
@jwt_required()
def storage_usage():
    """Per-company storage usage for the CEO-workspace indicator.

    Sums Upload.size_bytes across the caller's own company. Files uploaded before
    the size_bytes column existed count as 0 (COALESCE), so this is a lower bound
    until those are re-uploaded — surfaced honestly via `untracked_files`.
    """
    user = current_user()
    if not user or user.company_id is None:
        return jsonify({'error': 'No company attached to this account'}), 404

    used = db.session.query(func.coalesce(func.sum(Upload.size_bytes), 0)) \
        .filter(Upload.company_id == user.company_id).scalar() or 0
    file_count = db.session.query(func.count(Upload.id)) \
        .filter(Upload.company_id == user.company_id).scalar() or 0
    untracked = db.session.query(func.count(Upload.id)) \
        .filter(Upload.company_id == user.company_id, Upload.size_bytes.is_(None)).scalar() or 0

    quota = current_app.config.get('STORAGE_QUOTA_BYTES', 0)
    percent = round(used / quota * 100, 1) if quota else None
    return jsonify({
        'used_bytes':      int(used),
        'quota_bytes':     int(quota),
        'percent_used':    percent,
        'file_count':      int(file_count),
        'untracked_files': int(untracked),
    })


# ── List members (company-scoped) ───────────────────────────────────────────────

@company_bp.route('/members', methods=['GET'])
@jwt_required()
def list_members():
    user = current_user()
    if not user or user.company_id is None:
        return jsonify({'error': 'No company attached to this account'}), 404

    # SCOPED: only users of the caller's own company are ever returned.
    members = User.query.filter_by(company_id=user.company_id).all()
    return jsonify({
        'members': [{
            'id':             m.id,
            'username':       m.username,
            'email':          m.email,
            'company_role':   m.company_role,
            'email_verified': m.email_verified,
            'is_active':      m.is_active,
            'pending':        m.invite_pending,
        } for m in members],
        'total': len(members),
    })


# ── Invite a member ─────────────────────────────────────────────────────────────

@company_bp.route('/invite', methods=['POST'])
@require_company_role('admin')
def invite_member(user):
    data  = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    role  = (data.get('company_role') or data.get('role') or 'member').strip()

    if not email or '@' not in email:
        return jsonify({'error': 'A valid email is required'}), 400
    if role not in _VALID_COMPANY_ROLES:
        return jsonify({'error': f'Role must be one of: {", ".join(sorted(_VALID_COMPANY_ROLES))}'}), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        if existing.company_id == user.company_id:
            return jsonify({'error': 'That person is already in your company'}), 409
        return jsonify({'error': 'That email is already registered to another account'}), 409

    invitee = User(
        username                 = _derive_username(email),
        email                    = email,
        company_id               = user.company_id,   # SCOPED to the inviter's company
        company_role             = role,
        email_verified           = False,
        invite_pending           = True,
        email_verification_token = _token(),
    )
    # Unusable placeholder password until the invitee sets their own on acceptance.
    invitee.set_password(secrets.token_urlsafe(24))

    db.session.add(invitee)
    db.session.commit()

    link = (f"{current_app.config['APP_BASE_URL']}"
            f"/accept-invite?token={invitee.email_verification_token}")
    send_invite_email(invitee.email, user.company.name, user.username, link)

    return jsonify({
        'message': f'Invitation sent to {email}.',
        'member': {
            'id':           invitee.id,
            'email':        invitee.email,
            'company_role': invitee.company_role,
            'pending':      True,
        },
    }), 201


# ── Accept an invitation (public — the link doubles as verification) ────────────

@company_bp.route('/accept-invite', methods=['POST'])
def accept_invite():
    data     = request.get_json(silent=True) or {}
    token    = (data.get('token') or '').strip()
    password = (data.get('password') or '')
    username = (data.get('username') or '').strip()

    if not token or not password:
        return jsonify({'error': 'Token and password are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    invitee = User.query.filter_by(
        email_verification_token=token, invite_pending=True
    ).first()
    if not invitee:
        return jsonify({'error': 'Invalid or already-used invitation link'}), 400

    if username and username != invitee.username:
        if len(username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        clash = User.query.filter_by(username=username).first()
        if clash and clash.id != invitee.id:
            return jsonify({'error': 'Username already taken'}), 409
        invitee.username = username

    invitee.set_password(password)
    invitee.email_verified           = True   # invite link doubles as verification
    invitee.invite_pending           = False
    invitee.email_verification_token = None
    db.session.commit()

    access_token  = create_access_token(identity=str(invitee.id))
    refresh_token = create_refresh_token(identity=str(invitee.id))
    return jsonify({
        'user':          invitee.to_dict(),
        'access_token':  access_token,
        'refresh_token': refresh_token,
    }), 200


# ── Change a member's company role ──────────────────────────────────────────────

@company_bp.route('/members/<int:member_id>', methods=['PUT'])
@require_company_role('admin')
def update_member_role(user, member_id):
    target = User.query.get(member_id)
    # SCOPED: a member of another company is invisible here (treated as not found).
    if not target or target.company_id != user.company_id:
        return jsonify({'error': 'Member not found'}), 404
    if target.company_role == 'owner':
        return jsonify({'error': 'The company owner role cannot be changed'}), 403
    if target.id == user.id:
        return jsonify({'error': 'You cannot change your own role'}), 403

    data = request.get_json(silent=True) or {}
    role = (data.get('company_role') or data.get('role') or '').strip()
    if role not in _VALID_COMPANY_ROLES:
        return jsonify({'error': f'Role must be one of: {", ".join(sorted(_VALID_COMPANY_ROLES))}'}), 400

    target.company_role = role
    db.session.commit()
    return jsonify({'member': {'id': target.id, 'company_role': target.company_role}})


# ── Deactivate a member ─────────────────────────────────────────────────────────

@company_bp.route('/members/<int:member_id>', methods=['DELETE'])
@require_company_role('admin')
def deactivate_member(user, member_id):
    target = User.query.get(member_id)
    if not target or target.company_id != user.company_id:
        return jsonify({'error': 'Member not found'}), 404
    if target.company_role == 'owner':
        return jsonify({'error': 'The company owner cannot be removed'}), 403
    if target.id == user.id:
        return jsonify({'error': 'You cannot remove yourself'}), 403

    target.is_active = False
    db.session.commit()
    return jsonify({'message': 'Member deactivated'})
