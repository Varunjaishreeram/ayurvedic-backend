# app/__init__.py
import os
from flask import Flask, g, current_app
from flask_bcrypt import Bcrypt
# Removed: from flask_login import LoginManager
from flask_cors import CORS
from config import config_by_name, CurrentConfig # Import CurrentConfig too
from pymongo import MongoClient
from bson import ObjectId

bcrypt = Bcrypt()
# Removed: login_manager = LoginManager()

# --- MongoDB Helper ---
def get_db():
    """Opens a new database connection if there is none yet for the current app context."""
    if 'db_client' not in g:
        mongo_uri = current_app.config.get('MONGO_URI')
        if not mongo_uri:
            raise ValueError("MONGO_URI not set in the configuration")
        g.db_client = MongoClient(mongo_uri)
        db_name = current_app.config.get('MONGO_DB_NAME')
        if not db_name:
                raise ValueError("MONGO_DB_NAME not set in the configuration")
        g.db = g.db_client[db_name]
    return g.db

def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db_client = g.pop('db_client', None)
    if db_client is not None:
        db_client.close()

# Removed: @login_manager.user_loader

def create_app(config_name=None):
    """Application Factory Function"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    app = Flask(__name__, instance_relative_config=True)
    # Load configuration object directly
    app.config.from_object(config_by_name[config_name])

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass # Already exists

    # Initialize extensions
    bcrypt.init_app(app)
    # Removed: login_manager.init_app(app)

    # --- Configure CORS ---
    local_frontend = app.config.get('FRONTEND_URL')
    vercel_frontend = app.config.get('VERCEL_FRONTEND_URL')

    allowed_origins = []
    if local_frontend:
        allowed_origins.append(local_frontend)
    if vercel_frontend:
        allowed_origins.append(vercel_frontend)
        # Optional: Add preview URL pattern if needed
        # allowed_origins.append(r"https://.*-your-vercel-team\.vercel\.app")

    if not allowed_origins:
        print("WARNING: No specific CORS origins set. Allowing all - review security.")
        allowed_origins = "*" # Fallback, less secure

    print(f"Configuring CORS for origins: {allowed_origins}")

    CORS(
        app,
        origins=allowed_origins,
        # Set supports_credentials based on whether you need cookies for *other* reasons (like CSRF if added later)
        # For pure JWT in headers, it can often be False, but True is safer if unsure.
        supports_credentials=True,
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        # Ensure 'Authorization' header is allowed for JWT
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"]
    )

    # Register teardown function to close DB connection
    app.teardown_appcontext(close_db)

    with app.app_context():
        # Check MongoDB connection
        try:
            client = get_db().client
            client.admin.command('ping')
            current_app.logger.info("MongoDB connection successful.")
        except Exception as e:
            current_app.logger.error(f"MongoDB connection check failed: {e}")

        # Import and register Blueprints
        from .auth import auth_bp
        from .payments import payments_bp
        from .orders import orders_bp
        from .routes import main_bp # Ensure this doesn't have conflicting name

        app.register_blueprint(main_bp, url_prefix='/api')
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        app.register_blueprint(payments_bp, url_prefix='/api/payments')
        app.register_blueprint(orders_bp, url_prefix='/api/orders')

    return app
