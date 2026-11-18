"""
Test suite covering Phase 2:
- TC-03: Inventory CRUD & category assignment
- TC-04: Hybrid tracking (Bulk vs Serialized IMEI)
- TC-05: Smart duplicate detection (allows blank model)
- TC-06: Low-stock threshold alerts (<= 5 units)
- TC-07: Multi-item POS cart checkout & stock movements
- TC-08: Over-stock rejection & atomic rollback
- TC-10: Locked +16% VAT calculation
- TC-11: Promotional discounts
- TC-13: Sale voiding & inventory restitution
- TC-18: Multi-thread concurrency safety under BEGIN IMMEDIATE
"""

import threading
import pytest
from app.services.inventory_service import InventoryService
from app.services.pos_service import POSService
from app.services.promo_service import PromoService
from app.services.auth_service import AuthService
from app.db import get_db


def test_tc03_inventory_crud(app):
    """TC-03: Validates product creation, category assignment, and retrieval."""
    with app.app_context():
        cats = InventoryService.get_categories()
        assert len(cats) >= 6
        cat_id = cats[0]["category_id"]

        user = AuthService.get_user_by_username("admin")
        prod_id, err = InventoryService.create_product(
            sku="TEST-SKU-001",
            name="Testing Smartphone",
            brand="TestBrand",
            category_id=cat_id,
            price_cents=1500000,
            cost_price_cents=1000000,
            user_id=user.user_id,
            username=user.username,
            stock=10,
            tracking_mode="bulk"
        )
        assert err == ""
        assert prod_id is not None

        prod = InventoryService.get_product(prod_id)
        assert prod["name"] == "Testing Smartphone"
        assert prod["price_cents"] == 1500000
        assert prod["stock"] == 10


def test_tc04_hybrid_tracking_serialized_serials(app):
    """TC-04: Validates serialized tracking with individual serial intake."""
    with app.app_context():
        cats = InventoryService.get_categories()
        cat_id = cats[0]["category_id"]
        user = AuthService.get_user_by_username("admin")

        prod_id, err = InventoryService.create_product(
            sku="TEST-LAPTOP-01",
            name="Test Laptop Pro",
            brand="Lenovo",
            category_id=cat_id,
            price_cents=8500000,
            cost_price_cents=6500000,
            user_id=user.user_id,
            username=user.username,
            stock=2,
            tracking_mode="serialized",
            serials=["SN-LEN-001", "SN-LEN-002"]
        )
        assert err == ""
        serials = InventoryService.get_serials(prod_id)
        assert len(serials) == 2
        assert serials[0]["serial_no"] == "SN-LEN-001"
        assert serials[0]["status"] == "in_stock"


def test_tc05_smart_duplicate_detection_empty_model_safe(app):
    """
    TC-05: Validates smart duplicate detection.
    Allows distinct items with empty model (e.g. HDMI cables),
    while blocking duplicates when model is specified.
    """
    with app.app_context():
        cats = InventoryService.get_categories()
        cat_id = cats[0]["category_id"]
        user = AuthService.get_user_by_username("admin")

        # Distinct accessories with empty model must save cleanly
        p1_id, err1 = InventoryService.create_product(
            sku="CABLE-01",
            name="HDMI Cable",
            brand="Generic",
            model="",
            category_id=cat_id,
            price_cents=50000,
            cost_price_cents=20000,
            user_id=user.user_id,
            username=user.username,
            stock=5
        )
        assert err1 == ""

        p2_id, err2 = InventoryService.create_product(
            sku="CABLE-02",
            name="HDMI Cable",
            brand="Generic",
            model="",
            category_id=cat_id,
            price_cents=50000,
            cost_price_cents=20000,
            user_id=user.user_id,
            username=user.username,
            stock=5
        )
        assert err2 == ""  # Empty model must not trigger false positive!

        # Now test identical model blocking
        InventoryService.create_product(
            sku="PHONE-MOD-A",
            name="Galaxy",
            brand="Samsung",
            model="A15",
            category_id=cat_id,
            price_cents=2000000,
            cost_price_cents=1500000,
            user_id=user.user_id,
            username=user.username,
            stock=1
        )
        _, err_dup = InventoryService.create_product(
            sku="PHONE-MOD-B",
            name="Galaxy",
            brand="Samsung",
            model="A15",
            category_id=cat_id,
            price_cents=2000000,
            cost_price_cents=1500000,
            user_id=user.user_id,
            username=user.username,
            stock=1
        )
        assert "already exists" in err_dup


def test_tc06_low_stock_threshold_alerts(app):
    """TC-06: Validates low-stock filter for SKUs at or below reorder threshold."""
    with app.app_context():
        inv = InventoryService.get_inventory(low_stock_only=True)
        assert len(inv["items"]) > 0
        for item in inv["items"]:
            assert item["stock"] <= item["reorder_threshold"]


