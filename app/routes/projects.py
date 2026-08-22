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
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import (
    DCLetter,
    AuditLog,
    DailyReport,
    FinancialData,
    GanttData,
    GlobalParty,
    LabTest,
    PERMISSION_MODULES,
    Project,
    ProjectMember,
    ProjectMonitoringComment,
    SEED_GLOBAL_PARTY_ROLES,
    Subcontract,
    Submittal,
    User,
)
from app.tenancy import (
    authorize_project_access,
    can_read_project_management_records,
    can_manage_project_assignments,
    can_manage_project_portfolio,
    is_project_manager,
    is_project_closed,
    membership_or_none,
    phase_1b_schema_status,
    phase_1b_2_schema_status,
    same_company,
)
from app.audit import record_audit

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
    project, member, allowed = authorize_project_access(
        project_id, user_id, 'projects', 'view', 'viewer',
    )
    return (project, member) if allowed else (None, None)


def _requires_role(project_id: int, user_id: int, min_role: str):
    """Return (project, member) or abort with 404/403."""
    action = 'view' if min_role == 'viewer' else 'edit'
    project, member, allowed = authorize_project_access(
        project_id, user_id, 'projects', action, min_role,
    )
    return (project, member) if allowed else (None, None)


def _phase_1b_required():
    status = phase_1b_schema_status()
    if status['ready']:
        return None
    return jsonify({
        'error': 'Phase 1B database migration is required',
        'code': 'phase_1b_migration_required',
        'missing': status['missing'],
    }), 503


def _phase_1b_2_required():
    status = phase_1b_2_schema_status()
    if status['ready']:
        return None
    return jsonify({
        'error': 'Phase 1B-2 database migration is required',
        'code': 'phase_1b_2_migration_required',
        'missing': status['missing'],
    }), 503


def _with_lifecycle(project, data):
    if phase_1b_2_schema_status()['ready']:
        data.update({
            'is_closed': bool(project.is_closed),
            'closed_at': project.closed_at.isoformat() if project.closed_at else None,
            'closed_by_user_id': project.closed_by_user_id,
        })
    return data


def _management_project(project_id, user_id, read_only=False):
    user = User.query.get(user_id)
    project = Project.query.get(project_id)
    if not same_company(project, user):
        return None, user
    allowed = (can_read_project_management_records(user, project) if read_only
               else can_manage_project_portfolio(user))
    return (project if allowed else None), user


def _assignment_manager(project_id, user_id):
    user = User.query.get(user_id)
    project = Project.query.get(project_id)
    if can_manage_project_assignments(user, project):
        if is_project_closed(project):
            from app.tenancy import ProjectClosedError
            raise ProjectClosedError()
        return project, user
    # Backward compatibility: an existing technical admin/owner with projects
    # edit permission keeps the project-management access they already had.
    legacy_project, _member, allowed = authorize_project_access(
        project_id, user_id, 'projects', 'edit', 'admin',
    )
    return (legacy_project, user) if allowed else (None, None)


def _valid_project_manager(project, target_id):
    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        return None
    target = User.query.get(target_id)
    if (not target or not target.is_active
            or target.company_id != project.company_id):
        return None
    return target


