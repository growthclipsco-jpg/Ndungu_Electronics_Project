"""
Seed script to pre-populate Ndungu Electronics with realistic inventory & sales.
Matches Chapter Two wireframe products:
- Samsung 43" Smart TV (serial UA43-8842, Kes 38,500, low stock: 3)
- HP 15 Laptop (serial HP15-2207, Kes 52,000, stock: 12)
Plus realistic stock for Televisions, Laptops, Smartphones and Accessories.
"""
import os
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "inventory.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Run schema
with open(os.path.join(os.path.dirname(__file__), "schema.sql"), "r", encoding="utf-8") as f:
    c.executescript(f.read())

# 1. Create Default Owner (Ndungu) & Staff accounts
c.execute("DELETE FROM users")
c.execute("DELETE FROM products")
c.execute("DELETE FROM sales")

owner_hash = generate_password_hash("ndungu2026")
attendant_hash = generate_password_hash("staff123")

c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'owner')", ("ndungu", owner_hash))
owner_id = c.lastrowid
c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'attendant')", ("kamau", attendant_hash))
attendant_id = c.lastrowid

# 2. Add Catalog Products
products_data = [
    ("Samsung 43\" Smart TV", "Samsung", "UA43T5300", "Televisions", "UA43-8842", 38500.0, 3), # Low stock
    ("HP 15 Laptop", "HP", "15-dy2093dx", "Laptops", "HP15-2207", 52000.0, 12),
    ("LG 55\" 4K UHD TV", "LG", "55UQ7500", "Televisions", "LG55-9011", 64000.0, 4), # Low stock
    ("Dell Latitude 7490", "Dell", "7490-Core-i5", "Laptops", "DL74-3341", 42000.0, 8),
    ("Samsung Galaxy A24", "Samsung", "SM-A245F", "Smartphones", "SMA24-5501", 24500.0, 15),
    ("Redmi Note 13", "Xiaomi", "2312DRAABG", "Smartphones", "RN13-7729", 22000.0, 2), # Low stock
    ("Sony WH-CH520 Headphones", "Sony", "WH-CH520", "Accessories", "SNCH-1002", 7500.0, 14),
    ("SanDisk 64GB Ultra Flash Drive", "SanDisk", "SDCZ48-064G", "Accessories", "SD64-8890", 1200.0, 25),
    ("Hisense 32\" Digital LED TV", "Hisense", "32A3300", "Televisions", "HS32-4410", 16500.0, 1) # Critically low
]

for name, brand, model, cat, serial, price, stock in products_data:
    c.execute("""
        INSERT INTO products (name, brand, model, category, serial_no, price, stock, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, brand, model, cat, serial, price, stock, owner_id))

# 3. Add Realistic Prior Sales Transactions
sales_data = [
    (2, attendant_id, "HP 15 Laptop", "HP15-2207", "Laptops", 1, 52000.0, 52000.0, "2026-10-23 10:35:00"),
    (1, attendant_id, "Samsung 43\" Smart TV", "UA43-8842", "Televisions", 1, 38500.0, 38500.0, "2026-10-22 14:15:00"),
    (5, attendant_id, "Samsung Galaxy A24", "SMA24-5501", "Smartphones", 2, 24500.0, 49000.0, "2026-10-22 16:40:00"),
    (7, attendant_id, "Sony WH-CH520 Headphones", "SNCH-1002", "Accessories", 2, 7500.0, 15000.0, "2026-10-21 11:20:00")
]

for pid, uid, pname, serial, cat, qty, uprice, tot, sdate in sales_data:
    c.execute("""
        INSERT INTO sales (product_id, user_id, product_name, serial_no, category, quantity, unit_price, total_price, sale_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pid, uid, pname, serial, cat, qty, uprice, tot, sdate))

conn.commit()
conn.close()
print("Database seeded with sample data!")
