"""
BINNA — Document Control API
Phase 2

All routes are nested under:
    /api/v1/projects/<project_id>/dc
"""
from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import DCLetter, Project, ProjectMember, _ROLE_ORDER

dc_bp = Blueprint('dc', __name__)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_membership(project_id: int, user_id: int):
    """Return (Project, ProjectMember) or (None, None) if no access."""
    proj = Project.query.get(project_id)
    if not proj:
        return None, None
    mem = ProjectMember.query.filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    return (proj, mem) if mem else (None, None)


def _requires_role(project_id: int, user_id: int, min_role: str = 'viewer'):
    """Return (Project, ProjectMember) or abort with 403/404."""
    proj, mem = _get_membership(project_id, user_id)
    if not proj:
        return None, None   # 404
    if _ROLE_ORDER.get(mem.role, 0) < _ROLE_ORDER.get(min_role, 0):
        return proj, None   # 403
    return proj, mem


def _parse_date(val: str):
    """Parse ISO date string → date object, or None."""
    if not val:
        return None
    try:
        return date.fromisoformat(val[:10])
    except (ValueError, TypeError):
        return None


def _generate_code(project: Project, direction: str) -> str:
    """Generate next sequential code: {CODE}-Letter{IN|OUT}-{NNN}"""
    suffix = 'LetterIN' if direction == 'incoming' else 'LetterOUT'
    count = DCLetter.query.filter_by(
        project_id=project.id,
        direction=direction
    ).count()
    return f"{project.code}-{suffix}-{str(count + 1).zfill(3)}"


# ── List / Create ─────────────────────────────────────────────────────────────

@dc_bp.route('', methods=['GET'])
@jwt_required()
def list_letters(project_id: int):
    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    query = DCLetter.query.filter_by(project_id=project_id)

    # Optional filters
    direction = request.args.get('direction')
    status    = request.args.get('status')
    search    = request.args.get('q', '').strip().lower()

    if direction in ('incoming', 'outgoing'):
        query = query.filter_by(direction=direction)
    if status:
        query = query.filter_by(status=status)
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                DCLetter.code.ilike(like),
                DCLetter.subject.ilike(like),
                DCLetter.from_party.ilike(like),
                DCLetter.to_party.ilike(like),
            )
        )

    letters = query.order_by(DCLetter.created_at.desc()).all()
    return jsonify({
        'letters': [l.to_dict() for l in letters],
        'total':   len(letters),
    }), 200


@dc_bp.route('', methods=['POST'])
@jwt_required()
def create_letter(project_id: int):
    uid  = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    data = request.get_json(silent=True) or {}

    direction = data.get('direction', 'incoming')
    if direction not in ('incoming', 'outgoing'):
        return jsonify({'error': 'direction must be incoming or outgoing'}), 400

    subject    = (data.get('subject') or '').strip()
    from_party = (data.get('from_party') or '').strip()
    to_party   = (data.get('to_party') or '').strip()

    if not subject:
        return jsonify({'error': 'subject is required'}), 400
    if not from_party:
        return jsonify({'error': 'from_party is required'}), 400
    if not to_party:
        return jsonify({'error': 'to_party is required'}), 400

    letter_date = _parse_date(data.get('letter_date'))
    if not letter_date:
        return jsonify({'error': 'letter_date is required (ISO format: YYYY-MM-DD)'}), 400

    status = data.get('status', 'pending')
    valid_statuses = ('pending', 'received', 'replied', 'for-reference', 'sent')
    if status not in valid_statuses:
        status = 'pending'

    letter = DCLetter(
        project_id    = project_id,
        code          = _generate_code(proj, direction),
        direction     = direction,
        subject       = subject,
        from_party    = from_party,
        to_party      = to_party,
        cc            = (data.get('cc') or '').strip() if direction == 'outgoing' else '',
        letter_date   = letter_date,
        received_date = _parse_date(data.get('received_date')) if direction == 'incoming' else None,
        orig_no       = (data.get('orig_no') or '').strip() if direction == 'incoming' else '',
        status        = status,
        notes         = (data.get('notes') or '').strip(),
        file_name     = (data.get('file_name') or '').strip(),
        created_by    = uid,
    )
    db.session.add(letter)
    db.session.commit()

    return jsonify({'letter': letter.to_dict()}), 201


