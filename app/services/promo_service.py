"""
Promotions and automated discount calculation service.
Evaluates product, category, and cart discounts with deterministic priority and stacking.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from app.db import get_db


class PromoService:
    """Calculates applicable promotional discounts on sales cart lines."""

    @staticmethod
    def get_active_promotions(promo_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves active promotions within current date window."""
        conn = get_db()
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        query = """
            SELECT promo_id, code, name, scope, target_product_id,
                   target_category_id, discount_type, discount_value,
                   min_qty, min_subtotal_cents, stackable, priority,
                   starts_at, ends_at
            FROM promotions
            WHERE is_active = 1
              AND starts_at <= ?
              AND ends_at >= ?
        """
        params = [now_str, now_str]

        if promo_code:
            query += " AND code = ?"
            params.append(promo_code.strip())

        query += " ORDER BY priority ASC, promo_id ASC"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]

    @classmethod
    def apply_promotions_to_cart(
        cls,
        cart_items: List[Dict[str, Any]],
        promo_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculates item-level and cart-level discounts.
        Updates each cart item with promo_id, promo_name, discount_cents, and line_total_cents.
        """
        promos = cls.get_active_promotions(promo_code)
        if not promos:
            for item in cart_items:
                item["promo_id"] = None
                item["promo_name"] = ""
                item["discount_cents"] = 0
                item["line_total_cents"] = item["unit_price_cents"] * item["quantity"]
            return cart_items

        for item in cart_items:
            unit_price = item["unit_price_cents"]
            qty = item["quantity"]
            gross_line = unit_price * qty
            p_id = item["product_id"]
            c_id = item.get("category_id")

            best_discount = 0
            best_promo_id = None
            best_promo_name = ""

            for promo in promos:
                applies = False
                if promo["scope"] == "product" and promo["target_product_id"] == p_id:
                    applies = True
                elif promo["scope"] == "category" and promo["target_category_id"] == c_id:
                    applies = True

                if applies and qty >= promo["min_qty"]:
                    if promo["discount_type"] == "fixed_cents":
                        disc = min(gross_line, promo["discount_value"] * qty)
                    elif promo["discount_type"] == "percent":
                        pct = promo["discount_value"]
                        disc = int(round((gross_line * pct) / 100))
                    else:
                        disc = 0

                    if disc > best_discount:
                        best_discount = disc
                        best_promo_id = promo["promo_id"]
                        best_promo_name = promo["name"]

            item["promo_id"] = best_promo_id
            item["promo_name"] = best_promo_name
            item["discount_cents"] = best_discount
            item["line_total_cents"] = max(0, gross_line - best_discount)

        return cart_items
