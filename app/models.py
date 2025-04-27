# app/models.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin):
    """Custom User class for Flask-Login compatibility with MongoDB."""
    is_active = True
    is_anonymous = False

    def __init__(self, id=None, username=None, email=None, password_hash=None, created_at=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at if created_at else datetime.utcnow()

    @property
    def is_authenticated(self):
        """Returns True if the user is authenticated."""
        return True

    def get_id(self):
        """Required by Flask-Login. Returns the user's ID as a string."""
        return str(self.id)

    def set_password(self, password):
        """Hashes the password using Werkzeug."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks the provided password against the stored hash using Werkzeug."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Returns user data as a dictionary, excluding password."""
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# No Order or OrderItem classes defined here for PyMongo.
# Data structure is handled directly via dictionaries in routes.