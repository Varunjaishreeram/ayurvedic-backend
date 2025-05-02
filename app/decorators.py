# backend/app/decorators.py
import jwt
from functools import wraps
from flask import request, jsonify, current_app, g
from bson import ObjectId
from . import get_db # Use relative import within the app package
import datetime # Import datetime

def token_required(f):
    """
    Decorator to ensure a valid JWT token is present in the Authorization header.
    Attaches the authenticated user's data (as dict) to flask.g.current_user.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization') # Use .get for safety

        if auth_header and auth_header.startswith('Bearer '):
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Bearer token malformed'}), 401
        else:
                # Allow checking other places if needed (e.g., cookies for refresh tokens)
                pass # No Bearer token found in header

        if not token:
            return jsonify({'message': 'Authorization token is missing or invalid format'}), 401

        try:
            # Decode and verify the token
            secret_key = current_app.config['SECRET_KEY']
            # Add leeway for clock skew if needed: leeway=datetime.timedelta(seconds=10)
            data = jwt.decode(token, secret_key, algorithms=["HS256"])

            # --- Fetch user based on token data ---
            user_id = data.get('user_id')
            if not user_id:
                    return jsonify({'message': 'Token payload invalid (missing user_id)'}), 401

            db = get_db()
            # Select necessary fields including isAdmin
            current_user_data = db.users.find_one(
                {'_id': ObjectId(user_id)},
                {'_id': 1, 'username': 1, 'email': 1, 'isAdmin': 1} # <-- FETCH isAdmin
            )

            if current_user_data is None:
                # This could mean the user was deleted after the token was issued
                return jsonify({'message': 'Token references non-existent user'}), 401

            # Convert _id to string for consistency if needed downstream
            current_user_data['_id'] = str(current_user_data['_id'])
            current_user_data['id'] = current_user_data['_id'] # Add 'id' field
            # Ensure isAdmin is included, default to False if missing
            current_user_data['isAdmin'] = current_user_data.get('isAdmin', False)

            # Attach user data dictionary to Flask's g for this request context
            g.current_user = current_user_data

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError as e:
                current_app.logger.warning(f"Invalid token received: {e}")
                return jsonify({'message': 'Token is invalid'}), 401
        except ObjectId.InvalidId:
                current_app.logger.error(f"Invalid ObjectId format in token user_id: {data.get('user_id')}")
                return jsonify({'message': 'Invalid user identifier in token'}), 401
        except Exception as e:
            current_app.logger.error(f"Error during token validation: {e}")
            return jsonify({'message': 'Error processing token'}), 500

        # Call the original route function with the authenticated user available in g
        return f(*args, **kwargs)
    return decorated_function

# --- NEW: Decorator specifically for Admins ---
def admin_required(f):
    """
    Decorator to ensure the user is an admin. Must be used AFTER @token_required.
    Relies on g.current_user being set by @token_required.
    """
    @wraps(f)
    @token_required # Requires a valid token first
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'current_user') or not g.current_user or not g.current_user.get('isAdmin'):
            current_app.logger.warning(f"Non-admin user access attempt: User ID {g.current_user.get('id', 'Unknown') if hasattr(g, 'current_user') else 'Unknown'}")
            return jsonify({'message': 'Admin privileges required'}), 403 # Forbidden
        # User has a valid token AND is an admin
        return f(*args, **kwargs)
    return decorated_function