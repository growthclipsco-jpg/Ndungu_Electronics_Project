"""
Inventory management service.
Handles CRUD, hybrid SKU/serial tracking, smart duplicate detection (avoiding empty-model collisions),
soft archiving, and audited stock movements.
"""

from typing import List, Optional, Tuple, Dict, Any
from app.db import get_db, transaction
from app.domain.product import Product, normalize_sku


class InventoryService:
    """Manages inventory catalog, stock movements, and serial registries."""

    @staticmethod
    def get_categories(active_only: bool = True) -> List[Dict[str, Any]]:
        """Retrieves category list."""
        conn = get_db()
        cursor = conn.cursor()
        query = "SELECT category_id, name, is_active FROM categories"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name ASC"
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def check_duplicate(name: str, brand: str, model: str, exclude_product_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Smart duplicate detector.
        Only triggers a conflict on (name, brand, model) if model is NOT empty.
        Distinct generic accessories with empty model (e.g. HDMI-001 vs HDMI-002) save cleanly.
        """
        m_clean = model.strip()
        if not m_clean:
            return False, ""

        conn = get_db()
        cursor = conn.cursor()
        query = """
            SELECT product_id, sku, name
            FROM products
            WHERE LOWER(name) = LOWER(?)
              AND LOWER(brand) = LOWER(?)
              AND LOWER(model) = LOWER(?)
              AND is_active = 1
        """
        params = [name.strip(), brand.strip(), m_clean]
        if exclude_product_id:
            query += " AND product_id != ?"
            params.append(exclude_product_id)

        cursor.execute(query, params)
        dup = cursor.fetchone()
        if dup:
            return True, f"A product with identical Name, Brand, and Model already exists: [{dup['sku']}] {dup['name']}."
        return False, ""

    @classmethod
    def get_inventory(
        cls,
        search: str = "",
        category_id: Optional[int] = None,
        tracking_mode: Optional[str] = None,
        low_stock_only: bool = False,
        page: int = 1,
        per_page: int = 25,
        sort_by: str = "name",
        sort_dir: str = "asc"
    ) -> Dict[str, Any]:
        """
        Paginated inventory query with consistent total counting and allowlisted sorting.
        """
        conn = get_db()
        cursor = conn.cursor()

        # Build WHERE clause
        conditions = ["p.is_active = 1"]
        params = []

        if search:
            s_term = f"%{search.strip()}%"
            conditions.append("(p.name LIKE ? OR p.brand LIKE ? OR p.model LIKE ? OR p.sku LIKE ? OR ps.serial_no LIKE ?)")
            params.extend([s_term, s_term, s_term, s_term, s_term])

        if category_id:
            conditions.append("p.category_id = ?")
            params.append(category_id)

        if tracking_mode in ("bulk", "serialized"):
            conditions.append("p.tracking_mode = ?")
            params.append(tracking_mode)

        if low_stock_only:
            conditions.append("p.stock <= p.reorder_threshold")

        where_clause = " WHERE " + " AND ".join(conditions)

        # Allowlisted Sort Order
        allowed_sorts = {
            "name": "p.name",
            "sku": "p.sku",
            "price": "p.price_cents",
            "stock": "p.stock",
            "category": "c.name"
        }
        order_col = allowed_sorts.get(sort_by, "p.name")
        order_direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

        # Count total matching products
        count_sql = f"""
            SELECT COUNT(DISTINCT p.product_id) as total
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            LEFT JOIN product_serials ps ON p.product_id = ps.product_id
            {where_clause}
        """
        cursor.execute(count_sql, params)
        total_rows = cursor.fetchone()["total"]

        # Fetch paginated rows
        offset = max(0, (page - 1) * per_page)
        fetch_sql = f"""
            SELECT p.product_id, p.sku, p.name, p.brand, p.model,
                   p.tracking_mode, p.cost_price_cents, p.price_cents,
                   p.stock, p.reorder_threshold, p.reorder_qty,
                   p.supplier_name, p.supplier_phone, p.is_active,
                   c.name as category_name, c.category_id
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            LEFT JOIN product_serials ps ON p.product_id = ps.product_id
            {where_clause}
            GROUP BY p.product_id
            ORDER BY {order_col} {order_direction}
            LIMIT ? OFFSET ?
        """
        fetch_params = list(params) + [per_page, offset]
        cursor.execute(fetch_sql, fetch_params)
        products = [dict(row) for row in cursor.fetchall()]

        total_pages = max(1, (total_rows + per_page - 1) // per_page)

        # Calculate high-level KPIs across full active catalog
        cursor.execute("""
            SELECT SUM(price_cents * stock) AS total_valuation_cents,
                   COUNT(product_id) AS total_skus,
                   SUM(CASE WHEN stock <= reorder_threshold THEN 1 ELSE 0 END) AS low_stock_count
            FROM products
            WHERE is_active = 1
        """)
        kpi_row = cursor.fetchone()

        return {
            "items": products,
            "page": page,
            "per_page": per_page,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "kpi": {
                "total_valuation_cents": kpi_row["total_valuation_cents"] or 0,
                "total_skus": kpi_row["total_skus"] or 0,
                "low_stock_count": kpi_row["low_stock_count"] or 0
            }
        }

    @staticmethod
    def get_product(product_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves single product details."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.*, c.name as category_name
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.product_id = ?
            """,
            (product_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_product_by_sku(sku: str) -> Optional[Dict[str, Any]]:
        """Retrieves single product details by SKU."""
        norm = normalize_sku(sku)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.*, c.name as category_name
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.sku_normalized = ? AND p.is_active = 1
            """,
            (norm,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    @classmethod
    def create_product(
        cls,
        sku: str,
        name: str,
        brand: str,
        category_id: int,
        price_cents: int,
        cost_price_cents: int,
        user_id: int,
        username: str,
        model: str = "",
        tracking_mode: str = "bulk",
        stock: int = 0,
        reorder_threshold: int = 5,
        reorder_qty: int = 10,
        supplier_name: str = "",
        supplier_phone: str = "",
        serials: Optional[List[str]] = None
    ) -> Tuple[Optional[int], str]:
        """Creates a new inventory product, creates initial movements, and registers serials."""
        norm_sku = normalize_sku(sku)
        if not norm_sku:
            return None, "A valid alphanumeric SKU is required."

        if price_cents <= 0:
            return None, "Selling price must be strictly greater than zero."
        if stock < 0 or stock > 100000:
            return None, "Stock quantity must be between 0 and 100,000 units."

        # Check duplicate SKU
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT product_id FROM products WHERE sku_normalized = ?", (norm_sku,))
        if cursor.fetchone():
            return None, f"SKU '{sku}' already exists in inventory."

        # Check smart duplicate (name, brand, model)
        is_dup, dup_err = cls.check_duplicate(name, brand, model)
        if is_dup:
            return None, dup_err

        # Check serials count if serialized
        serials_clean = [s.strip() for s in (serials or []) if s.strip()]
        if tracking_mode == "serialized":
            if len(serials_clean) != stock:
                return None, f"Serialized item requires exactly {stock} serial numbers (provided {len(serials_clean)})."
            # Check unique serials within input
            if len(set(serials_clean)) != len(serials_clean):
                return None, "Duplicate serial numbers found within intake list."

        with transaction() as tx:
            cur_p = tx.execute(
                """
                INSERT INTO products (
                    sku, sku_normalized, name, brand, model, category_id,
                    tracking_mode, cost_price_cents, price_cents, stock,
                    reorder_threshold, reorder_qty, supplier_name, supplier_phone,
                    created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sku.strip(), norm_sku, name.strip(), brand.strip(), model.strip(),
                 category_id, tracking_mode, cost_price_cents, price_cents,
                 stock, reorder_threshold, reorder_qty, supplier_name.strip(),
                 supplier_phone.strip(), user_id)
            )
            prod_id = cur_p.lastrowid

            # Log stock movement
            tx.execute(
                """
                INSERT INTO stock_movements (
                    product_id, sku_snapshot, product_name_snapshot, user_id,
                    username_snapshot, movement_type, qty_delta, stock_before,
                    stock_after, note
                ) VALUES (?, ?, ?, ?, ?, 'initial', ?, 0, ?, 'Product catalog creation')
                """,
                (prod_id, sku.strip(), name.strip(), user_id, username, stock, stock)
            )

            # Insert serials
            if tracking_mode == "serialized":
                for s in serials_clean:
                    tx.execute(
                        """
                        INSERT INTO product_serials (product_id, serial_no, serial_normalized, status)
                        VALUES (?, ?, ?, 'in_stock')
                        """,
                        (prod_id, s, s.upper())
                    )

        return prod_id, ""

    @classmethod
    def restock_product(
        cls,
        product_id: int,
        qty_added: int,
        user_id: int,
        username: str,
        note: str = "",
        new_serials: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """Adds stock to existing product and registers any new serial numbers."""
        if qty_added <= 0:
            return False, "Restock quantity must be at least 1."

        prod = cls.get_product(product_id)
        if not prod or not prod["is_active"]:
            return False, "Product does not exist or has been archived."

        serials_clean = [s.strip() for s in (new_serials or []) if s.strip()]
        if prod["tracking_mode"] == "serialized":
            if len(serials_clean) != qty_added:
                return False, f"Restocking {qty_added} serialized units requires {qty_added} serial numbers."
            if len(set(serials_clean)) != len(serials_clean):
                return False, "Duplicate serial numbers found in restock list."

        with transaction() as tx:
            cur_p = tx.execute("SELECT stock, sku, name FROM products WHERE product_id = ?", (product_id,))
            live_prod = cur_p.fetchone()
            stock_before = live_prod["stock"]
            stock_after = stock_before + qty_added

            tx.execute(
                """
                UPDATE products
                SET stock = ?, updated_at = datetime('now', 'localtime')
                WHERE product_id = ?
                """,
                (stock_after, product_id)
            )

            tx.execute(
                """
                INSERT INTO stock_movements (
                    product_id, sku_snapshot, product_name_snapshot, user_id,
                    username_snapshot, movement_type, qty_delta, stock_before,
                    stock_after, note
                ) VALUES (?, ?, ?, ?, ?, 'restock', ?, ?, ?, ?)
                """,
                (product_id, live_prod["sku"], live_prod["name"], user_id, username,
                 qty_added, stock_before, stock_after, note or "Manual inventory restock")
            )

            if prod["tracking_mode"] == "serialized":
                for s in serials_clean:
                    tx.execute(
                        """
                        INSERT INTO product_serials (product_id, serial_no, serial_normalized, status)
                        VALUES (?, ?, ?, 'in_stock')
                        """,
                        (product_id, s, s.upper())
                    )

        return True, ""

    @classmethod
    def archive_product(cls, product_id: int, user_id: int, username: str) -> Tuple[bool, str]:
        """Soft-archives a product by setting is_active = 0."""
        prod = cls.get_product(product_id)
        if not prod:
            return False, "Product not found."

        with transaction() as tx:
            tx.execute(
                """
                UPDATE products
                SET is_active = 0, updated_at = datetime('now', 'localtime')
                WHERE product_id = ?
                """,
                (product_id,)
            )
            tx.execute(
                """
                INSERT INTO stock_movements (
                    product_id, sku_snapshot, product_name_snapshot, user_id,
                    username_snapshot, movement_type, qty_delta, stock_before,
                    stock_after, note
                ) VALUES (?, ?, ?, ?, ?, 'archive', 0, ?, ?, 'Product archived from active catalog')
                """,
                (product_id, prod["sku"], prod["name"], user_id, username, prod["stock"], prod["stock"])
            )

        return True, ""

    @staticmethod
    def get_serials(product_id: int, status: str = "in_stock") -> List[Dict[str, Any]]:
        """Retrieves serial numbers for a given product by status."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT serial_id, serial_no, status, created_at, sold_at
            FROM product_serials
            WHERE product_id = ? AND status = ?
            ORDER BY serial_id ASC
            """,
            (product_id, status)
        )
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_product_serials(product_id: int, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves all or filtered serial records for a product."""
        conn = get_db()
        cursor = conn.cursor()
        query = "SELECT serial_id, serial_no, status, created_at, sold_at FROM product_serials WHERE product_id = ?"
        params = [product_id]
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        query += " ORDER BY serial_id DESC"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_product_movements(product_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves recent audited stock movements for a product."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT movement_id, movement_type, qty_delta, stock_before, stock_after,
                   username_snapshot, reference_type, note, created_at
            FROM stock_movements
            WHERE product_id = ?
            ORDER BY movement_id DESC
            LIMIT ?
            """,
            (product_id, limit)
        )
        return [dict(r) for r in cursor.fetchall()]

    @classmethod
    def update_product(
        cls,
        product_id: int,
        name: str,
        brand: str,
        category_id: int,
        price_cents: int,
        cost_price_cents: int,
        user_id: int,
        username: str,
        model: str = "",
        reorder_threshold: int = 5,
        reorder_qty: int = 10,
        supplier_name: str = "",
        supplier_phone: str = ""
    ) -> Tuple[bool, str]:
        """Updates product metadata with validation."""
        if price_cents <= 0:
            return False, "Selling price must be strictly greater than zero."
        if cost_price_cents < 0:
            return False, "Cost price cannot be negative."

        is_dup, dup_err = cls.check_duplicate(name, brand, model, exclude_product_id=product_id)
        if is_dup:
            return False, dup_err

        with transaction() as tx:
            tx.execute(
                """
                UPDATE products
                SET name = ?, brand = ?, model = ?, category_id = ?,
                    price_cents = ?, cost_price_cents = ?, reorder_threshold = ?,
                    reorder_qty = ?, supplier_name = ?, supplier_phone = ?,
                    updated_at = datetime('now', 'localtime')
                WHERE product_id = ?
                """,
                (name.strip(), brand.strip(), model.strip(), category_id,
                 price_cents, cost_price_cents, reorder_threshold, reorder_qty,
                 supplier_name.strip(), supplier_phone.strip(), product_id)
            )
        return True, ""
