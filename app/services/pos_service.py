"""
Point-of-Sale (POS) cashier checkout and sale voiding service.
Enforces atomic BEGIN IMMEDIATE transactions, live stock re-reads,
and locked +16% VAT arithmetic.
"""

from datetime import datetime
import secrets
from typing import List, Dict, Any, Tuple, Optional
from app.db import transaction, get_db
from app.domain.sale import Sale, SaleItem
from app.domain.money import calculate_vat
from app.services.promo_service import PromoService


class POSService:
    """Orchestrates multi-item checkout, serial assignment, and sale reversal."""

    @classmethod
    def checkout(
        cls,
        cashier_user_id: int,
        cashier_name: str,
        items_payload: List[Dict[str, Any]],
        payment_method: str = "cash",
        payment_reference: str = "",
        promo_code: Optional[str] = None
    ) -> Sale:
        """
        Executes atomic checkout transaction:
        1. BEGIN IMMEDIATE exclusive lock
        2. Re-read live stock, price, and active status inside lock
        3. Enforce requested <= available stock
        4. Apply promotions
        5. Calculate +16% VAT on post-discount subtotal
        6. Deduct stock and log stock_movements
        7. Insert immutable sales & sale_items records
        """
        if not items_payload:
            raise ValueError("Cart is empty. Please select at least one item.")

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
        receipt_no = f"RCP-{now.strftime('%Y%m%d')}-{secrets.token_hex(2).upper()}"

        with transaction() as tx:
            # 1. Fetch live product data inside transaction to avoid race conditions
            evaluated_items = []
            for item_in in items_payload:
                p_id = item_in["product_id"]
                qty = item_in["quantity"]
                serial_raw = item_in.get("serial_no")
                serial_requested = (serial_raw or "").strip()

                if qty <= 0:
                    raise ValueError(f"Invalid quantity {qty} for product ID {p_id}.")

                cur_p = tx.execute(
                    """
                    SELECT p.product_id, p.sku, p.name, p.brand, p.category_id,
                           p.tracking_mode, p.price_cents, p.cost_price_cents,
                           p.stock, p.is_active, c.name as category_name
                    FROM products p
                    JOIN categories c ON p.category_id = c.category_id
                    WHERE p.product_id = ?
                    """,
                    (p_id,)
                )
                prod = cur_p.fetchone()
                if not prod or not prod["is_active"]:
                    raise ValueError(f"Product ID {p_id} does not exist or has been archived.")

                if qty > prod["stock"]:
                    raise ValueError(
                        f"Insufficient stock for '{prod['name']}' [{prod['sku']}]. "
                        f"Requested {qty}, but only {prod['stock']} available."
                    )

                evaluated_items.append({
                    "product_id": prod["product_id"],
                    "sku": prod["sku"],
                    "name": prod["name"],
                    "brand": prod["brand"],
                    "category_id": prod["category_id"],
                    "category_name": prod["category_name"],
                    "tracking_mode": prod["tracking_mode"],
                    "unit_price_cents": prod["price_cents"],
                    "cost_price_cents": prod["cost_price_cents"],
                    "stock_before": prod["stock"],
                    "quantity": qty,
                    "serial_requested": serial_requested
                })

            # 2. Evaluate promotional discounts
            evaluated_items = PromoService.apply_promotions_to_cart(evaluated_items, promo_code)

            # 3. Calculate monetary totals
            gross_subtotal = sum(i["unit_price_cents"] * i["quantity"] for i in evaluated_items)
            total_discount = sum(i["discount_cents"] for i in evaluated_items)
            discounted_subtotal = max(0, gross_subtotal - total_discount)
            tax_cents = calculate_vat(discounted_subtotal)
            total_cents = discounted_subtotal + tax_cents

            # 4. Insert into sales
            cur_sale = tx.execute(
                """
                INSERT INTO sales (
                    receipt_no, user_id, cashier_snapshot, payment_method,
                    payment_reference, subtotal_cents, discount_cents,
                    tax_cents, total_cents, sale_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (receipt_no, cashier_user_id, cashier_name, payment_method,
                 payment_reference, gross_subtotal, total_discount, tax_cents,
                 total_cents, date_str)
            )
            sale_id = cur_sale.lastrowid

            # 5. Insert sale_items and deduct stock
            domain_sale_items = []
            for item in evaluated_items:
                p_id = item["product_id"]
                qty = item["quantity"]
                stock_after = item["stock_before"] - qty

                # Update live stock
                tx.execute(
                    """
                    UPDATE products
                    SET stock = ?, updated_at = datetime('now', 'localtime')
                    WHERE product_id = ?
                    """,
                    (stock_after, p_id)
                )

                # Log stock deduction
                tx.execute(
                    """
                    INSERT INTO stock_movements (
                        product_id, sku_snapshot, product_name_snapshot, user_id,
                        username_snapshot, movement_type, qty_delta, stock_before,
                        stock_after, reference_type, reference_id, note
                    ) VALUES (?, ?, ?, ?, ?, 'sale', ?, ?, ?, 'sale', ?, ?)
                    """,
                    (p_id, item["sku"], item["name"], cashier_user_id, cashier_name,
                     -qty, item["stock_before"], stock_after, sale_id, f"Sold via {receipt_no}")
                )

                # Handle Serial allocation if serialized
                assigned_serial = ""
                if item["tracking_mode"] == "serialized":
                    if item["serial_requested"]:
                        cur_s = tx.execute(
                            """
                            SELECT serial_id, serial_no
                            FROM product_serials
                            WHERE product_id = ? AND serial_no = ? AND status = 'in_stock'
                            """,
                            (p_id, item["serial_requested"])
                        )
                    else:
                        cur_s = tx.execute(
                            """
                            SELECT serial_id, serial_no
                            FROM product_serials
                            WHERE product_id = ? AND status = 'in_stock'
                            LIMIT 1
                            """,
                            (p_id,)
                        )
                    serial_row = cur_s.fetchone()
                    if not serial_row:
                        raise ValueError(f"No available in-stock serial number for serialized item [{item['sku']}].")
                    assigned_serial = serial_row["serial_no"]
                    serial_id = serial_row["serial_id"]

                cur_si = tx.execute(
                    """
                    INSERT INTO sale_items (
                        sale_id, product_id, sku_snapshot, product_name_snapshot,
                        brand_snapshot, category_snapshot, serial_no_snapshot,
                        quantity, unit_price_cents, cost_price_cents, promo_id,
                        promo_name_snapshot, discount_cents, line_total_cents
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sale_id, p_id, item["sku"], item["name"], item["brand"],
                     item["category_name"], assigned_serial, qty, item["unit_price_cents"],
                     item["cost_price_cents"], item["promo_id"], item["promo_name"],
                     item["discount_cents"], item["line_total_cents"])
                )
                sale_item_id = cur_si.lastrowid

                if assigned_serial:
                    tx.execute(
                        """
                        UPDATE product_serials
                        SET status = 'sold', sale_item_id = ?, sold_at = ?
                        WHERE serial_id = ?
                        """,
                        (sale_item_id, date_str, serial_id)
                    )

                domain_sale_items.append(
                    SaleItem(
                        product_id=p_id,
                        sku_snapshot=item["sku"],
                        product_name_snapshot=item["name"],
                        brand_snapshot=item["brand"],
                        category_snapshot=item["category_name"],
                        quantity=qty,
                        unit_price_cents=item["unit_price_cents"],
                        cost_price_cents=item["cost_price_cents"],
                        serial_no_snapshot=assigned_serial,
                        promo_id=item["promo_id"],
                        promo_name_snapshot=item["promo_name"],
                        discount_cents=item["discount_cents"]
                    )
                )

        return Sale(
            receipt_no=receipt_no,
            cashier_snapshot=cashier_name,
            items=domain_sale_items,
            payment_method=payment_method,
            payment_reference=payment_reference,
            user_id=cashier_user_id,
            sale_id=sale_id,
            sale_date=date_str
        )

    @classmethod
    def void_sale(cls, sale_id: int, owner_user_id: int, owner_name: str, void_reason: str) -> bool:
        """
        Reverses a completed sale:
        1. Enforces sale status is 'completed'
        2. Restitutes inventory stock for every line item
        3. Sets serialized units back to 'in_stock'
        4. Logs 'void_return' in stock_movements
        5. Updates sale status to 'voided'
        """
        if not void_reason.strip():
            raise ValueError("A formal reason is required to void a completed sale.")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with transaction() as tx:
            cur_s = tx.execute("SELECT * FROM sales WHERE sale_id = ?", (sale_id,))
            sale = cur_s.fetchone()
            if not sale:
                raise ValueError("Sale transaction not found.")
            if sale["status"] == "voided":
                raise ValueError("Sale transaction has already been voided.")

            # Fetch line items
            cur_items = tx.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,))
            items = cur_items.fetchall()

            for item in items:
                p_id = item["product_id"]
                qty = item["quantity"]

                if p_id:
                    cur_p = tx.execute("SELECT stock, sku, name FROM products WHERE product_id = ?", (p_id,))
                    prod = cur_p.fetchone()
                    if prod:
                        stock_before = prod["stock"]
                        stock_after = stock_before + qty

                        tx.execute(
                            "UPDATE products SET stock = ?, updated_at = datetime('now', 'localtime') WHERE product_id = ?",
                            (stock_after, p_id)
                        )

                        tx.execute(
                            """
                            INSERT INTO stock_movements (
                                product_id, sku_snapshot, product_name_snapshot, user_id,
                                username_snapshot, movement_type, qty_delta, stock_before,
                                stock_after, reference_type, reference_id, note
                            ) VALUES (?, ?, ?, ?, ?, 'void_return', ?, ?, ?, 'sale_void', ?, ?)
                            """,
                            (p_id, item["sku_snapshot"], item["product_name_snapshot"],
                             owner_user_id, owner_name, qty, stock_before, stock_after,
                             sale_id, f"Voided {sale['receipt_no']}: {void_reason}")
                        )

                # Reset Serial status
                if item["serial_no_snapshot"]:
                    tx.execute(
                        """
                        UPDATE product_serials
                        SET status = 'in_stock', sale_item_id = NULL, sold_at = NULL
                        WHERE serial_no = ?
                        """,
                        (item["serial_no_snapshot"],)
                    )

            # Mark sale as voided
            tx.execute(
                """
                UPDATE sales
                SET status = 'voided', void_reason = ?, voided_by = ?, voided_at = ?
                WHERE sale_id = ?
                """,
                (void_reason.strip(), owner_user_id, now_str, sale_id)
            )

        return True
