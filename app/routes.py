# from __future__ import annotations

# from datetime import datetime
# from functools import wraps
# import subprocess
# import sys

# from flask import (
#     abort,
#     flash,
#     jsonify,
#     redirect,
#     render_template,
#     request,
#     session,
#     url_for,
# )
# from flask_login import current_user, login_required, login_user, logout_user

# from ci_monitoring.db_utils import get_ci_summary
# from .db import get_db, get_product_by_id, initialize_data, serialize_product
# from .models import User


# def register_routes(app):
#     with app.app_context():
#         initialize_data()

#     # ---------------- CART COUNT ----------------
#     @app.context_processor
#     def inject_cart_count():
#         cart = session.get("cart", {})
#         count = sum(item.get("quantity", 0) for item in cart.values())
#         return {"cart_count": count}

#     # ---------------- ADMIN CHECK ----------------
#     def admin_required(view_func):
#         @wraps(view_func)
#         def wrapped(*args, **kwargs):
#             if not current_user.is_authenticated:
#                 abort(403)
#             if not getattr(current_user, "is_admin", False):
#                 abort(403)
#             return view_func(*args, **kwargs)
#         return wrapped

#     # ---------------- HOME ----------------
#     @app.route("/")
#     def home():
#         db = get_db()
#         featured = [serialize_product(p) for p in db.products.find({"featured": True}).limit(4)]
#         latest = [serialize_product(p) for p in db.products.find().sort("created_at", -1).limit(6)]
#         return render_template("home.html", featured=featured, latest=latest)

#     @app.route("/api/health")
#     def health():
#         return jsonify({"status": "ok"})

#     # ---------------- PRODUCTS ----------------
#     @app.route("/products")
#     def products():
#         db = get_db()
#         query = {}

#         category = request.args.get("category", "").strip()
#         search = request.args.get("search", "").strip()

#         if category:
#             query["category"] = category
#         if search:
#             query["name"] = {"$regex": search, "$options": "i"}

#         items = [serialize_product(p) for p in db.products.find(query).sort("created_at", -1)]
#         categories = sorted(db.products.distinct("category"))

#         return render_template(
#             "products.html",
#             products=items,
#             categories=categories,
#             selected_category=category,
#             search=search,
#         )

#     @app.route("/products/<slug>")
#     def product_detail(slug):
#         db = get_db()
#         doc = db.products.find_one({"slug": slug})
#         if not doc:
#             abort(404)
#         return render_template("product_detail.html", product=serialize_product(doc))

#     # ---------------- CART ----------------
#     @app.post("/cart/add/<product_id>")
#     def add_to_cart(product_id):
#         product = get_product_by_id(product_id)
#         if not product:
#             abort(404)

#         quantity = max(int(request.form.get("quantity", 1)), 1)

#         cart = session.get("cart", {})
#         item = cart.get(
#             product_id,
#             {"name": product["name"], "price": product["price"], "quantity": 0},
#         )
#         item["quantity"] += quantity

#         cart[product_id] = item
#         session["cart"] = cart
#         session.modified = True

#         flash(f"Added {product['name']} to cart.", "success")
#         return redirect(request.referrer or url_for("products"))

#     @app.route("/cart")
#     def view_cart():
#         cart = session.get("cart", {})
#         items = []
#         subtotal = 0

#         for pid, item in cart.items():
#             total = item["price"] * item["quantity"]
#             subtotal += total
#             items.append({"product_id": pid, **item, "line_total": total})

#         return render_template("cart.html", items=items, subtotal=subtotal)

#     # ---------------- CHECKOUT ----------------
#     @app.route("/checkout", methods=["GET", "POST"])
#     @login_required
#     def checkout():
#         cart = session.get("cart", {})
#         if not cart:
#             flash("Cart is empty", "warning")
#             return redirect(url_for("products"))

#         items = []
#         total = 0

#         for pid, item in cart.items():
#             items.append(
#                 {
#                     "product_id": pid,
#                     "name": item["name"],
#                     "price": item["price"],
#                     "quantity": item["quantity"],
#                 }
#             )
#             total += item["price"] * item["quantity"]

#         if request.method == "POST":
#             customer_name = request.form.get("customer_name", "").strip()
#             address = request.form.get("address", "").strip()

#             if not customer_name or not address:
#                 flash("Customer name and address are required", "danger")
#                 return redirect(url_for("checkout"))

#             db = get_db()
#             db.orders.insert_one(
#                 {
#                     "user_id": current_user.get_id(),
#                     "customer_name": customer_name,
#                     "address": address,
#                     "items": items,
#                     "total": total,
#                     "status": "Placed",
#                     "created_at": datetime.utcnow(),
#                 }
#             )

#             session.pop("cart", None)
#             flash("Order placed successfully", "success")
#             return redirect(url_for("orders"))

#         return render_template("checkout.html", items=items, total=total)

