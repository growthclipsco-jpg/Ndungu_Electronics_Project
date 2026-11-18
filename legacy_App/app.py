"""
Ndungu Electronics Inventory Management System
==============================================
A Flask + SQLite web application that replaces the manual, notebook-based
inventory process at Ndungu Electronics, Thika.

Features (mapped to the specific objectives in Chapter One):
  1. Inventory management module - add, edit and delete products, categories and prices
  2. Automated sales processing  - a sale reduces stock and is logged in real time
  3. Low-stock alerts            - products with fewer than 5 items are flagged
  4. Search                      - by product name, brand, model or serial number
  5. Duplicate detection         - the same product cannot be recorded twice
Plus: secure login with roles (owner / attendant), sales log and reports.

Run locally:   python app.py      then open http://127.0.0.1:5000
"""
import math
import os
import re
import secrets
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (Blueprint, Flask, abort, current_app, flash, g, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

LOW_STOCK_THRESHOLD = 5  # Objective 3: flag products with FEWER than 5 items
CATEGORIES = ("Televisions", "Laptops", "Smartphones", "Accessories")
ROLES = ("owner", "attendant")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")

# Report periods. The SQL fragments are fixed strings (never user input).
REPORT_PERIODS = {
    "today": ("Today", "date(sale_date) = date('now', 'localtime')"),
    "week": ("Last 7 days", "date(sale_date) >= date('now', 'localtime', '-6 days')"),
    "month": ("This month", "date(sale_date) >= date('now', 'localtime', 'start of month')"),
    "all": ("All time", "1 = 1"),
}

bp = Blueprint("main", __name__)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or _load_or_create_secret(app.instance_path),
        DATABASE=os.path.join(app.instance_path, "inventory.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    app.register_blueprint(bp)
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.add_template_filter(format_kes, "kes")
    app.add_template_filter(format_datetime, "dt")
    app.add_template_filter(format_number, "num")

    for code in (400, 403, 404, 405):
        app.register_error_handler(code, render_error)

    with app.app_context():
        init_db()
    return app


def _load_or_create_secret(instance_path):
    """Keep a random secret key in instance/secret_key so sessions survive restarts."""
    path = os.path.join(instance_path, "secret_key")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    key = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    return key


def render_error(error):
    code = getattr(error, "code", 500)
    titles = {400: "Bad request", 403: "Access denied", 404: "Page not found",
              405: "Method not allowed"}
    return render_template("error.html", code=code, title=titles.get(code, "Error"),
                           message=getattr(error, "description", "")), code


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    """Return one SQLite connection per request (stored on flask.g)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tables (safe to run repeatedly - schema uses IF NOT EXISTS)."""
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    db.commit()


def user_count():
    return get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_product_or_404(product_id):
    product = get_db().execute(
        "SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if product is None:
        abort(404, "That product does not exist (it may have been removed).")
    return product


# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------
def format_kes(value):
    """38500 -> 'Kes. 38,500' ; 1250.5 -> 'Kes. 1,250.50'"""
    text = f"{float(value or 0):,.2f}"
    if text.endswith(".00"):
        text = text[:-3]
    return f"Kes. {text}"


def format_datetime(value, fmt="%d %b %Y, %I:%M %p"):
    if not value:
        return ""
    try:
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").strftime(fmt)
    except ValueError:
        return value


def format_number(value):
    """Show 52000.0 as '52000' in form inputs, keep other values unchanged."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return "" if value is None else str(value)


# ---------------------------------------------------------------------------
# Security: CSRF protection, current user, access control
# ---------------------------------------------------------------------------
def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["_csrf_token"] = token
    return token


@bp.before_app_request
def protect_and_load_user():
    # Every POST form must carry the secret token issued with the page (CSRF).
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not expected or not secrets.compare_digest(sent, expected):
            abort(400, "Your form session expired. Please reload the page and try again.")

    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = get_db().execute(
            "SELECT user_id, username, role FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if g.user is None:  # account was deleted
            session.clear()


@bp.app_context_processor
def inject_globals():
    low = 0
    if getattr(g, "user", None):
        low = get_db().execute(
            "SELECT COUNT(*) FROM products WHERE stock < ?", (LOW_STOCK_THRESHOLD,)
        ).fetchone()[0]
    return {"low_stock_count": low, "LOW_STOCK_THRESHOLD": LOW_STOCK_THRESHOLD,
            "CATEGORIES": CATEGORIES}


def _login_redirect():
    flash("Please log in to continue.", "info")
    return redirect(url_for("main.login", next=request.path))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return _login_redirect()
        return view(*args, **kwargs)
    return wrapped


def owner_required(view):
    """Only the shop owner may manage products, view reports and manage users."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return _login_redirect()
        if g.user["role"] != "owner":
            abort(403, "Only the shop owner can perform this action.")
        return view(*args, **kwargs)
    return wrapped


def _is_safe_next(target):
    return bool(target) and target.startswith("/") and not target.startswith("//")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def _clean_text(value):
    """Trim and collapse repeated spaces: '  HP   15 ' -> 'HP 15'."""
    return " ".join((value or "").split())


def normalize_serial(value):
    """Serial numbers: trim whitespace and convert to upper-case without stripping interior hyphens: '  ua43-8842 ' -> 'UA43-8842'."""
    return re.sub(r"\s+", " ", value or "").strip().upper()


def validate_product_form(form):
    """Return (values, errors). Values keep the user's input for re-display."""
    values = {
        "name": _clean_text(form.get("name")),
        "brand": _clean_text(form.get("brand")),
        "model": _clean_text(form.get("model")),
        "category": _clean_text(form.get("category")),
        "serial_no": normalize_serial(form.get("serial_no")),
        "price": (form.get("price") or "").strip(),
        "stock": (form.get("stock") or "").strip(),
    }
    errors = []
    if not values["name"]:
        errors.append("Product name is required.")
    if not values["brand"]:
        errors.append("Brand is required.")
    if values["category"] not in CATEGORIES:
        errors.append("Please choose a valid category.")
    if not values["serial_no"]:
        errors.append("Serial number is required.")
    elif len(values["serial_no"]) > 40:
        errors.append("Serial number must be 40 characters or fewer.")

    try:
        price = float(values["price"].replace(",", ""))
        if price < 0 or not math.isfinite(price):
            raise ValueError
        values["price"] = round(price, 2)
    except ValueError:
        errors.append("Price must be a number of zero or more (e.g. 38500).")

    try:
        stock = int(values["stock"])
        if stock < 0 or stock > 100000:
            raise ValueError
        values["stock"] = stock
    except ValueError:
        errors.append("Stock must be a whole number of zero or more.")
    return values, errors


def find_duplicate(db, values, exclude_id=None):
    """Objective 5 - duplicate detection. Returns an error message or None."""
    exclude_id = exclude_id or -1
    row = db.execute(
        "SELECT name FROM products WHERE serial_no = ? COLLATE NOCASE AND product_id != ?",
        (values["serial_no"], exclude_id),
    ).fetchone()
    if row:
        return (f"Duplicate detected: serial number {values['serial_no']} is already "
                f"recorded for '{row['name']}'.")
    row = db.execute(
        "SELECT serial_no FROM products WHERE lower(name) = lower(?) AND lower(brand) = lower(?) "
        "AND lower(model) = lower(?) AND product_id != ?",
        (values["name"], values["brand"], values["model"], exclude_id),
    ).fetchone()
    if row:
        return (f"Duplicate detected: '{values['name']}' by {values['brand']} already exists "
                f"(serial {row['serial_no']}). Restock the existing product instead.")
    return None


def validate_new_user(username, password, confirm=None):
    errors = []
    if not USERNAME_RE.match(username):
        errors.append("Username must be 3-30 characters (letters, numbers, _ or . only).")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters long.")
    if confirm is not None and password != confirm:
        errors.append("Passwords do not match.")
    if not errors and get_db().execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        errors.append("That username is already taken.")
    return errors


def _parse_date(value):
    try:
        return date.fromisoformat(value).isoformat() if value else ""
    except ValueError:
        return ""


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.inventory"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["user_id"]
            flash(f"Welcome back, {user['username']}!", "success")
            target = request.args.get("next", "")
            return redirect(target if _is_safe_next(target) else url_for("main.inventory"))
    return render_template("login.html", first_run=user_count() == 0)


@bp.route("/register", methods=["GET", "POST"])
def register():
    """First-run setup: creates the shop owner account. Disabled once it exists."""
    if user_count() > 0:
        flash("The owner account already exists. Please log in, "
              "or ask the owner to create an account for you.", "info")
        return redirect(url_for("main.login"))
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        errors = validate_new_user(username, password, request.form.get("confirm", ""))
        if not errors:
            db = get_db()
            db.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'owner')",
                       (username, generate_password_hash(password)))
            db.commit()
            flash("Owner account created. You can now log in.", "success")
            return redirect(url_for("main.login"))
        for error in errors:
            flash(error, "error")
    return render_template("register.html", username=username)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.login"))


# ---------------------------------------------------------------------------
# Inventory (dashboard, search, add / edit / delete / restock)
# ---------------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    return redirect(url_for("main.inventory"))


@bp.route("/inventory")
@login_required
def inventory():
    db = get_db()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    low_only = request.args.get("low") == "1"

    sql = "SELECT * FROM products WHERE 1 = 1"
    params = []
    if q:  # Objective 4: search by name, brand, model or serial number
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql += (" AND (name LIKE ? ESCAPE '\\' OR brand LIKE ? ESCAPE '\\' "
                "OR model LIKE ? ESCAPE '\\' OR serial_no LIKE ? ESCAPE '\\')")
        params += [like] * 4
    if category in CATEGORIES:
        sql += " AND category = ?"
        params.append(category)
    if low_only:
        sql += " AND stock < ?"
        params.append(LOW_STOCK_THRESHOLD)
    sql += " ORDER BY name COLLATE NOCASE"
    products = db.execute(sql, params).fetchall()

    stats = db.execute(
        "SELECT COUNT(*) AS products, IFNULL(SUM(stock), 0) AS units, "
        "IFNULL(SUM(price * stock), 0) AS value FROM products").fetchone()
    today = db.execute(
        "SELECT COUNT(*) AS transactions, IFNULL(SUM(total_price), 0) AS revenue "
        "FROM sales WHERE date(sale_date) = date('now', 'localtime')").fetchone()
    low_stock = db.execute(
        "SELECT product_id, name, stock FROM products WHERE stock < ? ORDER BY stock, name",
        (LOW_STOCK_THRESHOLD,)).fetchall()

    return render_template("inventory.html", products=products, stats=stats, today=today,
                           low_stock=low_stock, q=q, category=category, low_only=low_only)


@bp.route("/products/new", methods=["GET", "POST"])
@owner_required
def add_product():
    values = {}
    if request.method == "POST":
        db = get_db()
        values, errors = validate_product_form(request.form)
        if not errors:
            duplicate = find_duplicate(db, values)
            if duplicate:
                errors.append(duplicate)
        if not errors:
            try:
                db.execute(
                    "INSERT INTO products (name, brand, model, category, serial_no, price, stock, user_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (values["name"], values["brand"], values["model"], values["category"],
                     values["serial_no"], values["price"], values["stock"], g.user["user_id"]))
                db.commit()
            except sqlite3.IntegrityError:  # safety net: UNIQUE constraint on serial_no
                db.rollback()
                errors.append(f"Duplicate detected: serial number {values['serial_no']} already exists.")
            else:
                flash(f"'{values['name']}' was added to the inventory.", "success")
                return redirect(url_for("main.inventory"))
        for error in errors:
            flash(error, "error")
    return render_template("product_form.html", product=values, mode="add")


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@owner_required
def edit_product(product_id):
    product = get_product_or_404(product_id)
    values = dict(product)
    if request.method == "POST":
        db = get_db()
        values, errors = validate_product_form(request.form)
        values["product_id"] = product_id
        if not errors:
            duplicate = find_duplicate(db, values, exclude_id=product_id)
            if duplicate:
                errors.append(duplicate)
        if not errors:
            try:
                db.execute(
                    "UPDATE products SET name = ?, brand = ?, model = ?, category = ?, serial_no = ?, "
                    "price = ?, stock = ?, updated_at = datetime('now', 'localtime') WHERE product_id = ?",
                    (values["name"], values["brand"], values["model"], values["category"],
                     values["serial_no"], values["price"], values["stock"], product_id))
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                errors.append(f"Duplicate detected: serial number {values['serial_no']} already exists.")
            else:
                flash(f"'{values['name']}' was updated.", "success")
                return redirect(url_for("main.inventory"))
        for error in errors:
            flash(error, "error")
    return render_template("product_form.html", product=values, mode="edit")


