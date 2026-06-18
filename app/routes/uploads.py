"""
BINNA — File Uploads API  (Phase 8)
POST /api/v1/projects/<project_id>/uploads  → upload a file, returns {file_name, url}
GET  /api/v1/uploads/<filename>             → serve / download a file
"""
import os
import uuid

from flask import Blueprint, jsonify, request, send_from_directory, current_app, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app.models import Project, ProjectMember
from app.tenancy import membership_or_none

uploads_bp = Blueprint('uploads', __name__)

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx',
    'jpg', 'jpeg', 'png', 'gif', 'bmp',
    'zip', 'rar', 'txt', 'csv',
}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _check_access(project_id, user_id):
    # Company-scoped gate (company match + membership) — returns project or None.
    proj, mem = membership_or_none(project_id, user_id)
    return proj if mem else None


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
    ext          = f.filename.rsplit('.', 1)[1].lower()
    orig         = secure_filename(f.filename)
    stored_name  = f"{uuid.uuid4().hex}_{orig}"

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    f.save(os.path.join(upload_folder, stored_name))

    return jsonify({
        'file_name':    stored_name,
        'original_name': orig,
        'url':          f'/api/v1/uploads/{stored_name}',
    }), 201


@uploads_bp.route('/api/v1/uploads/<path:filename>', methods=['GET'])
@jwt_required()
def serve_file(filename):
    """Stream a stored upload back to the client."""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    safe = secure_filename(filename)
    if not safe or safe != filename:
        abort(400)
    full_path = os.path.join(upload_folder, safe)
    if not os.path.isfile(full_path):
        abort(404)
    return send_from_directory(upload_folder, safe, as_attachment=False)
