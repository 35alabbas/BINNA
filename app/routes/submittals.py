"""
BINNA — Submittals API  (Phase 3)
Handles five approval-workflow modules with a single blueprint:
  DWG  Drawing Submissions
  FIR  Field Inspection Requests
  MIR  Material Inspection Requests
  MS   Method Statements
  RFI  Requests for Information

All routes sit under:
  /api/v1/projects/<project_id>/submittals/<module_type>
"""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import (Submittal, Project, ProjectMember, _ROLE_ORDER,
                        VALID_SUBMITTAL_TYPES, VALID_SUBMITTAL_STATUSES)

submittals_bp = Blueprint('submittals', __name__)

# Maps module_type → uppercase code used inside the doc code string
_MODULE_CODES = {
    'dwg': 'DWG',
    'fir': 'FIR',
    'mir': 'MIR',
    'ms':  'MS',
    'rfi': 'RFI',
}


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_membership(project_id: int, user_id: int):
    proj = Project.query.get(project_id)
    if not proj:
        return None, None
    mem = ProjectMember.query.filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    return (proj, mem) if mem else (None, None)


def _requires_role(project_id: int, user_id: int, min_role: str = 'viewer'):
    proj, mem = _get_membership(project_id, user_id)
    if not proj:
        return None, None   # 404
    if _ROLE_ORDER.get(mem.role, 0) < _ROLE_ORDER.get(min_role, 0):
        return proj, None   # 403
    return proj, mem


def _parse_date(val):
    if not val:
        return None
    from datetime import date
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def _build_code(project_code: str, module_type: str, doc_number: int, revision: str) -> str:
    mc = _MODULE_CODES.get(module_type, module_type.upper())
    return f"{project_code}-{mc}-{str(doc_number).zfill(3)}-{revision or 'A'}"


def _validate_module(module_type: str):
    if module_type not in VALID_SUBMITTAL_TYPES:
        return jsonify({'error': f"Invalid module type '{module_type}'. "
                                 f"Must be one of: {', '.join(sorted(VALID_SUBMITTAL_TYPES))}"}), 400
    return None


# ── List / Create ─────────────────────────────────────────────────────────────

@submittals_bp.route('/<module_type>', methods=['GET'])
@jwt_required()
def list_submittals(project_id: int, module_type: str):
    err = _validate_module(module_type)
    if err:
        return err

    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    query = Submittal.query.filter_by(project_id=project_id, module_type=module_type)

    status = request.args.get('status')
    search = request.args.get('q', '').strip().lower()

    if status in VALID_SUBMITTAL_STATUSES:
        query = query.filter_by(status=status)
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                Submittal.code.ilike(like),
                Submittal.title.ilike(like),
                Submittal.location.ilike(like),
            )
        )

    items = query.order_by(Submittal.doc_number.asc(), Submittal.revision.asc()).all()
    return jsonify({
        'items': [s.to_dict() for s in items],
        'total': len(items),
    }), 200


@submittals_bp.route('/<module_type>', methods=['POST'])
@jwt_required()
def create_submittal(project_id: int, module_type: str):
    err = _validate_module(module_type)
    if err:
        return err

    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    data = request.get_json(silent=True) or {}

    # Required fields
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'title is required'}), 400

    submittal_date = _parse_date(data.get('submittal_date'))
    if not submittal_date:
        return jsonify({'error': 'submittal_date is required (ISO format: YYYY-MM-DD)'}), 400

    try:
        doc_number = int(data.get('doc_number', 1))
        if doc_number < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'error': 'doc_number must be a positive integer'}), 400

    revision = (data.get('revision') or 'A').strip().upper()
    description = (data.get('description') or '').strip()

    status = data.get('status', 'pending')
    if status not in VALID_SUBMITTAL_STATUSES:
        status = 'pending'

    code = _build_code(proj.code, module_type, doc_number, revision)

    item = Submittal(
        project_id     = project_id,
        module_type    = module_type,
        code           = code,
        doc_number     = doc_number,
        revision       = revision,
        title          = title,
        description    = description,
        submittal_date = submittal_date,
        location       = (data.get('location')     or '').strip(),
        engineer       = (data.get('engineer')      or '').strip(),
        related_refs   = (data.get('related_refs')  or '').strip(),
        submitted_to   = (data.get('submitted_to')  or '').strip(),
        cc_party       = (data.get('cc_party')      or '').strip(),
        notes          = (data.get('notes')         or '').strip(),
        status         = status,
        file_name      = (data.get('file_name')     or '').strip(),
        created_by     = uid,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'item': item.to_dict()}), 201


# ── Stats & next-code (must be defined BEFORE /<int:item_id> to avoid conflict)