def _ensure_manager_membership(project, target):
    membership = ProjectMember.query.filter_by(
        project_id=project.id, user_id=target.id,
    ).first()
    if membership is None:
        membership = ProjectMember(
            project_id=project.id, user_id=target.id,
            company_id=project.company_id, role='viewer',
        )
        db.session.add(membership)
    return membership


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

    membership_by_project = {m.project_id: m for m in memberships}
    if can_manage_project_portfolio(user):
        projects = (Project.query.filter_by(company_id=user.company_id)
                    .order_by(Project.created_at.desc()).all())
    else:
        projects = [m.project for m in memberships]

    result = []
    for project in projects:
        m = membership_by_project.get(project.id)
        if not can_manage_project_portfolio(user) and (
                m is None or not m.can('projects', 'view')):
            continue
        p = _with_lifecycle(project, project.to_dict())
        p['my_role']      = m.role if m else 'viewer'
        p['member_count'] = len(project.members)
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
    missing = _phase_1b_required()
    if missing:
        return missing
    if not can_manage_project_portfolio(user):
        return jsonify({'error': 'Company or projects manager access required'}), 403
    data    = request.get_json(silent=True) or {}

    code = (data.get('code') or '').strip().upper()
    name = (data.get('name') or '').strip()

    if not code or not name:
        return jsonify({'error': 'Project code and name are required'}), 400
    if len(code) > 10:
        return jsonify({'error': 'Project code must be ≤ 10 characters'}), 400

    # Stamp the creator's company onto the project (the tenant that owns it).
    company_id = user.company_id

    requested_manager = data.get('project_manager_user_id')
    if requested_manager in (None, ''):
        requested_manager = user.company.projects_manager_user_id
    if requested_manager in (None, ''):
        return jsonify({'error': 'A projects manager or project manager must be designated'}), 409
    manager_shell = type('ProjectShell', (), {'company_id': company_id})()
    manager = _valid_project_manager(manager_shell, requested_manager)
    if manager is None:
        return jsonify({'error': 'Project manager not found'}), 404

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
        project_manager_user_id = manager.id,
    )
    db.session.add(project)
    db.session.flush()          # populate project.id before member insert

    record_audit(
        company_id=company_id, project_id=project.id, actor_user_id=user_id,
        action_type='project.created',
        new_values={'project_id': project.id, 'code': project.code, 'name': project.name,
                    'status': project.status, 'project_manager_user_id': manager.id},
    )

    # Creator is the owner — membership row also carries the company stamp.
    _ensure_manager_membership(project, manager)

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
    creator_membership = ProjectMember.query.filter_by(
        project_id=project.id, user_id=user_id,
    ).first()
    result['my_role']   = creator_membership.role if creator_membership else 'viewer'
    result['project_manager_user_id'] = manager.id
    result['member_count'] = 1
    return jsonify({'project': result}), 201


# ── Get project ───────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>', methods=['GET'])
@jwt_required()
def get_project(project_id):
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'viewer')

    if not project:
        return jsonify({'error': 'Project not found or access denied'}), 404

    result             = _with_lifecycle(project, project.to_dict(include_members=True))
    result['my_role']  = member.role if member else 'viewer'
    if phase_1b_schema_status()['ready']:
        result['project_manager_user_id'] = project.project_manager_user_id
    return jsonify({'project': result})


@projects_bp.route('/<int:project_id>/close', methods=['POST'])
@jwt_required()
def close_project(project_id):
    missing = _phase_1b_2_required()
    if missing:
        return missing
    uid = int(get_jwt_identity())
    project, user = _management_project(project_id, uid)
    if project is None:
        candidate = Project.query.get(project_id)
        if candidate is not None and same_company(candidate, user):
            return jsonify({'error': 'Company or projects manager access required'}), 403
        return jsonify({'error': 'Project not found'}), 404
    if project.is_closed:
        return jsonify({'error': 'Project is already closed', 'code': 'project_already_closed'}), 409
    now = datetime.now(timezone.utc)
    project.is_closed = True
    project.closed_at = now
    project.closed_by_user_id = uid
    record_audit(
        company_id=project.company_id, project_id=project.id, actor_user_id=uid,
        action_type='project.closed',
        previous_values={'is_closed': False},
        new_values={'is_closed': True, 'closed_by_user_id': uid,
                    'closed_at': now.isoformat()},
    )
    db.session.commit()
    result = project.to_dict()
    result.update({'is_closed': True, 'closed_at': now.isoformat(),
                   'closed_by_user_id': uid})
    return jsonify({'project': result})


@projects_bp.route('/<int:project_id>/reopen', methods=['POST'])
@jwt_required()
def reopen_project(project_id):
    missing = _phase_1b_2_required()
    if missing:
        return missing
    uid = int(get_jwt_identity())
    project, user = _management_project(project_id, uid)
    if project is None:
        candidate = Project.query.get(project_id)
        if candidate is not None and same_company(candidate, user):
            return jsonify({'error': 'Company or projects manager access required'}), 403
        return jsonify({'error': 'Project not found'}), 404
    if not project.is_closed:
        return jsonify({'error': 'Project is not closed', 'code': 'project_not_closed'}), 409
    previous = {'is_closed': True, 'closed_by_user_id': project.closed_by_user_id,
                'closed_at': project.closed_at.isoformat() if project.closed_at else None}
    project.is_closed = False
    project.closed_at = None
    project.closed_by_user_id = None
    record_audit(
        company_id=project.company_id, project_id=project.id, actor_user_id=uid,
        action_type='project.reopened', previous_values=previous,
        new_values={'is_closed': False},
    )
    db.session.commit()
    result = project.to_dict()
    result.update({'is_closed': False, 'closed_at': None, 'closed_by_user_id': None})
    return jsonify({'project': result})