#     @app.route("/orders")
#     @login_required
#     def orders():
#         db = get_db()
#         orders = list(db.orders.find().sort("created_at", -1))

#         for o in orders:
#             o["_id"] = str(o["_id"])
#             o["items"] = o.get("items", [])

#         return render_template("orders.html", orders=orders)

#     # ---------------- AUTH ----------------
#     @app.route("/login", methods=["GET", "POST"])
#     def login():
#         if request.method == "POST":
#             db = get_db()
#             email = request.form["email"].strip().lower()
#             password = request.form["password"]

#             user_doc = db.users.find_one({"email": email})
#             user = User.from_document(user_doc)

#             if user and user.check_password(password):
#                 login_user(user)
#                 flash("Logged in successfully", "success")
#                 return redirect(url_for("dashboard"))

#             flash("Invalid credentials", "danger")

#         return render_template("login.html")

#     @app.route("/register", methods=["GET", "POST"])
#     def register():
#         if request.method == "POST":
#             db = get_db()

#             name = request.form["name"].strip()
#             email = request.form["email"].strip().lower()
#             password = request.form["password"]
#             confirm_password = request.form.get("confirm_password", "")

#             if password != confirm_password:
#                 flash("Passwords do not match", "danger")
#                 return redirect(url_for("register"))

#             existing_user = db.users.find_one({"email": email})
#             if existing_user:
#                 flash("Email already registered", "warning")
#                 return redirect(url_for("register"))

#             user_doc = {
#                 "name": name,
#                 "email": email,
#                 "password_hash": User.hash_password(password),
#                 "is_admin": False,
#                 "created_at": datetime.utcnow(),
#             }

#             result = db.users.insert_one(user_doc)
#             user_doc["_id"] = result.inserted_id

#             user = User.from_document(user_doc)
#             login_user(user)

#             flash("Registered successfully", "success")
#             return redirect(url_for("dashboard"))

#         return render_template("register.html")

#     @app.route("/logout")
#     def logout():
#         logout_user()
#         return redirect(url_for("home"))

#     # ---------------- DASHBOARD ----------------
#     @app.route("/dashboard")
#     @login_required
#     def dashboard():
#         db = get_db()
#         return render_template(
#             "dashboard.html",
#             my_orders=db.orders.count_documents({"user_id": current_user.get_id()}),
#             product_count=db.products.count_documents({}),
#             user_count=db.users.count_documents({}),
#         )

#     # ---------------- ADMIN ----------------
#     @app.route("/admin")
#     @login_required
#     @admin_required
#     def admin_panel():
#         db = get_db()
#         products = [serialize_product(p) for p in db.products.find()]
#         return render_template("admin.html", products=products)

#     # ---------------- CI DASHBOARD ----------------
#     @app.route("/ci-dashboard")
#     @login_required
#     def ci_dashboard():
#         data = get_ci_summary()
#         return render_template("ci_dashboard.html", data=data)

#     # ---------------- REFRESH CI ----------------
#     @app.route("/refresh-ci", methods=["POST"])
#     @login_required
#     def refresh_ci():
#         try:
#             subprocess.run(
#                 [sys.executable, "ci_monitoring/fetch_github_runs.py"],
#                 check=True,
#                 capture_output=True,
#                 text=True,
#             )
#             subprocess.run(
#                 [sys.executable, "ci_monitoring/train_ci_model.py"],
#                 check=True,
#                 capture_output=True,
#                 text=True,
#             )
#             subprocess.run(
#                 [sys.executable, "ci_monitoring/predict_ci_failure.py"],
#                 check=True,
#                 capture_output=True,
#                 text=True,
#             )

#             flash("CI data refreshed successfully!", "success")

#         except subprocess.CalledProcessError as e:
#             error_msg = e.stderr or e.stdout or str(e)
#             flash(f"Error refreshing CI: {error_msg}", "danger")

#         except Exception as e:
#             flash(f"Error refreshing CI: {str(e)}", "danger")

#         return redirect(url_for("ci_dashboard"))
from __future__ import annotations

from datetime import datetime
from functools import wraps
import subprocess
import sys