@submittals_bp.route('/<module_type>/stats', methods=['GET'])
@jwt_required()
def stats(project_id: int, module_type: str):
    err = _validate_module(module_type)
    if err:
        return err

    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    base = Submittal.query.filter_by(project_id=project_id, module_type=module_type)
    result = {
        'total':       base.count(),
        'pending':     base.filter_by(status='pending').count(),
        'approved':    base.filter_by(status='approved').count(),
        'notes':       base.filter_by(status='notes').count(),
        'rejected':    base.filter_by(status='rejected').count(),
        'corrections': base.filter_by(status='corrections').count(),
    }
    return jsonify(result), 200


@submittals_bp.route('/<module_type>/next-code', methods=['GET'])
@jwt_required()
def next_code(project_id: int, module_type: str):
    """Return the next suggested doc_number and a preview code."""
    err = _validate_module(module_type)
    if err:
        return err

    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    from sqlalchemy import func
    max_num = db.session.query(func.max(Submittal.doc_number)).filter_by(
        project_id=project_id, module_type=module_type
    ).scalar() or 0

    doc_number = max_num + 1
    revision   = request.args.get('revision', 'A').upper()
    code       = _build_code(proj.code, module_type, doc_number, revision)

    return jsonify({'doc_number': doc_number, 'code': code}), 200


# ── Single item CRUD ──────────────────────────────────────────────────────────

@submittals_bp.route('/<module_type>/<int:item_id>', methods=['GET'])
@jwt_required()
def get_submittal(project_id: int, module_type: str, item_id: int):
    err = _validate_module(module_type)
    if err:
        return err

    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    item = Submittal.query.filter_by(
        id=item_id, project_id=project_id, module_type=module_type
    ).first()
    if not item:
        return jsonify({'error': 'Record not found'}), 404

    return jsonify({'item': item.to_dict()}), 200


@submittals_bp.route('/<module_type>/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_submittal(project_id: int, module_type: str, item_id: int):
    err = _validate_module(module_type)
    if err:
        return err

    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    item = Submittal.query.filter_by(
        id=item_id, project_id=project_id, module_type=module_type
    ).first()
    if not item:
        return jsonify({'error': 'Record not found'}), 404

    data = request.get_json(silent=True) or {}

    # Submission fields
    if 'title' in data:
        item.title = data['title'].strip()
    if 'description' in data:
        item.description = data['description'].strip()
    if 'submittal_date' in data:
        d = _parse_date(data['submittal_date'])
        if d:
            item.submittal_date = d
    if 'doc_number' in data:
        try:
            dn = int(data['doc_number'])
            if dn >= 1:
                item.doc_number = dn
        except (TypeError, ValueError):
            pass
    if 'revision' in data:
        item.revision = (data['revision'] or 'A').strip().upper()
    # Rebuild code if doc_number or revision changed
    if 'doc_number' in data or 'revision' in data:
        item.code = _build_code(proj.code, module_type, item.doc_number, item.revision)
    if 'location' in data:
        item.location = data['location'].strip()
    if 'engineer' in data:
        item.engineer = data['engineer'].strip()
    if 'related_refs' in data:
        item.related_refs = data['related_refs'].strip()
    if 'submitted_to' in data:
        item.submitted_to = data['submitted_to'].strip()
    if 'cc_party' in data:
        item.cc_party = data['cc_party'].strip()
    if 'notes' in data:
        item.notes = data['notes'].strip()
    if 'status' in data and data['status'] in VALID_SUBMITTAL_STATUSES:
        item.status = data['status']
    if 'file_name' in data:
        item.file_name = data['file_name'].strip()

    # Response fields
    if 'response_status' in data:
        rs = data['response_status']
        item.response_status = rs if rs in VALID_SUBMITTAL_STATUSES else ''
        # Mirror to main status if a real outcome
        if rs and rs != 'pending':
            item.status = rs
    if 'response_date' in data:
        item.response_date = _parse_date(data['response_date'])
    if 'response_by' in data:
        item.response_by = data['response_by'].strip()
    if 'response_location' in data:
        item.response_location = data['response_location'].strip()
    if 'response_notes' in data:
        item.response_notes = data['response_notes'].strip()
    if 'response_file' in data:
        item.response_file = data['response_file'].strip()

    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'item': item.to_dict()}), 200


@submittals_bp.route('/<module_type>/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_submittal(project_id: int, module_type: str, item_id: int):
    err = _validate_module(module_type)
    if err:
        return err

    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    item = Submittal.query.filter_by(
        id=item_id, project_id=project_id, module_type=module_type
    ).first()
    if not item:
        return jsonify({'error': 'Record not found'}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Record deleted'}), 200
