"""
Generates the official Milestone 3 System Documentation (Chapter Three).
Includes:
1. System Architecture & Tech Stack Implementation (Flask, SQLite, HTML5/CSS3)
2. Database Development & Schema Realization (Users, Products, Sales)
3. Feature-by-Feature Development & Debugging:
   - Module 1: Product Inventory Management & Categorization
   - Module 2: Automated Sales Processing & Real-time Stock Deduction
   - Module 3: Low-Stock Alert System (< 5 Threshold)
   - Module 4: Multi-Attribute Product Search
   - Module 5: Duplicate Prevention via Unique SKU/Serial Constraints
   - Module 6: Authentication & Role-Based Access Control
   - Module 7: Reporting & Analytics Dashboard
4. Verification & Testing Matrix (Unit, Functional & Boundary Test Cases)
5. Execution & Deployment Guide for Supervisors/Lecturers
"""
import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

doc = docx.Document()

# Set standard 1-inch margins
for section in doc.sections:
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

def set_cell_background(cell, fill_hex):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def style_heading(p, font_size, bold=True, space_before=12, space_after=6, color_rgb=(20, 20, 20)):
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = RGBColor(*color_rgb)

def add_body_p(text, space_after=6, line_spacing=1.15):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    return p

# ----------------- COVER / TITLE SECTION -----------------
title_p = doc.add_paragraph()
title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
title_p.paragraph_format.space_before = Pt(18)
title_p.paragraph_format.space_after = Pt(6)
r = title_p.add_run("ZETECH UNIVERSITY\nDEPARTMENT OF COMPUTER SCIENCE & SOFTWARE ENGINEERING")
r.font.name = 'Times New Roman'
r.font.size = Pt(14)
r.font.bold = True

proj_p = doc.add_paragraph()
proj_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
proj_p.paragraph_format.space_after = Pt(18)
r2 = proj_p.add_run("\nMILESTONE 3: SYSTEM DEVELOPMENT & TESTING REPORT (PART 1/2)\nDESIGN AND IMPLEMENTATION OF A COMPUTERIZED INVENTORY MANAGEMENT SYSTEM FOR NDUNGU ELECTRONICS, THIKA")
r2.font.name = 'Times New Roman'
r2.font.size = Pt(13)
r2.font.bold = True
r2.font.color.rgb = RGBColor(0, 51, 102)

meta_p = doc.add_paragraph()
meta_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta_p.paragraph_format.space_after = Pt(24)
r3 = meta_p.add_run("Student Name: AUGUSTIN SANGA\nRegistration Number: DSE-01-0145/2025\nCourse: Diploma in Software Engineering\nAcademic Year: 2025/2026\nSubmission Date: October 2026")
r3.font.name = 'Times New Roman'
r3.font.size = Pt(11)

doc.add_page_break()

# ----------------- CHAPTER THREE CONTENT -----------------
h1 = doc.add_paragraph("CHAPTER THREE: SYSTEM DEVELOPMENT AND TESTING (1/2)")
style_heading(h1, 16, bold=True, space_before=0, space_after=12, color_rgb=(0, 51, 102))

add_body_p(
    "This chapter documents the practical development and empirical testing of the computerized inventory management "
    "system for Ndungu Electronics, Thika, fulfilling the requirements for Milestone 3 (Project Development & Testing 1/2). "
    "During this phase, the architectural designs, entity-relationship diagrams (ERD), data flow diagrams (DFD), and user interface "
    "wireframes formulated in Milestone 2 were translated into a fully functional, robust software application. "
    "The chapter outlines the technical implementation stack, database realization, feature-by-feature codebase construction, "
    "debugging iterations, and systematic test validation across the core operational objectives."
)

# 3.1
h2 = doc.add_paragraph("3.1 Implementation Architecture and Technology Stack")
style_heading(h2, 13, bold=True, space_before=12, space_after=6)

add_body_p(
    "In accordance with the software requirements defined in Chapter One, the system is engineered as a lightweight, "
    "secure, and modular full-stack web application designed for on-premises deployment within retail SME hardware. "
    "The architecture strictly separates data persistence, back-end transactional business logic, and front-end interface presentation:"
)

