# backend/app/auth.py
from flask import Blueprint, request, jsonify, current_app, g
from .models import User # Keep User model if used for structure/methods
from . import get_db
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import jwt # Import PyJWT
from .decorators import token_required # Import the token decorator

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['POST'])
def signup():
    db = get_db()
    data = request.get_json()
    if not data: return jsonify({'message': 'No input data provided'}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    # Basic Validation
    if not username or not email or not password:
        return jsonify({'message': 'Missing required fields'}), 400
    if len(password) < 6:
            return jsonify({'message': 'Password must be at least 6 characters'}), 400
    # Add more validation as needed (e.g., email format)

    # Check existing user
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
            'created_at': datetime.datetime.utcnow(),
            'isAdmin': False  # <-- ADDED: Default isAdmin to False
        }


        print(f"DEBUG: Attempting to insert user_doc: {user_doc}")
        result = db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        print(result)
        # --- Generate JWT Token on Signup ---
        token_payload = {
            'user_id': user_id,
            'username': username,
            'isAdmin': False, # <-- ADDED: Include isAdmin in JWT payload
            'exp': datetime.datetime.utcnow() + current_app.config['JWT_EXPIRATION_DELTA']
        }
        secret_key = current_app.config['SECRET_KEY']
        token = jwt.encode(token_payload, secret_key, algorithm="HS256")

        current_app.logger.info(f"User {username} created successfully.")

        # Return token and basic user info including isAdmin status
        return jsonify({
            'message': 'User created successfully',
            'access_token': token,
            'user': {
                'id': user_id,
                'username': username,
                'email': email,
                'isAdmin': False # <-- ADDED: Include isAdmin in response
            }
        }), 201
    except Exception as e:
        current_app.logger.error(f"Error creating user: {str(e)}")
        return jsonify({'message': 'Error creating user', 'error': str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    db = get_db()
    data = request.get_json()
    if not data: return jsonify({'message': 'No input data provided'}), 400

    identifier = data.get('identifier')
    password = data.get('password')

    if not identifier or not password:
        return jsonify({'message': 'Missing identifier or password'}), 400

    # Find user by email or username - Fetch isAdmin field
    user_data = db.users.find_one(
        {"$or": [{"email": identifier}, {"username": identifier}]},
        # Projection to get necessary fields including password hash and isAdmin
        {"_id": 1, "username": 1, "email": 1, "password_hash": 1, "isAdmin": 1} # <-- FETCH isAdmin
    )

    if user_data and check_password_hash(user_data.get('password_hash', ''), password):
        try:
            user_id_str = str(user_data['_id'])
            username_str = user_data.get('username')
            is_admin_status = user_data.get('isAdmin', False) # <-- Get isAdmin status

            # --- Generate JWT Token ---
            token_payload = {
                'user_id': user_id_str,
                'username': username_str,
                'isAdmin': is_admin_status, # <-- ADDED: Include isAdmin in JWT payload
                'exp': datetime.datetime.utcnow() + current_app.config['JWT_EXPIRATION_DELTA']
            }
            secret_key = current_app.config['SECRET_KEY']
            token = jwt.encode(token_payload, secret_key, algorithm="HS256")

            current_app.logger.info(f'User {username_str} logged in successfully.')
            return jsonify({
                'message': 'Login successful',
                'access_token': token,
                'user': {
                        'id': user_id_str,
                        'username': username_str,
                        'email': user_data.get('email'),
                        'isAdmin': is_admin_status # <-- ADDED: Include isAdmin in response
                    }
            }), 200
        except Exception as e:
                current_app.logger.error(f"Error generating token during login: {e}")
                return jsonify({"message": "Error during login process"}), 500
    else:
        current_app.logger.warning(f'Failed login attempt for identifier: {identifier}')
        return jsonify({'message': 'Invalid credentials'}), 401


# --- Protected Route to Get User Info ---
@auth_bp.route('/me', methods=['GET'])
@token_required # Use the decorator
def get_current_user_info():
    """Returns information about the currently authenticated user via token."""
    # The user data dictionary is attached to g.current_user by the decorator
    if hasattr(g, 'current_user') and g.current_user:
        # Return the user info dictionary directly (already includes isAdmin from decorator)
        return jsonify(g.current_user), 200
    else:
        # Should not happen if decorator works, but include for safety
        return jsonify({'message': 'Could not identify user from token'}), 401