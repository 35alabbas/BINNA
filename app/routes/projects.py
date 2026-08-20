"""
BINNA — Projects blueprint
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/<id>
PUT    /api/v1/projects/<id>
DELETE /api/v1/projects/<id>
GET    /api/v1/projects/<id>/members
POST   /api/v1/projects/<id>/members
DELETE /api/v1/projects/<id>/members/<member_id>
PUT    /api/v1/projects/<id>/members/<member_id>   (change role)
"""
import json

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import (
    DCLetter,
    DailyReport,
    FinancialData,
    GanttData,
    GlobalParty,
    LabTest,
    PERMISSION_MODULES,
    Project,
    ProjectMember,
    SEED_GLOBAL_PARTY_ROLES,
    Subcontract,
    Submittal,
    User,
)
from app.tenancy import membership_or_none

# Blank financial structure seeded for every new project — matches the schema
# the contract / financial frontends read (contractDetails, boq, vo, payments,
# income, expenses, incomeCategories, expenseCategories, usdRate).
_BLANK_FINANCIAL = {
    'contractDetails':   {},
    'boq':               [],
    'vo':                [],
    'payments':          [],
    'income':            [],
    'expenses':          [],
    'incomeCategories':  [],
    'expenseCategories': [],
    'usdRate':           1300,
}

projects_bp = Blueprint('projects', __name__, url_prefix='/api/v1/projects')

_ROLE_ORDER = {'viewer': 0, 'member': 1, 'admin': 2, 'owner': 3}
_VALID_ROLES = {'admin', 'member', 'viewer'}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_membership(project_id: int, user_id: int) -> tuple:
    """Return (Project, ProjectMember) or (None, None) if no access.

    Delegates to the central tenant-isolation gate — access requires the project
    to belong to the caller's company AND the user to be a member.
    """
    return membership_or_none(project_id, user_id)


def _requires_role(project_id: int, user_id: int, min_role: str):
    """Return (project, member) or abort with 404/403."""
    project, member = _get_membership(project_id, user_id)
    if not project:
        return None, None
    if _ROLE_ORDER.get(member.role, 0) < _ROLE_ORDER.get(min_role, 0):
        return None, None
    return project, member


# ── List projects ─────────────────────────────────────────────────────────────

@projects_bp.route('', methods=['GET'])
@jwt_required()
def list_projects():
    user_id = int(get_jwt_identity())
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # SCOPED: only memberships whose project belongs to the caller's own company.
    # The company filter is defence-in-depth — a stale cross-company membership
    # row can never surface another tenant's project in the list.
    memberships = (
        ProjectMember.query
        .filter_by(user_id=user_id)
        .join(Project)
        .filter(Project.company_id == user.company_id)
        .order_by(Project.created_at.desc())
        .all()
    )

    result = []
    for m in memberships:
        p = m.project.to_dict()
        p['my_role']      = m.role
        p['member_count'] = len(m.project.members)
        result.append(p)

    return jsonify({'projects': result, 'total': len(result)})


# ── Create project ────────────────────────────────────────────────────────────

@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    user_id = int(get_jwt_identity())
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    data    = request.get_json(silent=True) or {}

    code = (data.get('code') or '').strip().upper()
    name = (data.get('name') or '').strip()

    if not code or not name:
        return jsonify({'error': 'Project code and name are required'}), 400
    if len(code) > 10:
        return jsonify({'error': 'Project code must be ≤ 10 characters'}), 400

    # Stamp the creator's company onto the project (the tenant that owns it).
    company_id = user.company_id

    project = Project(
        company_id  = company_id,
        code        = code,
        name        = name,
        client      = (data.get('client')      or '').strip(),
        consultant  = (data.get('consultant')  or '').strip(),
        contractor  = (data.get('contractor')  or '').strip(),
        description = (data.get('description') or '').strip(),
        status      = data.get('status', 'active'),
        created_by  = user_id,
    )
    db.session.add(project)
    db.session.flush()          # populate project.id before member insert

    # Creator is the owner — membership row also carries the company stamp.
    member = ProjectMember(project_id=project.id, user_id=user_id,
                           role='owner', company_id=company_id)
    db.session.add(member)

    # Seed a blank financial record so the contract / financial pages open empty
    db.session.add(FinancialData(
        project_id = project.id,
        company_id = company_id,
        data       = json.dumps(_BLANK_FINANCIAL, ensure_ascii=False),
        updated_by = user_id,
    ))

    # Seed Global Parties Registry entries for Client / Consultant / Contractor
    # if those fields were filled on creation. Seeded entries can be edited but
    # never deleted (GlobalParty.is_seeded).
    for field, prole in SEED_GLOBAL_PARTY_ROLES:
        val = (data.get(field) or '').strip()
        if val:
            db.session.add(GlobalParty(
                project_id = project.id,
                company_id = company_id,
                name_en    = val,
                name_ar    = '',
                role       = prole,
                is_seeded  = True,
            ))

    db.session.commit()

    result              = project.to_dict()
    result['my_role']   = 'owner'
    result['member_count'] = 1
    return jsonify({'project': result}), 201


