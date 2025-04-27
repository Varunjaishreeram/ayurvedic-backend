# backend/config.py
import os
from dotenv import load_dotenv
import datetime # Keep if using JWT_EXPIRATION_DELTA

basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print("Info: .env file not found. Relying on system environment variables.")


class Config:
    """Base configuration."""
    # CRITICAL: Ensure this is a strong, unique secret key set via environment variables in production!
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-insecure-fallback-key-for-dev-only'
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
    RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET')

    # Frontend URLs for CORS configuration
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173') # Local dev default
    VERCEL_FRONTEND_URL = os.environ.get('VERCEL_FRONTEND_URL', None) # Production Vercel URL

    # --- MongoDB Config ---
    MONGO_URI = os.environ.get('MONGO_URI')
    MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME')

    if not MONGO_URI:
        print("CRITICAL WARNING: MONGO_URI environment variable not set!")
    if not MONGO_DB_NAME:
        print("CRITICAL WARNING: MONGO_DB_NAME environment variable not set!")

    # --- Optional JWT Settings ---
    # Define token expiration time (e.g., 1 hour)
    JWT_EXPIRATION_DELTA = datetime.timedelta(hours=1)
    # Define longer expiration for refresh tokens if implementing that pattern
    # JWT_REFRESH_EXPIRATION_DELTA = datetime.timedelta(days=7)


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # Use a different secret for dev if desired, but can use the base one
    # SECRET_KEY = 'dev-secret-key'


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    # Use a distinct testing database and potentially different keys
    MONGO_URI = os.environ.get('TEST_MONGO_URI') or 'mongodb://localhost:27017/'
    MONGO_DB_NAME = os.environ.get('TEST_MONGO_DB_NAME') or 'test_ecommerce_db'
    WTF_CSRF_ENABLED = False # Usually disable CSRF for testing APIs
    # Use a specific secret key for tests
    SECRET_KEY = 'test-secret-key'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # SECRET_KEY MUST be set via environment variable in production
    if Config.SECRET_KEY == 'a-very-insecure-fallback-key-for-dev-only':
            print("CRITICAL SECURITY WARNING: Default SECRET_KEY is being used in production!")
    # Ensure other sensitive keys (Razorpay, Mongo) are also set via env vars


# Dictionary to access config classes by name
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig # Default to Development if FLASK_ENV is not set
}

# Determine current config
FLASK_ENV = os.environ.get('FLASK_ENV', 'default')
CurrentConfig = config_by_name.get(FLASK_ENV, DevelopmentConfig)
print(f"INFO: Loading Flask config '{FLASK_ENV}' -> {CurrentConfig.__name__}")

    