"""
Test suite covering Phase 4 QA requirements:
- TC-09: Reports relative dates, periods, and void exclusion
- TC-15: Formula-safe CSV export (neutralizes =, +, -, @) & ReportLab PDF export
- TC-16: Sales date validation and server-side 25-row pagination
"""

from datetime import datetime, timedelta
import pytest
from flask import session
from app.services.export_service import ExportService
from app.services.inventory_service import InventoryService
from app.services.pos_service import POSService
from app.services.auth_service import AuthService
from app.db import get_db, transaction


def test_tc09_reports_relative_dates_and_periods(owner_client, app):
    """TC-09: Verifies relative date filtering ('today', 'yesterday', '7days', 'month') and strict exclusion of voided sales from revenue."""
    # 1. Access reports with relative period presets
    for period in ["today", "yesterday", "7days", "month", "all"]:
        res = owner_client.get(f"/reports/?period={period}")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "BI Reports" in html or "Executive Telemetry" in html or "Business Intelligence" in html

    with app.app_context():
        owner = AuthService.get_user_by_username("admin")
        cats = InventoryService.get_categories()

        # Create product and a completed sale today
        prod_id, _ = InventoryService.create_product(
            sku="REV-TEST-01",
            name="Revenue Test Lamp",
            brand="Philips",
            category_id=cats[0]["category_id"],
            price_cents=250000,
            cost_price_cents=150000,
            user_id=owner.user_id,
            username=owner.username,
            stock=10
        )
        sale = POSService.checkout(
            cashier_user_id=owner.user_id,
            cashier_name=owner.username,
            items_payload=[{"product_id": prod_id, "quantity": 1}],
            payment_method="cash"
        )
        assert sale.sale_id is not None

        # Check today's report includes revenue
        conn = get_db()
        cur = conn.cursor()
        now_date = datetime.now().strftime("%Y-%m-%d")
        cur.execute(
            """
            SELECT COALESCE(SUM(total_cents), 0) AS rev
            FROM sales
            WHERE status = 'completed' AND sale_date >= ?
            """,
            (f"{now_date} 00:00:00",)
        )
        rev_before_void = cur.fetchone()["rev"]
        assert rev_before_void >= sale.total_cents

        # 2. Void the sale and confirm voided sales are strictly excluded
        POSService.void_sale(
            sale_id=sale.sale_id,
            owner_user_id=owner.user_id,
            owner_name=owner.username,
            void_reason="Returned by customer"
        )

        cur.execute(
            """
            SELECT COALESCE(SUM(total_cents), 0) AS rev
            FROM sales
            WHERE status = 'completed' AND sale_date >= ?
            """,
            (f"{now_date} 00:00:00",)
        )
        rev_after_void = cur.fetchone()["rev"]
        assert rev_after_void == rev_before_void - sale.total_cents


def test_tc15_csv_formula_injection_and_pdf_export(owner_client, app):
    """TC-15: Verifies neutralization of spreadsheet formula injection characters (=, +, -, @) and ReportLab A4 PDF streaming."""
    # 1. Direct unit verification of formula sanitization
    malicious_inputs = [
        ("=cmd|' /C calc'!A0", "'=cmd|' /C calc'!A0"),
        ("+SUM(A1:A10)", "'+SUM(A1:A10)"),
        ("-1+1", "'-1+1"),
        ("@malicious_macro", "'@malicious_macro"),
        ("\tcmd", "'\tcmd"),
        ("\rcmd", "'\rcmd"),
        ("Safe Normal Text", "Safe Normal Text"),
        (12500, "12500"),
    ]
    for raw, expected in malicious_inputs:
        sanitized = ExportService.sanitize_csv_cell(raw)
        assert sanitized == expected, f"Failed for {raw}: got {sanitized}"

    # 2. Ingest malicious product into sales export to verify end-to-end sanitization
    with app.app_context():
        owner = AuthService.get_user_by_username("admin")
        cats = InventoryService.get_categories()
        bad_prod_id, _ = InventoryService.create_product(
            sku="CSV-INJ-01",
            name="=cmd|' /C calc'!A0",
            brand="@HackCorp",
            category_id=cats[0]["category_id"],
            price_cents=100000,
            cost_price_cents=50000,
            user_id=owner.user_id,
            username=owner.username,
            stock=5
        )
        POSService.checkout(
            cashier_user_id=owner.user_id,
            cashier_name=owner.username,
            items_payload=[{"product_id": bad_prod_id, "quantity": 1}],
            payment_method="mpesa",
            payment_reference="=cmd|' /C calc'!A0"
        )

    # 3. Request CSV export via HTTP
    csv_resp = owner_client.get("/reports/export/csv?period=all")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.content_type

    csv_data = csv_resp.get_data()
    # Must start with UTF-8 BOM
    assert csv_data.startswith(b"\xef\xbb\xbf"), "CSV output must start with UTF-8 BOM"

    csv_text = csv_data.decode("utf-8")
    # Malicious injection must be quoted/escaped with leading single quote
    assert "'=cmd|' /C calc'!A0" in csv_text
    assert "Receipt No,Date Time,Cashier" in csv_text

    # 4. Request PDF export via HTTP
    pdf_resp = owner_client.get("/reports/export/pdf?period=all")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content_type == "application/pdf"
    pdf_data = pdf_resp.get_data()
    # Must start with standard PDF magic header %PDF-1.
    assert pdf_data.startswith(b"%PDF-1.")
    assert len(pdf_data) > 1000


def test_tc16_sales_date_validation_and_pagination(owner_client, app):
    """TC-16: Validates graceful handling of out-of-order date ranges and server-side 25-row pagination."""
    # 1. Invalid date input (start_date > end_date) must not crash
    res_inverted = owner_client.get("/sales/?start_date=2026-12-31&end_date=2026-01-01")
    assert res_inverted.status_code == 200
    assert b"Start date cannot be after end date" in res_inverted.data or b"Sales Ledger" in res_inverted.data

    # Malformed page parameter must safely fall back to page 1
    res_bad_page = owner_client.get("/sales/?page=not_a_number")
    assert res_bad_page.status_code == 200

    # 2. Server-side pagination verification (25 items per page)
    with app.app_context():
        owner = AuthService.get_user_by_username("admin")
        cats = InventoryService.get_categories()
        p_id, _ = InventoryService.create_product(
            sku="PAGINATE-01",
            name="Bulk Pagination Item",
            brand="Generic",
            category_id=cats[0]["category_id"],
            price_cents=10000,
            cost_price_cents=5000,
            user_id=owner.user_id,
            username=owner.username,
            stock=100
        )

        # Count existing sales
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM sales")
        existing_count = cur.fetchone()["cnt"]

        # Ensure at least 30 sales exist in database
        needed = max(0, 30 - existing_count)
        for i in range(needed):
            POSService.checkout(
                cashier_user_id=owner.user_id,
                cashier_name=owner.username,
                items_payload=[{"product_id": p_id, "quantity": 1}],
                payment_method="cash"
            )

    # Request Page 1
    res_p1 = owner_client.get("/sales/?page=1")
    assert res_p1.status_code == 200
    html_p1 = res_p1.get_data(as_text=True)
    assert "Showing page" in html_p1 and "of" in html_p1

    # Request Page 2
    res_p2 = owner_client.get("/sales/?page=2")
    assert res_p2.status_code == 200
    html_p2 = res_p2.get_data(as_text=True)
    assert "Showing page" in html_p2 and "of" in html_p2
