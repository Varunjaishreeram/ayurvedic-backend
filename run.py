# run.py
import os
from app import create_app

config_name = os.getenv('FLASK_ENV') or 'default'
app = create_app(config_name)

# --- Flask CLI Commands ---
@app.shell_context_processor
def make_shell_context():
    """Makes variables available in the 'flask shell' context."""
    from app import get_db
    from app.models import User # Keep User if still using the class structure
    from bson import ObjectId
    # Add other models or helpers needed for debugging
    return {'get_db': get_db, 'User': User, 'ObjectId': ObjectId, 'app': app}

@app.cli.command('seed_db')
def seed_db_command():
    """Example command to seed data into MongoDB."""
    print('Database seeding command started (adapt logic for MongoDB).')
    # Example: Create an admin user
    # from app import get_db
    # from werkzeug.security import generate_password_hash
    # import datetime
    # db = get_db()
    # if not db.users.find_one({'username': 'admin'}):
    #    hashed_password = generate_password_hash('your_secure_password')
    #    admin_doc = { # ... admin user data ... }
    #    db.users.insert_one(admin_doc)
    #    print('Admin user created.')
    # else:
    #    print('Admin user already exists.')
    print('Database seeding command finished.')


if __name__ == '__main__':
    # Use app.run() for development only. Use Gunicorn/WSGI for production.
    is_production = os.getenv('FLASK_ENV') == 'production'
    if not is_production:
        app.run(host='0.0.0.0', port=5000,
                debug=app.config.get('DEBUG', False),
                use_reloader=app.config.get('DEBUG', False))

