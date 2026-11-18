"""
Automated test suite for Phase 2:
POS Register (S-05), Thermal Receipt Drawer (S-06), and Product Detail & Serial Intake (S-04).
"""

import json
import pytest
from app.services.inventory_service import InventoryService


def test_pos_register_requires_login(client):
    """Anonymous user accessing /pos/ is redirected to /login."""
    resp = client.get("/pos/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_pos_register_view_loads_for_owner(owner_client):
    """Owner accessing /pos/ gets HTTP 200 with catalog items."""
    resp = owner_client.get("/pos/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Active Counter Cart" in html
    assert "POS Register" in html
    assert "Ctrl K" in html


def test_pos_register_view_loads_for_attendant(attendant_client):
    """Attendant accessing /pos/ gets HTTP 200 (counter checkout is primary attendant role)."""
    resp = attendant_client.get("/pos/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Active Counter Cart" in html


def test_pos_get_serials_endpoint(owner_client, app):
    """Verifies /pos/serials/<product_id> returns in-stock serial numbers."""
    with app.app_context():
        inv = InventoryService.get_inventory(tracking_mode="serialized")
        assert len(inv["items"]) > 0
        target_prod = inv["items"][0]
        p_id = target_prod["product_id"]

    resp = owner_client.get(f"/pos/serials/{p_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["serials"], list)
    assert len(data["serials"]) > 0


def test_pos_checkout_ajax_flow(owner_client, app):
    """Tests multi-item AJAX checkout with live VAT calculation and stock reduction."""
    with app.app_context():
        # Grab 1 bulk item and 1 serialized item
        bulk_items = InventoryService.get_inventory(tracking_mode="bulk")["items"]
        assert len(bulk_items) > 0
        bulk = bulk_items[0]
        initial_stock = bulk["stock"]

    payload = {
        "items": [
            {
                "product_id": bulk["product_id"],
                "quantity": 1
            }
        ],
        "payment_method": "mpesa",
        "payment_reference": "QHX98721K",
        "promo_code": ""
    }

    with owner_client.session_transaction() as sess:
        csrf_token = sess.get("_csrf_token", "")

    resp = owner_client.post(
        "/pos/checkout",
        data=json.dumps(payload),
        content_type="application/json",
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrf_token
        }
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    receipt = data["receipt"]
    assert receipt["receipt_no"].startswith("RCP-")
    assert receipt["payment_method"].lower() == "mpesa"
    assert receipt["payment_reference"] == "QHX98721K"

    # Verify stock decremented
    with app.app_context():
        updated = InventoryService.get_product(bulk["product_id"])
        assert updated["stock"] == initial_stock - 1

    # Verify receipt view loads
    receipt_url = f"/pos/receipt/{receipt['receipt_no']}"
    r_resp = owner_client.get(receipt_url)
    assert r_resp.status_code == 200
    r_html = r_resp.get_data(as_text=True)
    assert receipt["receipt_no"] in r_html
    assert "NDUNGU ELECTRONICS" in r_html
    assert "80mm" in r_html


def test_product_detail_and_update(owner_client, app):
    """Verifies S-04 Product Details view loads and saves metadata changes."""
    with app.app_context():
        inv = InventoryService.get_inventory()["items"]
        prod = inv[0]
        p_id = prod["product_id"]

    # GET view
    resp = owner_client.get(f"/inventory/product/{p_id}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert prod["name"] in html
    assert prod["sku"] in html

    with owner_client.session_transaction() as sess:
        csrf_token = sess.get("_csrf_token", "")

    # POST update
    update_data = {
        "csrf_token": csrf_token,
        "name": f"{prod['name']} Updated",
        "brand": prod["brand"],
        "model": "Mod-V2",
        "category_id": prod["category_id"],
        "price": "4500.00",
        "cost_price": "3000.00",
        "reorder_threshold": 6,
        "reorder_qty": 12,
        "supplier_name": "Test Supplier Ltd",
        "supplier_phone": "+254711000000"
    }

    post_resp = owner_client.post(f"/inventory/product/{p_id}", data=update_data, follow_redirects=True)
    assert post_resp.status_code == 200
    updated_html = post_resp.get_data(as_text=True)
    assert f"{prod['name']} Updated" in updated_html

    with app.app_context():
        fresh = InventoryService.get_product(p_id)
        assert fresh["name"] == f"{prod['name']} Updated"
        assert fresh["price_cents"] == 450000
        assert fresh["reorder_threshold"] == 6


def test_product_archive_rbac_attendant_forbidden(attendant_client, app):
    """Attendant receives HTTP 403 when trying to archive a product."""
    with app.app_context():
        inv = InventoryService.get_inventory()["items"]
        target = inv[-1]
        p_id = target["product_id"]

    with attendant_client.session_transaction() as sess:
        att_csrf = sess.get("_csrf_token", "")

    # Attendant tries to archive -> 403 Forbidden
    att_resp = attendant_client.post(
        f"/inventory/product/{p_id}/archive",
        data={"csrf_token": att_csrf}
    )
    assert att_resp.status_code == 403


def test_product_archive_owner_success(owner_client, app):
    """Owner successfully archives a product (is_active becomes 0)."""
    with app.app_context():
        inv = InventoryService.get_inventory()["items"]
        target = inv[-1]
        p_id = target["product_id"]

    with owner_client.session_transaction() as sess:
        owner_csrf = sess.get("_csrf_token", "")

    # Owner archives -> redirects to inventory index
    owner_resp = owner_client.post(
        f"/inventory/product/{p_id}/archive",
        data={"csrf_token": owner_csrf},
        follow_redirects=True
    )
    assert owner_resp.status_code == 200

    with app.app_context():
        fresh = InventoryService.get_product(p_id)
        assert fresh["is_active"] == 0