# ── Get project ───────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>', methods=['GET'])
@jwt_required()
def get_project(project_id):
    user_id         = int(get_jwt_identity())
    project, member = _get_membership(project_id, user_id)

    if not project:
        return jsonify({'error': 'Project not found or access denied'}), 404

    result             = project.to_dict(include_members=True)
    result['my_role']  = member.role
    return jsonify({'project': result})


# ── Dashboard stats ───────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/stats', methods=['GET'])
@jwt_required()
def project_stats(project_id):
    """Aggregate counts for the project dashboard cards.

    Relational modules are counted directly; Financial and Gantt are stored as
    JSON blobs (one row per project) so their stat is the length of the relevant
    array, computed in Python.
    """
    uid = int(get_jwt_identity())
    project, _ = _requires_role(project_id, uid, 'viewer')
    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    stats = {
        # Relational counts
        'dc':  DCLetter.query.filter_by(project_id=project_id).count(),
        'dr':  DailyReport.query.filter_by(project_id=project_id).count(),
        'lbt': LabTest.query.filter_by(project_id=project_id).count(),
    }

    # Submittals broken out by module type
    for mtype in ('dwg', 'fir', 'mir', 'ms', 'rfi'):
        stats[mtype] = Submittal.query.filter_by(
            project_id=project_id, module_type=mtype
        ).count()

    # Financial blob holds two distinct dashboard metrics:
    #   financial → payments count (fallback to BOQ rows)  → Contract & Payment card
    #   cashflow  → income + expenses transaction count     → Financial card
    stats['financial'] = 0
    stats['cashflow']  = 0
    stats['certified'] = 0
    stats['received']  = 0
    fin = FinancialData.query.filter_by(project_id=project_id).first()
    if fin and fin.data:
        try:
            fdata = json.loads(fin.data)
            payments = fdata.get('payments') or []
            stats['financial'] = len(payments) if payments else len(fdata.get('boq') or [])
            stats['cashflow']  = len(fdata.get('income') or []) + len(fdata.get('expenses') or [])

            # Contract cashflow — recompute fresh from the saved payment JSON on
            # every request (never trust a cached summary that may be stale):
            #   certified = Σ each payment's net due (_netDue)
            #   received  = Σ all installment amounts under payments[].received[]
            def _num(x):
                try:
                    return float(x)
                except (ValueError, TypeError):
                    return 0.0
            certified = sum(_num(p.get('_netDue')) for p in payments)
            received  = sum(_num(r.get('amount'))
                            for p in payments for r in (p.get('received') or []))
            # Fall back to the stored summary for data saved before per-row fields existed
            if certified == 0 and received == 0:
                cf = fdata.get('cashflowSummary') or {}
                certified = _num(cf.get('totalCertified'))
                received  = _num(cf.get('totalReceived'))
            stats['certified'] = round(certified)
            stats['received']  = round(received)
        except (ValueError, TypeError):
            stats['financial'] = 0
            stats['cashflow']  = 0
            stats['certified'] = 0
            stats['received']  = 0

    # Gantt: total task count
    stats['gantt'] = 0
    gantt = GanttData.query.filter_by(project_id=project_id).first()
    if gantt and gantt.tasks:
        try:
            stats['gantt'] = len(json.loads(gantt.tasks) or [])
        except (ValueError, TypeError):
            stats['gantt'] = 0

    # Subcontractor card — active count + total Balance Payable (money still owed
    # to subcontractors/suppliers). Computed in Python from each payment blob
    # (no columns to SUM); resilient per-contract via try/except.
    def _snum(x):
        try:
            return float(x)
        except (ValueError, TypeError):
            return 0.0

    def _row_net(row):
        if row.get('_net') is not None:
            return _snum(row.get('_net'))
        return sum(_snum(sr.get('amount')) for sr in (row.get('summaryRows') or [])
                   if _snum(sr.get('amount')) > 0)

    sub_count   = 0
    sub_payable = 0.0
    for sub in Subcontract.query.filter_by(project_id=project_id).all():
        if sub.status == 'active':
            sub_count += 1
        try:
            blob = json.loads(sub.data) if sub.data else {}
            if sub.kind == 'open_supply':
                committed = sum(_snum(i.get('amount')) for i in (blob.get('invoices') or []))
                paid = sum(_snum(sp.get('amount')) for sp in (blob.get('supplyPayments') or [])
                           if sp.get('paid') or (sp.get('certificate') or {}).get('status') == 'paid')
                sub_payable += committed - paid
            else:
                certified = paid = 0.0
                for p in (blob.get('payments') or []):
                    net = _row_net(p)
                    status = (p.get('certificate') or {}).get('status', 'draft')
                    if status in ('certified', 'signed', 'paid'):
                        certified += net
                    if p.get('paid') or status == 'paid':
                        paid += net
                sub_payable += certified - paid
        except (ValueError, TypeError, AttributeError):
            continue
    stats['subcontracts'] = {'count': sub_count, 'payable': round(sub_payable)}

    return jsonify({'stats': stats})


