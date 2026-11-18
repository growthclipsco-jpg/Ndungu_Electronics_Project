"""
Sale and SaleItem domain models matching Milestone 2 Class Diagram (Fig 1.3.6).
Enforces locked VAT policy (+16% on discounted subtotal) and immutable snapshots.
"""

from typing import List, Optional, Dict, Any
from app.domain.money import Money, calculate_vat


class SaleItem:
    """Represents an individual line item in a customer purchase transaction."""

    def __init__(
        self,
        product_id: Optional[int],
        sku_snapshot: str,
        product_name_snapshot: str,
        brand_snapshot: str,
        category_snapshot: str,
        quantity: int,
        unit_price_cents: int,
        cost_price_cents: int = 0,
        serial_no_snapshot: str = "",
        promo_id: Optional[int] = None,
        promo_name_snapshot: str = "",
        discount_cents: int = 0
    ):
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if unit_price_cents < 0:
            raise ValueError("Unit price cannot be negative.")
        if discount_cents < 0:
            raise ValueError("Discount cannot be negative.")

        self.product_id = product_id
        self.sku_snapshot = sku_snapshot
        self.product_name_snapshot = product_name_snapshot
        self.brand_snapshot = brand_snapshot
        self.category_snapshot = category_snapshot
        self.quantity = quantity
        self.unit_price = Money(unit_price_cents)
        self.cost_price = Money(cost_price_cents)
        self.serial_no_snapshot = serial_no_snapshot.strip()
        self.promo_id = promo_id
        self.promo_name_snapshot = promo_name_snapshot
        self.discount = Money(discount_cents)

        raw_line = self.unit_price.cents * self.quantity
        self.line_total = Money(max(0, raw_line - self.discount.cents))


class Sale:
    """
    Represents a finalized counter sale in Ndungu Electronics POS register.
    Calculates subtotal, discounts, +16% VAT, and final total.
    """

    PAYMENT_CASH = "cash"
    PAYMENT_MPESA = "mpesa"
    PAYMENT_CARD = "card"

    STATUS_COMPLETED = "completed"
    STATUS_VOIDED = "voided"

    def __init__(
        self,
        receipt_no: str,
        cashier_snapshot: str,
        items: List[SaleItem],
        payment_method: str = PAYMENT_CASH,
        payment_reference: str = "",
        user_id: Optional[int] = None,
        sale_id: Optional[int] = None,
        sale_date: Optional[str] = None,
        status: str = STATUS_COMPLETED,
        void_reason: str = "",
        promo_summary: Optional[List[Dict[str, Any]]] = None
    ):
        if not items:
            raise ValueError("A sale must contain at least one item.")
        if payment_method not in (self.PAYMENT_CASH, self.PAYMENT_MPESA, self.PAYMENT_CARD):
            raise ValueError(f"Invalid payment method: {payment_method}")

        self.sale_id = sale_id
        self.receipt_no = receipt_no
        self.cashier_snapshot = cashier_snapshot
        self.items = items
        self.payment_method = payment_method
        self.payment_reference = (payment_reference or "").strip()
        self.user_id = user_id
        self.sale_date = sale_date
        self.status = status
        self.void_reason = void_reason
        self.promo_summary = promo_summary or []

        # Monetary Calculations
        self._calculate_totals()

    def _calculate_totals(self):
        """Computes subtotal, discounts, +16% VAT, and total."""
        gross_subtotal = sum(item.unit_price.cents * item.quantity for item in self.items)
        total_discount = sum(item.discount.cents for item in self.items)
        discounted_subtotal = max(0, gross_subtotal - total_discount)

        tax = calculate_vat(discounted_subtotal)
        total = discounted_subtotal + tax

        self.subtotal = Money(gross_subtotal)
        self.discount = Money(total_discount)
        self.tax = Money(tax)
        self.total = Money(total)

    @property
    def total_cents(self) -> int:
        return self.total.cents

    @property
    def subtotal_cents(self) -> int:
        return self.subtotal.cents

    @property
    def tax_cents(self) -> int:
        return self.tax.cents

    @property
    def discount_cents(self) -> int:
        return self.discount.cents

    def is_voided(self) -> bool:
        return self.status == self.STATUS_VOIDED

    def generate_receipt(self) -> Dict[str, Any]:
        """Generates receipt payload ready for JSON or thermal print rendering."""
        return {
            "receipt_no": self.receipt_no,
            "cashier": self.cashier_snapshot,
            "cashier_snapshot": self.cashier_snapshot,
            "date": self.sale_date or "Now",
            "sale_date": self.sale_date or "Now",
            "payment_method": self.payment_method.upper(),
            "payment_ref": self.payment_reference,
            "payment_reference": self.payment_reference,
            "items": [
                {
                    "sku": item.sku_snapshot,
                    "name": item.product_name_snapshot,
                    "product_name_snapshot": item.product_name_snapshot,
                    "qty": item.quantity,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price.format(),
                    "serial": item.serial_no_snapshot,
                    "serial_no_snapshot": item.serial_no_snapshot,
                    "discount": item.discount.format() if item.discount.cents > 0 else None,
                    "line_total": item.line_total.format()
                }
                for item in self.items
            ],
            "subtotal": self.subtotal.format(),
            "discount": self.discount.format() if self.discount.cents > 0 else "KES 0.00",
            "vat_16": self.tax.format(),
            "tax": self.tax.format(),
            "total": self.total.format(),
            "status": self.status
        }
