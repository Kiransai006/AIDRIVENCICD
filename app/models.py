from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from bson import ObjectId
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


@dataclass
class User(UserMixin):
    id: str
    name: str
    email: str
    password_hash: str
    is_admin: bool = False
    created_at: datetime | None = None

    @staticmethod
    def parse_object_id(value: str | ObjectId) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        return ObjectId(value)

    @classmethod
    def from_document(cls, doc: dict | None) -> "User | None":
        if not doc:
            return None
        return cls(
            id=str(doc["_id"]),
            name=doc["name"],
            email=doc["email"],
            password_hash=doc["password_hash"],
            is_admin=doc.get("is_admin", False),
            created_at=doc.get("created_at"),
        )

    def to_document(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "password_hash": self.password_hash,
            "is_admin": self.is_admin,
            "created_at": self.created_at or datetime.utcnow(),
        }

    @staticmethod
    def hash_password(password: str) -> str:
        return generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
