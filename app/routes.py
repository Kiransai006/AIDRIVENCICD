from __future__ import annotations
from ci_monitoring.db_utils import get_ci_summary
from datetime import datetime
from functools import wraps
from bson import ObjectId
from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from .db import get_db, get_product_by_id, initialize_data, serialize_product
from .models import User


def register_routes(app):
    with app.app_context():
        initialize_data()

    @app.context_processor
    def inject_cart_count():
        cart = session.get("cart", {})
        count = sum(item.get("quantity", 0) for item in cart.values())
        return {"cart_count": count}

    def admin_required(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    @app.route("/")
    def home():
        db = get_db()
        featured = [serialize_product(p) for p in db.products.find({"featured": True}).limit(4)]
        latest = [serialize_product(p) for p in db.products.find().sort("created_at", -1).limit(6)]
        return render_template("home.html", featured=featured, latest=latest)

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "cloudcart"})

    @app.route("/products")
    def products():
        db = get_db()
        query = {}
        category = request.args.get("category", "").strip()
        search = request.args.get("search", "").strip()

        if category:
            query["category"] = category
        if search:
            query["name"] = {"$regex": search, "$options": "i"}

        items = [serialize_product(p) for p in db.products.find(query).sort("created_at", -1)]
        categories = sorted(db.products.distinct("category"))
        return render_template(
            "products.html",
            products=items,
            categories=categories,
            selected_category=category,
            search=search,
        )

    @app.route("/products/<slug>")
    def product_detail(slug: str):
        db = get_db()
        doc = db.products.find_one({"slug": slug})
        if not doc:
            abort(404)
        product = serialize_product(doc)
        return render_template("product_detail.html", product=product)

    @app.post("/cart/add/<product_id>")
    def add_to_cart(product_id: str):
        product = get_product_by_id(product_id)
        if not product:
            abort(404)

        quantity = max(int(request.form.get("quantity", 1)), 1)
        cart = session.get("cart", {})
        item = cart.get(product_id, {"name": product["name"], "price": product["price"], "quantity": 0})
        item["quantity"] += quantity
        cart[product_id] = item
        session["cart"] = cart
        session.modified = True

        flash(f"Added {product['name']} to cart.", "success")
        return redirect(request.referrer or url_for("products"))

    @app.route("/cart")
    def view_cart():
        cart = session.get("cart", {})
        items = []
        subtotal = 0.0
        for product_id, item in cart.items():
            line_total = item["price"] * item["quantity"]
            subtotal += line_total
            items.append({"product_id": product_id, **item, "line_total": line_total})
        return render_template("cart.html", items=items, subtotal=subtotal)

    @app.post("/cart/update/<product_id>")
    def update_cart(product_id: str):
        cart = session.get("cart", {})
        if product_id not in cart:
            flash("Item not found in cart.", "warning")
            return redirect(url_for("view_cart"))

        quantity = max(int(request.form.get("quantity", 1)), 0)
        if quantity == 0:
            cart.pop(product_id, None)
        else:
            cart[product_id]["quantity"] = quantity

        session["cart"] = cart
        session.modified = True
        flash("Cart updated.", "success")
        return redirect(url_for("view_cart"))

    @app.post("/cart/remove/<product_id>")
    def remove_from_cart(product_id: str):
        cart = session.get("cart", {})
        cart.pop(product_id, None)
        session["cart"] = cart
        session.modified = True
        flash("Item removed from cart.", "info")
        return redirect(url_for("view_cart"))

    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        cart = session.get("cart", {})
        if not cart:
            flash("Your cart is empty.", "warning")
            return redirect(url_for("products"))

        items = []
        total = 0.0
        for product_id, item in cart.items():
            items.append(
                {
                    "product_id": product_id,
                    "name": item["name"],
                    "price": item["price"],
                    "quantity": item["quantity"],
                }
            )
            total += item["price"] * item["quantity"]

        if request.method == "POST":
            db = get_db()
            order = {
                "user_id": current_user.id,
                "user_email": current_user.email,
                "customer_name": request.form["customer_name"].strip(),
                "address": request.form["address"].strip(),
                "items": items,
                "total": total,
                "status": "Placed",
                "created_at": datetime.utcnow(),
            }
            db.orders.insert_one(order)
            session.pop("cart", None)
            flash("Order placed successfully.", "success")
            return redirect(url_for("orders"))

        return render_template("checkout.html", items=items, total=total)

    @app.route("/orders")
    @login_required
    def orders():
        db = get_db()
        query = {} if current_user.is_admin else {"user_id": current_user.id}
        orders_list = list(db.orders.find(query).sort("created_at", -1))
        for order in orders_list:
            order["_id"] = str(order["_id"])
        return render_template("orders.html", orders=orders_list)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            db = get_db()
            doc = db.users.find_one({"email": email})
            user = User.from_document(doc)
            if user and user.check_password(password):
                login_user(user)
                flash("Welcome back.", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "danger")

        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            name = request.form["name"].strip()
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]
            db = get_db()

            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return redirect(url_for("register"))

            if db.users.find_one({"email": email}):
                flash("An account with that email already exists.", "warning")
                return redirect(url_for("register"))

            user_doc = {
                "name": name,
                "email": email,
                "password_hash": User.hash_password(password),
                "is_admin": False,
                "created_at": datetime.utcnow(),
            }
            inserted = db.users.insert_one(user_doc)
            user = User.from_document({"_id": inserted.inserted_id, **user_doc})
            login_user(user)
            flash("Account created successfully.", "success")
            return redirect(url_for("dashboard"))

        return render_template("register.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("home"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        db = get_db()
        my_orders = db.orders.count_documents({"user_id": current_user.id}) if not current_user.is_admin else db.orders.count_documents({})
        product_count = db.products.count_documents({})
        user_count = db.users.count_documents({})
        latest_orders = list(db.orders.find({} if current_user.is_admin else {"user_id": current_user.id}).sort("created_at", -1).limit(5))
        for order in latest_orders:
            order["_id"] = str(order["_id"])
        return render_template(
            "dashboard.html",
            my_orders=my_orders,
            product_count=product_count,
            user_count=user_count,
            latest_orders=latest_orders,
        )

    @app.route("/ci-dashboard")
    @login_required
    def ci_dashboard():
        data = get_ci_summary()
        return render_template("ci_dashboard.html", data=data)

    @app.route("/admin")
    @login_required
    @admin_required
    def admin_panel():
        db = get_db()
        products = [serialize_product(p) for p in db.products.find().sort("created_at", -1)]
        return render_template("admin.html", products=products)

    @app.route("/admin/products/new", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_new_product():
        if request.method == "POST":
            db = get_db()
            slug = request.form["slug"].strip().lower()
            if db.products.find_one({"slug": slug}):
                flash("Slug already exists.", "warning")
                return redirect(url_for("admin_new_product"))
            db.products.insert_one(
                {
                    "name": request.form["name"].strip(),
                    "slug": slug,
                    "category": request.form["category"].strip(),
                    "price": float(request.form["price"]),
                    "stock": int(request.form["stock"]),
                    "image": request.form["image"].strip(),
                    "short_description": request.form["short_description"].strip(),
                    "description": request.form["description"].strip(),
                    "featured": True if request.form.get("featured") == "on" else False,
                    "created_at": datetime.utcnow(),
                }
            )
            flash("Product added successfully.", "success")
            return redirect(url_for("admin_panel"))
        return render_template("admin_product_form.html", product=None)

    @app.route("/admin/products/<product_id>/edit", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_edit_product(product_id: str):
        db = get_db()
        doc = db.products.find_one({"_id": ObjectId(product_id)})
        if not doc:
            abort(404)
        product = serialize_product(doc)

        if request.method == "POST":
            db.products.update_one(
                {"_id": ObjectId(product_id)},
                {
                    "$set": {
                        "name": request.form["name"].strip(),
                        "slug": request.form["slug"].strip().lower(),
                        "category": request.form["category"].strip(),
                        "price": float(request.form["price"]),
                        "stock": int(request.form["stock"]),
                        "image": request.form["image"].strip(),
                        "short_description": request.form["short_description"].strip(),
                        "description": request.form["description"].strip(),
                        "featured": True if request.form.get("featured") == "on" else False,
                    }
                },
            )
            flash("Product updated successfully.", "success")
            return redirect(url_for("admin_panel"))

        return render_template("admin_product_form.html", product=product)

    @app.post("/admin/products/<product_id>/delete")
    @login_required
    @admin_required
    def admin_delete_product(product_id: str):
        db = get_db()
        db.products.delete_one({"_id": ObjectId(product_id)})
        flash("Product deleted.", "info")
        return redirect(url_for("admin_panel"))
    
import subprocess

@app.route("/refresh-ci", methods=["POST"])
@login_required
def refresh_ci():
    try:
        subprocess.run(["python", "ci_monitoring/fetch_github_runs.py"], check=True)
        subprocess.run(["python", "ci_monitoring/train_ci_model.py"], check=True)
        subprocess.run(["python", "ci_monitoring/predict_ci_failure.py"], check=True)

        flash("CI data refreshed successfully!", "success")
    except Exception as e:
        flash(f"Error refreshing CI: {str(e)}", "danger")

    return redirect(url_for("ci_dashboard"))