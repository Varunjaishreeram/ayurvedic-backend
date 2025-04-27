# backend/config.py
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print("Warning: .env file not found. Using default or environment settings.")


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
    RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET')
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

    # --- MongoDB Config ---
    MONGO_URI = os.environ.get('MONGO_URI')
    # Get DB name directly from environment variable
    MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME')

    if not MONGO_URI:
        print("CRITICAL WARNING: MONGO_URI environment variable not set!")
    if not MONGO_DB_NAME:
        print("CRITICAL WARNING: MONGO_DB_NAME environment variable not set!")


    # --- Session Cookie Settings ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    MONGO_URI = os.environ.get('TEST_MONGO_URI') or 'mongodb://localhost:27017/' # Separate URI for testing if needed
    MONGO_DB_NAME = os.environ.get('TEST_MONGO_DB_NAME') or 'test_ecommerce_db' # Separate DB name for testing
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # Ensure MONGO_URI and MONGO_DB_NAME are set via environment variables for production
    # Ensure SESSION_COOKIE_SECURE=True and SESSION_COOKIE_SAMESITE are set appropriately


# Dictionary to access config classes by name
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
