"""
BINNA — Global Parties Registry API

Routes nested under:
    /api/v1/projects/<project_id>/global-parties

A flat per-project directory of every party involved in the project (client,
consultant, contractor, subcontractor, supplier, other). Independent of the
Subcontractor module's `Party` model (company directory for subcontract
agreements, mounted at /parties) — separate model, separate API surface.
"""
import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import (
    GlobalParty,
    Party,
    Subcontract,
    SupplyAgreement,
    Project,
    ProjectMember,
    _ROLE_ORDER,
    CREATABLE_GLOBAL_PARTY_ROLES,
    SEED_GLOBAL_PARTY_ROLES,
)
from app.tenancy import membership_or_none

global_parties_bp = Blueprint('global_parties', __name__)


# ── Access control (mirrors the other module blueprints) ──────────────────────

# This blueprint's per-module permission key (see ProjectMember.can / effective_permissions).
_MODULE = 'global_parties'


def _get_membership(project_id: int, user_id: int):
    # Delegates to the central tenant-isolation gate (company match + membership).
    # A member whose permission map hides this module is treated like a non-member
    # (→ (None, None)) so read handlers that only check `if not proj` deny cleanly.
    proj, mem = membership_or_none(project_id, user_id)
    if mem and not mem.can(_MODULE, 'view'):
        return None, None
    return proj, mem


def _requires_role(project_id: int, user_id: int, min_role: str = 'viewer'):
    proj, mem = _get_membership(project_id, user_id)
    if not proj:
        return None, None   # → 404
    if _ROLE_ORDER.get(mem.role, 0) < _ROLE_ORDER.get(min_role, 0):
        return proj, None   # → 403
    action = 'view' if min_role == 'viewer' else 'edit'
    if not mem.can(_MODULE, action):
        return proj, None   # module hidden/read-only via the per-member permission map
    return proj, mem


# ── Subcontractor / Supplier auto-wiring ──────────────────────────────────────
# Adding a subcontractor or supplier to this registry must make it appear in the
# Subcontractors & Suppliers module immediately — no separate creation step.
# A subcontractor auto-creates a Subcontract (payment-certificate workflow);
# a supplier auto-creates a SupplyAgreement (simpler PO + payment log).

def _next_subcontract_ref(project) -> str:
    """{PROJECT_CODE}-SUB-NNN — max existing number + 1, zero-padded to 3.
    Mirrors subcontracts._generate_sub_ref (kept local to avoid a cross-blueprint
    import cycle)."""
    existing = Subcontract.query.filter_by(project_id=project.id).all()
    max_num = 0
    for s in existing:
        try:
            n = int((s.ref or '').rsplit('-', 1)[1])
            max_num = max(max_num, n)
        except (ValueError, IndexError):
            continue
    return f"{project.code}-SUB-{str(max_num + 1).zfill(3)}"


def _ensure_subcontract_for_global_party(project, gp):
    """Ensure a subcontractor/supplier GlobalParty has a backing Subcontract.

    `Subcontract.party_id` FKs the subcontract-module `Party` table (not
    `global_parties`), so the GlobalParty is first mirrored into a `Party` row;
    the Subcontract then links to that. Idempotent — reuses an existing mirror
    Party / Subcontract so repeated calls (and PUT backfills) never duplicate.
    """
    party = Party.query.filter_by(
        project_id=project.id, role=gp.role, name=gp.name_en,
    ).first()
    if not party:
        party = Party(
            project_id = project.id,
            name       = gp.name_en,
            name_ar    = gp.name_ar or '',
            role       = gp.role,
            is_default = False,
            documents  = '[]',
        )
        db.session.add(party)
        db.session.flush()   # assign party.id for the FK below

    existing = Subcontract.query.filter_by(
        project_id=project.id, party_id=party.id,
    ).first()
    if existing:
        return existing

    sub = Subcontract(
        project_id = project.id,
        party_id   = party.id,
        ref        = _next_subcontract_ref(project),
        title      = '',
        kind       = 'subcontractor',
        status     = 'active',
        data       = '{}',           # empty blob — contract details filled in later
        documents  = '[]',
    )
    db.session.add(sub)
    db.session.flush()
    return sub


def _next_po_ref(project) -> str:
    """{PROJECT_CODE}-PO-NNN — max existing number + 1, zero-padded to 3."""
    existing = SupplyAgreement.query.filter_by(project_id=project.id).all()
    max_num = 0
    for s in existing:
        try:
            n = int((s.ref or '').rsplit('-', 1)[1])
            max_num = max(max_num, n)
        except (ValueError, IndexError):
            continue
    return f"{project.code}-PO-{str(max_num + 1).zfill(3)}"


def _ensure_supply_agreement_for_global_party(project, gp):
    """A supplier added to the registry gets a Supply Agreement (PO) so it shows
    up in the Supply Agreements tab with no extra user action. Idempotent —
    keyed on global_party_id so repeated calls / PUT backfills never duplicate."""
    existing = SupplyAgreement.query.filter_by(
        project_id=project.id, global_party_id=gp.id,
    ).first()
    if existing:
        return existing
    sa = SupplyAgreement(
        project_id      = project.id,
        global_party_id = gp.id,
        ref             = _next_po_ref(project),
        description     = 'Supply Agreement',
        po_value        = 0,
        currency        = 'IQD',
        date_issued     = '',
        status          = 'open',
        data            = json.dumps({'payments': [], 'notes': ''}),
    )
    db.session.add(sa)
    db.session.flush()
    return sa


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
    db.session.flush()   # assign party.id

    # Subcontractor → Subcontract; Supplier → Supply Agreement (PO). Either way
    # the party shows up in its dashboard tab with no extra user action.
    if party.role == 'subcontractor':
        _ensure_subcontract_for_global_party(proj, party)
    elif party.role == 'supplier':
        _ensure_supply_agreement_for_global_party(proj, party)

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

    # Backfill: ensure the backing Subcontract / Supply Agreement exists
    # (e.g. party predates the auto-wiring, or role changed). Idempotent.
    if party.role == 'subcontractor':
        _ensure_subcontract_for_global_party(proj, party)
    elif party.role == 'supplier':
        _ensure_supply_agreement_for_global_party(proj, party)

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
