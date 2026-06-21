"""
BINNA — Authentication blueprint  (Phase 2: account & access flows)

POST /api/v1/auth/register          self-signup → unverified account + email
GET  /api/v1/auth/verify/<token>    verify → create company → owner → 14-day trial
POST /api/v1/auth/login             login (blocked until email verified)
POST /api/v1/auth/refresh
GET  /api/v1/auth/me
PUT  /api/v1/auth/me                (change password / username)
POST /api/v1/auth/forgot-password   request a reset link
POST /api/v1/auth/reset-password    consume a reset token
"""
import re
import secrets
from datetime import timedelta

from flask import Blueprint, request, jsonify, redirect, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)

from app import db
from app.models import User, Company, _now
from app.email import send_verification_email, send_password_reset_email

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

TRIAL_DAYS = 14


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _token() -> str:
    return secrets.token_urlsafe(32)


def _slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')
    return slug or 'company'


def _unique_slug(name: str) -> str:
    base = _slugify(name)
    slug = base
    n = 2
    while Company.query.filter_by(slug=slug).first():
        slug = f'{base}-{n}'
        n += 1
    return slug


def create_company_for(user: User, name: str) -> Company:
    """Create a tenant for `user`, make them owner, and start the 14-day trial.

    This is the single place a company comes into existence — both self-signup
    verification and (re-used by) any future bootstrap path go through here.
    """
    company = Company(
        name          = (name or '').strip() or f"{user.username}'s workspace",
        slug          = _unique_slug(name or user.username),
        plan          = 'trial',
        status        = 'trial',
        trial_ends_at = _now() + timedelta(days=TRIAL_DAYS),
    )
    db.session.add(company)
    db.session.flush()                 # populate company.id

    user.company_id   = company.id
    user.company_role = 'owner'
    return company


# ── Register (self-signup) ──────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}

    username     = (data.get('username') or '').strip()
    email        = (data.get('email')    or '').strip().lower()
    password     = (data.get('password') or '')
    company_name = (data.get('company_name') or data.get('company') or '').strip()

    # Validate
    if not username or not email or not password:
        return jsonify({'error': 'Username, email and password are required'}), 400
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    # Account is created UNVERIFIED. The company is NOT created yet — it is
    # materialised at the moment of verification (see verify_email).
    user = User(
        username             = username,
        email                = email,
        email_verified       = False,
        email_verification_token = _token(),
        pending_company_name = company_name,
    )
    user.set_password(password)

    # First user ever → BINNA platform super-admin (platform role, independent of
    # the tenant role they get as their own company's owner).
    if User.query.count() == 0:
        user.role = 'admin'

    db.session.add(user)
    db.session.commit()

    link = f"{current_app.config['APP_BASE_URL']}/api/v1/auth/verify/{user.email_verification_token}"
    email_sent = send_verification_email(user.email, link)

    # D1 fix: don't claim the email was sent when it wasn't. The account IS
    # created either way (still 201); the message + email_sent flag tell the
    # truth so the client can offer "Resend verification email".
    if email_sent:
        message = (f'Account created! Check your inbox at {user.email} for a '
                   'verification link, then sign in.')
    else:
        message = (f"Account created - but we couldn't send the verification email "
                   f"to {user.email}. Use the link below to try again.")

    return jsonify({
        'message':    message,
        'email':      user.email,
        'email_sent': email_sent,
    }), 201


# ── Verify email → create company → owner → trial ───────────────────────────────

@auth_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    user = User.query.filter_by(email_verification_token=token).first()
    if not user:
        # Already-verified links land here too (token cleared); send them to login.
        return redirect(f"{current_app.config['APP_BASE_URL']}/?signin=1&verified=already")

    if not user.email_verified:
        user.email_verified = True
        # Self-signup users own a brand-new company. Invited users (invite_pending)
        # already have a company_id assigned by the inviter — never create one for
        # them; their invite acceptance sets the password separately.
        if user.company_id is None and not user.invite_pending:
            create_company_for(user, user.pending_company_name)
        user.email_verification_token = None
        user.pending_company_name     = None
        db.session.commit()

    return redirect(f"{current_app.config['APP_BASE_URL']}/?signin=1&verified=1")


# ── Resend verification email (D2 fix) ──────────────────────────────────────────

