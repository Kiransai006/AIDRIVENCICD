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
    )

    if test_config:
        app.config.update(test_config)

    # ---------------- DATABASE INIT ----------------
    # Tests usually pass a mongomock database through test_config["MONGO_DB"]
    # Otherwise, you can initialize your real Mongo database here.
    mongo_db = app.config.get("MONGO_DB")
    if mongo_db is None:
        try:
            from pymongo import MongoClient

            mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
            mongo_name = os.environ.get("MONGO_DBNAME", "cloudcart")
            client = MongoClient(mongo_uri)
            mongo_db = client[mongo_name]
        except Exception:
            mongo_db = None

    app.extensions["mongo_db"] = mongo_db

    # ---------------- LOGIN MANAGER ----------------
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        db = app.extensions.get("mongo_db")
        if db is None:
            return None
        try:
            doc = db.users.find_one({"_id": ObjectId(user_id)})
            return User.from_document(doc)
        except Exception:
            return None

    # ---------------- ROUTES ----------------
    register_routes(app)

    return app