# ── Single letter ─────────────────────────────────────────────────────────────

@dc_bp.route('/<int:letter_id>', methods=['GET'])
@jwt_required()
def get_letter(project_id: int, letter_id: int):
    uid  = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    letter = DCLetter.query.filter_by(id=letter_id, project_id=project_id).first()
    if not letter:
        return jsonify({'error': 'Letter not found'}), 404

    return jsonify({'letter': letter.to_dict()}), 200


@dc_bp.route('/<int:letter_id>', methods=['PUT'])
@jwt_required()
def update_letter(project_id: int, letter_id: int):
    uid  = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    letter = DCLetter.query.filter_by(id=letter_id, project_id=project_id).first()
    if not letter:
        return jsonify({'error': 'Letter not found'}), 404

    data = request.get_json(silent=True) or {}

    # Updateable fields (code and direction are immutable after creation)
    if 'subject' in data:
        letter.subject = data['subject'].strip()
    if 'from_party' in data:
        letter.from_party = data['from_party'].strip()
    if 'to_party' in data:
        letter.to_party = data['to_party'].strip()
    if 'cc' in data and letter.direction == 'outgoing':
        letter.cc = data['cc'].strip()
    if 'letter_date' in data:
        d = _parse_date(data['letter_date'])
        if d:
            letter.letter_date = d
    if 'received_date' in data and letter.direction == 'incoming':
        letter.received_date = _parse_date(data['received_date'])
    if 'orig_no' in data and letter.direction == 'incoming':
        letter.orig_no = data['orig_no'].strip()
    if 'status' in data:
        valid = ('pending', 'received', 'replied', 'for-reference', 'sent')
        if data['status'] in valid:
            letter.status = data['status']
    if 'notes' in data:
        letter.notes = data['notes'].strip()
    if 'file_name' in data:
        letter.file_name = data['file_name'].strip()

    from datetime import datetime, timezone
    letter.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({'letter': letter.to_dict()}), 200


@dc_bp.route('/<int:letter_id>', methods=['DELETE'])
@jwt_required()
def delete_letter(project_id: int, letter_id: int):
    uid  = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    letter = DCLetter.query.filter_by(id=letter_id, project_id=project_id).first()
    if not letter:
        return jsonify({'error': 'Letter not found'}), 404

    db.session.delete(letter)
    db.session.commit()

    return jsonify({'message': 'Letter deleted'}), 200


# ── Next code preview ─────────────────────────────────────────────────────────

@dc_bp.route('/next-code', methods=['GET'])
@jwt_required()
def next_code(project_id: int):
    """Return the next auto-generated code for a given direction."""
    uid  = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    direction = request.args.get('direction', 'incoming')
    if direction not in ('incoming', 'outgoing'):
        direction = 'incoming'

    return jsonify({'code': _generate_code(proj, direction)}), 200


# ── Stats ─────────────────────────────────────────────────────────────────────

@dc_bp.route('/stats', methods=['GET'])
@jwt_required()
def stats(project_id: int):
    uid  = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    total   = DCLetter.query.filter_by(project_id=project_id).count()
    inc     = DCLetter.query.filter_by(project_id=project_id, direction='incoming').count()
    out     = DCLetter.query.filter_by(project_id=project_id, direction='outgoing').count()
    pending = DCLetter.query.filter_by(project_id=project_id, status='pending').count()

    return jsonify({
        'total': total, 'incoming': inc, 'outgoing': out, 'pending': pending
    }), 200
