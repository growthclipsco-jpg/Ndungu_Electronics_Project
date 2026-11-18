"""
Inventory Blueprint for Ndungu Electronics IMS.
Renders the S-03 Inventory Dashboard, product intake, restock actions, and catalog administration.
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, session
)
from app.blueprints.auth import login_required, owner_required
from app.services.inventory_service import InventoryService
from app.services.auth_service import AuthService
from app.domain.money import format_kes

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/", methods=["GET"])
@login_required
def index():
    """Renders S-03 Inventory Dashboard with live KPIs, search, and pagination."""
    search = request.args.get("q", "").strip()
    cat_id_raw = request.args.get("category", "")
    category_id = int(cat_id_raw) if cat_id_raw.isdigit() else None
    tracking_mode = request.args.get("tracking", "").strip() or None
    low_stock = request.args.get("low_stock") == "1"
    page = max(1, int(request.args.get("page", 1)))
    sort_by = request.args.get("sort", "name")
    sort_dir = request.args.get("dir", "asc")

    categories = InventoryService.get_categories()
    inv_data = InventoryService.get_inventory(
        search=search,
        category_id=category_id,
        tracking_mode=tracking_mode,
        low_stock_only=low_stock,
        page=page,
        per_page=25,
        sort_by=sort_by,
        sort_dir=sort_dir
    )

    return render_template(
        "inventory.html",
        items=inv_data["items"],
        categories=categories,
        kpi=inv_data["kpi"],
        search=search,
        selected_category=category_id,
        selected_tracking=tracking_mode,
        low_stock=low_stock,
        page=page,
        total_pages=inv_data["total_pages"],
        total_rows=inv_data["total_rows"]
    )


@inventory_bp.route("/new", methods=["POST"])
@owner_required
def create_product():
    """Handles adding a completely new catalog product with initial stock."""
    user = AuthService.get_user_by_id(session["user_id"])
    sku = request.form.get("sku", "").strip()
    name = request.form.get("name", "").strip()
    brand = request.form.get("brand", "").strip()
    model = request.form.get("model", "").strip()
    category_id = int(request.form.get("category_id", 1))
    price_raw = request.form.get("price", "0").strip()
    cost_raw = request.form.get("cost_price", "0").strip()
    tracking_mode = request.form.get("tracking_mode", "bulk")
    stock = max(0, int(request.form.get("stock", 0)))
    reorder_threshold = max(0, int(request.form.get("reorder_threshold", 5)))
    reorder_qty = max(1, int(request.form.get("reorder_qty", 10)))
    supplier_name = request.form.get("supplier_name", "").strip()
    supplier_phone = request.form.get("supplier_phone", "").strip()
    serials_raw = request.form.get("serials", "").strip()
    serials = [s.strip() for s in serials_raw.splitlines() if s.strip()] if serials_raw else None

    from app.domain.money import to_cents
    try:
        price_cents = to_cents(price_raw)
        cost_price_cents = to_cents(cost_raw)
    except Exception:
        flash("Invalid price or cost amount.", "error")
        return redirect(url_for("inventory.index"))

    prod_id, err = InventoryService.create_product(
        sku=sku,
        name=name,
        brand=brand,
        model=model,
        category_id=category_id,
        price_cents=price_cents,
        cost_price_cents=cost_price_cents,
        user_id=user.user_id,
        username=user.username,
        tracking_mode=tracking_mode,
        stock=stock,
        reorder_threshold=reorder_threshold,
        reorder_qty=reorder_qty,
        supplier_name=supplier_name,
        supplier_phone=supplier_phone,
        serials=serials
    )

    if err:
        flash(err, "error")
    else:
        flash(f"New product '{name}' [{sku}] successfully added to inventory ledger.", "success")

    return redirect(url_for("inventory.index"))


@inventory_bp.route("/restock", methods=["POST"])
@login_required
def restock():
    """Handles quick restock intake."""
    product_id = int(request.form.get("product_id", 0))
    qty = int(request.form.get("quantity", 0))
    note = request.form.get("note", "").strip()
    serials_raw = request.form.get("serials", "").strip()
    serials = [s.strip() for s in serials_raw.splitlines() if s.strip()] if serials_raw else None

    user = AuthService.get_user_by_id(session["user_id"])
    ok, err = InventoryService.restock_product(
        product_id=product_id,
        qty_added=qty,
        user_id=user.user_id,
        username=user.username,
        note=note,
        new_serials=serials
    )

    if not ok:
        flash(err, "error")
    else:
        flash(f"Successfully restocked {qty} units.", "success")

    return redirect(url_for("inventory.index"))


@inventory_bp.route("/product/<int:product_id>", methods=["GET", "POST"])
@login_required
def product_detail(product_id):
    """Renders S-04 Product Details & Serial Intake; handles product updates."""
    product = InventoryService.get_product(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("inventory.index"))

    categories = InventoryService.get_categories()
    serials = InventoryService.get_product_serials(product_id)
    movements = InventoryService.get_product_movements(product_id, limit=15)

    if request.method == "POST":
        user = AuthService.get_user_by_id(session["user_id"])
        name = request.form.get("name", "").strip()
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        cat_id = int(request.form.get("category_id", product["category_id"]))
        price_raw = request.form.get("price", "0")
        cost_raw = request.form.get("cost_price", "0")
        reorder_th = int(request.form.get("reorder_threshold", 5))
        reorder_q = int(request.form.get("reorder_qty", 10))
        supplier_name = request.form.get("supplier_name", "").strip()
        supplier_phone = request.form.get("supplier_phone", "").strip()

        from app.domain.money import to_cents
        try:
            price_cents = to_cents(price_raw)
            cost_cents = to_cents(cost_raw)
        except Exception:
            flash("Invalid price or cost format.", "error")
            return redirect(url_for("inventory.product_detail", product_id=product_id))

        ok, err = InventoryService.update_product(
            product_id=product_id,
            name=name,
            brand=brand,
            category_id=cat_id,
            price_cents=price_cents,
            cost_price_cents=cost_cents,
            user_id=user.user_id,
            username=user.username,
            model=model,
            reorder_threshold=reorder_th,
            reorder_qty=reorder_q,
            supplier_name=supplier_name,
            supplier_phone=supplier_phone
        )
        if not ok:
            flash(err, "error")
        else:
            flash(f"Product '{name}' successfully updated.", "success")
        return redirect(url_for("inventory.product_detail", product_id=product_id))

    return render_template(
        "product_detail.html",
        product=product,
        categories=categories,
        serials=serials,
        movements=movements
    )


@inventory_bp.route("/product/<int:product_id>/archive", methods=["POST"])
@owner_required
def archive_product(product_id):
    """Soft-archives a product (sets is_active=0)."""
    user = AuthService.get_user_by_id(session["user_id"])
    ok, err = InventoryService.archive_product(product_id, user.user_id, user.username)
    if not ok:
        flash(err, "error")
    else:
        flash("Product archived from active catalog.", "success")
    return redirect(url_for("inventory.index"))
