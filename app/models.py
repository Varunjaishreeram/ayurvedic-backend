# app/models.py
# Removed: from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# This class is now optional for JWT. You can work directly with dictionaries
# fetched from MongoDB if preferred. Keeping it might help structure.
class User:
    """Represents a user (optional structure for JWT)."""

    def __init__(self, id=None, username=None, email=None, password_hash=None, created_at=None):
        self.id = id # Store as string representation of ObjectId if instantiated
        self.username = username
        self.email = email
        self.password_hash = password_hash # Needed if checking password via this object
        self.created_at = created_at if created_at else datetime.utcnow()

    # Keep password methods if checking password via User object instance
    def check_password(self, password):
        """Checks the provided password against the stored hash using Werkzeug."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    # Removed Flask-Login properties (is_authenticated, get_id, etc.)

    # Keep to_dict if used elsewhere
    def to_dict(self):
        """Returns user data as a dictionary, excluding password."""
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# No changes needed for Order/OrderItem models conceptually
