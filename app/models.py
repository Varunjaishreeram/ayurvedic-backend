# backend/app/models.py
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# This class represents the intended structure of a user document,
# including the isAdmin field.
class User:
    """Represents a user, including admin status."""

    def __init__(self, id=None, username=None, email=None, password_hash=None, created_at=None, isAdmin=False): # Added isAdmin parameter
        self.id = id # Store as string representation of ObjectId if instantiated
        self.username = username
        self.email = email
        self.password_hash = password_hash # Needed if checking password via this object
        self.created_at = created_at if created_at else datetime.utcnow()
        self.isAdmin = isAdmin  # <-- ADDED: Store isAdmin status

    def check_password(self, password):
        """Checks the provided password against the stored hash using Werkzeug."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    # Removed Flask-Login properties (is_authenticated, get_id, etc.)

    def to_dict(self):
        """Returns user data as a dictionary, excluding password, including isAdmin."""
        return {
            'id': str(self.id) if self.id else None, # Handle potential None id
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'isAdmin': self.isAdmin # <-- ADDED: Include isAdmin in dictionary representation
        }

# No changes needed for Order/OrderItem conceptual models