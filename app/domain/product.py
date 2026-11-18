"""
Product domain model matching Milestone 2 Class Diagram (Fig 1.3.6).
Enforces hybrid tracking mode (bulk vs serialized) and normalized SKU identity.
"""

import re
from typing import Optional
from app.domain.money import Money


def normalize_sku(sku: str) -> str:
    """Normalizes SKU by uppercase conversion and removing non-alphanumeric chars."""
    if not sku:
        return ""
    return re.sub(r"[^A-Z0-9]", "", sku.strip().upper())


class Product:
    """Represents an inventory item in Ndungu Electronics catalog."""

    TRACKING_BULK = "bulk"
    TRACKING_SERIALIZED = "serialized"

    def __init__(
        self,
        product_id: Optional[int],
        sku: str,
        name: str,
        brand: str,
        category_id: int,
        price_cents: int,
        cost_price_cents: int = 0,
        model: str = "",
        tracking_mode: str = TRACKING_BULK,
        stock: int = 0,
        reorder_threshold: int = 5,
        reorder_qty: int = 10,
        supplier_name: str = "",
        supplier_phone: str = "",
        is_active: bool = True
    ):
        if price_cents <= 0:
            raise ValueError("Selling price must be strictly greater than zero.")
        if cost_price_cents < 0:
            raise ValueError("Cost price cannot be negative.")
        if stock < 0 or stock > 100000:
            raise ValueError("Stock must be between 0 and 100,000 units.")
        if tracking_mode not in (self.TRACKING_BULK, self.TRACKING_SERIALIZED):
            raise ValueError(f"Invalid tracking mode: {tracking_mode}")

        self.product_id = product_id
        self.sku = sku.strip()
        self.sku_normalized = normalize_sku(sku)
        self.name = name.strip()
        self.brand = brand.strip()
        self.model = model.strip()
        self.category_id = category_id
        self.price = Money(price_cents)
        self.cost_price = Money(cost_price_cents)
        self.tracking_mode = tracking_mode
        self.stock = stock
        self.reorder_threshold = max(1, reorder_threshold)
        self.reorder_qty = max(1, reorder_qty)
        self.supplier_name = supplier_name.strip()
        self.supplier_phone = supplier_phone.strip()
        self.is_active = bool(is_active)

    @property
    def is_serialized(self) -> bool:
        return self.tracking_mode == self.TRACKING_SERIALIZED

    @property
    def is_low_stock(self) -> bool:
        return self.stock <= self.reorder_threshold

    def calculate_valuation(self) -> Money:
        """Returns total retail stock value for this SKU."""
        return self.price * self.stock

    def __repr__(self) -> str:
        return f"<Product [{self.sku}] {self.name} stock={self.stock} price={self.price.format()}>"
