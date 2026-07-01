from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from .models import db
from .security.security import init_jwt
from .routers.auth import auth_bp
from .routers.translation import translation_bp
from .routers.payment import payment_bp
from .routers.history import history_bp
from .routers.admin import admin_bp
from .routers.contact import contact_bp
from .routers.public import public_bp

def create_app(config_class='app.config.DevelopmentConfig'):
    app = Flask(__name__)

    # Load config
    if isinstance(config_class, str):
        app.config.from_object(config_class)
    else:
        app.config.update(config_class)

    # Initialize extensions
    CORS(app)
    db.init_app(app)
    init_jwt(app)

    # Create database tables + run safe migrations
    with app.app_context():
        db.create_all()
        from .db_migrations import run_schema_migrations
        run_schema_migrations(db)

    # Register blueprints
    app.register_blueprint(auth_bp,        url_prefix='/api/auth')
    app.register_blueprint(translation_bp, url_prefix='/api/translation')
    app.register_blueprint(payment_bp,     url_prefix='/api/payment')
    app.register_blueprint(history_bp,     url_prefix='/api/history')
    app.register_blueprint(admin_bp,       url_prefix='/api/admin')
    app.register_blueprint(contact_bp,     url_prefix='/api/contact')
    app.register_blueprint(public_bp,      url_prefix='/api/public')

    return app
