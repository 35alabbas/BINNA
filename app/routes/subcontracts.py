"""
BINNA — Subcontractor Module API  (Phase 1)

All routes nested under:
    /api/v1/projects/<project_id>/...

Money direction is PAYABLE — this module tracks money the user owes and pays to
subcontractors / suppliers (the reverse of the main client contract). Wording is
"Net Payable / Total Paid / Balance Payable", never receivable.

Two NEW tables (Party, Subcontract) are created by db.create_all() on deploy.
The payment blob lives inside Subcontract.data (JSON) — aggregations json.loads()
and compute in Python (the established constraint; there are no columns to SUM).
"""
import json
from datetime import datetime, timezone, date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import (
    Party,
    Subcontract,
    SupplyAgreement,
    Project,
    ProjectMember,
    GlobalParty,
    _ROLE_ORDER,
    VALID_PARTY_ROLES,
    VALID_SUBCONTRACT_KINDS,
)
from app.tenancy import authorize_project_access

subcontracts_bp = Blueprint('subcontracts', __name__)


# ── Access control (mirrors the other module blueprints) ──────────────────────

# This blueprint's per-module permission key (see ProjectMember.can / effective_permissions).
_MODULE = 'subcontracts'


def _get_membership(project_id: int, user_id: int):
    # Delegates to the central tenant-isolation gate (company match + membership).
    # A member whose permission map hides this module is treated like a non-member
    # (→ (None, None)) so read handlers that only check `if not proj` deny cleanly.
    proj, mem, allowed = authorize_project_access(
        project_id, user_id, _MODULE, 'view', 'viewer')
    if not allowed:
        return None, None
    return proj, mem


def _requires_role(project_id: int, user_id: int, min_role: str = 'viewer'):
    action = 'view' if min_role == 'viewer' else 'edit'
    proj, mem, allowed = authorize_project_access(
        project_id, user_id, _MODULE, action, min_role)
    if not proj:
        return None, None   # → 404
    if not allowed:
        return proj, None   # → 403
    action = 'view' if min_role == 'viewer' else 'edit'
    if not allowed:
        return proj, None   # module hidden/read-only via the per-member permission map
    return proj, mem