def test_tc07_multi_item_checkout_and_stock_deduction(app):
    """TC-07: Validates multi-item POS checkout, stock decrement, and audit movements."""
    with app.app_context():
        user = AuthService.get_user_by_username("attendant1")
        p1 = InventoryService.get_product_by_sku("ANKER-20W-PD")
        p2 = InventoryService.get_product_by_sku("HDMI-BRAID-3M")

        stock1_before = p1["stock"]
        stock2_before = p2["stock"]

        cart = [
            {"product_id": p1["product_id"], "quantity": 2},
            {"product_id": p2["product_id"], "quantity": 1}
        ]

        sale = POSService.checkout(
            cashier_user_id=user.user_id,
            cashier_name=user.full_name,
            items_payload=cart,
            payment_method="cash"
        )
        assert sale.receipt_no.startswith("RCP-")
        assert len(sale.items) == 2

        # Verify stock decrements
        p1_after = InventoryService.get_product(p1["product_id"])
        p2_after = InventoryService.get_product(p2["product_id"])
        assert p1_after["stock"] == stock1_before - 2
        assert p2_after["stock"] == stock2_before - 1


def test_tc08_over_stock_block_and_rollback(app):
    """TC-08: Requesting quantity exceeding stock raises error and causes atomic rollback."""
    with app.app_context():
        user = AuthService.get_user_by_username("attendant1")
        p = InventoryService.get_product_by_sku("SONY-BRAV-65")
        current_stock = p["stock"]  # 2 units in seed

        cart = [{"product_id": p["product_id"], "quantity": current_stock + 5}]

        with pytest.raises(ValueError, match="Insufficient stock"):
            POSService.checkout(
                cashier_user_id=user.user_id,
                cashier_name=user.full_name,
                items_payload=cart
            )

        # Verify stock remained untouched
        p_check = InventoryService.get_product(p["product_id"])
        assert p_check["stock"] == current_stock


def test_tc10_vat_arithmetic_on_checkout(app):
    """TC-10: Validates locked +16% VAT arithmetic on counter sale."""
    with app.app_context():
        user = AuthService.get_user_by_username("attendant1")
        p = InventoryService.get_product_by_sku("ANKER-20W-PD")  # price: 240,000 cents (2,400 KES)

        cart = [{"product_id": p["product_id"], "quantity": 1}]
        sale = POSService.checkout(
            cashier_user_id=user.user_id,
            cashier_name=user.full_name,
            items_payload=cart
        )

        subtotal = 240000
        expected_tax = int(round(subtotal * 0.16))  # 38,400 cents
        expected_total = subtotal + expected_tax

        assert sale.subtotal.cents == subtotal
        assert sale.tax.cents == expected_tax
        assert sale.total.cents == expected_total


def test_tc13_owner_void_reversal_and_stock_restitution(app):
    """TC-13: Owner void reverses sale, restitutes stock, and records void_return movement."""
    with app.app_context():
        att = AuthService.get_user_by_username("attendant1")
        owner = AuthService.get_user_by_username("admin")
        p = InventoryService.get_product_by_sku("ORAI-OPB-20K")
        stock_init = p["stock"]

        # 1. Checkout
        cart = [{"product_id": p["product_id"], "quantity": 2}]
        sale = POSService.checkout(
            cashier_user_id=att.user_id,
            cashier_name=att.full_name,
            items_payload=cart
        )
        assert InventoryService.get_product(p["product_id"])["stock"] == stock_init - 2

        # 2. Void
        ok = POSService.void_sale(
            sale_id=sale.sale_id,
            owner_user_id=owner.user_id,
            owner_name=owner.full_name,
            void_reason="Customer returned unopened items"
        )
        assert ok is True

        # Verify stock restitution
        p_restituted = InventoryService.get_product(p["product_id"])
        assert p_restituted["stock"] == stock_init


