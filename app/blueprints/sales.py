"""
Sales Ledger Blueprint for Ndungu Electronics IMS.
Renders S-08 Sales Ledger & Void Management with server-side pagination,
receipt line inspection, and Owner-authorized sale reversals with inventory restitution.
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, session
)
from app.blueprints.auth import login_required, owner_required
from app.services.pos_service import POSService
from app.services.auth_service import AuthService
from app.domain.money import format_kes
from app.db import get_db

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")


@sales_bp.route("/", methods=["GET"])
@login_required
def index():
    """Renders S-08 Sales Ledger with server-side pagination and filters."""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 25
    offset = (page - 1) * per_page

    status_filter = request.args.get("status", "").strip().lower()
    payment_filter = request.args.get("payment", "").strip().lower()
    search = request.args.get("q", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    if start_date and end_date and start_date > end_date:
        flash("Start date cannot be after end date.", "warning")
        start_date, end_date = end_date, start_date

    conn = get_db()
    cursor = conn.cursor()

    where_clauses = ["1=1"]
    params = []

    if status_filter in ("completed", "voided"):
        where_clauses.append("status = ?")
        params.append(status_filter)

    if payment_filter in ("cash", "mpesa", "card"):
        where_clauses.append("payment_method = ?")
        params.append(payment_filter)

    if search:
        where_clauses.append("(receipt_no LIKE ? OR cashier_snapshot LIKE ? OR payment_reference LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term])

    if start_date:
        where_clauses.append("sale_date >= ?")
        params.append(f"{start_date} 00:00:00")

    if end_date:
        where_clauses.append("sale_date <= ?")
        params.append(f"{end_date} 23:59:59")

    where_sql = " AND ".join(where_clauses)

    # Count total rows sharing identical WHERE clause
    cursor.execute(f"SELECT COUNT(*) AS total FROM sales WHERE {where_sql}", params)
    total_rows = cursor.fetchone()["total"]
    total_pages = max(1, (total_rows + per_page - 1) // per_page)

    # Fetch page items
    query = f"""
        SELECT sale_id, receipt_no, cashier_snapshot, subtotal_cents,
               discount_cents, tax_cents, total_cents, payment_method,
               payment_reference, status, void_reason, sale_date
        FROM sales
        WHERE {where_sql}
        ORDER BY sale_id DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(query, params + [per_page, offset])
    sales_rows = [dict(r) for r in cursor.fetchall()]

    # Aggregate telemetry KPIs
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN status = 'completed' THEN total_cents ELSE 0 END) AS completed_revenue_cents,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) AS completed_count,
            COUNT(CASE WHEN status = 'voided' THEN 1 END) AS voided_count,
            COUNT(DISTINCT cashier_snapshot) AS cashier_count
        FROM sales
    """)
    kpi_row = cursor.fetchone()

    kpi = {
        "completed_revenue_cents": kpi_row["completed_revenue_cents"] or 0,
        "completed_count": kpi_row["completed_count"] or 0,
        "voided_count": kpi_row["voided_count"] or 0,
        "cashier_count": kpi_row["cashier_count"] or 0
    }

    return render_template(
        "sales.html",
        sales=sales_rows,
        kpi=kpi,
        page=page,
        total_pages=total_pages,
        total_rows=total_rows,
        status_filter=status_filter,
        payment_filter=payment_filter,
        search=search,
        start_date=start_date,
        end_date=end_date
    )


@sales_bp.route("/<int:sale_id>/detail", methods=["GET"])
@login_required
def sale_detail(sale_id):
    """Returns JSON itemized lines and metadata for receipt modal."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sales WHERE sale_id = ?", (sale_id,))
    sale = cursor.fetchone()
    if not sale:
        return jsonify({"success": False, "error": "Sale not found."}), 404

    cursor.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,))
    items = cursor.fetchall()

    return jsonify({
        "success": True,
        "sale": dict(sale),
        "items": [dict(i) for i in items]
    })


@sales_bp.route("/<int:sale_id>/void", methods=["POST"])
@owner_required
def void_sale(sale_id):
    """Owner authorizes reversal of a completed sale with full inventory restitution."""
    reason = request.form.get("reason", "").strip()
    if not reason:
        flash("A formal reason is required to void a completed transaction.", "error")
        return redirect(url_for("sales.index"))

    user = AuthService.get_user_by_id(session["user_id"])
    try:
        POSService.void_sale(
            sale_id=sale_id,
            owner_user_id=user.user_id,
            owner_name=user.full_name or user.username,
            void_reason=reason
        )
        flash(f"Sale #{sale_id} successfully voided and inventory stock restituted.", "success")
    except Exception as exc:
        flash(f"Failed to void sale: {str(exc)}", "error")

    return redirect(url_for("sales.index"))