@projects_bp.route('/<int:project_id>/monitoring-comments', methods=['GET'])
@jwt_required()
def list_monitoring_comments(project_id):
    missing = _phase_1b_2_required()
    if missing:
        return missing
    uid = int(get_jwt_identity())
    project, user = _management_project(project_id, uid, read_only=True)
    if project is None:
        candidate = Project.query.get(project_id)
        if candidate is not None and same_company(candidate, user):
            return jsonify({'error': 'Management record access required'}), 403
        return jsonify({'error': 'Project not found'}), 404
    rows = (ProjectMonitoringComment.query
            .filter_by(company_id=project.company_id, project_id=project.id)
            .order_by(ProjectMonitoringComment.created_at.asc(),
                      ProjectMonitoringComment.id.asc()).all())
    return jsonify({'comments': [row.to_dict() for row in rows], 'total': len(rows)})


@projects_bp.route('/<int:project_id>/monitoring-comments', methods=['POST'])
@jwt_required()
def add_monitoring_comment(project_id):
    missing = _phase_1b_2_required()
    if missing:
        return missing
    uid = int(get_jwt_identity())
    project, user = _management_project(project_id, uid)
    if project is None:
        candidate = Project.query.get(project_id)
        if candidate is not None and same_company(candidate, user):
            return jsonify({'error': 'Company or projects manager access required'}), 403
        return jsonify({'error': 'Project not found'}), 404
    body = ((request.get_json(silent=True) or {}).get('body') or '').strip()
    if not body:
        return jsonify({'error': 'Comment body is required'}), 400
    row = ProjectMonitoringComment(
        company_id=project.company_id, project_id=project.id,
        author_user_id=uid, body=body,
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({'comment': row.to_dict()}), 201


@projects_bp.route('/<int:project_id>/audit-logs', methods=['GET'])
@jwt_required()
def list_project_audit_logs(project_id):
    missing = _phase_1b_2_required()
    if missing:
        return missing
    uid = int(get_jwt_identity())
    project, user = _management_project(project_id, uid, read_only=True)
    if project is None:
        candidate = Project.query.get(project_id)
        if candidate is not None and same_company(candidate, user):
            return jsonify({'error': 'Management record access required'}), 403
        return jsonify({'error': 'Project not found'}), 404
    rows = (AuditLog.query.filter_by(company_id=project.company_id, project_id=project.id)
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc()).all())
    return jsonify({'audit_logs': [row.to_dict() for row in rows], 'total': len(rows)})


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
    project, member = _requires_role(project_id, uid, 'viewer')
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

    # Keep the dashboard response shape stable while withholding counts and
    # money from modules this member cannot view. Existing clients still receive
    # every established key, with a neutral zero value for hidden modules.
    hidden_stat_keys = {
        'dc':           ('dc',),
        'dr':           ('dr',),
        'lbt':          ('lbt',),
        'submittals':   ('dwg', 'fir', 'mir', 'ms', 'rfi'),
        'financial':    ('financial', 'cashflow', 'certified', 'received'),
        'gantt':        ('gantt',),
    }
    user = User.query.get(uid)
    unrestricted_view = (can_manage_project_portfolio(user)
                         or is_project_manager(user, project))
    for module, keys in hidden_stat_keys.items():
        if not unrestricted_view and member and not member.can(module, 'view'):
            for key in keys:
                stats[key] = 0
    if (not unrestricted_view and member
            and not member.can('subcontracts', 'view')):
        stats['subcontracts'] = {'count': 0, 'payable': 0}

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
    user = User.query.get(user_id)
    if (not is_project_manager(user, project)
            and (not member or not member.can('projects', 'edit'))):
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
    project, member = membership_or_none(project_id, user_id)

    if (not project or not member or member.role != 'owner'
            or not member.can('projects', 'edit')):
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    return jsonify({
        'error': 'Project deletion is disabled; close the project instead',
        'code': 'project_deletion_disabled',
    }), 409


