# app/__init__.py
import os
from flask import Flask, g, current_app
from flask_bcrypt import Bcrypt
# Removed: from flask_login import LoginManager
from flask_cors import CORS # Make sure CORS is imported
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

    # --- Configure CORS to Allow All Origins ---
    # WARNING: Using origins="*" with supports_credentials=True is insecure
    # and potentially problematic. List specific origins for production.
    print("WARNING: Configuring CORS to allow all origins ('*'). Review security implications.")
    CORS(
        app,
        origins="*", # Allow requests from ANY origin
        supports_credentials=True, # Allow cookies/auth headers to be sent
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Allowed methods
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