@bp.route("/products/<int:product_id>/restock", methods=["POST"])
@owner_required
def restock_product(product_id):
    product = get_product_or_404(product_id)
    try:
        quantity = int(request.form.get("quantity", ""))
        if quantity <= 0 or quantity > 10000:
            raise ValueError
    except ValueError:
        flash("Restock quantity must be a whole number between 1 and 10,000.", "error")
        return redirect(url_for("main.edit_product", product_id=product_id))
    db = get_db()
    db.execute("UPDATE products SET stock = stock + ?, updated_at = datetime('now', 'localtime') "
               "WHERE product_id = ?", (quantity, product_id))
    db.commit()
    flash(f"Added {quantity} unit(s) to '{product['name']}'. "
          f"New stock: {product['stock'] + quantity}.", "success")
    return redirect(url_for("main.inventory"))


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
@owner_required
def delete_product(product_id):
    product = get_product_or_404(product_id)
    db = get_db()
    db.execute("DELETE FROM products WHERE product_id = ?", (product_id,))
    db.commit()  # past sales keep their snapshot (product_id is set to NULL)
    flash(f"'{product['name']}' was removed from the inventory.", "success")
    return redirect(url_for("main.inventory"))


# ---------------------------------------------------------------------------
# Sales processing (Objective 2) and sales log
# ---------------------------------------------------------------------------
@bp.route("/products/<int:product_id>/sell", methods=["GET", "POST"])
@login_required
def sell_product(product_id):
    product = get_product_or_404(product_id)
    if request.method == "POST":
        raw = request.form.get("quantity", "")
        try:
            quantity = int(raw)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            flash("Quantity must be a whole number greater than zero.", "error")
            return render_template("sell.html", product=product, quantity=raw)

        db = get_db()
        # Atomic update: only succeeds if enough stock exists, so stock can never
        # go negative even if two staff members sell the last item at once.
        cursor = db.execute(
            "UPDATE products SET stock = stock - ?, updated_at = datetime('now', 'localtime') "
            "WHERE product_id = ? AND stock >= ?", (quantity, product_id, quantity))
        if cursor.rowcount == 0:
            db.rollback()
            product = get_product_or_404(product_id)
            flash(f"Not enough stock: only {product['stock']} unit(s) of "
                  f"'{product['name']}' available.", "error")
            return render_template("sell.html", product=product, quantity=raw)

        total = round(product["price"] * quantity, 2)
        db.execute(
            "INSERT INTO sales (product_id, user_id, product_name, serial_no, category, "
            "quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (product_id, g.user["user_id"], product["name"], product["serial_no"],
             product["category"], quantity, product["price"], total))
        db.commit()

        remaining = product["stock"] - quantity
        flash(f"Sale recorded: {quantity} x {product['name']} for {format_kes(total)}.", "success")
        if remaining < LOW_STOCK_THRESHOLD:
            flash(f"Low stock alert: only {remaining} unit(s) of '{product['name']}' left. "
                  "Consider restocking.", "warning")
        return redirect(url_for("main.inventory"))
    return render_template("sell.html", product=product, quantity=1)


