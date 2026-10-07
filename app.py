import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "court_district.db"))
DEMO_MODE = os.environ.get("DEMO_MODE", "0").lower() in {"1", "true", "yes"}
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

SAMPLE_SHOES = [
    (
        "Air Court Legacy",
        "Nike",
        "Indoor",
        129.00,
        "7, 8, 9, 10, 11, 12",
        "A responsive, low-profile court shoe for quick changes of direction.",
        "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85",
        8,
    ),
    (
        "Dame 9",
        "Adidas",
        "Indoor",
        119.00,
        "7, 8, 9, 10, 11, 12, 13",
        "Lightweight support and a grippy outsole made for creating space.",
        "https://images.unsplash.com/photo-1552346154-21d32810aba3?auto=format&fit=crop&w=900&q=85",
        5,
    ),
    (
        "All-Court Rise",
        "Jordan",
        "Outdoor",
        104.00,
        "6, 7, 8, 9, 10, 11",
        "Durable traction and cushioned comfort from warm-up to final point.",
        "https://images.unsplash.com/photo-1495555961986-6d4c1ecb7be3?auto=format&fit=crop&w=900&q=85",
        3,
    ),
]


def connect_db():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with connect_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'customer' CHECK(role IN ('admin', 'customer')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS shoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                brand TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                sizes TEXT NOT NULL,
                description TEXT NOT NULL,
                image_url TEXT NOT NULL,
                stock INTEGER NOT NULL CHECK(stock >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                shoe_id INTEGER NOT NULL REFERENCES shoes(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, shoe_id)
            );
            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                shoe_id INTEGER NOT NULL REFERENCES shoes(id) ON DELETE CASCADE,
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, shoe_id, size)
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                order_number TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                delivery_method TEXT NOT NULL,
                address TEXT NOT NULL DEFAULT '',
                total REAL NOT NULL CHECK(total >= 0),
                status TEXT NOT NULL DEFAULT 'Placed',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                shoe_id INTEGER REFERENCES shoes(id) ON DELETE SET NULL,
                shoe_name TEXT NOT NULL,
                brand TEXT NOT NULL,
                unit_price REAL NOT NULL,
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0)
            );
            """
        )
        if db.execute("SELECT COUNT(*) FROM shoes").fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO shoes (name, brand, category, price, sizes, description, image_url, stock) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                SAMPLE_SHOES,
            )

        if DEMO_MODE:
            demo_users = [
                ("Court District Manager", "manager@courtdistrict.test", "DistrictDemo1!", "admin"),
                ("Jordan Lee", "player@courtdistrict.test", "CourtSide1!", "customer"),
            ]
            for name, email, password, role in demo_users:
                db.execute(
                    "INSERT OR IGNORE INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (name, email, generate_password_hash(password), role),
                )

        admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.environ.get("ADMIN_PASSWORD", "")
        if admin_email and admin_password:
            db.execute(
                "INSERT OR IGNORE INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                (
                    "Court District Admin",
                    admin_email,
                    generate_password_hash(admin_password),
                ),
            )


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    with connect_db() as db:
        return db.execute("SELECT id, name, email, role FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please log in to continue.", "notice")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user()["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def customer_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user()["role"] != "customer":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def validate_csrf():
    submitted = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(submitted, expected):
        abort(400, description="Your form expired. Please try again.")


def shoe_form_data():
    return {
        "name": request.form.get("name", "").strip(),
        "brand": request.form.get("brand", "").strip(),
        "category": request.form.get("category", "").strip(),
        "price": request.form.get("price", "").strip(),
        "sizes": request.form.get("sizes", "").strip(),
        "description": request.form.get("description", "").strip(),
        "image_url": request.form.get("image_url", "").strip(),
        "stock": request.form.get("stock", "").strip(),
    }


def validate_shoe(data):
    required = ("name", "brand", "category", "price", "sizes", "description", "image_url", "stock")
    if any(not data[field] for field in required):
        return "Please complete every field."
    if len(data["name"]) > 80 or len(data["brand"]) > 50:
        return "Keep the shoe name under 80 characters and brand under 50."
    try:
        price = float(data["price"])
        stock = int(data["stock"])
    except ValueError:
        return "Price must be a number and stock must be a whole number."
    if price < 0 or stock < 0:
        return "Price and stock cannot be negative."
    if data["category"] not in {"Indoor", "Outdoor", "Apparel"}:
        return "Choose a valid category."
    if len(data["description"]) > 400 or len(data["sizes"]) > 100:
        return "Description or size list is too long."
    if not (data["image_url"].startswith("https://") or data["image_url"].startswith("http://")):
        return "Image URL must start with http:// or https://."
    return None


@app.context_processor
def inject_template_values():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    user = current_user()
    cart_count = 0
    if user and user["role"] == "customer":
        with connect_db() as db:
            cart_count = db.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE user_id = ?", (user["id"],)
            ).fetchone()[0]
    return {"current_user": user, "csrf_token": session["csrf_token"], "cart_count": cart_count}


@app.route("/")
def index():
    with connect_db() as db:
        shoes = db.execute("SELECT * FROM shoes ORDER BY created_at DESC, id DESC").fetchall()
        favorite_ids = set()
        user = current_user()
        if user:
            favorite_ids = {
                row[0]
                for row in db.execute("SELECT shoe_id FROM favorites WHERE user_id = ?", (user["id"],))
            }
    return render_template("index.html", shoes=shoes, favorite_ids=favorite_ids)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        validate_csrf()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or len(name) > 80 or "@" not in email:
            flash("Enter your name and a valid email address.", "error")
        elif len(password) < 8:
            flash("Your password must be at least 8 characters.", "error")
        else:
            try:
                with connect_db() as db:
                    cursor = db.execute(
                        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                        (name, email, generate_password_hash(password)),
                    )
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                flash("Your account is ready. Welcome to the District.", "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash("That email is already registered. Try logging in.", "error")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        validate_csrf()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with connect_db() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            destination = request.args.get("next", "")
            if not destination.startswith("/") or destination.startswith("//"):
                destination = url_for("index")
            return redirect(destination)
        flash("Email or password didn't match.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    validate_csrf()
    session.clear()
    flash("You are signed out.", "notice")
    return redirect(url_for("index"))


@app.route("/wishlist")
@login_required
def wishlist():
    user = current_user()
    with connect_db() as db:
        shoes = db.execute(
            "SELECT shoes.* FROM favorites JOIN shoes ON shoes.id = favorites.shoe_id "
            "WHERE favorites.user_id = ? ORDER BY favorites.created_at DESC",
            (user["id"],),
        ).fetchall()
    return render_template("favorites.html", shoes=shoes)


@app.route("/favorites")
@login_required
def favorites_alias():
    return redirect(url_for("wishlist"))


@app.route("/favorites/<int:shoe_id>/toggle", methods=["POST"])
@app.route("/wishlist/<int:shoe_id>/toggle", methods=["POST"])
@login_required
def toggle_favorite(shoe_id):
    validate_csrf()
    user = current_user()
    with connect_db() as db:
        exists = db.execute("SELECT id FROM shoes WHERE id = ?", (shoe_id,)).fetchone()
        if not exists:
            abort(404)
        saved = db.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND shoe_id = ?", (user["id"], shoe_id)
        ).fetchone()
        if saved:
            db.execute("DELETE FROM favorites WHERE user_id = ? AND shoe_id = ?", (user["id"], shoe_id))
            flash("Removed from your saved pairs.", "notice")
        else:
            db.execute("INSERT INTO favorites (user_id, shoe_id) VALUES (?, ?)", (user["id"], shoe_id))
            flash("Pair saved to your list.", "success")
    next_path = request.form.get("next", "")
    if not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path:
        next_path = url_for("index")
    return redirect(next_path)


def load_cart_items(db, user_id):
    return db.execute(
        "SELECT cart_items.shoe_id, cart_items.size, cart_items.quantity, shoes.name, shoes.brand, "
        "shoes.price, shoes.image_url, shoes.stock, shoes.sizes FROM cart_items "
        "JOIN shoes ON shoes.id = cart_items.shoe_id WHERE cart_items.user_id = ? "
        "ORDER BY cart_items.created_at, shoes.name",
        (user_id,),
    ).fetchall()


@app.route("/cart")
@customer_required
def cart():
    user = current_user()
    with connect_db() as db:
        items = load_cart_items(db, user["id"])
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    return render_template("cart.html", items=items, subtotal=subtotal)


@app.route("/cart/<int:shoe_id>/add", methods=["POST"])
@customer_required
def add_to_cart(shoe_id):
    validate_csrf()
    user = current_user()
    size = request.form.get("size", "").strip()
    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        quantity = 0
    with connect_db() as db:
        shoe = db.execute("SELECT * FROM shoes WHERE id = ?", (shoe_id,)).fetchone()
        if not shoe:
            abort(404)
        sizes = {available.strip() for available in shoe["sizes"].split(",")}
        if size not in sizes:
            flash("Choose a size from the available options.", "error")
        elif quantity < 1:
            flash("Choose a quantity of at least one.", "error")
        else:
            existing = db.execute(
                "SELECT quantity FROM cart_items WHERE user_id = ? AND shoe_id = ? AND size = ?",
                (user["id"], shoe_id, size),
            ).fetchone()
            total_quantity = quantity + (existing["quantity"] if existing else 0)
            if shoe["stock"] < 1 or total_quantity > shoe["stock"]:
                flash("That quantity is not available in stock.", "error")
            elif existing:
                db.execute(
                    "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND shoe_id = ? AND size = ?",
                    (total_quantity, user["id"], shoe_id, size),
                )
                flash("Cart updated with your pair.", "success")
            else:
                db.execute(
                    "INSERT INTO cart_items (user_id, shoe_id, size, quantity) VALUES (?, ?, ?, ?)",
                    (user["id"], shoe_id, size, quantity),
                )
                flash("Pair added to your cart.", "success")
    return redirect(url_for("cart"))


@app.route("/cart/<int:shoe_id>/update", methods=["POST"])
@customer_required
def update_cart_item(shoe_id):
    validate_csrf()
    user = current_user()
    size = request.form.get("size", "").strip()
    try:
        quantity = int(request.form.get("quantity", "0"))
    except ValueError:
        quantity = 0
    with connect_db() as db:
        item = db.execute(
            "SELECT cart_items.quantity, shoes.stock FROM cart_items JOIN shoes ON shoes.id = cart_items.shoe_id "
            "WHERE cart_items.user_id = ? AND cart_items.shoe_id = ? AND cart_items.size = ?",
            (user["id"], shoe_id, size),
        ).fetchone()
        if not item:
            abort(404)
        if quantity < 1 or quantity > item["stock"]:
            flash("Choose a quantity available in stock.", "error")
        else:
            db.execute(
                "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND shoe_id = ? AND size = ?",
                (quantity, user["id"], shoe_id, size),
            )
            flash("Cart quantity updated.", "success")
    return redirect(url_for("cart"))


@app.route("/cart/<int:shoe_id>/remove", methods=["POST"])
@customer_required
def remove_cart_item(shoe_id):
    validate_csrf()
    user = current_user()
    size = request.form.get("size", "").strip()
    with connect_db() as db:
        db.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND shoe_id = ? AND size = ?",
            (user["id"], shoe_id, size),
        )
    flash("Pair removed from your cart.", "notice")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@customer_required
def checkout():
    user = current_user()
    with connect_db() as db:
        items = load_cart_items(db, user["id"])
    if not items:
        flash("Your cart is empty. Add a pair before checking out.", "notice")
        return redirect(url_for("cart"))
    subtotal = sum(item["price"] * item["quantity"] for item in items)
    if request.method == "POST":
        validate_csrf()
        customer_name = request.form.get("customer_name", "").strip()
        delivery_method = request.form.get("delivery_method", "")
        address = request.form.get("address", "").strip()
        if not customer_name or len(customer_name) > 80:
            flash("Enter a name for this order.", "error")
        elif delivery_method not in {"Store pickup", "Cash on delivery"}:
            flash("Choose store pickup or cash on delivery.", "error")
        elif delivery_method == "Cash on delivery" and not address:
            flash("Enter a delivery address for cash on delivery.", "error")
        else:
            with connect_db() as db:
                db.execute("BEGIN IMMEDIATE")
                items = load_cart_items(db, user["id"])
                unavailable = next(
                    (item for item in items if item["quantity"] > item["stock"]), None
                )
                if not items:
                    flash("Your cart is empty. Add a pair before checking out.", "notice")
                    return redirect(url_for("cart"))
                if unavailable:
                    flash(f"{unavailable['name']} no longer has that quantity in stock.", "error")
                    return redirect(url_for("cart"))
                subtotal = sum(item["price"] * item["quantity"] for item in items)
                order_number = f"CD-{secrets.token_hex(4).upper()}"
                cursor = db.execute(
                    "INSERT INTO orders (user_id, order_number, customer_name, delivery_method, address, total) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        user["id"], order_number, customer_name, delivery_method,
                        address if delivery_method == "Cash on delivery" else "", subtotal,
                    ),
                )
                order_id = cursor.lastrowid
                for item in items:
                    db.execute(
                        "INSERT INTO order_items (order_id, shoe_id, shoe_name, brand, unit_price, size, quantity) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            order_id, item["shoe_id"], item["name"], item["brand"],
                            item["price"], item["size"], item["quantity"],
                        ),
                    )
                    db.execute(
                        "UPDATE shoes SET stock = stock - ? WHERE id = ? AND stock >= ?",
                        (item["quantity"], item["shoe_id"], item["quantity"]),
                    )
                db.execute("DELETE FROM cart_items WHERE user_id = ?", (user["id"],))
                db.commit()
            flash("Order placed. Thanks for shopping Court District.", "success")
            return redirect(url_for("order_detail", order_id=order_id))
    return render_template(
        "checkout.html", items=items, subtotal=subtotal, customer_name=user["name"]
    )


@app.route("/orders")
@customer_required
def orders():
    user = current_user()
    with connect_db() as db:
        user_orders = db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC, id DESC", (user["id"],)
        ).fetchall()
    return render_template("orders.html", orders=user_orders)


@app.route("/orders/<int:order_id>")
@customer_required
def order_detail(order_id):
    user = current_user()
    with connect_db() as db:
        order = db.execute(
            "SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, user["id"])
        ).fetchone()
        if not order:
            abort(404)
        items = db.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    return render_template("order_detail.html", order=order, items=items)


@app.route("/admin")
@admin_required
def admin_index():
    with connect_db() as db:
        shoes = db.execute("SELECT * FROM shoes ORDER BY name COLLATE NOCASE").fetchall()
    return render_template("admin.html", shoes=shoes)


@app.route("/admin/shoes/new", methods=["GET", "POST"])
@admin_required
def new_shoe():
    if request.method == "POST":
        validate_csrf()
        data = shoe_form_data()
        error = validate_shoe(data)
        if error:
            flash(error, "error")
            return render_template("shoe_form.html", shoe=data, editing=False)
        with connect_db() as db:
            db.execute(
                "INSERT INTO shoes (name, brand, category, price, sizes, description, image_url, stock) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    data["name"], data["brand"], data["category"], float(data["price"]),
                    data["sizes"], data["description"], data["image_url"], int(data["stock"]),
                ),
            )
        flash("Shoe added to the lineup.", "success")
        return redirect(url_for("admin_index"))
    return render_template("shoe_form.html", shoe=None, editing=False)


@app.route("/admin/shoes/<int:shoe_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_shoe(shoe_id):
    with connect_db() as db:
        shoe = db.execute("SELECT * FROM shoes WHERE id = ?", (shoe_id,)).fetchone()
        if not shoe:
            abort(404)
        if request.method == "POST":
            validate_csrf()
            data = shoe_form_data()
            error = validate_shoe(data)
            if error:
                flash(error, "error")
                return render_template("shoe_form.html", shoe=data, editing=True)
            db.execute(
                "UPDATE shoes SET name = ?, brand = ?, category = ?, price = ?, sizes = ?, "
                "description = ?, image_url = ?, stock = ? WHERE id = ?",
                (
                    data["name"], data["brand"], data["category"], float(data["price"]),
                    data["sizes"], data["description"], data["image_url"], int(data["stock"]), shoe_id,
                ),
            )
            flash("Shoe details updated.", "success")
            return redirect(url_for("admin_index"))
    return render_template("shoe_form.html", shoe=shoe, editing=True)


@app.route("/admin/shoes/<int:shoe_id>/delete", methods=["POST"])
@admin_required
def delete_shoe(shoe_id):
    validate_csrf()
    with connect_db() as db:
        db.execute("DELETE FROM shoes WHERE id = ?", (shoe_id,))
    flash("Shoe removed from the lineup.", "notice")
    return redirect(url_for("admin_index"))


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="This area is for Court District staff."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="We couldn't find that page or shoe."), 404


initialize_database()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)