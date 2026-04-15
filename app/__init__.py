from __future__ import annotations

import os

from bson import ObjectId
from flask import Flask
from flask_login import LoginManager

from .models import User
from .routes import register_routes

login_manager = LoginManager()
login_manager.login_view = "login"


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        TESTING=False,
        MONGO_MOCK=False,
        MONGO_DB_NAME=os.environ.get("MONGO_DB_NAME", "cloudcart"),
        ADMIN_EMAIL=os.environ.get("ADMIN_EMAIL", "admin@cloudcart.local"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "Admin@123"),
    )

    if test_config:
        app.config.update(test_config)

    # ---------------- DATABASE INIT ----------------
    if app.config.get("MONGO_MOCK"):
        import mongomock

        client = mongomock.MongoClient()
        db = client[app.config["MONGO_DB_NAME"]]
    else:
        from pymongo import MongoClient

        mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        client = MongoClient(mongo_uri)
        db = client[app.config["MONGO_DB_NAME"]]

    app.extensions["mongo_db"] = db

    # ---------------- LOGIN MANAGER ----------------
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            doc = db.users.find_one({"_id": ObjectId(user_id)})
            return User.from_document(doc)
        except Exception:
            return None

    register_routes(app)
    return app