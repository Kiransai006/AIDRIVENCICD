from app import create_app
from app.db import get_db, initialize_data

app = create_app()
with app.app_context():
    db = get_db()
    db.users.delete_many({"is_admin": {"$ne": True}})
    db.orders.delete_many({})
    db.products.delete_many({})
    initialize_data()
    print("Demo data reset complete.")
