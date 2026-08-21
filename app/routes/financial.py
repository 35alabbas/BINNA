"""
BINNA — Financial Data API  (Phase 6)
Routes: /api/v1/projects/<project_id>/financial
Stores the entire financial data as a JSON blob per project.
"""
import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import FinancialData, Project, ProjectMember, _ROLE_ORDER
from app.tenancy import authorize_project_access

financial_bp = Blueprint('financial', __name__)


# This blueprint's per-module permission key (see ProjectMember.can / effective_permissions).
_MODULE = 'financial'


def _check_access(project_id, user_id):
    # Company-scoped gate (READ): returns the project only when it belongs to the
    # caller's company AND the user is a member; otherwise None.
    proj, _mem, allowed = authorize_project_access(
        project_id, user_id, _MODULE, 'view', 'viewer')
    return proj if allowed else None


def _requires_role(project_id, user_id, min_role='member'):
    """Company-scoped gate (WRITE) — mirrors the seven already-gated modules.
    (None, None) → 404 (no access / wrong tenant); (project, None) → 403 (role too low)."""
    proj, mem, allowed = authorize_project_access(
        project_id, user_id, _MODULE, 'edit', min_role)
    if not proj:
        return None, None
    if not allowed:
        return proj, None
    if not allowed:
        return proj, None   # module edit revoked via the per-member permission map → 403
    return proj, mem


@financial_bp.route('', methods=['GET'])
@jwt_required()
def get_financial(project_id):
    uid = int(get_jwt_identity())
    proj = _check_access(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    fd = FinancialData.query.filter_by(project_id=project_id).first()
    if not fd or not fd.data:
        return jsonify({'data': None}), 200

    try:
        data = json.loads(fd.data)
    except (ValueError, TypeError):
        data = None

    return jsonify({'data': data}), 200


@financial_bp.route('', methods=['PUT'])
@jwt_required()
def save_financial(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    body = request.get_json(silent=True) or {}
    payload = body.get('data')

    fd = FinancialData.query.filter_by(project_id=project_id).first()
    if not fd:
        fd = FinancialData(project_id=project_id, updated_by=uid)
        db.session.add(fd)

    fd.data       = json.dumps(payload, ensure_ascii=False)
    fd.updated_by = uid
    fd.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True}), 200


@financial_bp.route('/income', methods=['PUT'])
@jwt_required()
def save_income_expenses(project_id):
    """Partial update — only writes income/expense fields, never touches BOQ/VO/payments."""
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    body = request.get_json(silent=True) or {}

    fd = FinancialData.query.filter_by(project_id=project_id).first()
    if not fd:
        fd = FinancialData(project_id=project_id, updated_by=uid)
        db.session.add(fd)

    # Load existing blob, preserving contract/BOQ/VO/payments
    existing = {}
    if fd.data:
        try:
            existing = json.loads(fd.data) or {}
        except (ValueError, TypeError):
            existing = {}

    # Patch only the income/expense fields
    existing['income']             = body.get('income',             existing.get('income', []))
    existing['expenses']           = body.get('expenses',           existing.get('expenses', []))
    existing['incomeCategories']   = body.get('incomeCategories',   existing.get('incomeCategories', []))
    existing['expenseCategories']  = body.get('expenseCategories',  existing.get('expenseCategories', []))
    existing['usdRate']            = body.get('usdRate',            existing.get('usdRate', 1310))

    fd.data       = json.dumps(existing, ensure_ascii=False)
    fd.updated_by = uid
    fd.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True}), 200