tech_points = [
    ("Back-End Framework (Python Flask): ", "Selected for its zero-bloat footprint, native Python performance, and direct integration with transactional databases. Flask serves application routing, session management, CSRF validation, and business rule enforcement without excessive computational overhead."),
    ("Relational Database (SQLite): ", "Implemented as the primary ACID-compliant storage engine. SQLite provides immediate transactional durability (foreign key enforcement, atomic commits) through an embedded, file-based model (inventory.db), eliminating complex server maintenance while supporting high reliability for a single-outlet retail store."),
    ("Front-End Layer (Semantic HTML5, Responsive CSS3, JavaScript): ", "Directly constructed from the dark wireframe mockups established in Chapter Two. The interface utilizes structured layouts, rounded input pills, real-time client-side price computation, and alert notification bars to ensure high usability for both the shop owner and attendant."),
    ("Security & Data Protection: ", "Employs Werkzeug PBKDF2:SHA256 password hashing for stored credentials, per-session cryptographically generated CSRF tokens on all state-altering POST requests, and parameterized SQL queries to completely mitigate SQL injection vectors.")
]

for title, desc in tech_points:
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(4)
    r1 = p.add_run(title)
    r1.font.name = 'Times New Roman'
    r1.font.bold = True
    r2 = p.add_run(desc)
    r2.font.name = 'Times New Roman'

# 3.2
h2 = doc.add_paragraph("3.2 Database Development and Schema Realization")
style_heading(h2, 13, bold=True, space_before=14, space_after=6)

add_body_p(
    "The database schema was implemented strictly from the Chapter Two Entity-Relationship Diagram (ERD). "
    "The database architecture comprises three primary relational tables: users (system credentials and roles), "
    "products (physical catalog items with unique serial numbers), and sales (immutable transaction records)."
)

add_body_p(
    "Table 3.1 below presents the data dictionary detailing field names, data types, constraints, and relational mappings:"
)

