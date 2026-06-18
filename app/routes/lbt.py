"""
BINNA — Lab Tests API  (Phase 5)
Routes: /api/v1/projects/<project_id>/lbt
Handles LBTOUT (sent-sample) and LBTIN (result) records.
"""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from app import db
from app.models import LabTest, VALID_LBT_RESULTS, Project, ProjectMember, _ROLE_ORDER
from app.tenancy import membership_or_none

lbt_bp = Blueprint('lbt', __name__)

VALID_DIRECTIONS = ('out', 'in')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_membership(project_id, user_id):
    # Delegates to the central tenant-isolation gate (company match + membership).
    return membership_or_none(project_id, user_id)


def _requires_role(project_id, user_id, min_role='viewer'):
    proj, mem = _get_membership(project_id, user_id)
    if not proj:
        return None, None
    if _ROLE_ORDER.get(mem.role, 0) < _ROLE_ORDER.get(min_role, 0):
        return proj, None
    return proj, mem


def _parse_date(val):
    if not val:
        return None
    from datetime import date
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def _build_code(project_code, direction, doc_number):
    tag = 'LBTOUT' if direction == 'out' else 'LBTIN'
    return f"{project_code}-{tag}-{str(doc_number).zfill(3)}"


# ── List / Create ─────────────────────────────────────────────────────────────

@lbt_bp.route('', methods=['GET'])
@jwt_required()
def list_tests(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    query = LabTest.query.filter_by(project_id=project_id)

    direction = request.args.get('direction', '').strip().lower()
    if direction in VALID_DIRECTIONS:
        query = query.filter_by(direction=direction)

    result_f = request.args.get('result', '').strip().lower()
    if result_f in VALID_LBT_RESULTS:
        query = query.filter_by(result=result_f, direction='in')

    search = request.args.get('q', '').strip().lower()
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                LabTest.code.ilike(like),
                LabTest.material.ilike(like),
                LabTest.test_type.ilike(like),
                LabTest.lab.ilike(like),
            )
        )

    items = query.order_by(LabTest.direction.asc(), LabTest.doc_number.asc()).all()
    return jsonify({'items': [t.to_dict() for t in items], 'total': len(items)}), 200


@lbt_bp.route('', methods=['POST'])
@jwt_required()
def create_test(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    data = request.get_json(silent=True) or {}

    direction = (data.get('direction') or '').strip().lower()
    if direction not in VALID_DIRECTIONS:
        return jsonify({'error': "direction must be 'out' or 'in'"}), 400

    test_date = _parse_date(data.get('date'))
    if not test_date:
        return jsonify({'error': 'date is required (ISO format: YYYY-MM-DD)'}), 400

    if direction == 'out':
        material  = (data.get('material')  or '').strip()
        test_type = (data.get('test_type') or '').strip()
        if not material:
            return jsonify({'error': 'material is required for LBTOUT'}), 400
        if not test_type:
            return jsonify({'error': 'test_type is required for LBTOUT'}), 400

    if direction == 'in':
        related_out_id = data.get('related_out_id')
        if not related_out_id:
            return jsonify({'error': 'related_out_id is required for LBTIN'}), 400
        # Verify the related LBTOUT exists and belongs to this project
        related = LabTest.query.filter_by(
            id=related_out_id, project_id=project_id, direction='out'
        ).first()
        if not related:
            return jsonify({'error': 'related_out_id not found in this project'}), 400

    max_num = db.session.query(func.max(LabTest.doc_number)).filter_by(
        project_id=project_id, direction=direction
    ).scalar() or 0
    doc_number = max_num + 1
    code = _build_code(proj.code, direction, doc_number)

    result_val = (data.get('result') or 'pending').strip()
    if result_val not in VALID_LBT_RESULTS:
        result_val = 'pending'

    item = LabTest(
        project_id     = project_id,
        code           = code,
        doc_number     = doc_number,
        direction      = direction,
        date           = test_date,
        material       = (data.get('material')     or '').strip(),
        test_type      = (data.get('test_type')    or '').strip(),
        lab            = (data.get('lab')          or '').strip(),
        lab_party_id   = data.get('lab_party_id') or None,
        location       = (data.get('location')     or '').strip(),
        sample_ref     = (data.get('sample_ref')   or '').strip(),
        qty            = (data.get('qty')          or '').strip(),
        notes          = (data.get('notes')        or '').strip(),
        file_name      = (data.get('file_name')    or '').strip(),
        related_out_id = data.get('related_out_id') if direction == 'in' else None,
        result         = result_val,
        req_val        = (data.get('req_val')      or '').strip(),
        act_val        = (data.get('act_val')      or '').strip(),
        unit           = (data.get('unit')         or '').strip(),
        result_notes   = (data.get('result_notes') or '').strip(),
        result_file    = (data.get('result_file')  or '').strip(),
        created_by     = uid,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'item': item.to_dict()}), 201


# ── Stats / Next-code ─────────────────────────────────────────────────────────

@lbt_bp.route('/stats', methods=['GET'])
@jwt_required()
def stats(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    base = LabTest.query.filter_by(project_id=project_id)
    return jsonify({
        'total':   base.count(),
        'out':     base.filter_by(direction='out').count(),
        'in':      base.filter_by(direction='in').count(),
        'pending': base.filter_by(direction='in', result='pending').count(),
        'pass':    base.filter_by(result='pass').count(),
        'fail':    base.filter_by(result='fail').count(),
    }), 200


@lbt_bp.route('/next-code', methods=['GET'])
@jwt_required()
def next_code(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    direction = request.args.get('direction', 'out').strip().lower()
    if direction not in VALID_DIRECTIONS:
        direction = 'out'

    max_num = db.session.query(func.max(LabTest.doc_number)).filter_by(
        project_id=project_id, direction=direction
    ).scalar() or 0
    doc_number = max_num + 1
    code = _build_code(proj.code, direction, doc_number)
    return jsonify({'doc_number': doc_number, 'code': code, 'direction': direction}), 200


# ── Single item CRUD ──────────────────────────────────────────────────────────

@lbt_bp.route('/<int:item_id>', methods=['GET'])
@jwt_required()
def get_test(project_id, item_id):
    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    item = LabTest.query.filter_by(id=item_id, project_id=project_id).first()
    if not item:
        return jsonify({'error': 'Record not found'}), 404
    return jsonify({'item': item.to_dict()}), 200


@lbt_bp.route('/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_test(project_id, item_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    item = LabTest.query.filter_by(id=item_id, project_id=project_id).first()
    if not item:
        return jsonify({'error': 'Record not found'}), 404

    data = request.get_json(silent=True) or {}

    if 'date' in data:
        d = _parse_date(data['date'])
        if d:
            item.date = d
    for field in ('material', 'test_type', 'lab', 'location', 'sample_ref',
                  'qty', 'notes', 'file_name', 'req_val', 'act_val',
                  'unit', 'result_notes', 'result_file'):
        if field in data:
            setattr(item, field, (data[field] or '').strip())
    if 'result' in data and data['result'] in VALID_LBT_RESULTS:
        item.result = data['result']
    if 'lab_party_id' in data:
        item.lab_party_id = data['lab_party_id'] or None
    if 'related_out_id' in data and item.direction == 'in':
        item.related_out_id = data['related_out_id'] or None

    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'item': item.to_dict()}), 200


@lbt_bp.route('/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_test(project_id, item_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    item = LabTest.query.filter_by(id=item_id, project_id=project_id).first()
    if not item:
        return jsonify({'error': 'Record not found'}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Record deleted'}), 200