# ── Update project ────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>', methods=['PUT'])
@jwt_required()
def update_project(project_id):
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'admin')

    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404
    # 'projects' module = Project Settings. Editing settings needs the admin role
    # (enforced above) AND edit on the module in the per-member permission map.
    if not member or not member.can('projects', 'edit'):
        return jsonify({'error': 'Insufficient permissions'}), 403

    data = request.get_json(silent=True) or {}

    if 'code' in data and data['code'].strip():
        project.code = data['code'].strip().upper()[:10]
    if 'name' in data and data['name'].strip():
        project.name = data['name'].strip()
    if 'client'      in data: project.client      = (data['client']      or '').strip()
    if 'consultant'  in data: project.consultant  = (data['consultant']  or '').strip()
    if 'contractor'  in data: project.contractor  = (data['contractor']  or '').strip()
    if 'description' in data: project.description = (data['description'] or '').strip()
    if 'status'      in data and data['status'] in ('active', 'on-hold', 'completed'):
        project.status = data['status']

    db.session.commit()

    result            = project.to_dict()
    result['my_role'] = member.role
    return jsonify({'project': result})


# ── Delete project ────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>', methods=['DELETE'])
@jwt_required()
def delete_project(project_id):
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'owner')

    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    db.session.delete(project)
    db.session.commit()
    return jsonify({'message': f'Project "{project.name}" deleted'})


# ── List members ──────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/members', methods=['GET'])
@jwt_required()
def list_members(project_id):
    user_id         = int(get_jwt_identity())
    project, member = _get_membership(project_id, user_id)

    if not project:
        return jsonify({'error': 'Project not found or access denied'}), 404

    members = [m.to_dict() for m in project.members]
    return jsonify({'members': members, 'total': len(members)})


# ── Add member ────────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/members', methods=['POST'])
@jwt_required()
def add_member(project_id):
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'admin')

    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    data       = request.get_json(silent=True) or {}
    identifier = (data.get('email') or data.get('username') or '').strip()
    if not identifier:
        return jsonify({'error': 'Provide email or username of the user to invite'}), 400

    target = (
        User.query.filter_by(email=identifier.lower()).first()
        or User.query.filter_by(username=identifier).first()
    )
    if not target:
        return jsonify({'error': f'No user found with email/username "{identifier}"'}), 404

    # TENANT ISOLATION: a project may only include members of its own company.
    # Surfacing whether a foreign-company user exists would itself leak, so this
    # mirrors the generic "no user found" message.
    if target.company_id != project.company_id:
        return jsonify({'error': f'No user found with email/username "{identifier}"'}), 404

    if ProjectMember.query.filter_by(project_id=project_id, user_id=target.id).first():
        return jsonify({'error': 'User is already a member of this project'}), 409

    role = data.get('role', 'member')
    if role not in _VALID_ROLES:
        role = 'member'

    new_member = ProjectMember(project_id=project_id, user_id=target.id, role=role,
                               company_id=project.company_id)
    db.session.add(new_member)
    db.session.commit()

    return jsonify({'member': new_member.to_dict()}), 201


