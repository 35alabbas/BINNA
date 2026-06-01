"""
BINNA — Page routes (HTML views)
All authentication / authorisation is handled client-side (JWT in localStorage).
Flask simply serves the HTML; the JS on each page calls the API.
"""
import os
from flask import Blueprint, render_template, redirect, send_from_directory, abort

pages_bp = Blueprint('pages', __name__)

# Absolute path of the project root
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── SPA pages ─────────────────────────────────────────────────────────────────

@pages_bp.route('/')
def index():
    return redirect('/dashboard')


@pages_bp.route('/login')
def login_page():
    return render_template('login.html')


@pages_bp.route('/register')
def register_page():
    return render_template('register.html')


@pages_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@pages_bp.route('/project/<int:project_id>')
def project_home(project_id):
    return render_template('project.html')


# ── Legacy module pages (original HTML files, still use localStorage) ─────────
# These will be replaced one-by-one in Phase 2+

_LEGACY_MODULES = frozenset({
    'contract', 'dc', 'dr', 'dwg', 'expense', 'financial', 'fir', 'gantt', 'income', 'lbt', 'mir', 'ms', 'rfi', 'sub'
})


@pages_bp.route('/legacy/<module_name>')
def legacy_module(module_name):
    """Serve the original standalone HTML files directly from the project root."""
    if module_name not in _LEGACY_MODULES:
        abort(404)
    return send_from_directory(_ROOT, f'binna-{module_name}.html')


# ── 404 handler ───────────────────────────────────────────────────────────────

@pages_bp.app_errorhandler(404)
def not_found(e):
    # Return JSON for API routes, HTML for everything else
    from flask import request, jsonify
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return render_template('404.html'), 404