@bp.route("/sales")
@login_required
def sales_log():
    date_from = _parse_date(request.args.get("from", ""))
    date_to = _parse_date(request.args.get("to", ""))
    where, params = "WHERE 1 = 1", []
    if date_from:
        where += " AND date(s.sale_date) >= ?"
        params.append(date_from)
    if date_to:
        where += " AND date(s.sale_date) <= ?"
        params.append(date_to)

    db = get_db()
    sales = db.execute(
        "SELECT s.*, u.username FROM sales s LEFT JOIN users u ON u.user_id = s.user_id "
        f"{where} ORDER BY s.sale_date DESC, s.sale_id DESC LIMIT 500", params).fetchall()
    totals = db.execute(
        "SELECT COUNT(*) AS transactions, IFNULL(SUM(quantity), 0) AS units, "
        f"IFNULL(SUM(total_price), 0) AS revenue FROM sales s {where}", params).fetchone()
    return render_template("sales.html", sales=sales, totals=totals,
                           date_from=date_from, date_to=date_to)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@bp.route("/reports")
@owner_required
def reports():
    period = request.args.get("period", "month")
    if period not in REPORT_PERIODS:
        period = "month"
    label, where = REPORT_PERIODS[period]
    db = get_db()

    summary = db.execute(
        "SELECT COUNT(*) AS transactions, IFNULL(SUM(quantity), 0) AS units, "
        f"IFNULL(SUM(total_price), 0) AS revenue FROM sales WHERE {where}").fetchone()
    best_sellers = db.execute(
        "SELECT product_name, serial_no, SUM(quantity) AS qty, SUM(total_price) AS revenue "
        f"FROM sales WHERE {where} GROUP BY product_name, serial_no "
        "ORDER BY qty DESC, revenue DESC LIMIT 5").fetchall()
    by_category = db.execute(
        "SELECT category, SUM(quantity) AS qty, SUM(total_price) AS revenue "
        f"FROM sales WHERE {where} GROUP BY category ORDER BY revenue DESC").fetchall()
    daily = db.execute(
        "SELECT date(sale_date) AS day, SUM(quantity) AS qty, SUM(total_price) AS revenue "
        f"FROM sales WHERE {where} GROUP BY day ORDER BY day DESC LIMIT 31").fetchall()
    inventory = db.execute(
        "SELECT COUNT(*) AS products, IFNULL(SUM(stock), 0) AS units, "
        "IFNULL(SUM(price * stock), 0) AS value FROM products").fetchone()
    low_stock = db.execute(
        "SELECT * FROM products WHERE stock < ? ORDER BY stock, name",
        (LOW_STOCK_THRESHOLD,)).fetchall()

    max_daily = max((row["revenue"] for row in daily), default=0) or 1
    return render_template("reports.html", period=period, periods=REPORT_PERIODS,
                           label=label, summary=summary, best_sellers=best_sellers,
                           by_category=by_category, daily=daily, max_daily=max_daily,
                           inventory=inventory, low_stock=low_stock,
                           generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ---------------------------------------------------------------------------
# User management (owner only)
# ---------------------------------------------------------------------------
@bp.route("/users", methods=["GET", "POST"])
@owner_required
def users():
    db = get_db()
    form = {"username": "", "role": "attendant"}
    if request.method == "POST":
        form["username"] = request.form.get("username", "").strip()
        form["role"] = request.form.get("role", "attendant")
        password = request.form.get("password", "")
        errors = validate_new_user(form["username"], password)
        if form["role"] not in ROLES:
            errors.append("Please choose a valid role.")
        if not errors:
            db.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                       (form["username"], generate_password_hash(password), form["role"]))
            db.commit()
            flash(f"Account '{form['username']}' ({form['role']}) created.", "success")
            return redirect(url_for("main.users"))
        for error in errors:
            flash(error, "error")
    accounts = db.execute(
        "SELECT user_id, username, role, created_at FROM users ORDER BY role DESC, username"
    ).fetchall()
    return render_template("users.html", accounts=accounts, form=form, roles=ROLES)


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@owner_required
def delete_user(user_id):
    db = get_db()
    account = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if account is None:
        abort(404, "That user does not exist.")
    if account["user_id"] == g.user["user_id"]:
        flash("You cannot delete your own account while logged in.", "error")
    elif account["role"] == "owner" and db.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'owner'").fetchone()[0] <= 1:
        flash("The system must keep at least one owner account.", "error")
    else:
        db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        db.commit()
        flash(f"Account '{account['username']}' was deleted.", "success")
    return redirect(url_for("main.users"))


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000,
                     debug=os.environ.get("FLASK_DEBUG", "1") == "1")
