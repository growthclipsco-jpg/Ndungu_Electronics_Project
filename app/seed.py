"""
Database seeder with dynamic relative dates.
Ensures Ndungu Electronics IMS boots with live telemetry,
preventing dead reports or 'KES 0' default dashboard metrics.
"""

from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app.db import get_db, transaction
from app.domain.product import normalize_sku


def seed_database(reset: bool = False, db=None):
    """Populates database with relative-date operational records."""
    conn = db or get_db()

    with transaction(conn) as tx:
        if reset:
            tx.execute("DELETE FROM auth_events")
            tx.execute("DELETE FROM stock_movements")
            tx.execute("DELETE FROM product_serials")
            tx.execute("DELETE FROM sale_items")
            tx.execute("DELETE FROM sales")
            tx.execute("DELETE FROM promotions")
            tx.execute("DELETE FROM products")
            tx.execute("DELETE FROM categories")
            tx.execute("DELETE FROM invite_tokens")
            tx.execute("DELETE FROM users")

        # Check if already seeded
        cursor = tx.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM users")
        if cursor.fetchone()["cnt"] > 0:
            return  # Already seeded

        # 1. Users
        pw_owner = generate_password_hash("NdunguAdmin2026!", method="scrypt")
        pw_attendant = generate_password_hash("NdunguAttendant2026!", method="scrypt")

        cur_owner = tx.execute(
            """
            INSERT INTO users (username, full_name, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            ("admin", "Augustin Ndungu (Owner)", pw_owner, "owner")
        )
        owner_id = cur_owner.lastrowid

        cur_att = tx.execute(
            """
            INSERT INTO users (username, full_name, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            ("attendant1", "Grace Wambui (Senior Cashier)", pw_attendant, "attendant")
        )
        attendant_id = cur_att.lastrowid

        # 2. Categories
        categories = [
            "Smartphones & Tablets",
            "Smart TVs & Home Entertainment",
            "Laptops & Computing",
            "Audio & Sound Systems",
            "Power, Solar & Inverters",
            "Cables & Charging Accessories"
        ]
        cat_ids = {}
        for cat_name in categories:
            cur_cat = tx.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
            cat_ids[cat_name] = cur_cat.lastrowid

        # 3. Products (Hybrid Tracking: bulk accessories vs serialized devices)
        # Prices in integer cents: 1 KES = 100 cents
        products_data = [
            # Serialized
            ("SAMS-A15-BLU", "Samsung Galaxy A15 128GB", "Samsung", "SM-A155F", "Smartphones & Tablets", "serialized", 1750000, 2250000, 14, 5, 10, "Afritech Nairobi", "+254711000111"),
            ("IPHONE-15-128", "Apple iPhone 15 128GB Black", "Apple", "A3090", "Smartphones & Tablets", "serialized", 9500000, 11800000, 4, 3, 5, "Alpha Distributors", "+254722000222"),
            ("TCL-55-4K", "TCL 55-inch 4K Google TV", "TCL", "55P635", "Smart TVs & Home Entertainment", "serialized", 4200000, 5250000, 8, 4, 6, "Digital Vision Thika", "+254733000333"),
            ("SONY-BRAV-65", "Sony Bravia 65-inch OLED 4K", "Sony", "XR-65A80L", "Smart TVs & Home Entertainment", "serialized", 18500000, 22900000, 2, 2, 3, "Sony Kenya", "+254700000444"),
            ("HP-250-G9", "HP 250 G9 Core i5 8GB 512GB", "HP", "250-G9", "Laptops & Computing", "serialized", 5100000, 6490000, 6, 3, 5, "Compute Kenya", "+254711222333"),
            ("JBL-PARTY-310", "JBL PartyBox 310 Bluetooth", "JBL", "PARTYBOX310", "Audio & Sound Systems", "serialized", 6200000, 7850000, 3, 2, 4, "SoundWave Ltd", "+254722333444"),

            # Bulk Accessories
            ("HDMI-BRAID-3M", "High-Speed HDMI 2.1 Cable 3m", "Generic", "", "Cables & Charging Accessories", "bulk", 45000, 120000, 45, 10, 25, "Crown Supplies", "+254744111222"),
            ("HDMI-BRAID-5M", "High-Speed HDMI 2.1 Cable 5m", "Generic", "", "Cables & Charging Accessories", "bulk", 65000, 160000, 32, 10, 20, "Crown Supplies", "+254744111222"),
            ("ANKER-20W-PD", "Anker PowerPort III 20W USB-C", "Anker", "A2149", "Cables & Charging Accessories", "bulk", 120000, 240000, 28, 8, 20, "Anker East Africa", "+254755111333"),
            ("ORAI-OPB-20K", "Oraimo 20000mAh Toast 10 PowerBank", "Oraimo", "OPB-P204DN", "Power, Solar & Inverters", "bulk", 185000, 320000, 19, 5, 15, "Oraimo Kenya", "+254766222444"),
            ("SOLAR-INVT-1KVA", "Felicity 1KVA Hybrid Solar Inverter", "Felicity", "FL-IVPS1012", "Power, Solar & Inverters", "bulk", 2400000, 3150000, 3, 2, 4, "GreenPower Thika", "+254777333555")
        ]

        prod_ids = {}
        for (sku, name, brand, model, cat_name, tracking, cost_c, price_c, stock, reorder_t, reorder_q, supp_name, supp_phone) in products_data:
            sku_norm = normalize_sku(sku)
            cat_id = cat_ids[cat_name]
            cur_prod = tx.execute(
                """
                INSERT INTO products (
                    sku, sku_normalized, name, brand, model, category_id,
                    tracking_mode, cost_price_cents, price_cents, stock,
                    reorder_threshold, reorder_qty, supplier_name, supplier_phone,
                    created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sku, sku_norm, name, brand, model, cat_id, tracking, cost_c, price_c, stock, reorder_t, reorder_q, supp_name, supp_phone, owner_id)
            )
            prod_id = cur_prod.lastrowid
            prod_ids[sku] = (prod_id, price_c, cost_c, name, brand, cat_name, tracking)

            # Record initial stock movement
            tx.execute(
                """
                INSERT INTO stock_movements (
                    product_id, sku_snapshot, product_name_snapshot, user_id,
                    username_snapshot, movement_type, qty_delta, stock_before,
                    stock_after, note
                ) VALUES (?, ?, ?, ?, ?, 'initial', ?, 0, ?, 'Initial inventory baseline')
                """,
                (prod_id, sku, name, owner_id, "admin", stock, stock)
            )

            # If serialized, seed individual serial numbers
            if tracking == "serialized":
                for idx in range(1, stock + 1):
                    s_no = f"SN-{sku_norm}-{idx:04d}"
                    tx.execute(
                        """
                        INSERT INTO product_serials (product_id, serial_no, serial_normalized, status)
                        VALUES (?, ?, ?, 'in_stock')
                        """,
                        (prod_id, s_no, s_no)
                    )

        # 4. Relative-Date Promotions
        now = datetime.now()
        promo_start = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        promo_end = (now + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

        sams_id = prod_ids["SAMS-A15-BLU"][0]
        cur_promo = tx.execute(
            """
            INSERT INTO promotions (
                code, name, scope, target_product_id, discount_type,
                discount_value, priority, starts_at, ends_at, created_by
            ) VALUES (?, ?, 'product', ?, 'fixed_cents', 150000, 10, ?, ?, ?)
            """,
            ("SAMSALE15", "Samsung Galaxy A15 Special Discount", sams_id, promo_start, promo_end, owner_id)
        )
        promo_id = cur_promo.lastrowid

        # 5. Relative-Date Completed Sales (Today, Yesterday, 3 Days Ago)
        sales_schedule = [
            (now, "RCP-2026-0001", "cash", [("SAMS-A15-BLU", 1, "SN-SAMSA15BLU-0001", promo_id, 150000), ("ANKER-20W-PD", 1, "", None, 0)]),
            (now - timedelta(days=1), "RCP-2026-0002", "mpesa", [("TCL-55-4K", 1, "SN-TCL554K-0001", None, 0), ("HDMI-BRAID-3M", 2, "", None, 0)]),
            (now - timedelta(days=3), "RCP-2026-0003", "mpesa", [("ORAI-OPB-20K", 2, "", None, 0), ("HDMI-BRAID-5M", 1, "", None, 0)])
        ]

        for sale_time, rcp_no, pay_method, line_items in sales_schedule:
            sale_date_str = sale_time.strftime("%Y-%m-%d %H:%M:%S")

            # Calculate totals
            subtotal = 0
            discount = 0
            for sku, qty, serial, p_id, disc in line_items:
                p_id_db, unit_p, cost_p, p_name, brand, cat, tracking = prod_ids[sku]
                subtotal += unit_p * qty
                discount += disc

            disc_sub = max(0, subtotal - discount)
            # +16% VAT on post-discount subtotal
            tax = int(round(disc_sub * 0.16))
            total = disc_sub + tax

            cur_sale = tx.execute(
                """
                INSERT INTO sales (
                    receipt_no, user_id, cashier_snapshot, payment_method,
                    subtotal_cents, discount_cents, tax_cents, total_cents,
                    sale_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rcp_no, attendant_id, "Grace Wambui (Senior Cashier)", pay_method, subtotal, discount, tax, total, sale_date_str)
            )
            sale_id = cur_sale.lastrowid

            for sku, qty, serial, p_id_promo, disc in line_items:
                p_id_db, unit_p, cost_p, p_name, brand, cat, tracking = prod_ids[sku]
                line_total = max(0, (unit_p * qty) - disc)
                cur_item = tx.execute(
                    """
                    INSERT INTO sale_items (
                        sale_id, product_id, sku_snapshot, product_name_snapshot,
                        brand_snapshot, category_snapshot, serial_no_snapshot,
                        quantity, unit_price_cents, cost_price_cents, promo_id,
                        discount_cents, line_total_cents
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sale_id, p_id_db, sku, p_name, brand, cat, serial, qty, unit_p, cost_p, p_id_promo, disc, line_total)
                )
                sale_item_id = cur_item.lastrowid

                # Update serial status if serialized
                if serial:
                    tx.execute(
                        """
                        UPDATE product_serials
                        SET status = 'sold', sale_item_id = ?, sold_at = ?
                        WHERE serial_no = ?
                        """,
                        (sale_item_id, sale_date_str, serial)
                    )
