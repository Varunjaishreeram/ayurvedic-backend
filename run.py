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
    from app.models import User
    from bson import ObjectId
    # Add more imports here for debugging in the shell if needed
    return {'get_db': get_db, 'User': User, 'ObjectId': ObjectId, 'app': app}

@app.cli.command('seed_db')
def seed_db_command():
    """Example command to seed data into MongoDB."""
    print('Database seeding command started (add actual seeding logic here).')
    # Example: Create an admin user
    # from app import get_db
    # from app.models import User
    # from werkzeug.security import generate_password_hash
    # import datetime
    # db = get_db()
    # if not db.users.find_one({'username': 'admin'}):
    #    hashed_password = generate_password_hash('your_secure_password')
    #    admin_doc = {
    #        'username': 'admin',
    #        'email': 'admin@example.com',
    #        'password_hash': hashed_password,
    #        'created_at': datetime.datetime.utcnow()
    #    }
    #    db.users.insert_one(admin_doc)
    #    print('Admin user created.')
    # else:
    #    print('Admin user already exists.')
    print('Database seeding command finished.')


if __name__ == '__main__':
    # Use app.run() for development only. Use Gunicorn/WSGI for production.
    is_production = os.getenv('FLASK_ENV') == 'production'
    if not is_production:
        # Debug and reloader settings controlled by Flask config (DevelopmentConfig)
        app.run(host='0.0.0.0', port=5000,
                debug=app.config.get('DEBUG', False),
                use_reloader=app.config.get('DEBUG', False))