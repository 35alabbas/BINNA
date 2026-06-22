import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from config import config_by_name

# ── Extensions (initialised later via init_app) ───────────────────────────────
db      = SQLAlchemy()
migrate = Migrate()
jwt     = JWTManager()

# Absolute path of the project root (one level above this package)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(config_name: str = 'default') -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(_ROOT, 'templates'),
        static_folder=os.path.join(_ROOT, 'static'),
    )

    # ── Config ────────────────────────────────────────────────────────────────
    app.config.from_object(config_by_name[config_name])
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ── UTF-8 enforcement ─────────────────────────────────────────────────────
    app.config['JSON_AS_ASCII'] = False  # Flask <2.2 compat; no-op in Flask 3

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app, resources={r'/api/*': {'origins': '*'}})

    # ── Force UTF-8 charset on every JSON response ───────────────────────────
    from flask import request as _req

    @app.after_request
    def set_utf8_header(response):
        ct = response.headers.get('Content-Type', '')
        if 'application/json' in ct and 'charset' not in ct:
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

    # ── JWT error handlers ────────────────────────────────────────────────────
    from flask import jsonify

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify({'error': 'Missing or invalid token', 'detail': reason}), 401

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired'}), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify({'error': 'Invalid token', 'detail': reason}), 422

    # ── Import models so Flask-Migrate can detect them ────────────────────────
    from app import models  # noqa: F401

    # ── Blueprints ────────────────────────────────────────────────────────────
    from app.auth import auth_bp
    from app.company import company_bp
    from app.routes.projects import projects_bp
    from app.routes.dc import dc_bp
    from app.routes.submittals import submittals_bp
    from app.routes.dr import dr_bp
    from app.routes.lbt import lbt_bp
    from app.routes.financial import financial_bp
    from app.routes.gantt import gantt_bp
    from app.routes.subcontracts import subcontracts_bp
    from app.routes.global_parties import global_parties_bp
    from app.routes.uploads import uploads_bp
    from app.pages import pages_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(company_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(dc_bp,
        url_prefix='/api/v1/projects/<int:project_id>/dc')
    app.register_blueprint(submittals_bp,
        url_prefix='/api/v1/projects/<int:project_id>/submittals')
    app.register_blueprint(dr_bp,
        url_prefix='/api/v1/projects/<int:project_id>/dr')
    app.register_blueprint(lbt_bp,
        url_prefix='/api/v1/projects/<int:project_id>/lbt')
    app.register_blueprint(financial_bp,
        url_prefix='/api/v1/projects/<int:project_id>/financial')
    app.register_blueprint(gantt_bp,
        url_prefix='/api/v1/projects/<int:project_id>/gantt')
    app.register_blueprint(subcontracts_bp,
        url_prefix='/api/v1/projects/<int:project_id>')
    app.register_blueprint(global_parties_bp,
        url_prefix='/api/v1/projects/<int:project_id>/global-parties')
    app.register_blueprint(uploads_bp)   # has its own full URL paths
    app.register_blueprint(pages_bp)

    # ── Phase 4 billing lifecycle: read-only lock enforced lazily per request ──
    from app import billing
    billing.init_app(app)

    return app
