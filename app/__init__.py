import os
from flask import Flask
from flask_login import LoginManager
from pymongo import MongoClient
from dotenv import load_dotenv

from .models import User

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message_category = "warning"

mongo_client = None
mongo_db = None


def create_app(test_config: dict | None = None):
    load_dotenv()

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key"),
        MONGO_URI=os.getenv("MONGO_URI", "mongodb://localhost:27017/cloudcart"),
        MONGO_DB_NAME=os.getenv("MONGO_DB_NAME", "cloudcart"),
        ADMIN_EMAIL=os.getenv("ADMIN_EMAIL", "admin@cloudcart.local"),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", "Admin@123"),
    )

    if test_config:
        app.config.update(test_config)

    login_manager.init_app(app)

    with app.app_context():
        init_db(app)

    from .routes import register_routes
    register_routes(app)

    return app


def init_db(app: Flask):
    global mongo_client, mongo_db

    if app.config.get("MONGO_MOCK"):
        import mongomock
        mongo_client = mongomock.MongoClient()
    else:
        mongo_client = MongoClient(app.config["MONGO_URI"])

    mongo_db = mongo_client[app.config["MONGO_DB_NAME"]]
    app.extensions["mongo_db"] = mongo_db


@login_manager.user_loader
def load_user(user_id: str):
    if mongo_db is None:
        return None
    doc = mongo_db.users.find_one({"_id": User.parse_object_id(user_id)})
    return User.from_document(doc) if doc else None
