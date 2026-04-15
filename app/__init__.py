from __future__ import annotations

import os

from bson import ObjectId
from flask import Flask
from flask_login import LoginManager

from .db import get_db
from .models import User
from .routes import register_routes

login_manager = LoginManager()
login_manager.login_view = "login"


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        MONGO_URI=os.environ.get("MONGO_URI", "mongodb://localhost:27017/cloudcart"),
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            db = get_db()
            doc = db.users.find_one({"_id": ObjectId(user_id)})
            return User.from_document(doc)
        except Exception:
            return None

    register_routes(app)
    return app