# Table 3.1
table = doc.add_table(rows=1, cols=5)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr_cells = table.rows[0].cells
headers = ["Table", "Attribute / Field", "Data Type", "Constraints", "Description & Purpose"]
for i, h in enumerate(headers):
    hdr_cells[i].text = h
    set_cell_background(hdr_cells[i], "1F497D")
    p = hdr_cells[i].paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(9.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

data_dict = [
    ("users", "user_id", "INTEGER", "PK, AUTOINCREMENT", "Surrogate unique key for each user account"),
    ("users", "username", "TEXT", "NOT NULL, UNIQUE", "Account login name (3-30 chars, case-insensitive)"),
    ("users", "password_hash", "TEXT", "NOT NULL", "PBKDF2 cryptographically salted password hash"),
    ("users", "role", "TEXT", "CHECK(owner/attendant)", "Access control designation for permissions"),
    ("products", "product_id", "INTEGER", "PK, AUTOINCREMENT", "Surrogate unique identifier for products"),
    ("products", "name", "TEXT", "NOT NULL", "Descriptive commercial item name (e.g. Smart TV)"),
    ("products", "brand", "TEXT", "NOT NULL", "Manufacturer name (Samsung, HP, LG, Sony)"),
    ("products", "model", "TEXT", "DEFAULT ''", "Manufacturer model number / code"),
    ("products", "category", "TEXT", "NOT NULL", "Televisions, Laptops, Smartphones, Accessories"),
    ("products", "serial_no", "TEXT", "NOT NULL, UNIQUE", "Unique hardware SKU / serial; duplicate barrier"),
    ("products", "price", "REAL", "NOT NULL, CHECK(>=0)", "Retail price per unit in Kenya Shillings (KES)"),
    ("products", "stock", "INTEGER", "NOT NULL, CHECK(>=0)", "Current physical unit count; non-negative bound"),
    ("products", "user_id", "INTEGER", "FK -> users(user_id)", "Identifies the manager who registered the item"),
    ("sales", "sale_id", "INTEGER", "PK, AUTOINCREMENT", "Unique receipt/transaction ledger ID"),
    ("sales", "product_id", "INTEGER", "FK -> products (SET NULL)", "Links transaction to product (preserves ledger)"),
    ("sales", "user_id", "INTEGER", "FK -> users (SET NULL)", "Links sale to attendant/owner who completed it"),
    ("sales", "product_name", "TEXT", "NOT NULL", "Immutable product name snapshot at time of sale"),
    ("sales", "serial_no", "TEXT", "NOT NULL", "Immutable serial number snapshot"),
    ("sales", "category", "TEXT", "NOT NULL", "Product category snapshot for reporting"),
    ("sales", "quantity", "INTEGER", "NOT NULL, CHECK(>0)", "Number of units purchased in transaction"),
    ("sales", "unit_price", "REAL", "NOT NULL, CHECK(>=0)", "Unit selling price in KES at transaction point"),
    ("sales", "total_price", "REAL", "NOT NULL, CHECK(>=0)", "Computed transaction total (unit_price * quantity)"),
    ("sales", "sale_date", "TEXT", "DEFAULT datetime('now')", "Timestamp of sale execution")
]

for row_data in data_dict:
    row = table.add_row()
    for i, val in enumerate(row_data):
        cell = row.cells[i]
        cell.text = val
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(2)
        for run in p.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(8.5)

p_cap = doc.add_paragraph()
p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_cap.paragraph_format.space_after = Pt(12)
r = p_cap.add_run("Table 3.1: Database Schema and Data Dictionary")
r.font.name = 'Times New Roman'
r.font.size = Pt(9.5)
r.font.italic = True

# 3.3
h2 = doc.add_paragraph("3.3 Feature-by-Feature Development and Codebase Implementation")
style_heading(h2, 13, bold=True, space_before=14, space_after=6)

add_body_p(
    "Development proceeded sequentially through seven dedicated functional modules mapped directly to the research objectives:"
)

modules = [
    ("3.3.1 Module 1: Product Inventory Management & Restocking (Objective 1)",
     "The inventory management module provides full CRUD (Create, Read, Update, Delete) capabilities. "
     "Shop managers can register incoming stock with attributes including commercial title, manufacturer brand, model number, "
     "hardware serial number, unit selling price, and opening inventory count. In addition, an incremental Restock sub-module "
     "allows incoming shipments to be credited directly to existing product records without manual recalculation errors."),

    ("3.3.2 Module 2: Automated Sales Processing & Real-Time Stock Deduction (Objective 2)",
     "The point-of-sale module processes transactions in real time. When a sale is confirmed, the system executes an atomic "
     "SQL condition: UPDATE products SET stock = stock - ? WHERE product_id = ? AND stock >= ?. "
     "This mechanism guarantees that stock deductions are instantaneous and prevents race conditions or phantom stockouts. "
     "Simultaneously, a complete transaction record is appended to the sales ledger with price snapshots."),

    ("3.3.3 Module 3: Automated Low-Stock Alert Engine (Objective 3)",
     "To eliminate unexpected stock depletion, an automated surveillance trigger continuously monitors unit levels against the "
     "threshold of 5 units (defined in Chapter One). Products with fewer than 5 units remaining are immediately highlighted with "
     "amber visual badges in the inventory table, registered in an actionable banner notification on the dashboard, and flagged "
     "in a dedicated Low-Stock Reorder Report."),

    ("3.3.4 Module 4: Multi-Attribute Search & Filter System (Objective 4)",
     "Replaces manual notebook lookups with a high-speed search index. Attendants can query items across four simultaneous "
     "attributes: product name, brand name, model code, or unique serial number. Queries are sanitized and executed using SQL "
     "LIKE patterns with wildcard escaping, enabling instantaneous item retrieval during customer inquiries."),

    ("3.3.5 Module 5: Duplicate Prevention Engine (Objective 5)",
     "Directly resolves the critical failure mode documented in Chapter One where identical items were entered multiple times. "
     "The engine enforces duplicate prevention through two coordinated tiers: (1) an application-level duplicate verification "
     "routine checking normalized serial numbers and exact name/brand/model combinations prior to write operations, and (2) a "
     "strict UNIQUE database index on the serial_no column in SQLite acting as an inviolable database integrity constraint."),

    ("3.3.6 Module 6: Authentication and Role-Based Access Control (RBAC)",
     "Implements two operational roles: 'owner' (full administrative authority over product additions, edits, deletions, user accounts, "
     "and financial reports) and 'attendant' (operational access restricted to inventory browsing, product search, sales execution, "
     "and sales log inspection). Passwords are cryptographically salted and hashed using PBKDF2:SHA256."),

    ("3.3.7 Module 7: Reporting and Business Intelligence Dashboard",
     "Aggregates real-time operational metrics across configurable reporting windows (Today, Last 7 Days, This Month, and All Time). "
     "The dashboard computes total revenue, units sold, gross transaction volume, inventory valuation, category performance breakdowns, "
     "and top five best-selling products to empower evidence-based restocking decisions.")
]

for mod_title, mod_desc in modules:
    h3 = doc.add_paragraph(mod_title)
    style_heading(h3, 11.5, bold=True, space_before=8, space_after=4, color_rgb=(0, 51, 102))
    add_body_p(mod_desc)

# 3.4
h2 = doc.add_paragraph("3.4 Debugging Challenges and Iterative Resolution")
style_heading(h2, 13, bold=True, space_before=14, space_after=6)

add_body_p(
    "During development and initial integration, several technical bugs and edge-case exceptions were identified and systematically resolved:"
)

debugging_cases = [
    ("Issue 1: Serial Number Whitespace Formatting Discrepancies: ", 
     "Initial testing revealed that manual entry of serial numbers with incidental leading or trailing spaces (e.g. ' UA43-8842 ') "
     "bypassed equality comparisons. Resolution: Implemented a normalization helper (normalize_serial) that strips whitespace and converts "
     "all incoming serial numbers to uppercase before both validation and storage."),

    ("Issue 2: Negative Stock Anomaly on Concurrent Sales: ", 
     "If an attendant attempted to sell more units than physically available, inventory counts could theoretically fall below zero. "
     "Resolution: Enforced a dual-layer check consisting of a database CHECK (stock >= 0) constraint combined with a conditional atomic "
     "UPDATE query verifying (stock >= quantity), which rolls back the transaction and presents a user-friendly error notification."),

    ("Issue 3: Historical Sales Integrity on Product Deletion: ", 
     "Deleting a discontinued product previously risked cascade-deleting linked past sales transactions, corrupting historical revenue reports. "
     "Resolution: Configured the sales foreign key as ON DELETE SET NULL and supplemented the sales schema with snapshot columns "
     "(product_name, serial_no, category) to preserve historical accounting audits indefinitely."),

    ("Issue 4: Cross-Site Request Forgery (CSRF) on Form Submissions: ", 
     "State-altering POST actions required protection against unauthorized cross-site requests. "
     "Resolution: Embedded a cryptographically generated session CSRF token into all forms, validated rigorously through a global Flask "
     "before_app_request hook using secrets.compare_digest.")
]

for title, desc in debugging_cases:
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(4)
    r1 = p.add_run(title)
    r1.font.name = 'Times New Roman'
    r1.font.bold = True
    r2 = p.add_run(desc)
    r2.font.name = 'Times New Roman'

# 3.5
h2 = doc.add_paragraph("3.5 System Testing and Verification Matrix")
style_heading(h2, 13, bold=True, space_before=14, space_after=6)

add_body_p(
    "To rigorously evaluate the system against user requirements, an automated test suite (implemented with pytest and Flask test client) "
    "was executed alongside manual functional verification. The test cases directly target the specific research objectives:"
)

test_table = doc.add_table(rows=1, cols=6)
test_table.alignment = WD_TABLE_ALIGNMENT.CENTER
t_hdr = test_table.rows[0].cells
t_headers = ["Test ID", "Test Objective / Feature", "Input / Action", "Expected Result", "Actual Result", "Status"]
for i, h in enumerate(t_headers):
    t_hdr[i].text = h
    set_cell_background(t_hdr[i], "1F497D")
    p = t_hdr[i].paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(9.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

test_cases = [
    ("TC-01", "User Authentication", "Submit valid credentials (ndungu / ndungu2026)", "Authentication granted; dashboard displayed", "Session created; redirected to inventory", "PASS"),
    ("TC-02", "Access Control (RBAC)", "Attendant attempts to access /products/new", "HTTP 403 Forbidden error returned", "403 Access Denied rendered", "PASS"),
    ("TC-03", "Product Intake (Obj 1)", "Enter Samsung 43 TV, price 38500, stock 3", "Item stored; visible in catalog table", "Product saved with correct attributes", "PASS"),
    ("TC-04", "Duplicate Check (Obj 5)", "Submit second product with existing serial UA43-8842", "Validation blocks save; duplicate warning displayed", "Duplicate detected warning returned", "PASS"),
    ("TC-05", "Low Stock Alert (Obj 3)", "Observe catalog display for TV with stock = 3 (<5)", "Visual amber badge and alert banner displayed", "Low stock alert triggered on dashboard", "PASS"),
    ("TC-06", "Product Search (Obj 4)", "Search query string 'UA43-8842'", "Matching Samsung TV displayed exclusively", "Exact product returned instantly", "PASS"),
    ("TC-07", "Sales Processing (Obj 2)", "Execute sale of 2 units of Samsung 43 TV", "Stock decremented from 3 to 1; sale logged in ledger", "Stock updated to 1; Kes 77,000 logged", "PASS"),
    ("TC-08", "Over-Stock Sale Prevention", "Attempt to sell 5 units when only 1 is in stock", "Transaction blocked; error notification returned", "Error: 'Not enough stock' displayed", "PASS"),
    ("TC-09", "Reporting Aggregation", "Load /reports for 'All Time' period", "Revenue, best-sellers, category metrics computed", "Metrics match exact ledger totals", "PASS")
]

for row_data in test_cases:
    row = test_table.add_row()
    for i, val in enumerate(row_data):
        cell = row.cells[i]
        cell.text = val
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(2)
        if i in (0, 5):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(8.5)
            if i == 5 and val == "PASS":
                run.font.bold = True
                run.font.color.rgb = RGBColor(0, 128, 0)

p_cap2 = doc.add_paragraph()
p_cap2.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_cap2.paragraph_format.space_after = Pt(12)
r = p_cap2.add_run("Table 3.2: Milestone 3 System Testing and Verification Matrix")
r.font.name = 'Times New Roman'
r.font.size = Pt(9.5)
r.font.italic = True

# 3.6
h2 = doc.add_paragraph("3.6 Deployment and Operational Demonstration Guide")
style_heading(h2, 13, bold=True, space_before=14, space_after=6)

add_body_p(
    "The application is packaged with an automated startup script and self-contained database initializer for immediate evaluation "
    "by the project supervisor and examining panel:"
)

run_steps = [
    ("Application Directory: ", "C:\\Users\\Sanga\\.gemini\\antigravity\\scratch\\ndungu-inventory"),
    ("Automated Execution: ", "Double-click 'run_system.bat' or run 'python app.py' in the project terminal."),
    ("Local Web Endpoint: ", "Open http://127.0.0.1:5000 in any standard web browser (Chrome, Edge, Firefox)."),
    ("Pre-configured Credentials: ", "Shop Owner Administrator: username = 'ndungu', password = 'ndungu2026' | Staff Attendant: username = 'kamau', password = 'staff123'."),
    ("Automated Testing Suite: ", "Execute 'pytest test_system.py -v' to automatically run all unit and functional tests.")
]

for label, val in run_steps:
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(4)
    r1 = p.add_run(label)
    r1.font.name = 'Times New Roman'
    r1.font.bold = True
    r2 = p.add_run(val)
    r2.font.name = 'Times New Roman'

# 3.7
h2 = doc.add_paragraph("3.7 Chapter Summary and Milestone Transition")
style_heading(h2, 13, bold=True, space_before=14, space_after=6)

add_body_p(
    "Chapter Three has documented the successful development, debugging, and verification of the Ndungu Electronics "
    "Inventory Management System under Milestone 3 (Development & Testing 1/2). All five primary functional objectives—inventory management, "
    "automated real-time stock deductions, low-stock surveillance, multi-parameter search, and duplicate prevention—have been fully implemented "
    "and verified through comprehensive test suites. The project transitions directly into Milestone 4 (Development & Testing 2/2) and Milestone 5, "
    "which will focus on advanced reporting exports, live environment deployment on PythonAnywhere, and end-user acceptance testing."
)

out_doc_path = r"C:\Users\Sanga\Downloads\NDUNGU_ELECTRONICS_MILESTONE_3_REPORT.docx"
doc.save(out_doc_path)
print(f"Report saved to: {out_doc_path}")
