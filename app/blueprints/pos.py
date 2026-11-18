"""
POS Register Blueprint.
Renders S-05 Multi-Item POS Register and S-06 Printable Receipt Drawer.
"""

from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from app.blueprints.auth import login_required
from app.services.inventory_service import InventoryService
from app.services.pos_service import POSService
from app.services.promo_service import PromoService
from app.services.auth_service import AuthService
from app.db import get_db

pos_bp = Blueprint("pos", __name__, url_prefix="/pos")


@pos_bp.route("/", methods=["GET"])
@login_required
def register():
    """Renders S-05 Multi-Item POS Register."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.product_id, p.sku, p.name, p.brand, p.price_cents, p.stock,
               p.tracking_mode, c.name as category_name
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        WHERE p.is_active = 1 AND p.stock > 0
        ORDER BY p.name ASC
    """)
    products = [dict(r) for r in cursor.fetchall()]

    # Fetch active promotions for display
    active_promos = PromoService.get_active_promotions()

    return render_template(
        "pos.html",
        products=products,
        active_promos=active_promos
    )


@pos_bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    """Processes counter sale."""
    user = AuthService.get_user_by_id(session["user_id"])
    data = request.get_json() if request.is_json else request.form

    items = data.get("items", [])
    if isinstance(items, str):
        import json
        items = json.loads(items)

    payment_method = (data.get("payment_method") or "cash").strip().lower()
    payment_ref = (data.get("payment_reference") or "").strip()
    raw_promo = data.get("promo_code")
    promo_code = raw_promo.strip() if isinstance(raw_promo, str) and raw_promo.strip() else None

    try:
        sale = POSService.checkout(
            cashier_user_id=user.user_id,
            cashier_name=user.full_name or user.username,
            items_payload=items,
            payment_method=payment_method,
            payment_reference=payment_ref,
            promo_code=promo_code
        )
        receipt_data = sale.generate_receipt()
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "receipt": receipt_data}), 200

        flash(f"Sale completed successfully! Receipt #{sale.receipt_no}", "success")
        return redirect(url_for("pos.receipt_view", receipt_no=sale.receipt_no))
    except Exception as exc:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": str(exc)}), 400
        flash(str(exc), "error")
        return redirect(url_for("pos.register"))


@pos_bp.route("/serials/<int:product_id>", methods=["GET"])
@login_required
def get_available_serials(product_id):
    """Returns in-stock serial numbers for a serialized product."""
    serials = InventoryService.get_product_serials(product_id, status_filter="in_stock")
    return jsonify({"success": True, "serials": [s["serial_no"] for s in serials]})


@pos_bp.route("/receipt/<receipt_no>", methods=["GET"])
@login_required
def receipt_view(receipt_no):
    """Renders S-06 Printable Thermal Receipt view."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sales WHERE receipt_no = ?", (receipt_no,))
    sale = cursor.fetchone()
    if not sale:
        flash("Receipt not found.", "error")
        return redirect(url_for("pos.register"))

    cursor.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale["sale_id"],))
    items = cursor.fetchall()

    return render_template("receipt.html", sale=dict(sale), items=[dict(i) for i in items])
