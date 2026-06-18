import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # ── Core ─────────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'binna-dev-secret-CHANGE-IN-PRODUCTION')

    # ── Database ──────────────────────────────────────────────────────────────────
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'binna.db'))
    # Normalize postgres:// → postgresql://
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    # Use psycopg3 driver for PostgreSQL connections
    if _db_url.startswith('postgresql://'):
        _db_url = _db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── JWT ───────────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'binna-jwt-secret-CHANGE-IN-PRODUCTION')
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # ── File uploads ──────────────────────────────────────────────────────────────
    UPLOAD_FOLDER      = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    # ── Email (Resend) ──────────────────────────────────────────────────────────────
    # Phase 2 account flows (verification / invite / password-reset) send mail via
    # Resend's HTTP API (https://resend.com). Free tier: 3,000/mo, 100/day.
    # When RESEND_API_KEY is unset (local dev / tests) the email module logs the
    # message + link to stderr instead of sending — so the flows are fully testable
    # offline. Wire RESEND_API_KEY into Render env vars for production.
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
    MAIL_FROM      = os.environ.get('MAIL_FROM', 'BINNA <onboarding@resend.dev>')
    # Public base URL used to build the tokenised links inside emails. Defaults to
    # localhost for dev; set APP_BASE_URL on Render to the live origin.
    APP_BASE_URL   = os.environ.get('APP_BASE_URL', 'http://localhost:5000')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
