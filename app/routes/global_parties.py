"""
BINNA — Global Parties Registry API

Routes nested under:
    /api/v1/projects/<project_id>/global-parties

A flat per-project directory of every party involved in the project (client,
consultant, contractor, subcontractor, supplier, other). Independent of the
Subcontractor module's `Party` model (company directory for subcontract
agreements, mounted at /parties) — separate model, separate API surface.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import (
    GlobalParty,
    Project,
    ProjectMember,
    _ROLE_ORDER,
    CREATABLE_GLOBAL_PARTY_ROLES,
    SEED_GLOBAL_PARTY_ROLES,
)

global_parties_bp = Blueprint('global_parties', __name__)


# ── Access control (mirrors the other module blueprints) ──────────────────────

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
        return None, None   # → 404
    if _ROLE_ORDER.get(mem.role, 0) < _ROLE_ORDER.get(min_role, 0):
        return proj, None   # → 403
    return proj, mem


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL PARTIES
# ══════════════════════════════════════════════════════════════════════════════

@global_parties_bp.route('', methods=['GET'])
@jwt_required()
def list_global_parties(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'viewer')
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    parties = GlobalParty.query.filter_by(project_id=project_id).order_by(GlobalParty.id).all()
    return jsonify({'parties': [p.to_dict() for p in parties], 'total': len(parties)}), 200


@global_parties_bp.route('', methods=['POST'])
@jwt_required()
def create_global_party(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    body = request.get_json(silent=True) or {}
    name_en = (body.get('name_en') or '').strip()
    if not name_en:
        return jsonify({'error': 'name_en is required'}), 400

    role = body.get('role', 'other')
    if role not in CREATABLE_GLOBAL_PARTY_ROLES:
        return jsonify({'error': f'role must be one of: {", ".join(CREATABLE_GLOBAL_PARTY_ROLES)}'}), 400

    party = GlobalParty(
        project_id    = project_id,
        name_en       = name_en,
        name_ar       = (body.get('name_ar') or '').strip(),
        role          = role,
        logo_filename = (body.get('logo_filename') or '').strip() or None,
        notes         = (body.get('notes') or '').strip() or None,
        is_seeded     = False,
    )
    db.session.add(party)
    db.session.commit()
    return jsonify({'party': party.to_dict()}), 201


@global_parties_bp.route('/seed', methods=['POST'])
@jwt_required()
def seed_global_parties(project_id):
    """Backfill Client/Consultant/Contractor GlobalParty rows for a project
    that was created before the Global Parties Registry existed. Idempotent —
    skips any role that already has a seeded entry."""
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    created = []
    for field, role in SEED_GLOBAL_PARTY_ROLES:
        val = (getattr(proj, field, '') or '').strip()
        if not val:
            continue
        if GlobalParty.query.filter_by(project_id=project_id, role=role, is_seeded=True).first():
            continue
        party = GlobalParty(
            project_id = project_id,
            name_en    = val,
            name_ar    = '',
            role       = role,
            is_seeded  = True,
        )
        db.session.add(party)
        created.append(party)

    db.session.commit()
    return jsonify({
        'created':       [p.to_dict() for p in created],
        'total_created': len(created),
    }), 200


@global_parties_bp.route('/<int:party_id>', methods=['PUT'])
@jwt_required()
def update_global_party(project_id, party_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    party = GlobalParty.query.filter_by(id=party_id, project_id=project_id).first()
    if not party:
        return jsonify({'error': 'Party not found'}), 404

    body = request.get_json(silent=True) or {}
    if 'name_en' in body and (body['name_en'] or '').strip():
        party.name_en = body['name_en'].strip()
    if 'name_ar' in body:
        party.name_ar = (body['name_ar'] or '').strip()
    if 'logo_filename' in body:
        party.logo_filename = (body['logo_filename'] or '').strip() or None
    if 'notes' in body:
        party.notes = (body['notes'] or '').strip() or None
    # role is immutable after creation

    db.session.commit()
    return jsonify({'party': party.to_dict()}), 200


@global_parties_bp.route('/<int:party_id>', methods=['DELETE'])
@jwt_required()
def delete_global_party(project_id, party_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'admin')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — admin role required'}), 403

    party = GlobalParty.query.filter_by(id=party_id, project_id=project_id).first()
    if not party:
        return jsonify({'error': 'Party not found'}), 404

    if party.is_seeded:
        return jsonify({'error': 'Seeded parties (Client/Consultant/Contractor) cannot be deleted'}), 409

    db.session.delete(party)
    db.session.commit()
    return jsonify({'message': f'Party "{party.name_en}" deleted'}), 200
