"""
BI Reports Blueprint for Ndungu Electronics IMS.
Renders S-09 BI Reports & Low-Stock Reorder Center.
Streams pure-Python ReportLab A4 PDF and formula-safe CSV exports.
Enforces @owner_required across all financial analytics.
"""

from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request, Response, session, redirect, url_for
)
from app.blueprints.auth import owner_required
from app.services.inventory_service import InventoryService
from app.services.export_service import ExportService
from app.domain.money import format_kes
from app.db import get_db

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def get_period_dates(period: str):
    """Calculates start and end timestamps for relative date presets."""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if period == "today":
        return today_start.strftime("%Y-%m-%d %H:%M:%S"), today_end.strftime("%Y-%m-%d %H:%M:%S"), "Today"
    elif period == "yesterday":
        y_start = today_start - timedelta(days=1)
        y_end = today_end - timedelta(days=1)
        return y_start.strftime("%Y-%m-%d %H:%M:%S"), y_end.strftime("%Y-%m-%d %H:%M:%S"), "Yesterday"
    elif period == "7days":
        w_start = today_start - timedelta(days=7)
        return w_start.strftime("%Y-%m-%d %H:%M:%S"), today_end.strftime("%Y-%m-%d %H:%M:%S"), "Last 7 Days"
    elif period == "month":
        m_start = today_start.replace(day=1)
        return m_start.strftime("%Y-%m-%d %H:%M:%S"), today_end.strftime("%Y-%m-%d %H:%M:%S"), "This Month"
    else:
        # All time
        return "2020-01-01 00:00:00", today_end.strftime("%Y-%m-%d %H:%M:%S"), "All Time"


@reports_bp.route("/", methods=["GET"])
@owner_required
def index():
    """Renders S-09 BI Reports & Analytics Dashboard."""
    period = request.args.get("period", "month").lower()
    start_date, end_date, period_label = get_period_dates(period)

    conn = get_db()
    cursor = conn.cursor()

    # Telemetry KPIs for completed sales in period
    cursor.execute("""
        SELECT 
            COUNT(*) AS sales_count,
            COALESCE(SUM(subtotal_cents), 0) AS gross_subtotal_cents,
            COALESCE(SUM(discount_cents), 0) AS discount_cents,
            COALESCE(SUM(tax_cents), 0) AS tax_cents,
            COALESCE(SUM(total_cents), 0) AS net_revenue_cents,
            COALESCE(AVG(total_cents), 0) AS avg_basket_cents
        FROM sales
        WHERE status = 'completed'
          AND sale_date >= ? AND sale_date <= ?
    """, (start_date, end_date))
    kpi_raw = cursor.fetchone()

    # Void count
    cursor.execute("""
        SELECT COUNT(*) AS void_count
        FROM sales
        WHERE status = 'voided'
          AND sale_date >= ? AND sale_date <= ?
    """, (start_date, end_date))
    void_count = cursor.fetchone()["void_count"]

    # Payment distribution
    cursor.execute("""
        SELECT payment_method, COUNT(*) AS cnt, COALESCE(SUM(total_cents), 0) AS total_cents
        FROM sales
        WHERE status = 'completed'
          AND sale_date >= ? AND sale_date <= ?
        GROUP BY payment_method
    """, (start_date, end_date))
    payment_stats = [dict(r) for r in cursor.fetchall()]

    # Estimated COGS from sale_items
    cursor.execute("""
        SELECT COALESCE(SUM(si.cost_price_cents * si.quantity), 0) AS total_cogs_cents
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.sale_id
        WHERE s.status = 'completed'
          AND s.sale_date >= ? AND s.sale_date <= ?
    """, (start_date, end_date))
    cogs_cents = cursor.fetchone()["total_cogs_cents"]
    net_revenue_cents = kpi_raw["net_revenue_cents"]
    gross_profit_cents = max(0, net_revenue_cents - cogs_cents)
    margin_pct = (gross_profit_cents / net_revenue_cents * 100) if net_revenue_cents > 0 else 0.0

    kpi = {
        "sales_count": kpi_raw["sales_count"],
        "voided_count": void_count,
        "gross_revenue_cents": kpi_raw["gross_subtotal_cents"],
        "discount_cents": kpi_raw["discount_cents"],
        "tax_cents": kpi_raw["tax_cents"],
        "net_revenue_cents": net_revenue_cents,
        "avg_basket_cents": int(kpi_raw["avg_basket_cents"]),
        "cogs_cents": cogs_cents,
        "gross_profit_cents": gross_profit_cents,
        "margin_pct": round(margin_pct, 1)
    }

    # Low-Stock Surveillance (< 5 threshold or stock <= reorder_threshold)
    cursor.execute("""
        SELECT p.product_id, p.sku, p.name, p.brand, p.stock,
               p.reorder_threshold, p.reorder_qty, p.price_cents,
               p.supplier_name, p.supplier_phone, c.name AS category_name
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        WHERE p.is_active = 1 AND p.stock <= p.reorder_threshold
        ORDER BY p.stock ASC, p.name ASC
    """)
    low_stock_items = [dict(r) for r in cursor.fetchall()]

    # Top selling items
    cursor.execute("""
        SELECT si.product_name_snapshot, si.sku_snapshot,
               SUM(si.quantity) AS units_sold,
               SUM(si.line_total_cents) AS revenue_cents
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.sale_id
        WHERE s.status = 'completed'
          AND s.sale_date >= ? AND s.sale_date <= ?
        GROUP BY si.sku_snapshot
        ORDER BY units_sold DESC
        LIMIT 5
    """, (start_date, end_date))
    top_products = [dict(r) for r in cursor.fetchall()]

    # Overall Catalog Valuation
    cursor.execute("""
        SELECT COUNT(*) AS total_skus, COALESCE(SUM(stock * price_cents), 0) AS total_valuation_cents
        FROM products WHERE is_active = 1
    """)
    cat_summary = cursor.fetchone()

    return render_template(
        "reports.html",
        kpi=kpi,
        period=period,
        period_label=period_label,
        low_stock_items=low_stock_items,
        top_products=top_products,
        payment_stats=payment_stats,
        total_skus=cat_summary["total_skus"],
        valuation_cents=cat_summary["total_valuation_cents"]
    )