# ── Update member role ────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/members/<int:member_id>', methods=['PUT'])
@jwt_required()
def update_member_role(project_id, member_id):
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'admin')

    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    target = ProjectMember.query.get(member_id)
    if not target or target.project_id != project_id:
        return jsonify({'error': 'Member not found'}), 404
    if target.role == 'owner':
        return jsonify({'error': 'Cannot change the role of the project owner'}), 403

    data = request.get_json(silent=True) or {}
    role = data.get('role', 'member')
    if role not in _VALID_ROLES:
        return jsonify({'error': f'Role must be one of: {", ".join(_VALID_ROLES)}'}), 400

    target.role = role
    db.session.commit()
    return jsonify({'member': target.to_dict()})


# ── Remove member ─────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/members/<int:member_id>', methods=['DELETE'])
@jwt_required()
def remove_member(project_id, member_id):
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'admin')

    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    target = ProjectMember.query.get(member_id)
    if not target or target.project_id != project_id:
        return jsonify({'error': 'Member not found'}), 404
    if target.role == 'owner':
        return jsonify({'error': 'Cannot remove the project owner'}), 403

    db.session.delete(target)
    db.session.commit()
    return jsonify({'message': 'Member removed successfully'})


# ── Per-module permissions (CEO / project-admin management) ─────────────────────
# The permission map lives on ProjectMember.permissions ({module:{view,edit}}).
# A project admin/owner manages the map for that ONE project; company-level access
# still flows through list_projects, so a project manager only ever reaches the
# projects they belong to. Enforcement of the map itself lives in each module's
# route helpers (it reads ProjectMember.can()).

def _normalize_permission_map(raw, base):
    """Merge a client-supplied permission map onto `base`, over known modules.

    Only PERMISSION_MODULES keys are honoured; unknown keys are dropped. Each
    entry is coerced to real booleans and `edit` forces `view` on (you cannot
    grant edit without view). Modules absent from `raw` keep their `base` value,
    so a single-toggle save that sends the whole grid — or a partial one — both
    behave correctly.
    """
    out = {}
    for mod in PERMISSION_MODULES:
        b = base.get(mod) or {'view': True, 'edit': False}
        entry = raw.get(mod) if isinstance(raw, dict) else None
        if isinstance(entry, dict):
            edit = bool(entry.get('edit'))
            view = bool(entry.get('view')) or edit
        else:
            edit = bool(b.get('edit'))
            view = bool(b.get('view')) or edit
        out[mod] = {'view': view, 'edit': edit}
    return out


@projects_bp.route('/<int:project_id>/permissions', methods=['GET'])
@jwt_required()
def get_permissions(project_id):
    """Every member of the project with their effective per-module permission map.

    Project admin/owner only — this is the data behind the CEO permissions grid.
    """
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'admin')
    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    members = []
    for m in project.members:
        row = m.to_dict()
        row['member_id']   = m.id
        row['permissions'] = m.effective_permissions()
        members.append(row)

    return jsonify({
        'modules': list(PERMISSION_MODULES),
        'members': members,
        'total':   len(members),
    })


@projects_bp.route('/<int:project_id>/members/<int:member_id>/permissions', methods=['PUT'])
@jwt_required()
def update_member_permissions(project_id, member_id):
    """Set one member's per-module view/edit grants for this project.

    Project admin/owner only. The owner's grants are fixed (always full access)
    and cannot be edited — mirrors the role-change / removal protections above.
    """
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'admin')
    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    target = ProjectMember.query.get(member_id)
    if not target or target.project_id != project_id:
        return jsonify({'error': 'Member not found'}), 404
    if target.role == 'owner':
        return jsonify({'error': 'The project owner always has full access'}), 403

    data = request.get_json(silent=True) or {}
    raw  = data.get('permissions')
    if not isinstance(raw, dict):
        return jsonify({'error': 'A "permissions" object is required'}), 400

    final = _normalize_permission_map(raw, target.get_permissions())
    target.permissions = json.dumps(final)
    db.session.commit()

    return jsonify({'member_id': target.id, 'permissions': final})
