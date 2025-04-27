# app/__init__.py
import os
from flask import Flask, g, current_app
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_cors import CORS # Make sure CORS is imported
from config import config_by_name
from pymongo import MongoClient
from bson import ObjectId

bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
login_manager.session_protection = "strong"

# --- MongoDB Helper ---
def get_db():
    """Opens a new database connection if there is none yet for the current app context."""
    if 'db_client' not in g:
        mongo_uri = current_app.config.get('MONGO_URI')
        if not mongo_uri:
            raise ValueError("MONGO_URI not set in the configuration")
        g.db_client = MongoClient(mongo_uri)
        db_name = current_app.config.get('MONGO_DB_NAME') # Get DB name from config
        if not db_name:
             raise ValueError("MONGO_DB_NAME not set in the configuration")
        g.db = g.db_client[db_name]
    return g.db

def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db_client = g.pop('db_client', None)
    if db_client is not None:
        db_client.close()

@login_manager.user_loader
def load_user(user_id):
    """Loads user object from MongoDB based on user_id string."""
    try:
        db = get_db()
        user_data = db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            from .models import User
            user = User(
                id=str(user_data['_id']),
                username=user_data.get('username'),
                email=user_data.get('email'),
                password_hash=user_data.get('password_hash'),
                created_at=user_data.get('created_at')
            )
            return user
    except (ObjectId.InvalidId, Exception) as e:
        current_app.logger.error(f"Error loading user {user_id}: {e}")
        return None
    return None

def create_app(config_name=None):
    """Application Factory Function"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[config_name])

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass # Already exists

    # Initialize extensions
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # --- Configure CORS ---
    # WARNING: Using origins="*" with supports_credentials=True is insecure.
    # It's better to list specific origins like your Vercel URL and localhost.
    # Example: origins=["http://localhost:5173", "https://your-app.vercel.app"]
    CORS(
        app,
        # Allows requests from ANY origin. Use specific origins for better security.
        origins="*",
        # Allows cookies and credentials to be sent with requests
        supports_credentials=True,
        # Specify allowed HTTP methods
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         # Specify allowed headers (adjust as needed)
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"]
    )
    # Note: The 'resources' argument is an alternative way to configure per-route CORS.
    # Using the main CORS() arguments applies settings globally unless overridden.
    # CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True) # This line is equivalent if only /api/* needs CORS

    # Register teardown function to close DB connection
    app.teardown_appcontext(close_db)

    with app.app_context():
        # Check MongoDB connection during app creation
        try:
            client = get_db().client
            client.admin.command('ping')
            current_app.logger.info("MongoDB connection successful.")
        except Exception as e:
            current_app.logger.error(f"MongoDB connection check failed: {e}")
            # Consider raising an exception depending on severity

        # Import and register Blueprints
        from .auth import auth_bp
        from .payments import payments_bp
        from .orders import orders_bp
        from .routes import main_bp

        app.register_blueprint(main_bp, url_prefix='/api')
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        app.register_blueprint(payments_bp, url_prefix='/api/payments')
        app.register_blueprint(orders_bp, url_prefix='/api/orders')

    return app
