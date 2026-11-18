"""
Promotions Blueprint for Ndungu Electronics IMS.
Renders S-07 Pricing & Promotions Manager.
Enforces @owner_required on all promotional campaign mutations.
"""

from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, session
)
from app.blueprints.auth import owner_required
from app.services.inventory_service import InventoryService
from app.domain.money import to_cents, format_kes
from app.db import get_db, transaction

promotions_bp = Blueprint("promotions", __name__, url_prefix="/promotions")


@promotions_bp.route("/", methods=["GET"])
@owner_required
def index():
    """Renders S-07 Pricing & Promotions Manager dashboard."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pr.*, 
               p.name AS product_name,
               c.name AS category_name
        FROM promotions pr
        LEFT JOIN products p ON pr.target_product_id = p.product_id
        LEFT JOIN categories c ON pr.target_category_id = c.category_id
        ORDER BY pr.priority ASC, pr.promo_id DESC
    """)
    promos = [dict(r) for r in cursor.fetchall()]

    products = InventoryService.get_inventory(per_page=100)["items"]
    categories = InventoryService.get_categories()

    # Metrics
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_count = sum(1 for p in promos if p["is_active"] and p["starts_at"] <= now_str <= p["ends_at"])
    upcoming_count = sum(1 for p in promos if p["is_active"] and p["starts_at"] > now_str)

    return render_template(
        "promotions.html",
        promotions=promos,
        products=products,
        categories=categories,
        active_count=active_count,
        upcoming_count=upcoming_count,
        total_count=len(promos)
    )


@promotions_bp.route("/new", methods=["POST"])
@owner_required
def create_promotion():
    """Creates a new promotional pricing rule."""
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper() or None
    scope = request.form.get("scope", "cart")
    discount_type = request.form.get("discount_type", "percent")
    if discount_type in ("percentage", "percent"):
        discount_type = "percent"
    elif discount_type not in ("percent", "fixed_cents"):
        discount_type = "percent"
    discount_raw = request.form.get("discount_value", "0").strip()

    target_product_id = int(request.form.get("target_product_id")) if request.form.get("target_product_id") else None
    target_category_id = int(request.form.get("target_category_id")) if request.form.get("target_category_id") else None
    min_qty = max(1, int(request.form.get("min_qty", 1)))
    starts_at = request.form.get("starts_at", "").strip()
    ends_at = request.form.get("ends_at", "").strip()

    if not name:
        flash("Promotion name is required.", "error")
        return redirect(url_for("promotions.index"))

    try:
        if discount_type == "fixed_cents":
            discount_value = to_cents(discount_raw)
        else:
            discount_value = int(float(discount_raw))
    except Exception:
        flash("Invalid discount value format.", "error")
        return redirect(url_for("promotions.index"))

    if not starts_at or not ends_at:
        flash("Start and end schedule dates are required.", "error")
        return redirect(url_for("promotions.index"))

    # Append time if date only
    if len(starts_at) == 10:
        starts_at += " 00:00:00"
    if len(ends_at) == 10:
        ends_at += " 23:59:59"

    with transaction() as conn:
        conn.execute("""
            INSERT INTO promotions (
                code, name, scope, target_product_id,
                target_category_id, discount_type, discount_value,
                min_qty, starts_at, ends_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (code, name, scope, target_product_id,
              target_category_id, discount_type, discount_value, min_qty, starts_at, ends_at))

    flash(f"Promotion campaign '{name}' created successfully.", "success")
    return redirect(url_for("promotions.index"))


@promotions_bp.route("/<int:promo_id>/toggle", methods=["POST"])
@owner_required
def toggle_status(promo_id):
    """Toggles active status of a promotion."""
    with transaction() as conn:
        conn.execute("""
            UPDATE promotions
            SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
                updated_at = datetime('now', 'localtime')
            WHERE promo_id = ?
        """, (promo_id,))
    flash("Promotion status updated.", "success")
    return redirect(url_for("promotions.index"))
