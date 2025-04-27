# app/auth.py
from flask import Blueprint, request, jsonify, current_app, make_response
from flask_login import login_user, logout_user, login_required, current_user
from .models import User
from . import get_db # <-- CORRECTED IMPORT
from bson import ObjectId
from werkzeug.security import generate_password_hash
import datetime

auth_bp = Blueprint('auth', __name__)

# --- Routes remain the same ---

@auth_bp.route('/signup', methods=['POST'])
def signup():
    db = get_db()
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({'message': 'Missing required fields (username, email, password)'}), 400

    if len(password) < 6:
         return jsonify({'message': 'Password must be at least 6 characters long'}), 400

    if db.users.find_one({"email": email}):
        return jsonify({'message': 'Email already exists'}), 409

    if db.users.find_one({"username": username}):
        return jsonify({'message': 'Username already exists'}), 409

    try:
        hashed_password = generate_password_hash(password)
        user_doc = {
            'username': username,
            'email': email,
            'password_hash': hashed_password,
            'created_at': datetime.datetime.utcnow()
        }
        result = db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)

        new_user_obj = User(id=user_id, username=username, email=email, password_hash=hashed_password, created_at=user_doc['created_at'])

        login_user(new_user_obj, remember=True)
        current_app.logger.info(f"User {new_user_obj.username} created and logged in.")

        return jsonify({
            'message': 'User created successfully',
            'user': new_user_obj.to_dict()
        }), 201
    except Exception as e:
        current_app.logger.error(f"Error creating user: {str(e)}")
        return jsonify({'message': 'Error creating user', 'error': str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    db = get_db()
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), 400

    identifier = data.get('identifier')
    password = data.get('password')

    if not identifier or not password:
        return jsonify({'message': 'Missing identifier or password'}), 400

    user_data = db.users.find_one({"$or": [{"email": identifier}, {"username": identifier}]})

    if user_data:
        user_obj = User(
            id=str(user_data['_id']),
            username=user_data.get('username'),
            email=user_data.get('email'),
            password_hash=user_data.get('password_hash'),
            created_at=user_data.get('created_at')
        )

        if user_obj.check_password(password):
            remember_session = data.get('remember', True)
            login_user(user_obj, remember=remember_session)
            current_app.logger.info(f'User {user_obj.username} logged in successfully.')
            return jsonify({
                'message': 'Login successful',
                'user': user_obj.to_dict()
            }), 200
        else:
            current_app.logger.warning(f'Failed login attempt for identifier: {identifier} - Incorrect password')
            return jsonify({'message': 'Invalid credentials'}), 401
    else:
        current_app.logger.warning(f'Failed login attempt for identifier: {identifier} - User not found')
        return jsonify({'message': 'Invalid credentials'}), 401

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    username = current_user.username
    logout_user()
    current_app.logger.info(f'User {username} logged out.')
    response = make_response(jsonify({'message': 'Logout successful'}), 200)
    return response


@auth_bp.route('/status', methods=['GET'])
def session_status():
    """Check if a user session is active and return user info."""
    if current_user.is_authenticated:
        return jsonify({
            'logged_in': True,
            'user': current_user.to_dict()
        }), 200
    else:
        return jsonify({'logged_in': False}), 200
