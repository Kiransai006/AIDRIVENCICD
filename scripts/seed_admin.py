from app import create_app
from app.db import initialize_data

app = create_app()
with app.app_context():
    initialize_data()
    print("Admin user and starter products ensured.")
    print(f"Admin email: {app.config['ADMIN_EMAIL']}")