@reports_bp.route("/export/csv", methods=["GET"])
@owner_required
def export_csv():
    """Streams formula-safe CSV export of sales transactions."""
    period = request.args.get("period", "month").lower()
    start_date, end_date, _ = get_period_dates(period)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT receipt_no, sale_date, cashier_snapshot, payment_method,
               payment_reference, status, subtotal_cents, discount_cents,
               tax_cents, total_cents
        FROM sales
        WHERE sale_date >= ? AND sale_date <= ?
        ORDER BY sale_id DESC
    """, (start_date, end_date))
    records = [dict(r) for r in cursor.fetchall()]

    csv_data = ExportService.export_sales_csv(records)
    filename = f"ndungu_sales_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@reports_bp.route("/export/pdf", methods=["GET"])
@owner_required
def export_pdf():
    """Streams pure-Python ReportLab A4 PDF telemetry report."""
    period = request.args.get("period", "month").lower()
    start_date, end_date, period_label = get_period_dates(period)

    conn = get_db()
    cursor = conn.cursor()

    # KPI
    cursor.execute("""
        SELECT 
            COUNT(*) AS sales_count,
            COALESCE(SUM(subtotal_cents), 0) AS gross_subtotal_cents,
            COALESCE(SUM(discount_cents), 0) AS discount_cents,
            COALESCE(SUM(tax_cents), 0) AS tax_cents,
            COALESCE(SUM(total_cents), 0) AS net_revenue_cents
        FROM sales
        WHERE status = 'completed' AND sale_date >= ? AND sale_date <= ?
    """, (start_date, end_date))
    kpi_raw = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) AS void_count FROM sales
        WHERE status = 'voided' AND sale_date >= ? AND sale_date <= ?
    """, (start_date, end_date))
    void_count = cursor.fetchone()["void_count"]

    # Catalog summary
    cursor.execute("SELECT COUNT(*) as total_skus, COALESCE(SUM(stock * price_cents), 0) as valuation_cents FROM products WHERE is_active = 1")
    cat = cursor.fetchone()

    # Low stock
    cursor.execute("""
        SELECT sku, name, stock, reorder_threshold, reorder_qty, supplier_name, supplier_phone
        FROM products WHERE is_active = 1 AND stock <= reorder_threshold
        ORDER BY stock ASC LIMIT 20
    """)
    low_stock = [dict(r) for r in cursor.fetchall()]

    # Recent sales
    cursor.execute("""
        SELECT receipt_no, sale_date, cashier_snapshot, payment_method, status, total_cents
        FROM sales ORDER BY sale_id DESC LIMIT 15
    """)
    recent = [dict(r) for r in cursor.fetchall()]

    report_payload = {
        "period_label": period_label,
        "kpi": {
            "sales_count": kpi_raw["sales_count"],
            "voided_count": void_count,
            "gross_revenue_cents": kpi_raw["gross_subtotal_cents"],
            "discount_cents": kpi_raw["discount_cents"],
            "tax_cents": kpi_raw["tax_cents"],
            "net_revenue_cents": kpi_raw["net_revenue_cents"]
        },
        "total_skus": cat["total_skus"],
        "valuation_cents": cat["valuation_cents"],
        "low_stock_items": low_stock,
        "recent_sales": recent
    }

    pdf_bytes = ExportService.generate_bi_pdf(report_payload)
    filename = f"ndungu_bi_report_{period}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
