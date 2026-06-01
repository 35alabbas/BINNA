"""
BINNA — Authentication blueprint
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
GET  /api/v1/auth/me
PUT  /api/v1/auth/me        (change password / username)
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)

from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')


# ── Register ──────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}

    username = (data.get('username') or '').strip()
    email    = (data.get('email')    or '').strip().lower()
    password = (data.get('password') or '')

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

    user = User(username=username, email=email)
    user.set_password(password)

    # First user ever → admin
    if User.query.count() == 0:
        user.role = 'admin'

    db.session.add(user)
    db.session.commit()

    access_token  = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        'message':       'Account created successfully',
        'user':          user.to_dict(),
        'access_token':  access_token,
        'refresh_token': refresh_token,
    }), 201


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}

    login_id = (data.get('email') or data.get('username') or '').strip()
    password = (data.get('password') or '')

    if not login_id or not password:
        return jsonify({'error': 'Email/username and password are required'}), 400

    # Accept login by email OR username
    user = (
        User.query.filter_by(email=login_id.lower()).first()
        or User.query.filter_by(username=login_id).first()
    )

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is deactivated — contact your administrator'}), 403

    access_token  = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        'user':          user.to_dict(),
        'access_token':  access_token,
        'refresh_token': refresh_token,
    })


# ── Refresh ───────────────────────────────────────────────────────────────────

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id      = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({'access_token': access_token})


# ── Me ────────────────────────────────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()})


@auth_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_me():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}

    # Change username
    if 'username' in data:
        new_username = data['username'].strip()
        if len(new_username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        existing = User.query.filter_by(username=new_username).first()
        if existing and existing.id != user.id:
            return jsonify({'error': 'Username already taken'}), 409
        user.username = new_username

    # Change password
    if 'new_password' in data:
        old_pw = data.get('current_password', '')
        if not user.check_password(old_pw):
            return jsonify({'error': 'Current password is incorrect'}), 400
        if len(data['new_password']) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        user.set_password(data['new_password'])

    db.session.commit()
    return jsonify({'user': user.to_dict()})
