"""
BINNA — Daily Reports API  (Phase 4)
Routes: /api/v1/projects/<project_id>/dr
"""
import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from app import db
from app.models import DailyReport, Project, ProjectMember, _ROLE_ORDER
from app.tenancy import membership_or_none

dr_bp = Blueprint('dr', __name__)


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


def _build_code(project_code, doc_number):
    return f"{project_code}-DR-{str(doc_number).zfill(3)}"


# ── List / Create ─────────────────────────────────────────────────────────────

@dr_bp.route('', methods=['GET'])
@jwt_required()
def list_reports(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    query = DailyReport.query.filter_by(project_id=project_id)

    search = request.args.get('q', '').strip().lower()
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                DailyReport.code.ilike(like),
                DailyReport.weather.ilike(like),
                DailyReport.notes.ilike(like),
            )
        )

    items = query.order_by(DailyReport.date.desc(), DailyReport.doc_number.desc()).all()
    return jsonify({'items': [r.to_dict() for r in items], 'total': len(items)}), 200


@dr_bp.route('', methods=['POST'])
@jwt_required()
def create_report(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    data = request.get_json(silent=True) or {}

    report_date = _parse_date(data.get('date'))
    if not report_date:
        return jsonify({'error': 'date is required (ISO format: YYYY-MM-DD)'}), 400

    max_num = db.session.query(func.max(DailyReport.doc_number)).filter_by(
        project_id=project_id
    ).scalar() or 0
    doc_number = max_num + 1
    code = _build_code(proj.code, doc_number)

    works_raw    = data.get('works',    [])
    visitors_raw = data.get('visitors', [])

    item = DailyReport(
        project_id    = project_id,
        code          = code,
        doc_number    = doc_number,
        date          = report_date,
        weather       = (data.get('weather') or 'sunny').strip(),
        weather_notes = (data.get('weather_notes') or '').strip(),
        engineers     = int(data.get('engineers',     0) or 0),
        laborers      = int(data.get('laborers',      0) or 0),
        technicians   = int(data.get('technicians',   0) or 0),
        other_workers = int(data.get('other_workers', 0) or 0),
        works         = json.dumps(works_raw    if isinstance(works_raw,    list) else [], ensure_ascii=False),
        visitors      = json.dumps(visitors_raw if isinstance(visitors_raw, list) else [], ensure_ascii=False),
        next_plan     = (data.get('next_plan')   or '').strip(),
        notes         = (data.get('notes')        or '').strip(),
        prepared_by   = (data.get('prepared_by') or '').strip(),
        reviewed_by   = (data.get('reviewed_by') or '').strip(),
        created_by    = uid,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'item': item.to_dict()}), 201


# ── Stats / Next-code ─────────────────────────────────────────────────────────

@dr_bp.route('/stats', methods=['GET'])
@jwt_required()
def stats(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    base = DailyReport.query.filter_by(project_id=project_id)
    total = base.count()

    from datetime import date
    today = date.today()
    this_month = base.filter(
        db.extract('month', DailyReport.date) == today.month,
        db.extract('year',  DailyReport.date) == today.year,
    ).count()

    return jsonify({'total': total, 'this_month': this_month}), 200


@dr_bp.route('/next-code', methods=['GET'])
@jwt_required()
def next_code(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    max_num = db.session.query(func.max(DailyReport.doc_number)).filter_by(
        project_id=project_id
    ).scalar() or 0
    doc_number = max_num + 1
    code = _build_code(proj.code, doc_number)
    return jsonify({'doc_number': doc_number, 'code': code}), 200


# ── Single item CRUD ──────────────────────────────────────────────────────────

@dr_bp.route('/<int:item_id>', methods=['GET'])
@jwt_required()
def get_report(project_id, item_id):
    uid = int(get_jwt_identity())
    proj, mem = _get_membership(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    item = DailyReport.query.filter_by(id=item_id, project_id=project_id).first()
    if not item:
        return jsonify({'error': 'Record not found'}), 404
    return jsonify({'item': item.to_dict()}), 200


@dr_bp.route('/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_report(project_id, item_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    item = DailyReport.query.filter_by(id=item_id, project_id=project_id).first()
    if not item:
        return jsonify({'error': 'Record not found'}), 404

    data = request.get_json(silent=True) or {}

    if 'date' in data:
        d = _parse_date(data['date'])
        if d:
            item.date = d
    if 'weather' in data:
        item.weather = (data['weather'] or 'sunny').strip()
    if 'weather_notes' in data:
        item.weather_notes = data['weather_notes'].strip()
    if 'engineers' in data:
        item.engineers = int(data['engineers'] or 0)
    if 'laborers' in data:
        item.laborers = int(data['laborers'] or 0)
    if 'technicians' in data:
        item.technicians = int(data['technicians'] or 0)
    if 'other_workers' in data:
        item.other_workers = int(data['other_workers'] or 0)
    if 'works' in data:
        w = data['works']
        item.works = json.dumps(w if isinstance(w, list) else [], ensure_ascii=False)
    if 'visitors' in data:
        v = data['visitors']
        item.visitors = json.dumps(v if isinstance(v, list) else [], ensure_ascii=False)
    if 'next_plan' in data:
        item.next_plan = data['next_plan'].strip()
    if 'notes' in data:
        item.notes = data['notes'].strip()
    if 'prepared_by' in data:
        item.prepared_by = data['prepared_by'].strip()
    if 'reviewed_by' in data:
        item.reviewed_by = data['reviewed_by'].strip()

    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'item': item.to_dict()}), 200


@dr_bp.route('/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_report(project_id, item_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    item = DailyReport.query.filter_by(id=item_id, project_id=project_id).first()
    if not item:
        return jsonify({'error': 'Record not found'}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Record deleted'}), 200
