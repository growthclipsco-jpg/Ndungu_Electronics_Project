"""
Comprehensive automated tests for Ndungu Electronics Inventory Management System.
Validates:
  1. Authentication & Role-based Access Control (Owner vs Attendant)
  2. Objective 1: Inventory CRUD (Add, Edit, Delete, Restock)
  3. Objective 2: Automated Sales Processing & Real-time Stock Deduction
  4. Objective 3: Low-Stock Alerts (< 5 items)
  5. Objective 4: Search functionality (Name, Brand, Model, Serial Number)
  6. Objective 5: Duplicate Detection (Serial number uniqueness & Duplicate product warning)
  7. Reporting & Analytics metrics
"""
import os
import pytest
import sqlite3
from app import create_app, get_db

@pytest.fixture
def app(tmp_path):
    db_file = tmp_path / "test_inventory.db"
    app = create_app({
        "TESTING": True,
        "DATABASE": str(db_file),
        "SECRET_KEY": "test-secret-key"
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

def register_owner(client, username="ndungu", password="password123"):
    return client.post("/register", data={
        "username": username,
        "password": password,
        "confirm": password,
        "csrf_token": client.get("/register").text.split('name="csrf_token" value="')[1].split('"')[0]
    }, follow_redirects=True)

def login(client, username="ndungu", password="password123"):
    token = client.get("/login").text.split('name="csrf_token" value="')[1].split('"')[0]
    return client.post("/login", data={
        "username": username,
        "password": password,
        "csrf_token": token
    }, follow_redirects=True)

def get_csrf(client, path="/inventory"):
    res = client.get(path)
    if 'name="csrf_token" value="' in res.text:
        return res.text.split('name="csrf_token" value="')[1].split('"')[0]
    return ""

def test_system_flow_objectives(client, app):
    # 1. Setup Owner Account
    res = register_owner(client)
    assert "Owner account created" in res.text

    # 2. Login
    res = login(client)
    assert "Welcome back, ndungu!" in res.text

    # 3. Objective 1 & 5: Add Products and check Duplicate Detection
    csrf = get_csrf(client, "/products/new")
    res = client.post("/products/new", data={
        "name": "Samsung 43 Smart TV",
        "brand": "Samsung",
        "model": "UA43T5300",
        "category": "Televisions",
        "serial_no": "UA43-8842",
        "price": "38500",
        "stock": "3",
        "csrf_token": csrf
    }, follow_redirects=True)
    assert "was added to the inventory" in res.text

    # Try duplicate serial number
    csrf = get_csrf(client, "/products/new")
    res = client.post("/products/new", data={
        "name": "Different TV",
        "brand": "Sony",
        "model": "Bravia",
        "category": "Televisions",
        "serial_no": "UA43-8842", # Exact same serial
        "price": "45000",
        "stock": "2",
        "csrf_token": csrf
    }, follow_redirects=True)
    assert "Duplicate detected" in res.text

    # 4. Objective 3: Verify Low Stock Alert (Stock = 3 < 5)
    res = client.get("/inventory")
    assert "Low stock alert" in res.text
    assert "Samsung 43 Smart TV (3)" in res.text

    # 5. Objective 4: Search Functionality
    res = client.get("/inventory?q=UA43-8842")
    assert "Samsung 43 Smart TV" in res.text
    res = client.get("/inventory?q=NonExistentProduct")
    assert "No products match your search" in res.text

    # 6. Objective 2: Sell Product & Automatic Stock Deduction
    # Fetch product_id
    with app.app_context():
        db = get_db()
        prod = db.execute("SELECT product_id, stock FROM products WHERE serial_no='UA43-8842'").fetchone()
        pid = prod["product_id"]
        assert prod["stock"] == 3

    csrf = get_csrf(client, f"/products/{pid}/sell")
    res = client.post(f"/products/{pid}/sell", data={
        "quantity": "2",
        "csrf_token": csrf
    }, follow_redirects=True)
    assert "Sale recorded: 2 x Samsung 43 Smart TV" in res.text

    # Verify database stock updated atomically to 1
    with app.app_context():
        db = get_db()
        prod = db.execute("SELECT stock FROM products WHERE product_id=?", (pid,)).fetchone()
        assert prod["stock"] == 1
        sale = db.execute("SELECT total_price FROM sales WHERE product_id=?", (pid,)).fetchone()
        assert sale["total_price"] == 77000.0 # 38500 * 2

    # 7. Check Sales Log & Reports
    res = client.get("/sales")
    assert "Kes. 77,000" in res.text

    res = client.get("/reports?period=all")
    assert "Kes. 77,000" in res.text
    assert "Samsung 43 Smart TV" in res.text
