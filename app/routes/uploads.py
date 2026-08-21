"""
BINNA — File Uploads API  (Phase 8 · file isolation closed in Phase 2 follow-up)
POST /api/v1/projects/<project_id>/uploads  → upload a file, returns {file_name, url}
GET  /api/v1/uploads/<filename>             → serve / download a file (tenant-gated)

Every stored file gets an Upload ownership row (company_id + project_id). The
serve endpoint resolves that row and routes through the SAME tenancy gate as
every other endpoint, so a file can only be fetched by a member of its owning
project/company. There is no longer any authenticated-but-unscoped file access.
"""
import uuid

from flask import Blueprint, jsonify, request, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app import db, storage
from app.models import Project, ProjectMember, Upload, User, _ROLE_ORDER
from app.tenancy import authorize_project_access

uploads_bp = Blueprint('uploads', __name__)

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx',   # documents
    'dwg',                                  # CAD
    'jpg', 'jpeg', 'png', 'webp',          # images
    'zip', 'rar',                          # archives
}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# This blueprint's per-module permission key (see ProjectMember.can / effective_permissions).
_MODULE = 'uploads'


def _check_access(project_id, user_id):
    # Company-scoped gate (READ): company match + membership — returns project or None.
    proj, _mem, allowed = authorize_project_access(
        project_id, user_id, _MODULE, 'view', 'viewer')
    return proj if allowed else None


def _requires_role(project_id, user_id, min_role='member'):
    """Company-scoped gate (WRITE) — mirrors the seven already-gated modules.
    (None, None) → 404 (no access / wrong tenant); (project, None) → 403 (role too low)."""
    proj, mem, allowed = authorize_project_access(
        project_id, user_id, _MODULE, 'edit', min_role)
    if not proj:
        return None, None
    if not allowed:
        return proj, None
    if not allowed:
        return proj, None   # module edit revoked via the per-member permission map → 403
    return proj, mem


def record_upload(stored_name, original_name, project, user_id, size_bytes=None):
    """Create the ownership record that scopes a stored file to its tenant.

    Shared by every endpoint that stores a file (this blueprint + the DC archive
    upload), so the serve gate can always resolve company/project for a filename.
    `size_bytes` (returned by storage.save_file) feeds the per-company storage
    usage indicator; legacy callers that omit it record NULL.
    """
    db.session.add(Upload(
        stored_name   = stored_name,
        original_name = original_name,
        company_id    = project.company_id,
        project_id    = project.id,
        uploaded_by   = user_id,
        size_bytes    = size_bytes,
    ))


@uploads_bp.route('/api/v1/projects/<int:project_id>/uploads', methods=['POST'])
@jwt_required()
def upload_file(project_id):
    uid = int(get_jwt_identity())
    proj, mem = _requires_role(project_id, uid, 'member')
    if proj is None:
        return jsonify({'error': 'Project not found'}), 404
    if mem is None:
        return jsonify({'error': 'Insufficient permissions — member role required'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f = request.files['file']
    if not f or not f.filename:
        return jsonify({'error': 'Empty filename'}), 400

    if not _allowed(f.filename):
        return jsonify({
            'error': f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        }), 400

    # Build unique filename:  <uuid>_<original_secure_name>
    orig         = secure_filename(f.filename)
    stored_name  = f"{uuid.uuid4().hex}_{orig}"

    # Persist to R2 (or local disk when R2 is unset). Key = company/project/name.
    size = storage.save_file(f, proj.company_id, proj.id, stored_name)

    # Ownership record — scopes this file to the project's company/tenant.
    record_upload(stored_name, orig, proj, uid, size_bytes=size)
    db.session.commit()

    return jsonify({
        'file_name':    stored_name,
        'original_name': orig,
        'url':          f'/api/v1/uploads/{stored_name}',
    }), 201


@uploads_bp.route('/api/v1/uploads/<path:filename>', methods=['GET'])
@jwt_required()
def serve_file(filename):
    """Stream a stored upload back — only to a member of its owning project/company."""
    uid = int(get_jwt_identity())

    safe = secure_filename(filename)
    if not safe or safe != filename:
        abort(400)

    # TENANT ISOLATION: resolve the file's ownership record, then run the exact
    # same gate as every other endpoint. No record, or a cross-tenant caller →
    # 404 (indistinguishable from "file does not exist").
    upload = Upload.query.filter_by(stored_name=safe).first()
    if not upload:
        abort(404)

    proj, mem, allowed = authorize_project_access(
        upload.project_id, uid, _MODULE, 'view', 'viewer')
    if not allowed:
        abort(404)   # non-member, or uploads view revoked via the permission map

    # Gate passed → hand off to the storage backend. R2: JSON {url: presigned} for
    # the client to navigate to. Disk: stream the bytes. ?download=1 forces save.
    return storage.serve(upload, download=(request.args.get('download') == '1'))
