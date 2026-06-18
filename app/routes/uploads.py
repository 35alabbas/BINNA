"""
BINNA — File Uploads API  (Phase 8 · file isolation closed in Phase 2 follow-up)
POST /api/v1/projects/<project_id>/uploads  → upload a file, returns {file_name, url}
GET  /api/v1/uploads/<filename>             → serve / download a file (tenant-gated)

Every stored file gets an Upload ownership row (company_id + project_id). The
serve endpoint resolves that row and routes through the SAME tenancy gate as
every other endpoint, so a file can only be fetched by a member of its owning
project/company. There is no longer any authenticated-but-unscoped file access.
"""
import os
import uuid

from flask import Blueprint, jsonify, request, send_from_directory, current_app, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app import db
from app.models import Project, ProjectMember, Upload, User
from app.tenancy import membership_or_none

uploads_bp = Blueprint('uploads', __name__)

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx',
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp',
    'zip', 'rar', 'txt', 'csv',
}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _check_access(project_id, user_id):
    # Company-scoped gate (company match + membership) — returns project or None.
    proj, mem = membership_or_none(project_id, user_id)
    return proj if mem else None


def record_upload(stored_name, original_name, project, user_id):
    """Create the ownership record that scopes a stored file to its tenant.

    Shared by every endpoint that stores a file (this blueprint + the DC archive
    upload), so the serve gate can always resolve company/project for a filename.
    """
    db.session.add(Upload(
        stored_name   = stored_name,
        original_name = original_name,
        company_id    = project.company_id,
        project_id    = project.id,
        uploaded_by   = user_id,
    ))


@uploads_bp.route('/api/v1/projects/<int:project_id>/uploads', methods=['POST'])
@jwt_required()
def upload_file(project_id):
    uid = int(get_jwt_identity())
    proj = _check_access(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

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

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    f.save(os.path.join(upload_folder, stored_name))

    # Ownership record — scopes this file to the project's company/tenant.
    record_upload(stored_name, orig, proj, uid)
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

    proj, mem = membership_or_none(upload.project_id, uid)
    if not mem:
        abort(404)

    upload_folder = current_app.config['UPLOAD_FOLDER']
    full_path = os.path.join(upload_folder, safe)
    if not os.path.isfile(full_path):
        abort(404)
    return send_from_directory(upload_folder, safe, as_attachment=False)
