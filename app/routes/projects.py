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
    LabTest,
    Project,
    ProjectMember,
    Submittal,
    User,
)

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
    """Return (Project, ProjectMember) or (None, None) if no access."""
    project = Project.query.get(project_id)
    if not project:
        return None, None
    member = ProjectMember.query.filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    if not member:
        return None, None
    return project, member


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
    user_id     = int(get_jwt_identity())
    memberships = (
        ProjectMember.query
        .filter_by(user_id=user_id)
        .join(Project)
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
    data    = request.get_json(silent=True) or {}

    code = (data.get('code') or '').strip().upper()
    name = (data.get('name') or '').strip()

    if not code or not name:
        return jsonify({'error': 'Project code and name are required'}), 400
    if len(code) > 10:
        return jsonify({'error': 'Project code must be ≤ 10 characters'}), 400

    project = Project(
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

    # Creator is the owner
    member = ProjectMember(project_id=project.id, user_id=user_id, role='owner')
    db.session.add(member)

    # Seed a blank financial record so the contract / financial pages open empty
    db.session.add(FinancialData(
        project_id = project.id,
        data       = json.dumps(_BLANK_FINANCIAL, ensure_ascii=False),
        updated_by = user_id,
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

    # Financial: length of payments array (fall back to boq when no payments)
    stats['financial'] = 0
    fin = FinancialData.query.filter_by(project_id=project_id).first()
    if fin and fin.data:
        try:
            fdata = json.loads(fin.data)
            payments = fdata.get('payments') or []
            stats['financial'] = len(payments) if payments else len(fdata.get('boq') or [])
        except (ValueError, TypeError):
            stats['financial'] = 0

    # Gantt: total task count
    stats['gantt'] = 0
    gantt = GanttData.query.filter_by(project_id=project_id).first()
    if gantt and gantt.tasks:
        try:
            stats['gantt'] = len(json.loads(gantt.tasks) or [])
        except (ValueError, TypeError):
            stats['gantt'] = 0

    return jsonify({'stats': stats})


# ── Update project ────────────────────────────────────────────────────────────

@projects_bp.route('/<int:project_id>', methods=['PUT'])
@jwt_required()
def update_project(project_id):
    user_id         = int(get_jwt_identity())
    project, member = _requires_role(project_id, user_id, 'admin')

    if not project:
        return jsonify({'error': 'Project not found or insufficient permissions'}), 404

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

    if ProjectMember.query.filter_by(project_id=project_id, user_id=target.id).first():
        return jsonify({'error': 'User is already a member of this project'}), 409

    role = data.get('role', 'member')
    if role not in _VALID_ROLES:
        role = 'member'

    new_member = ProjectMember(project_id=project_id, user_id=target.id, role=role)
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
