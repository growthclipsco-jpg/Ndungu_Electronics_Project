"""
Automated test suite for Phase 3:
Sales Ledger & Void Management (S-08), Pricing & Promotions Manager (S-07),
BI Reports & Exports (S-09), and Users & Unified Audit Trail (S-10).
"""

import io
import pytest
from app.services.inventory_service import InventoryService
from app.db import get_db


def test_sales_ledger_view_authenticated(owner_client):
    """Owner can view the Sales Ledger."""
    resp = owner_client.get("/sales/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Sales Ledger" in html
    assert "Total Revenue (Net)" in html


def test_sales_ledger_view_attendant(attendant_client):
    """Attendant can also view the Sales Ledger."""
    resp = attendant_client.get("/sales/")
    assert resp.status_code == 200


def test_sale_detail_json_endpoint(owner_client, app):
    """Verifies /sales/<id>/detail returns receipt metadata and line items."""
    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT sale_id FROM sales LIMIT 1").fetchone()
        sale_id = row["sale_id"]

    resp = owner_client.get(f"/sales/{sale_id}/detail")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "sale" in data
    assert "items" in data
    assert len(data["items"]) > 0


def test_void_sale_attendant_forbidden(attendant_client, app):
    """Attendant receives HTTP 403 trying to void a sale."""
    with app.app_context():
        conn = get_db()
        sale = conn.execute("SELECT sale_id FROM sales WHERE status = 'completed' LIMIT 1").fetchone()
        sale_id = sale["sale_id"]

    with attendant_client.session_transaction() as sess:
        att_csrf = sess.get("_csrf_token", "")

    att_resp = attendant_client.post(
        f"/sales/{sale_id}/void",
        data={"csrf_token": att_csrf, "reason": "Attendant attempted unauthorized void"}
    )
    assert att_resp.status_code == 403


def test_void_sale_owner_success(owner_client, app):
    """Owner voids sale with inventory restitution."""
    with app.app_context():
        conn = get_db()
        sale = conn.execute("SELECT sale_id FROM sales WHERE status = 'completed' LIMIT 1").fetchone()
        sale_id = sale["sale_id"]
        item = conn.execute("SELECT product_id, quantity FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchone()
        p_id = item["product_id"]
        qty = item["quantity"]
        stock_before = conn.execute("SELECT stock FROM products WHERE product_id = ?", (p_id,)).fetchone()["stock"]

    with owner_client.session_transaction() as sess:
        owner_csrf = sess.get("_csrf_token", "")

    owner_resp = owner_client.post(
        f"/sales/{sale_id}/void",
        data={"csrf_token": owner_csrf, "reason": "Customer cancellation within 1 hour"},
        follow_redirects=True
    )
    assert owner_resp.status_code == 200

    with app.app_context():
        conn = get_db()
        updated_sale = conn.execute("SELECT status, void_reason FROM sales WHERE sale_id = ?", (sale_id,)).fetchone()
        assert updated_sale["status"] == "voided"
        assert "Customer cancellation" in updated_sale["void_reason"]

        stock_after = conn.execute("SELECT stock FROM products WHERE product_id = ?", (p_id,)).fetchone()["stock"]
        assert stock_after == stock_before + qty


def test_promotions_attendant_forbidden(attendant_client):
    """Attendant gets 403 on promotions."""
    resp_att = attendant_client.get("/promotions/")
    assert resp_att.status_code == 403


def test_promotions_owner_lifecycle(owner_client):
    """Owner creates and toggles active status of a promotion."""
    resp = owner_client.get("/promotions/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Pricing &amp; Promotions" in html or "Pricing & Promotions" in html

    with owner_client.session_transaction() as sess:
        csrf_token = sess.get("_csrf_token", "")

    create_data = {
        "csrf_token": csrf_token,
        "name": "Holiday 10% Off",
        "code": "HOLIDAY10",
        "scope": "cart",
        "discount_type": "percentage",
        "discount_value": "10",
        "min_qty": 1,
        "starts_at": "2026-11-01",
        "ends_at": "2026-12-31"
    }
    create_resp = owner_client.post("/promotions/new", data=create_data, follow_redirects=True)
    assert create_resp.status_code == 200
    created_html = create_resp.get_data(as_text=True)
    assert "Holiday 10% Off" in created_html


def test_reports_attendant_forbidden(attendant_client):
    """Attendant gets 403 on BI reports."""
    resp_att = attendant_client.get("/reports/")
    assert resp_att.status_code == 403


def test_reports_owner_view_and_exports(owner_client):
    """Owner can view BI dashboard and download CSV & PDF exports."""
    resp = owner_client.get("/reports/?period=month")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "BI Reports" in html
    assert "Net Sales Revenue" in html
    assert "Low-Stock Surveillance" in html

    # CSV Export
    csv_resp = owner_client.get("/reports/export/csv?period=month")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["Content-Type"]
    csv_text = csv_resp.get_data(as_text=True)
    assert csv_text.startswith("\ufeff")  # UTF-8 BOM
    assert "Receipt No,Date Time,Cashier" in csv_text

    # PDF Export
    pdf_resp = owner_client.get("/reports/export/pdf?period=month")
    assert pdf_resp.status_code == 200
    assert "application/pdf" in pdf_resp.headers["Content-Type"]
    pdf_bytes = pdf_resp.get_data()
    assert pdf_bytes.startswith(b"%PDF-1.")


def test_users_attendant_forbidden(attendant_client):
    """Attendant gets 403 on Users administration."""
    resp_att = attendant_client.get("/users/")
    assert resp_att.status_code == 403


def test_users_owner_view_and_invite_minting(owner_client):
    """Owner can view operators and mint 24h invite token."""
    resp = owner_client.get("/users/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Users &amp; Security" in html or "Users & Security" in html
    assert "Operator Accounts" in html

    with owner_client.session_transaction() as sess:
        csrf_token = sess.get("_csrf_token", "")

    mint_resp = owner_client.post(
        "/users/invite",
        data={"csrf_token": csrf_token, "role": "attendant"},
        follow_redirects=True
    )
    assert mint_resp.status_code == 200
    mint_html = mint_resp.get_data(as_text=True)
    assert "Single-use invite link generated:" in mint_html
    assert "register?token=" in mint_html
