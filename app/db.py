from __future__ import annotations

from datetime import datetime
from bson import ObjectId
from flask import current_app


def get_db():
    return current_app.extensions["mongo_db"]


def ensure_indexes():
    db = get_db()
    db.users.create_index("email", unique=True)
    db.products.create_index([("name", 1)])
    db.orders.create_index([("created_at", -1)])


def create_admin_if_missing():
    db = get_db()
    from .models import User

    admin_email = current_app.config["ADMIN_EMAIL"].strip().lower()
    if not db.users.find_one({"email": admin_email}):
        db.users.insert_one(
            {
                "name": "CloudCart Admin",
                "email": admin_email,
                "password_hash": User.hash_password(current_app.config["ADMIN_PASSWORD"]),
                "is_admin": True,
                "created_at": datetime.utcnow(),
            }
        )


def seed_products_if_empty():
    db = get_db()
    if db.products.count_documents({}) > 0:
        return

    products = [
        {
            "name": "Nimbus Wireless Headphones",
            "slug": "nimbus-wireless-headphones",
            "category": "Electronics",
            "price": 89.99,
            "stock": 20,
            "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1200&q=80&auto=format&fit=crop",
            "short_description": "Immersive over-ear headphones with cloud-soft cushions.",
            "description": "Premium wireless headphones with 30-hour battery life, active noise cancellation, and ultra-soft comfort for work and travel.",
            "featured": True,
            "created_at": datetime.utcnow(),
        },
        {
            "name": "Stratus Smartwatch",
            "slug": "stratus-smartwatch",
            "category": "Wearables",
            "price": 149.0,
            "stock": 15,
            "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=1200&q=80&auto=format&fit=crop",
            "short_description": "Elegant smartwatch with health tracking and productivity tools.",
            "description": "Track steps, heart rate, sleep, and notifications with a clean cloud-inspired display and all-day battery.",
            "featured": True,
            "created_at": datetime.utcnow(),
        },
        {
            "name": "Cirrus Office Lamp",
            "slug": "cirrus-office-lamp",
            "category": "Home",
            "price": 59.5,
            "stock": 30,
            "image": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=1200&q=80&auto=format&fit=crop",
            "short_description": "Minimal desk lamp designed for calm productivity.",
            "description": "A sleek LED desk lamp with adjustable brightness and warm/cool modes for a modern workspace.",
            "featured": False,
            "created_at": datetime.utcnow(),
        },
        {
            "name": "Aero Backpack",
            "slug": "aero-backpack",
            "category": "Lifestyle",
            "price": 74.25,
            "stock": 25,
            "image": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=1200&q=80&auto=format&fit=crop",
            "short_description": "Lightweight everyday backpack for work, study, and travel.",
            "description": "Water-resistant backpack with laptop sleeve, hidden pockets, and a clean aesthetic for daily use.",
            "featured": True,
            "created_at": datetime.utcnow(),
        },
        {
            "name": "Skyline Mechanical Keyboard",
            "slug": "skyline-mechanical-keyboard",
            "category": "Electronics",
            "price": 109.0,
            "stock": 18,
            "image": "https://images.unsplash.com/photo-1511467687858-23d96c32e4ae?w=1200&q=80&auto=format&fit=crop",
            "short_description": "Mechanical keyboard with tactile feedback and subtle RGB.",
            "description": "Compact keyboard with premium switches, detachable cable, and productivity-focused layout.",
            "featured": False,
            "created_at": datetime.utcnow(),
        },
        {
            "name": "CloudCup Travel Mug",
            "slug": "cloudcup-travel-mug",
            "category": "Lifestyle",
            "price": 24.99,
            "stock": 40,
            "image": "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?w=1200&q=80&auto=format&fit=crop",
            "short_description": "Double-wall insulated mug for coffee on the move.",
            "description": "Keeps drinks hot or cold for hours with a spill-resistant lid and matte finish.",
            "featured": False,
            "created_at": datetime.utcnow(),
        },
    ]

    db.products.insert_many(products)


def initialize_data():
    ensure_indexes()
    create_admin_if_missing()
    seed_products_if_empty()


def serialize_product(doc: dict) -> dict:
    item = dict(doc)
    item["_id"] = str(item["_id"])
    return item


def get_product_by_id(product_id: str):
    db = get_db()
    doc = db.products.find_one({"_id": ObjectId(product_id)})
    return serialize_product(doc) if doc else None