@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Re-send the verification email for an unverified account.

    For a missing or already-verified address we return a generic 200 (no work,
    no account-state disclosure). Only an existing UNVERIFIED account triggers a
    real send — and a send failure is reported honestly (same spirit as D1).
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user or user.email_verified:
        return jsonify({
            'message': 'If that email has an unverified BINNA account, a new '
                       'verification link is on its way.',
        }), 200

    # Unverified account: make sure a token exists, then re-send.
    if not user.email_verification_token:
        user.email_verification_token = _token()
        db.session.commit()

    link = f"{current_app.config['APP_BASE_URL']}/api/v1/auth/verify/{user.email_verification_token}"
    if send_verification_email(user.email, link):
        return jsonify({'message': 'Verification email sent - check your inbox.'}), 200
    return jsonify({
        'error': "We couldn't send the verification email right now. "
                 "Please try again in a moment.",
    }), 502


# ── Login ───────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}

    login_id = (data.get('email') or data.get('username') or '').strip()
    password = (data.get('password') or '')

    if not login_id or not password:
        return jsonify({'error': 'Email/username and password are required'}), 400

    user = (
        User.query.filter_by(email=login_id.lower()).first()
        or User.query.filter_by(username=login_id).first()
    )

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is deactivated — contact your administrator'}), 403

    if not user.email_verified:
        return jsonify({
            'error': 'Please verify your email before signing in. Check your inbox '
                     'for the verification link.',
            'unverified': True,
        }), 403

    access_token  = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        'user':          user.to_dict(),
        'access_token':  access_token,
        'refresh_token': refresh_token,
    })


# ── Refresh ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id      = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({'access_token': access_token})


# ── Me ──────────────────────────────────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    payload = {'user': user.to_dict()}
    if user.company:
        payload['company'] = user.company.to_dict()
    return jsonify(payload)


@auth_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_me():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}

    if 'username' in data:
        new_username = data['username'].strip()
        if len(new_username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        existing = User.query.filter_by(username=new_username).first()
        if existing and existing.id != user.id:
            return jsonify({'error': 'Username already taken'}), 409
        user.username = new_username

    if 'new_password' in data:
        old_pw = data.get('current_password', '')
        if not user.check_password(old_pw):
            return jsonify({'error': 'Current password is incorrect'}), 400
        if len(data['new_password']) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        user.set_password(data['new_password'])

    db.session.commit()
    return jsonify({'user': user.to_dict()})


# ── Password reset (reuses the same email plumbing) ─────────────────────────────

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data  = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()

    # Always return the same generic response — never reveal whether an email is
    # registered (account-enumeration defence).
    generic = jsonify({
        'message': 'If that email is registered, a password reset link has been sent.'
    })

    if email:
        user = User.query.filter_by(email=email).first()
        if user and user.email_verified:
            user.password_reset_token   = _token()
            user.password_reset_expires = _now() + timedelta(hours=1)
            db.session.commit()
            link = (f"{current_app.config['APP_BASE_URL']}"
                    f"/reset-password?token={user.password_reset_token}")
            send_password_reset_email(user.email, link)

    return generic, 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data     = request.get_json(silent=True) or {}
    token    = (data.get('token') or '').strip()
    new_pw   = (data.get('new_password') or data.get('password') or '')

    if not token or not new_pw:
        return jsonify({'error': 'Token and new password are required'}), 400
    if len(new_pw) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    user = User.query.filter_by(password_reset_token=token).first()
    if not user or not user.password_reset_expires:
        return jsonify({'error': 'Invalid or expired reset link'}), 400

    # tz-safe compare: values round-tripped through SQLite come back naive, while
    # _now() is tz-aware. Normalise to the same flavour before comparing.
    expires = user.password_reset_expires
    now     = _now()
    if expires.tzinfo is None:
        now = now.replace(tzinfo=None)
    if expires < now:
        return jsonify({'error': 'Invalid or expired reset link'}), 400

    user.set_password(new_pw)
    user.password_reset_token   = None
    user.password_reset_expires = None
    # A successful reset proves email ownership — treat it as verification too.
    user.email_verified = True
    db.session.commit()

    return jsonify({'message': 'Password updated. You can now sign in.'}), 200