from flask import (
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from ci_monitoring.db_utils import get_ci_summary
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
            if not current_user.is_authenticated:
                abort(403)
            if not getattr(current_user, "is_admin", False):
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
        return jsonify({"status": "ok"})

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
    def product_detail(slug):
        db = get_db()
        doc = db.products.find_one({"slug": slug})
        if not doc:
            abort(404)
        return render_template("product_detail.html", product=serialize_product(doc))

    @app.post("/cart/add/<product_id>")
    def add_to_cart(product_id):
        product = get_product_by_id(product_id)
        if not product:
            abort(404)

        try:
            quantity = max(int(request.form.get("quantity", 1)), 1)
        except ValueError:
            quantity = 1

        cart = session.get("cart", {})
        item = cart.get(
            product_id,
            {"name": product["name"], "price": product["price"], "quantity": 0},
        )
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
        subtotal = 0

        for pid, item in cart.items():
            total = item["price"] * item["quantity"]
            subtotal += total
            items.append({"product_id": pid, **item, "line_total": total})

        return render_template("cart.html", items=items, subtotal=subtotal)

    @app.post("/cart/update/<product_id>")
    def update_cart(product_id):
        cart = session.get("cart", {})

        if product_id not in cart:
            flash("Item not found in cart.", "warning")
            return redirect(url_for("view_cart"))

        try:
            quantity = int(request.form.get("quantity", 1))
        except ValueError:
            quantity = 1

        if quantity <= 0:
            cart.pop(product_id, None)
            flash("Item removed from cart.", "info")
        else:
            cart[product_id]["quantity"] = quantity
            flash("Cart updated successfully.", "success")

        session["cart"] = cart
        session.modified = True

        return redirect(url_for("view_cart"))

    @app.post("/cart/remove/<product_id>")
    def remove_from_cart(product_id):
        cart = session.get("cart", {})

        if product_id in cart:
            cart.pop(product_id, None)
            flash("Item removed from cart.", "info")
        else:
            flash("Item not found in cart.", "warning")

        session["cart"] = cart
        session.modified = True

        return redirect(url_for("view_cart"))

    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        cart = session.get("cart", {})
        if not cart:
            flash("Cart is empty", "warning")
            return redirect(url_for("products"))

        items = []
        total = 0

        for pid, item in cart.items():
            items.append(
                {
                    "product_id": pid,
                    "name": item["name"],
                    "price": item["price"],
                    "quantity": item["quantity"],
                }
            )
            total += item["price"] * item["quantity"]

        if request.method == "POST":
            customer_name = request.form.get("customer_name", "").strip()
            address = request.form.get("address", "").strip()

            if not customer_name or not address:
                flash("Customer name and address are required", "danger")
                return redirect(url_for("checkout"))

            db = get_db()
            db.orders.insert_one(
                {
                    "user_id": current_user.get_id(),
                    "customer_name": customer_name,
                    "address": address,
                    "items": items,
                    "total": total,
                    "status": "Placed",
                    "created_at": datetime.utcnow(),
                }
            )

            session.pop("cart", None)
            flash("Order placed successfully", "success")
            return redirect(url_for("orders"))

        return render_template("checkout.html", items=items, total=total)

    @app.route("/orders")
    @login_required
    def orders():
        db = get_db()
        orders = list(db.orders.find().sort("created_at", -1))

        for order in orders:
            order["_id"] = str(order["_id"])
            order["items"] = order.get("items", [])

        return render_template("orders.html", orders=orders)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            db = get_db()
            email = request.form["email"].strip().lower()
            password = request.form["password"]

            user_doc = db.users.find_one({"email": email})
            user = User.from_document(user_doc)

            if user and user.check_password(password):
                login_user(user)
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard"))

            flash("Invalid credentials", "danger")

        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            db = get_db()

            name = request.form["name"].strip()
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            confirm_password = request.form.get("confirm_password", "")

            if password != confirm_password:
                flash("Passwords do not match", "danger")
                return redirect(url_for("register"))

            existing_user = db.users.find_one({"email": email})
            if existing_user:
                flash("Email already registered", "warning")
                return redirect(url_for("register"))

            user_doc = {
                "name": name,
                "email": email,
                "password_hash": User.hash_password(password),
                "is_admin": False,
                "created_at": datetime.utcnow(),
            }

            result = db.users.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id

            user = User.from_document(user_doc)
            login_user(user)

            flash("Registered successfully", "success")
            return redirect(url_for("dashboard"))

        return render_template("register.html")

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for("home"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        db = get_db()
        return render_template(
            "dashboard.html",
            my_orders=db.orders.count_documents({"user_id": current_user.get_id()}),
            product_count=db.products.count_documents({}),
            user_count=db.users.count_documents({}),
        )

    @app.route("/admin")
    @login_required
    @admin_required
    def admin_panel():
        db = get_db()
        products = [serialize_product(p) for p in db.products.find()]
        return render_template("admin.html", products=products)

    @app.route("/ci-dashboard")
    @login_required
    def ci_dashboard():
        data = get_ci_summary()
        return render_template("ci_dashboard.html", data=data)

    @app.route("/refresh-ci", methods=["POST"])
    @login_required
    def refresh_ci():
        try:
            subprocess.run(
                [sys.executable, "ci_monitoring/fetch_github_runs.py"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "ci_monitoring/train_ci_model.py"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "ci_monitoring/predict_ci_failure.py"],
                check=True,
                capture_output=True,
                text=True,
            )

            flash("CI data refreshed successfully!", "success")

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or e.stdout or str(e)
            flash(f"Error refreshing CI: {error_msg}", "danger")

        except Exception as e:
            flash(f"Error refreshing CI: {str(e)}", "danger")

        return redirect(url_for("ci_dashboard"))