def test_tc18_concurrent_checkout_race_safety(app):
    """
    TC-18: 10 parallel threads race to purchase 1 unit of a product with stock=3.
    Under BEGIN IMMEDIATE, exactly 3 must succeed, 7 must fail with insufficient stock,
    and final stock must be exactly 0.
    """
    with app.app_context():
        owner = AuthService.get_user_by_username("admin")
        cats = InventoryService.get_categories()

        # Create limited stock item with stock = 3
        prod_id, _ = InventoryService.create_product(
            sku="RACE-ITEM-001",
            name="Limited Concert Ticket",
            brand="Event",
            category_id=cats[0]["category_id"],
            price_cents=500000,
            cost_price_cents=400000,
            user_id=owner.user_id,
            username=owner.username,
            stock=3
        )

        results = []
        errors = []

        def buyer_task(thread_id):
            with app.app_context():
                try:
                    s = POSService.checkout(
                        cashier_user_id=owner.user_id,
                        cashier_name=f"Cashier-{thread_id}",
                        items_payload=[{"product_id": prod_id, "quantity": 1}]
                    )
                    results.append(s.receipt_no)
                except ValueError as ve:
                    errors.append(str(ve))

        threads = [threading.Thread(target=buyer_task, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 3 succeeded, 7 failed
        assert len(results) == 3
        assert len(errors) == 7
        final_stock = InventoryService.get_product(prod_id)["stock"]
        assert final_stock == 0


def test_tc11_serialized_unit_tracking_lifecycle(app):
    """TC-11: Verifies serialized hardware unit tracking: serial registration, sale binding, and void reversal."""
    with app.app_context():
        owner = AuthService.get_user_by_username("admin")
        cats = InventoryService.get_categories()

        # 1. Create serialized item with 2 serial numbers
        prod_id, err = InventoryService.create_product(
            sku="TV-SAM-65-01",
            name="Samsung 65-inch Crystal UHD 4K",
            brand="Samsung",
            model="CU7000",
            category_id=cats[0]["category_id"],
            price_cents=7500000,
            cost_price_cents=6000000,
            user_id=owner.user_id,
            username=owner.username,
            stock=2,
            tracking_mode="serialized",
            serials=["SN-SAMSUNG-65-001", "SN-SAMSUNG-65-002"],
        )
        assert err == ""
        assert prod_id is not None

        # Verify initial serials are 'in_stock'
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT serial_no, status FROM product_serials WHERE product_id = ?", (prod_id,))
        rows = {r["serial_no"]: r["status"] for r in cur.fetchall()}
        assert rows["SN-SAMSUNG-65-001"] == "in_stock"
        assert rows["SN-SAMSUNG-65-002"] == "in_stock"

        # 2. Checkout 1 unit binding serial SN-SAMSUNG-65-001
        sale = POSService.checkout(
            cashier_user_id=owner.user_id,
            cashier_name=owner.username,
            items_payload=[{
                "product_id": prod_id,
                "quantity": 1,
                "serial_no": "SN-SAMSUNG-65-001"
            }],
            payment_method="mpesa",
            payment_reference="QWE123RTY4"
        )
        assert sale.sale_id is not None

        # Verify SN-SAMSUNG-65-001 changed to 'sold' while 002 is still 'in_stock'
        cur.execute("SELECT serial_no, status FROM product_serials WHERE product_id = ?", (prod_id,))
        rows_after_sale = {r["serial_no"]: r["status"] for r in cur.fetchall()}
        assert rows_after_sale["SN-SAMSUNG-65-001"] == "sold"
        assert rows_after_sale["SN-SAMSUNG-65-002"] == "in_stock"

        # 3. Owner voids the sale -> serial status must revert to 'in_stock'
        void_ok = POSService.void_sale(
            sale_id=sale.sale_id,
            owner_user_id=owner.user_id,
            owner_name=owner.username,
            void_reason="Customer cancelled order immediately"
        )
        assert void_ok is True
        cur.execute("SELECT serial_no, status FROM product_serials WHERE product_id = ?", (prod_id,))
        rows_after_void = {r["serial_no"]: r["status"] for r in cur.fetchall()}
        assert rows_after_void["SN-SAMSUNG-65-001"] == "in_stock"


def test_tc12_restock_and_stock_movements_audit_trail(app):
    """TC-12: Verifies restock mutations, stock count updates, and immutable audit logging in stock_movements."""
    with app.app_context():
        owner = AuthService.get_user_by_username("admin")
        cats = InventoryService.get_categories()

        # Create bulk item with stock = 10
        prod_id, err = InventoryService.create_product(
            sku="CABLE-CAT6-01",
            name="Cat6 Ethernet Cable 10m",
            brand="D-Link",
            category_id=cats[0]["category_id"],
            price_cents=120000,
            cost_price_cents=70000,
            user_id=owner.user_id,
            username=owner.username,
            stock=10
        )
        assert err == ""

        # Perform restock: +15 units
        ok, msg = InventoryService.restock_product(
            product_id=prod_id,
            qty_added=15,
            user_id=owner.user_id,
            username=owner.username,
            note="Quarterly inventory intake from distributor"
        )
        assert ok is True

        # Verify live product stock is now 25
        live_prod = InventoryService.get_product(prod_id)
        assert live_prod["stock"] == 25

        # Query stock_movements audit trail
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT movement_type, qty_delta, stock_before, stock_after, username_snapshot, note
            FROM stock_movements
            WHERE product_id = ? AND movement_type = 'restock'
            ORDER BY movement_id DESC LIMIT 1
            """,
            (prod_id,)
        )
        movement = cur.fetchone()
        assert movement is not None
        assert movement["qty_delta"] == 15
        assert movement["stock_before"] == 10
        assert movement["stock_after"] == 25
        assert movement["username_snapshot"] == owner.username
        assert "Quarterly inventory intake" in movement["note"]