# ── Designated project manager ────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/project-manager', methods=['PUT'])
@jwt_required()
def set_project_manager(project_id):
    missing = _phase_1b_required()
    if missing:
        return missing
    user_id = int(get_jwt_identity())
    project, manager = _assignment_manager(project_id, user_id)
    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    data = request.get_json(silent=True) or {}
    target = _valid_project_manager(project, data.get('user_id'))
    if target is None:
        return jsonify({'error': 'Project manager not found'}), 404

    previous_id = project.project_manager_user_id
    _ensure_manager_membership(project, target)
    project.project_manager_user_id = target.id
    record_audit(
        company_id=project.company_id, project_id=project.id, actor_user_id=user_id,
        action_type='project.manager_assigned',
        previous_values={'project_manager_user_id': previous_id},
        new_values={'project_manager_user_id': target.id},
    )
    db.session.commit()
    return jsonify({
        'project_id': project.id,
        'project_manager_user_id': target.id,
    })


# ── List members ──────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/members', methods=['GET'])
@jwt_required()
def list_members(project_id):
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'viewer')

    if not project:
        return jsonify({'error': 'Project not found or access denied'}), 404

    members = [m.to_dict() for m in project.members]
    return jsonify({'members': members, 'total': len(members)})


# ── Add member ────────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/members', methods=['POST'])
@jwt_required()
def add_member(project_id):
    user_id         = int(get_jwt_identity())
    project, member = _assignment_manager(project_id, user_id)

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
    db.session.flush()
    record_audit(
        company_id=project.company_id, project_id=project.id, actor_user_id=user_id,
        action_type='project.member_added',
        new_values={'member_id': new_member.id, 'user_id': target.id, 'role': role},
    )
    db.session.commit()

    return jsonify({'member': new_member.to_dict()}), 201


# ── Update member role ────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/members/<int:member_id>', methods=['PUT'])
@jwt_required()
def update_member_role(project_id, member_id):
    user_id         = int(get_jwt_identity())
    project, member = _assignment_manager(project_id, user_id)

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

    previous_role = target.role
    target.role = role
    record_audit(
        company_id=project.company_id, project_id=project.id, actor_user_id=user_id,
        action_type='project.member_role_changed',
        previous_values={'member_id': target.id, 'user_id': target.user_id,
                         'role': previous_role},
        new_values={'member_id': target.id, 'user_id': target.user_id, 'role': role},
    )
    db.session.commit()
    return jsonify({'member': target.to_dict()})


# ── Remove member ─────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>/members/<int:member_id>', methods=['DELETE'])
@jwt_required()
def remove_member(project_id, member_id):
    user_id         = int(get_jwt_identity())
    project, member = _assignment_manager(project_id, user_id)

    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

    target = ProjectMember.query.get(member_id)
    if not target or target.project_id != project_id:
        return jsonify({'error': 'Member not found'}), 404
    if target.role == 'owner':
        return jsonify({'error': 'Cannot remove the project owner'}), 403
    if (phase_1b_schema_status()['ready']
            and target.user_id == project.project_manager_user_id):
        return jsonify({'error': 'Replace the project manager before removing them'}), 403

    removed = {'member_id': target.id, 'user_id': target.user_id, 'role': target.role}
    db.session.delete(target)
    record_audit(
        company_id=project.company_id, project_id=project.id, actor_user_id=user_id,
        action_type='project.member_removed', previous_values=removed,
    )
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
    project, member = _assignment_manager(project_id, user_id)
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
    project, member = _assignment_manager(project_id, user_id)
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

    previous = target.effective_permissions()
    final = _normalize_permission_map(raw, target.get_permissions())
    target.permissions = json.dumps(final)
    record_audit(
        company_id=project.company_id, project_id=project.id, actor_user_id=user_id,
        action_type='project.permissions_changed',
        previous_values={'member_id': target.id, 'user_id': target.user_id,
                         'permissions': previous},
        new_values={'member_id': target.id, 'user_id': target.user_id,
                    'permissions': final},
    )
    db.session.commit()

    return jsonify({'member_id': target.id, 'permissions': final})
