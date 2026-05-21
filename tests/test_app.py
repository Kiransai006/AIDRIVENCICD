from app import create_app
from app.db import get_db


def make_app():
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "MONGO_MOCK": True,
            "MONGO_DB_NAME": "cloudcart_test",
            "ADMIN_EMAIL": "admin@test.local",
            "ADMIN_PASSWORD": "Admin@123",
        }
    )


def register_and_login(client):
    client.post(
        "/register",
        data={
            "name": "Test User",
            "email": "user@test.local",
            "password": "Password@123",
            "confirm_password": "Password@123",
        },
        follow_redirects=True,
    )


def test_home_page():
    app = make_app()
    with app.test_client() as client:
        response = client.get("/")
        assert response.status_code == 200
        assert b"CloudCart" in response.data


def test_product_listing():
    app = make_app()
    with app.test_client() as client:
        response = client.get("/products")
        assert response.status_code == 200
        assert b"Nimbus Wireless Headphones" in response.data


def test_register_login_checkout_flow():
    app = make_app()
    with app.test_client() as client:
        register_and_login(client)

        with app.app_context():
            db = get_db()
            product = db.products.find_one({})
            product_id = str(product["_id"])

        add_response = client.post(
            f"/cart/add/{product_id}",
            data={"quantity": 1},
            follow_redirects=True,
        )
        assert add_response.status_code == 200

        checkout_response = client.post(
            "/checkout",
            data={"customer_name": "Test User", "address": "123 Demo Street"},
            follow_redirects=True,
        )
        assert checkout_response.status_code == 200
        assert b"Order placed successfully" in checkout_response.data


def test_admin_panel_requires_admin():
    app = make_app()
    with app.test_client() as client:
        register_and_login(client)
        response = client.get("/admin")
        assert response.status_code == 403


# ──────────────────────────────────────────────────────────────────
# INTENTIONAL FAILURE — triggers auto-remediation pipeline
# ──────────────────────────────────────────────────────────────────

def test_cart_price_calculation():
    """
    INJECTED FAILURE: wrong expected total.
    Real: 3 * 49.99 = 149.97  →  we assert 999  →  AssertionError
    This pushes test_error_count up → risk score crosses 0.65
    → Decision Engine triggers RERUN_TESTS action
    """
    price = 49.99
    quantity = 3
    total = round(price * quantity, 2)
    assert total == 999, f"ERROR: Cart total wrong. Expected 999, got {total}"


def test_discount_logic():
    """
    INJECTED FAILURE: discount calculation is wrong on purpose.
    Simulates a developer breaking promo code logic.
    Produces a second ERROR in logs → confirms High risk signal.
    """
    original_price = 100.00
    discount_percent = 20
    discounted = original_price - (original_price * discount_percent / 100)
    assert discounted == 999, f"ERROR: Discount wrong. Expected 999, got {discounted}"