def _num(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return 0.0


# ── Blob helpers ──────────────────────────────────────────────────────────────

def _blank_blob(kind: str) -> dict:
    """§3 default payment blob — payable settings shape."""
    base = {
        'currency': 'IQD', 'currency_custom': '', 'decimalPlaces': 0,
        'settings': {
            'advanceEnabled': False, 'advanceAmount': '', 'advanceRecoveryPct': '20',
            'retentionEnabled': False, 'retentionPct': '5',
            'taxEnabled': False, 'taxRate': '',
            'contractValue': '',
        },
    }
    if kind == 'open_supply':
        base['invoices'] = []
        base['supplyPayments'] = []
    else:
        base['payments'] = []
    return base


def _has_payment_data(blob: dict) -> bool:
    """Server-side mirror of hasPaymentData — any row with a non-zero amount."""
    try:
        for p in (blob.get('payments') or []):
            for sr in (p.get('summaryRows') or []):
                if _num(sr.get('amount')):
                    return True
            if _num(p.get('_net')):
                return True
        for inv in (blob.get('invoices') or []):
            if _num(inv.get('amount')):
                return True
        for sp in (blob.get('supplyPayments') or []):
            if _num(sp.get('amount')):
                return True
    except (AttributeError, TypeError):
        return False
    return False


# ── Ref numbering ─────────────────────────────────────────────────────────────

def _generate_sub_ref(project: Project) -> str:
    """{PROJECT_CODE}-SUB-NNN — max existing number + 1, zero-padded to 3."""
    existing = Subcontract.query.filter_by(project_id=project.id).all()
    max_num = 0
    for s in existing:
        try:
            n = int((s.ref or '').rsplit('-', 1)[1])
            max_num = max(max_num, n)
        except (ValueError, IndexError):
            continue
    return f"{project.code}-SUB-{str(max_num + 1).zfill(3)}"


# ══════════════════════════════════════════════════════════════════════════════
# PARTIES
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_PARTIES = [
    ('Main Contractor', 'main_contractor'),
    ('Consultant',      'consultant'),
    ('Client',          'client'),
]


@subcontracts_bp.route('/parties', methods=['GET'])
@jwt_required()
def list_parties(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'viewer')
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    parties = Party.query.filter_by(project_id=project_id).order_by(Party.id).all()

    # Lazy seeding — gives existing live projects their defaults on first GET,
    # with no migration. Only seeds when the project has zero parties.
    if not parties:
        for name, role in _DEFAULT_PARTIES:
            db.session.add(Party(
                project_id=project_id, name=name, role=role, is_default=True,
            ))
        db.session.commit()
        parties = Party.query.filter_by(project_id=project_id).order_by(Party.id).all()

    # Backfill the Global Parties Registry for subcontractor Parties that
    # predate the mirroring done in create_party() below.
    existing_gp_names = {
        gp.name_en for gp in GlobalParty.query.filter_by(
            project_id=project_id, role='subcontractor',
        ).all()
    }
    added = False
    for p in parties:
        if p.role == 'subcontractor' and p.name not in existing_gp_names:
            db.session.add(GlobalParty(
                project_id = project_id,
                name_en    = p.name,
                name_ar    = p.name_ar or '',
                role       = 'subcontractor',
                is_seeded  = False,
            ))
            existing_gp_names.add(p.name)
            added = True
    if added:
        db.session.commit()

    return jsonify({'parties': [p.to_dict() for p in parties], 'total': len(parties)}), 200


@subcontracts_bp.route('/parties', methods=['POST'])
@jwt_required()
def create_party(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    role = body.get('role', 'subcontractor')
    if role not in VALID_PARTY_ROLES:
        role = 'subcontractor'

    name_ar = (body.get('name_ar') or '').strip()
    party = Party(
        project_id   = project_id,
        name         = name,
        name_ar      = name_ar,
        role         = role,
        contact_name = (body.get('contact_name') or '').strip(),
        phone        = (body.get('phone') or '').strip(),
        email        = (body.get('email') or '').strip(),
        notes        = (body.get('notes') or '').strip(),
        is_default   = False,
        documents    = '[]',
    )
    db.session.add(party)

    # Mirror into the Global Parties Registry so this subcontractor becomes
    # selectable project-wide (e.g. the "Party" picker on New Subcontract).
    if role == 'subcontractor':
        exists = GlobalParty.query.filter_by(
            project_id=project_id, role='subcontractor', name_en=name,
        ).first()
        if not exists:
            db.session.add(GlobalParty(
                project_id = project_id,
                name_en    = name,
                name_ar    = name_ar,
                role       = 'subcontractor',
                is_seeded  = False,
            ))

    db.session.commit()
    return jsonify({'party': party.to_dict()}), 201


@subcontracts_bp.route('/parties/<int:party_id>', methods=['PUT'])
@jwt_required()
def update_party(project_id, party_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    party = Party.query.filter_by(id=party_id, project_id=project_id).first()
    if not party:
        return jsonify({'error': 'Party not found'}), 404

    body = request.get_json(silent=True) or {}
    if 'name' in body and (body['name'] or '').strip():
        party.name = body['name'].strip()
    if 'name_ar'      in body: party.name_ar      = (body['name_ar'] or '').strip()
    if 'contact_name' in body: party.contact_name = (body['contact_name'] or '').strip()
    if 'phone'        in body: party.phone        = (body['phone'] or '').strip()
    if 'email'        in body: party.email        = (body['email'] or '').strip()
    if 'notes'        in body: party.notes        = (body['notes'] or '').strip()
    if 'role' in body and body['role'] in VALID_PARTY_ROLES:
        party.role = body['role']
    if 'documents' in body:
        party.documents = json.dumps(body['documents'] or [], ensure_ascii=False)

    db.session.commit()
    return jsonify({'party': party.to_dict()}), 200


@subcontracts_bp.route('/parties/<int:party_id>', methods=['DELETE'])
@jwt_required()
def delete_party(project_id, party_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'admin')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — admin role required'}), 403

    party = Party.query.filter_by(id=party_id, project_id=project_id).first()
    if not party:
        return jsonify({'error': 'Party not found'}), 404

    # Block deletion (default or not) while referenced by any subcontract.
    sub_count = Subcontract.query.filter_by(project_id=project_id, party_id=party_id).count()
    if sub_count:
        return jsonify({
            'error': f'Cannot delete "{party.name}" — it has {sub_count} '
                     f'subcontract(s). Reassign or delete those agreements first.'
        }), 409

    db.session.delete(party)
    db.session.commit()
    return jsonify({'message': f'Party "{party.name}" deleted'}), 200


# ══════════════════════════════════════════════════════════════════════════════
# SUBCONTRACTS
# ══════════════════════════════════════════════════════════════════════════════

@subcontracts_bp.route('/subcontracts', methods=['GET'])
@jwt_required()
def list_subcontracts(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'viewer')
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    subs = (Subcontract.query
            .filter_by(project_id=project_id)
            .order_by(Subcontract.created_at.desc())
            .all())
    return jsonify({'subcontracts': [s.to_meta_dict() for s in subs], 'total': len(subs)}), 200


@subcontracts_bp.route('/subcontracts', methods=['POST'])
@jwt_required()
def create_subcontract(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    body = request.get_json(silent=True) or {}
    party_id = body.get('party_id')
    title    = (body.get('title') or '').strip()
    kind     = body.get('kind', 'custom')

    if not party_id:
        return jsonify({'error': 'party_id is required'}), 400
    if kind not in VALID_SUBCONTRACT_KINDS:
        return jsonify({'error': f'kind must be one of: {", ".join(VALID_SUBCONTRACT_KINDS)}'}), 400

    party = Party.query.filter_by(id=party_id, project_id=project_id).first()
    if not party:
        return jsonify({'error': 'Party not found in this project'}), 404

    sub = Subcontract(
        project_id = project_id,
        party_id   = party_id,
        ref        = _generate_sub_ref(proj),
        title      = title,
        kind       = kind,
        status     = 'active',
        data       = json.dumps(_blank_blob(kind), ensure_ascii=False),
        documents  = '[]',
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({'subcontract': sub.to_dict()}), 201


@subcontracts_bp.route('/subcontracts/<int:sub_id>', methods=['GET'])
@jwt_required()
def get_subcontract(project_id, sub_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'viewer')
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    sub = Subcontract.query.filter_by(id=sub_id, project_id=project_id).first()
    if not sub:
        return jsonify({'error': 'Subcontract not found'}), 404
    return jsonify({'subcontract': sub.to_dict()}), 200


@subcontracts_bp.route('/subcontracts/<int:sub_id>', methods=['PUT'])
@jwt_required()
def update_subcontract(project_id, sub_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    sub = Subcontract.query.filter_by(id=sub_id, project_id=project_id).first()
    if not sub:
        return jsonify({'error': 'Subcontract not found'}), 404

    body = request.get_json(silent=True) or {}

    if 'title' in body:
        sub.title = (body['title'] or '').strip()
    if 'status' in body and body['status'] in ('active', 'closed'):
        sub.status = body['status']
    if 'documents' in body:
        sub.documents = json.dumps(body['documents'] or [], ensure_ascii=False)

    # `kind` is immutable once the blob holds real payment data.
    if 'kind' in body and body['kind'] != sub.kind:
        if body['kind'] not in VALID_SUBCONTRACT_KINDS:
            return jsonify({'error': 'Invalid kind'}), 400
        try:
            current_blob = json.loads(sub.data) if sub.data else {}
        except (ValueError, TypeError):
            current_blob = {}
        if _has_payment_data(current_blob):
            return jsonify({
                'error': 'Cannot change contract kind after payment data has been entered.'
            }), 409
        sub.kind = body['kind']

    # Full blob replace (same pattern as the financial PUT).
    if 'data' in body:
        sub.data = json.dumps(body['data'], ensure_ascii=False)

    db.session.commit()
    return jsonify({'subcontract': sub.to_dict()}), 200


@subcontracts_bp.route('/subcontracts/<int:sub_id>', methods=['DELETE'])
@jwt_required()
def delete_subcontract(project_id, sub_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'admin')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — admin role required'}), 403

    sub = Subcontract.query.filter_by(id=sub_id, project_id=project_id).first()
    if not sub:
        return jsonify({'error': 'Subcontract not found'}), 404

    db.session.delete(sub)
    db.session.commit()
    return jsonify({'message': 'Subcontract deleted'}), 200


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD SUMMARY  — json.loads() every blob, compute in Python, resilient.
# ══════════════════════════════════════════════════════════════════════════════

_CERT_RANK = {'draft': 0, 'certified': 1, 'signed': 2, 'paid': 3}


def _row_net(row: dict) -> float:
    """Prefer the client-persisted net (mirrors contract `_netDue`); fall back to
    the gross of positive summary rows so older / partial blobs still aggregate."""
    if row.get('_net') is not None:
        return _num(row.get('_net'))
    g = 0.0
    for sr in (row.get('summaryRows') or []):
        a = _num(sr.get('amount'))
        if a > 0:
            g += a
    return g


def _summarize_one(sub: Subcontract) -> dict:
    """Per-contract payable rollup. Wrapped by the caller in try/except."""
    blob = json.loads(sub.data) if sub.data else {}
    if not isinstance(blob, dict):
        blob = {}

    committed = certified = paid = retained = 0.0
    signed = unsigned = 0

    if sub.kind == 'open_supply':
        invoices = blob.get('invoices') or []
        sps      = blob.get('supplyPayments') or []
        committed = sum(_num(i.get('amount')) for i in invoices)
        for sp in sps:
            amt = _num(sp.get('amount'))
            cert = sp.get('certificate') or {}
            status = cert.get('status', 'draft')
            if _CERT_RANK.get(status, 0) >= _CERT_RANK['certified']:
                certified += amt
            if sp.get('paid') or status == 'paid':
                paid += amt
            if _CERT_RANK.get(status, 0) >= _CERT_RANK['signed']:
                signed += 1
            else:
                unsigned += 1
        balance = committed - paid          # running account: invoices − payments
    else:
        payments = blob.get('payments') or []
        settings = blob.get('settings') or {}
        contract_value = _num(settings.get('contractValue'))
        alloc = sum(_row_net(p) for p in payments)
        committed = contract_value if contract_value > 0 else alloc
        for p in payments:
            net = _row_net(p)
            cert = p.get('certificate') or {}
            status = cert.get('status', 'draft')
            if _CERT_RANK.get(status, 0) >= _CERT_RANK['certified']:
                certified += net
            if p.get('paid') or status == 'paid':
                paid += net
            retained += _num(p.get('_retHeld')) - _num(p.get('_retReleased'))
            if _CERT_RANK.get(status, 0) >= _CERT_RANK['signed']:
                signed += 1
            else:
                unsigned += 1
        balance = certified - paid

    return {
        'id':        sub.id,
        'ref':       sub.ref or '',
        'title':     sub.title or '',
        'kind':      sub.kind,
        'status':    sub.status,
        'party':     {'id': sub.party.id, 'name': sub.party.name, 'role': sub.party.role} if sub.party else {},
        'currency':  blob.get('currency', 'IQD'),
        'currency_custom': blob.get('currency_custom', ''),
        'committed': round(committed, 3),
        'certified': round(certified, 3),
        'paid':      round(paid, 3),
        'retained':  round(retained, 3),
        'balance':   round(balance, 3),
        'signed':    signed,
        'unsigned':  unsigned,
    }


@subcontracts_bp.route('/subcontracts/summary', methods=['GET'])
@jwt_required()
def subcontracts_summary(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'viewer')
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    subs = Subcontract.query.filter_by(project_id=project_id).all()

    rows = []
    # Totals are kept per-currency (no conversion) plus a flat all-currency sum.
    by_currency = {}
    totals = {'committed': 0.0, 'certified': 0.0, 'paid': 0.0, 'retained': 0.0, 'balance': 0.0}
    active_count = 0

    for sub in subs:
        try:
            r = _summarize_one(sub)
        except Exception:
            # Skip-and-continue on malformed / empty blobs.
            continue
        rows.append(r)
        if sub.status == 'active':
            active_count += 1
        cur = r['currency'] if r['currency'] != 'custom' else (r['currency_custom'] or 'custom')
        bucket = by_currency.setdefault(cur, {'committed': 0.0, 'certified': 0.0, 'paid': 0.0, 'retained': 0.0, 'balance': 0.0})
        for k in totals:
            bucket[k] += r[k]
            totals[k] += r[k]

    for k in totals:
        totals[k] = round(totals[k], 3)
    for cur in by_currency:
        for k in by_currency[cur]:
            by_currency[cur][k] = round(by_currency[cur][k], 3)

    return jsonify({
        'contracts':    rows,
        'totals':       totals,
        'by_currency':  by_currency,
        'active_count': active_count,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# SUPPLY AGREEMENTS (Purchase Orders)  — simple PO header + flat payment log.
#   No retention, no cumulative درعة, no progress certificates.
# ══════════════════════════════════════════════════════════════════════════════

def _generate_po_ref(project: Project) -> str:
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


def _po_rollup(sa: SupplyAgreement):
    """(total_paid, balance) from the JSON payment log."""
    try:
        blob = json.loads(sa.data) if sa.data else {}
    except (ValueError, TypeError):
        blob = {}
    if not isinstance(blob, dict):
        blob = {}
    total_paid = sum(_num(p.get('amount')) for p in (blob.get('payments') or []) if isinstance(p, dict))
    return total_paid, (_num(sa.po_value) - total_paid)


def _po_status_for(total_paid: float, po_value: float) -> str:
    if total_paid <= 0:
        return 'open'
    if total_paid < po_value:
        return 'partially_paid'
    return 'closed'


def _sa_dict(sa: SupplyAgreement, name_map=None) -> dict:
    d = sa.to_dict()
    total_paid, balance = _po_rollup(sa)
    d['total_paid'] = round(total_paid, 3)
    d['balance'] = round(balance, 3)
    if name_map is not None:
        d['party_name'] = name_map.get(sa.global_party_id, '')
    else:
        gp = GlobalParty.query.get(sa.global_party_id) if sa.global_party_id else None
        d['party_name'] = gp.name_en if gp else ''
    return d


@subcontracts_bp.route('/supply-agreements', methods=['GET'])
@jwt_required()
def list_supply_agreements(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'viewer')
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    sas = (SupplyAgreement.query
           .filter_by(project_id=project_id)
           .order_by(SupplyAgreement.id.desc())
           .all())
    party_ids = {sa.global_party_id for sa in sas if sa.global_party_id}
    name_map = {}
    if party_ids:
        for gp in GlobalParty.query.filter(GlobalParty.id.in_(party_ids)).all():
            name_map[gp.id] = gp.name_en
    return jsonify({
        'agreements': [_sa_dict(sa, name_map) for sa in sas],
        'total': len(sas),
    }), 200


@subcontracts_bp.route('/supply-agreements/summary', methods=['GET'])
@jwt_required()
def supply_agreements_summary(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'viewer')
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    sas = SupplyAgreement.query.filter_by(project_id=project_id).all()
    total_po = total_paid = 0.0
    for sa in sas:
        tp, _ = _po_rollup(sa)
        total_po += _num(sa.po_value)
        total_paid += tp
    return jsonify({
        'total_po_value': round(total_po, 3),
        'total_paid':     round(total_paid, 3),
        'balance':        round(total_po - total_paid, 3),
        'count':          len(sas),
    }), 200


@subcontracts_bp.route('/supply-agreements', methods=['POST'])
@jwt_required()
def create_supply_agreement(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    body = request.get_json(silent=True) or {}
    description = (body.get('description') or '').strip()
    currency    = (body.get('currency') or '').strip()
    date_issued = (body.get('date_issued') or '').strip()
    if not description:
        return jsonify({'error': 'description is required'}), 400
    if body.get('po_value') in (None, ''):
        return jsonify({'error': 'po_value is required'}), 400
    if not currency:
        return jsonify({'error': 'currency is required'}), 400
    if not date_issued:
        return jsonify({'error': 'date_issued is required'}), 400

    blob = {'payments': [], 'notes': (body.get('notes') or '')}
    sa = SupplyAgreement(
        project_id      = project_id,
        global_party_id = body.get('global_party_id') or None,
        ref             = _generate_po_ref(proj),
        description     = description,
        po_value        = _num(body.get('po_value')),
        currency        = currency,
        date_issued     = date_issued,
        status          = 'open',
        data            = json.dumps(blob, ensure_ascii=False),
    )
    db.session.add(sa)
    db.session.commit()
    return jsonify({'agreement': _sa_dict(sa)}), 201


@subcontracts_bp.route('/supply-agreements/<int:agreement_id>', methods=['GET'])
@jwt_required()
def get_supply_agreement(project_id, agreement_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'viewer')
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    sa = SupplyAgreement.query.filter_by(id=agreement_id, project_id=project_id).first()
    if not sa:
        return jsonify({'error': 'Supply agreement not found'}), 404
    return jsonify({'agreement': _sa_dict(sa)}), 200


@subcontracts_bp.route('/supply-agreements/<int:agreement_id>', methods=['PUT'])
@jwt_required()
def update_supply_agreement(project_id, agreement_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions'}), 403

    sa = SupplyAgreement.query.filter_by(id=agreement_id, project_id=project_id).first()
    if not sa:
        return jsonify({'error': 'Supply agreement not found'}), 404

    body = request.get_json(silent=True) or {}
    if 'description' in body:
        sa.description = (body['description'] or '').strip()
    if 'po_value' in body:
        sa.po_value = _num(body['po_value'])
    if 'currency' in body and (body['currency'] or '').strip():
        sa.currency = body['currency'].strip()
    if 'date_issued' in body:
        sa.date_issued = (body['date_issued'] or '').strip()
    # Full blob replace (same pattern as the subcontract PUT).
    if 'data' in body:
        sa.data = json.dumps(body['data'], ensure_ascii=False)

    # Status is derived from the resulting payment log — never trust the client.
    total_paid, _ = _po_rollup(sa)
    sa.status = _po_status_for(total_paid, _num(sa.po_value))

    db.session.commit()
    return jsonify({'agreement': _sa_dict(sa)}), 200


@subcontracts_bp.route('/supply-agreements/<int:agreement_id>', methods=['DELETE'])
@jwt_required()
def delete_supply_agreement(project_id, agreement_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'admin')
    if not proj:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — admin role required'}), 403

    sa = SupplyAgreement.query.filter_by(id=agreement_id, project_id=project_id).first()
    if not sa:
        return jsonify({'error': 'Supply agreement not found'}), 404

    db.session.delete(sa)
    db.session.commit()
    return jsonify({'message': 'Supply agreement deleted'}), 200
