# Forensic Engineering & Academic Audit — Ndungu Electronics Inventory Management System (`App/` & Milestones 1–3)

**Auditor:** `codebase-auditor`  
**Audit Date:** 2026-11-13  
**Workspace:** `C:\Users\Sanga\Documents\Ndungu_Electronics_Project`  
**Scope:** Full read-only forensic inspection of `App/` (code, templates, static assets, batch/doc scripts, `App/instance/inventory.db`), `Milestone_1_Planning_and_Analysis.{pdf,docx}`, `Milestone_2_Design_and_Modeling.{pdf,docx}`, `Milestone_3_Development_and_Testing.{pdf,docx}`, and `Milestone_Instructions/*.png`.

---

## 1. Executive Verdict

**Verdict: FAIL — Unfit for Production or A-Grade Academic Evaluation (Milestones 3–6).**

Although the former `App/` implementation passes its single automated test (`pytest App/test_system.py -v -p no:cacheprovider` → `1 passed in 1.15s`), that pass is an artifact of an incomplete smoke script (`test_system_flow_objectives`) rather than proof of system correctness or rubric compliance. Forensically, the existing attempt fails both **academic traceability** and **production engineering standards** for five decisive reasons:

1. **Core Functional & Design Promises Missing:** Milestone 1 Table 1.4.1 explicitly requires **Pricing and promotion management** (row 6) and **Sign up and log in** (row 1), while Milestone 2 Figure 1.3.6 (Class Diagram) explicitly specifies **`Sale.generateReceipt()`** and **`Sale` `contains *` `Product`** (multi-item checkout). `App/` omits pricing/promotion management entirely, omits receipt generation entirely, restricts checkout to a single product per transaction, lacks CSV/PDF report exports, and provides zero PythonAnywhere deployment artifacts (`wsgi.py`, `requirements.txt`, production config) promised in Milestone 1 Section 1.5.
2. **Broken Out-of-the-Box Experience on Current Dates:** `App/seed.py` hardcodes sales timestamps to `2026-10-21` through `2026-10-23`. Evaluated against the system date (`2026-11-13`), the live `App/instance/inventory.db` displays **`Kes. 0`** for **Today's sales** on `/inventory` and **`Kes. 0` (`No sales in this period.`)** on `/reports` under its default `This month` period, `Today`, and `Last 7 days`.
3. **Flawed Domain & Data Modeling:** `App/` conflates per-unit hardware serial numbers with bulk catalog SKUs (`HP 15 Laptop` holds `stock = 12` under a single `serial_no = 'HP15-2207'`), uses IEEE-754 floating-point (`REAL` / `float`) for KES currency, and implements `find_duplicate()` (`App/app.py:289-307`) in a way that blocks distinct products whenever the optional `model` field is left blank.
4. **Severe Documentation-to-Code Misalignment & Misleading Test Claims:** `Milestone_3_Development_and_Testing.pdf` Table 3.2 reports **9 passing test cases (`TC-01`–`TC-09`)**, including RBAC `403` enforcement (`TC-02`) and over-stock prevention (`TC-08`). In reality, `App/test_system.py` contains **only 1 test function** and never tests `TC-02` or `TC-08`. Meanwhile, Section 3.6 references a stale scratch path (`C:\Users\Sanga\.gemini\antigravity\scratch\ndungu-inventory`), Sec 3.1 / Sec 3.3.6 claim `PBKDF2:SHA256` (and Table 3.1 claims `PBKDF2`) hashes while `inventory.db` stores `scrypt:32768:8:1` hashes, and Milestone 2 diagrams deviate substantially from the implemented UI, database columns, and procedural codebase.
5. **Security & Operational Readiness Gaps:** `App/app.py:685-686` defaults to `FLASK_DEBUG=1` (`debug=True`), lacks security headers (`CSP`, `X-Frame-Options`, `X-Content-Type-Options`), lacks login rate limiting/lockout, stores `instance/secret_key` and `instance/inventory.db` with no `.gitignore`, has no `500` error handler, and runs SQLite in `DELETE` journal mode without `WAL` or `busy_timeout`.

---

## 2. Requirements & Traceability Gaps

### 2.1 Milestone 1 Specific Objectives & Table 1.4.1 vs. `App/`

| Milestone 1 Requirement / Source | Expected Behaviour | Observed State in `App/` | Gap Severity |
| :--- | :--- | :--- | :--- |
| **Table 1.4.1 Row 6:** Manage pricing and promotions (`Milestone_1` PDF p. 9) | Pricing and promotion management module (discounts, promo rules, active dates, discounted checkout totals) | **COMPLETELY MISSING.** `products` (`App/schema.sql:20-32`) only has a flat `price REAL` column; no promotions table, routes, templates, or checkout discount logic exist. | **Critical** |
| **Table 1.4.1 Row 1:** Sign up and log in (`Milestone_1` PDF p. 9) | Sign up and login workflow | `/register` (`App/app.py:354-375`) is a first-run-only owner bootstrap that permanently disables itself (`if user_count() > 0: redirect("/login")`). After `seed.py` runs, `/register` returns `302 -> /login` (verified empirically) and `login.html:18-20` hides the link. | **High** |
| **Table 1.4.1 Row 4 & M3 Sec 3.7:** Sales and inventory reporting tools & exports (`Milestone_1` p. 9; `Milestone_3` p. 7) | Printable/exportable inventory & sales reports | `/reports` (`App/templates/reports.html:10`) has only an inline `onclick="window.print()"` button. `App/static/style.css` has **zero `@media print` rules**, so printing dumps dark `#121316` background and top navigation chrome. Zero CSV or PDF export endpoints exist. | **High** |
| **Table 1.4.1 Row 5 & Obj III:** Low-stock and reorder alerts (`Milestone_1` pp. 8–9) | Flag `< 5` items + support purchasing/restocking decisions | Global constant `LOW_STOCK_THRESHOLD = 5` (`App/app.py:29`) flags `< 5`, and `restock_product` (`App/app.py:494-511`) increments stock. However, there is no per-product reorder threshold, suggested reorder quantity, supplier contact, or purchase-order log. | **Medium** |
| **Obj I:** Inventory management module (`Milestone_1` p. 8) | Add, edit, delete product records, categories, and prices | Implemented (`App/app.py:432-522`), but `CATEGORIES` (`app.py:30`) is a hardcoded tuple `("Televisions", "Laptops", "Smartphones", "Accessories")` with no cost price, margin, or category management. | **Low** |
| **Obj II:** Automated sales processing (`Milestone_1` p. 8) | Reduce stock and log transactions in real time | Works only for **single-product** sales (`App/app.py:528-569`). No shopping cart / multi-line invoice, no customer/payment method (Cash/M-Pesa), no sale void/refund. | **High** |
| **Obj IV:** Search functionality (`Milestone_1` p. 8) | Quick retrieval by name, brand, model, or serial number | Implemented (`App/app.py:404-408`) using SQL `LIKE` across those 4 fields plus category and low-stock filters. Lacks pagination or sorting controls. | **Low** |
| **Obj V:** Duplicate detection (`Milestone_1` p. 8) | Prevent the same product from being recorded twice | Overly rigid `(name, brand, model)` collision breaks valid multi-SKU/empty-model products while bulk `stock` on one `serial_no` breaks per-unit serial tracking (see Section 3.2). | **High** |
| **Sec 1.5 (3) Deployment Resources:** PythonAnywhere hosting (`Milestone_1` p. 9) | Live Flask + SQLite hosting on PythonAnywhere | **COMPLETELY MISSING.** No `wsgi.py`, no `requirements.txt`, no `.env.example`, no PythonAnywhere static/DB path configuration. | **Critical** |
| **Sec 1.5 (4) Hardware Resources:** Smartphones (`Milestone_1` p. 10) | Accessible on desktop, laptop, and smartphone screens | `App/static/style.css` (`1-537`) contains **zero `@media` responsive breakpoints**. `.topbar` (`style.css:44-51`) has no `flex-wrap: wrap` or mobile drawer, overflowing on small viewports. | **Medium** |

### 2.2 Milestone 2 Diagrams & Wireframes vs. `App/`

| Milestone 2 Artifact | Model Specification (`Milestone_2` PDF & `.docx`) | Actual Implementation in `App/` | Traceability Defect |
| :--- | :--- | :--- | :--- |
| **Class Diagram** (`Fig 1.3.6` PDF p. 9 / `Fig 2.3.6` DOCX) | Classes `User`, `Product`, `Sale`, `Report`. `Sale` explicitly declares `+ generateReceipt()`, `+ calculateTotal()`, and association `Sale contains * Product`. `User` declares `makes 1..* Sale`. | `App/app.py` is purely procedural (`bp = Blueprint("main", __name__)`) with **zero domain classes**. **`Sale.generateReceipt()` does not exist anywhere** (no receipt route, view, or template). `sales` (`App/schema.sql:37-48`) holds one `product_id` per `sale_id`, failing `contains *` multiplicity. `Report` has no persisted `report_id`/`type` or export artifact. | **Critical** |
| **Login Wireframe** (`Fig 1.2.1` PDF p. 1 / `Fig 2.2.1` DOCX) | Two-column horizontal rows: rounded pill label boxes (`Username`, `Password`) on the left, rectangular inputs on the right, and a centered rounded pill `sign in` button below. | `App/templates/login.html:8-16` + `App/static/style.css:168-179, 266-268` stack labels vertically above inputs (`flex-direction: column`), render plain uppercase text instead of pill badges, and use a full-width `.btn-block` button. | **Medium** |
| **Inventory Wireframe** (`Fig 1.2.2` PDF p. 2 / `Fig 2.2.2` DOCX) | 5 columns (`Product info`, `SERIAL NO`, `PRICE`, `STOCK`, `ACTION`) with stacked `sell / edit / remove` links and a bottom-right `Add Stock` pill button. | `App/templates/inventory.html:4-73` uses **6 columns** (adds `Category`), moves `+ Add Stock` to top-right `.page-head`, and introduces 4 KPI stat boxes, an alert banner, and a search/filter toolbar absent from the wireframe. | **Medium** |
| **Sales Log Wireframe** (`Fig 1.2.3` PDF p. 2 / `Fig 2.2.3` DOCX) | 4 columns (`TIME`, `PRODUCT`, `QUANTITY`, `VALUE`) with top-right `summary report` pill button. | `App/templates/sales.html:4-39` renders **6 columns** (`Time`, `Product`, `Serial No`, `Quantity`, `Value`, `Sold by`) plus date filters and 3 KPI boxes. | **Low** |
| **Reports Wireframe** (`Fig 1.2.4` PDF p. 3 / `Fig 2.2.4` DOCX) | `total revenue` card, `Best selling products` (`product name`, `qty`), and `View full logs` button. | `App/templates/reports.html:4-73` adds period selector tabs, 4 KPI cards, `Sales by category`, `Daily sales` bar chart, and `Low stock` table. | **Low** |
| **Unmodeled Screens** (Milestone 2 Sec 1.2) | Rubric (`Milestone_1_and_2_Sheet_1.png`) requires *"Identify all user screens/interfaces and draw a rough sketch of each"*. | Milestone 2 only sketches 4 screens. It omits sketches for **Register/Setup**, **Add/Edit/Restock Product**, **Sell Product / POS Cart**, **Printable Receipt**, **Promotions**, and **Users Management**. | **High** |
| **ERD** (`Fig 1.3.4` PDF p. 6 / `Fig 2.3.4` DOCX) | 3 entities: `Shop owner` (`user_id`, `username`, `password`), `Product` (`product_id`, `name`, `brand`, `serial_no`, `price`, `stock`), `Sale` (`sale_id`, `product_id`, `quantity`, `total_price`, `sale_date`). | `App/schema.sql` adds unmodeled columns: `users.role`, `users.created_at`, `products.model`, `products.category`, `products.user_id`, `products.created_at`, `products.updated_at`, `sales.user_id`, `sales.product_name`, `sales.serial_no`, `sales.category`, `sales.unit_price`. No `promotions`, `sale_items`, or `stock_movements` entities exist in either M2 or `App/`. | **High** |
| **System Flowchart, DFD & Use Case** (`Fig 1.3.2, 1.3.3, 1.3.5` PDF pp. 4–7) | Single actor (`shop owner` / `SHOP OWNER`). System flowchart (`Fig 1.3.2`) omits `sell product`. Level 1 DFD (`Fig 1.3.3`) wires `2 MANAGE INVENTORY` to `D1 user db` (`access data`) and fails to wire `D2 product db` to `4 GENERATE REPORTS` despite outputting `stock alerts`. | `App/` introduces an `attendant` role (`kamau`) and `Sell Product` flow that are invisible in Milestone 2's Flowchart, DFD, ERD, and Use Case Diagram. | **High** |

---

## 3. Bugs, Data Integrity & Runtime Pitfalls in `App/`

### 3.1 Stale Seeded Sales Dates Yield `Kes. 0` on Default Views (Verified Empirically)

- **Root Cause:** `App/seed.py:55-60` inserts 4 historical sales with static October timestamps: `"2026-10-23 10:35:00"`, `"2026-10-22 14:15:00"`, `"2026-10-22 16:40:00"`, and `"2026-10-21 11:20:00"`.
- **Code Path:**
  - `/inventory` (`App/app.py:421-423`) computes `Today's sales` via `WHERE date(sale_date) = date('now', 'localtime')`.
  - `/reports` (`App/app.py:35-40, 602-605`) defaults `period` to `"month"` (`date(sale_date) >= date('now', 'localtime', 'start of month')`).
- **Observed Behavior (Read-Only DB Inspection & Runtime Probe on `2026-11-13`):**
  - `App/instance/inventory.db` evaluates `date('now', 'localtime') = 2026-11-13` and `start of month = 2026-11-01`.
  - Live query results: `today` = `0 transactions, Kes. 0`; `week` = `0 transactions, Kes. 0`; `month` = `0 transactions, Kes. 0`; `all` = `4 transactions, 6 units, Kes. 154,500.0`.
  - Visiting `/inventory` renders: `Today's sales` → `Kes. 0` (`0 transaction(s)`).
  - Visiting `/reports` renders: `Reports · This month`, `Total revenue` → `Kes. 0`, and `No sales in this period.` across Best selling products, Sales by category, and Daily sales. A grading supervisor inspecting the app sees zeros unless they manually click `All time`.

### 3.2 Overly Rigid `find_duplicate()` & Serial-Number vs. SKU Identity Conflict

- **Empty-Model False-Positive Block (`App/app.py:289-307`, `App/templates/product_form.html:20`, `App/schema.sql:24`):**
  - In `product_form.html:20`, `model` is optional (`<input type="text" name="model" ...>` without `required`), defaulting to `""`.
  - `find_duplicate()` checks `serial_no` uniqueness (`lines 292-298`), then unconditionally executes:
    ```sql
    SELECT serial_no FROM products
    WHERE lower(name) = lower(?) AND lower(brand) = lower(?) AND lower(model) = lower(?) AND product_id != ?
    ```
  - **Empirical Probe Result:** Adding `"HDMI Cable"`, brand `"Generic"`, model `""`, serial `"HDMI-001"` succeeds. Subsequently adding `"HDMI Cable"`, brand `"Generic"`, model `""`, serial `"HDMI-002"` (different length/price/batch) is **blocked** with `"Duplicate detected"` because `(lower('HDMI Cable'), lower('Generic'), lower(''))` collides.
- **SKU vs. Per-Unit Serial Contradiction:**
  - `seed.py:37-46` stores `stock = 12` for `"HP 15 Laptop"` under a single `serial_no = "HP15-2207"` and `stock = 25` for `"SanDisk 64GB Ultra Flash Drive"` under `"SD64-8890"`. Thus `serial_no` behaves as a **bulk SKU**, yet `find_duplicate()` forbids adding another distinct unit/variant that shares `(name, brand, model)` with a different hardware serial number. Meanwhile, selling 1 of 12 laptops writes the same `"HP15-2207"` onto every receipt/sale row, preventing per-unit warranty tracking.
- **Bypassable Serial Normalization (`App/app.py:243-245`):**
  - `normalize_serial()` collapses whitespace (`re.sub(r"\s+", " ", value or "").strip().upper()`) but preserves hyphens/spaces differently: `"UA43-8842"`, `"UA43 8842"`, and `"UA438842"` are treated as three distinct products.

### 3.3 Floating-Point Currency (`REAL` / `float`) & Input Validation Defects

- **IEEE-754 Money Arithmetic:** `App/schema.sql:27,45,46` stores `price`, `unit_price`, and `total_price` as `REAL`. `App/app.py:272,275` parses `float(...)`, `App/app.py:555` computes `round(product["price"] * quantity, 2)`, and `App/app.py:420,623` computes `SUM(price * stock)` in SQLite floating point. While tolerable for whole-shilling prices, introducing fractional discounts, percentage promotions, or VAT will accumulate IEEE-754 rounding drift instead of exact `INTEGER` cents or `Decimal`.
- **Zero-Price Products Allowed (`App/app.py:273`):** `if price < 0` permits `price = 0` (`Kes. 0`). Verified empirically: submitting `price="0"` adds `"Zero Price Test"` to inventory without error.
- **Misleading Stock Upper-Bound Error (`App/app.py:280-285`):** `if stock < 0 or stock > 100000: raise ValueError`, but the `except ValueError:` handler flashes `"Stock must be a whole number of zero or more."` Verified empirically with `stock="100001"`.
- **Missing Server-Side Length Limits (`App/app.py:248-269`):** HTML templates specify `maxlength="100"` (`name`) and `maxlength="50"` (`brand`, `model`), but `validate_product_form()` only enforces `len <= 40` on `serial_no`; POST requests can store arbitrary-length strings in `name`, `brand`, `model`.
- **Client-Side Negative Quantity Preview (`App/static/app.js:17-25`):** Typing `-5` into the quantity input on `/products/<id>/sell` renders `Kes. -192,500.00` live before server validation rejects it.

### 3.4 Concurrency Race in `sell_product()` & Silent Query Defects

- **Stale Read Before Atomic `UPDATE` (`App/app.py:531, 545-566`):** `sell_product()` reads `product = get_product_or_404(product_id)` on line `531`, executes the atomic stock decrement on lines `545-547`, and then reads `product["price"]` (line `555`) and `product["stock"] - quantity` (line `563`) from the pre-update snapshot! If the owner updates price or restocks concurrently between line `531` and line `545`, the logged `unit_price`/`total_price` or the displayed `remaining` count in the low-stock flash alert will be stale.
- **Silent `LIMIT 500` Metric Mismatch in `/sales` (`App/app.py:586-593`):** The table query uses `LIMIT 500`, whereas the `totals` KPI query (`transactions`, `units`, `revenue`) aggregates **all** matching rows without `LIMIT`. Once sales exceed 500 rows, the KPI cards and the displayed table disagree silently with zero pagination or truncation banner.
- **Silent Invalid Date Handling (`App/app.py:324-328, 575-583`):** `_parse_date()` swallows invalid strings (verified empirically: `GET /sales?from=2026-13-99` silently resets `from` to `""`), and `from > to` returns empty results with no validation message.
- **Missing `username` Snapshot on `sales` (`App/templates/sales.html:33` & `App/schema.sql:40`):** Deleting a user sets `sales.user_id` to `NULL`, causing the `Sold by` column to degrade to `'—'` instead of preserving an immutable seller username snapshot.

### 3.5 Broken CSS Classes & Missing UI Behaviour

- **`App/static/style.css` omits selectors actively referenced by templates and Flask:**
  - `.flash-warning` (`App/app.py:567` + `App/templates/base.html:38`) — low-stock warning flashed after a sale renders unstyled (no background, border, or alert color).
  - `.row-low` (`App/templates/inventory.html:44`) — low-stock table rows receive no highlight styling.
  - `.tabs`, `.stat-hero`, `.table.compact` (`App/templates/reports.html:6,15,24,36,59`; `.table.compact` also at `App/templates/users.html:9`) — period switcher tabs, hero revenue metric, and compact tables lack dedicated CSS rules.
  - Confirmed via `Select-String` against `App/static/style.css`: none of these classes exist in the stylesheet.
- **No Audit Trail & No Pagination:** Direct stock overrides in `edit_product()` (`App/app.py:478`), `restock_product()` (`App/app.py:506`), and `delete_product()` (`App/app.py:519`) leave no `stock_movements` / audit log record. `/inventory` (`App/app.py:416`) loads the entire `products` table unpaginated.
- **Nav Active State Drop (`App/templates/base.html:14`):** `request.endpoint == 'main.inventory'` fails to highlight `Inventory` when on `/products/new`, `/products/<id>/edit`, or `/products/<id>/sell`.
- **Redundant Query on Every Request (`App/app.py:194-202`):** `inject_globals()` runs `SELECT COUNT(*) FROM products WHERE stock < ?` on every authenticated template render, duplicating the `low_stock` query already run in `inventory()` and `reports()`.

### 3.6 `test_system.py` Fabrication / Coverage Gap vs. Milestone 3 Table 3.2

`Milestone_3_Development_and_Testing.pdf` Section 3.5 (Table 3.2, p. 6) claims **9 distinct `PASS` test cases (`TC-01`–`TC-09`)** executed via `pytest` and the Flask test client. Inspection of `App/test_system.py` reveals:

- `App/test_system.py` contains **only 1 test function** (`test_system_flow_objectives`, lines `53-130`).
- **`TC-02` (Access Control / RBAC):** *"Attendant attempts to access `/products/new` → HTTP 403 Forbidden error returned"* is **NOT tested anywhere in `test_system.py`**. No attendant account is ever created or logged in during the test suite.
- **`TC-08` (Over-Stock Sale Prevention):** *"Attempt to sell 5 units when only 1 is in stock → Error: 'Not enough stock' displayed"* is **NOT tested anywhere in `test_system.py`**.
- **`TC-01` Credential Mismatch:** Table 3.2 states `ndungu / ndungu2026`, whereas `test_system.py:31` registers `ndungu / password123`.
- **Other Untested Paths:** `edit_product`, `restock_product`, `delete_product` (and `ON DELETE SET NULL` sale snapshot retention), `(name, brand, model)` duplicate detection, `normalize_serial` whitespace/case normalization, CSRF rejection (`400`), `/register` post-seed lockout, `/users` creation & self/last-owner deletion guards, `/sales` date filtering, `/reports` `today`/`week`/`month` windows, invalid prices/quantities, and search by `name`/`brand`/`model`.

### 3.7 Stale Paths, Non-Portable Scripts & Schema Documentation Drift

- **`App/run_system.bat:16`:** Hardcodes `"C:\Users\Sanga\AppData\Local\Programs\Python\Python312\python.exe" app.py` and omits `cd /d "%~dp0"`. Breaks on any machine with a different Python path or working directory.
- **Stale Scratch Directory (`Milestone_3_Development_and_Testing.pdf` Sec 3.6 p. 6; `App/generate_m3_doc.py:364`):** Documents `Application Directory: C:\Users\Sanga\.gemini\antigravity\scratch\ndungu-inventory` instead of `C:\Users\Sanga\Documents\Ndungu_Electronics_Project\App`.
- **Hardcoded Downloads Output (`App/generate_m3_doc.py:392`):** Writes `C:\Users\Sanga\Downloads\NDUNGU_ELECTRONICS_MILESTONE_3_REPORT.docx` and resides inside the deployable `App/` folder.
- **Milestone 3 Table 3.1 Schema & Hashing Drift (`Milestone_3` pp. 2–5 vs. `App/schema.sql` & `App/instance/inventory.db`):**
  - Milestone 3 Sec 3.1 (p. 2) and Sec 3.3.6 (p. 5) state passwords use **`PBKDF2:SHA256`** (and Table 3.1 p. 3 states **`PBKDF2`** cryptographically salted password hash), whereas `App/instance/inventory.db` (`users` rows 1 and 2, inspected read-only) actually stores **`scrypt:32768:8:1$...`** hashes (Werkzeug 3.x default).
  - Table 3.1 omits `users.created_at`, `products.created_at`, and `products.updated_at`.
  - Table 3.1 lists `sales.sale_date` default as `datetime('now')`, whereas `App/schema.sql:47` uses `DEFAULT (datetime('now', 'localtime'))`.
  - `App/seed.py:15-16` omits `PRAGMA foreign_keys = ON`.

---

## 4. Security & Operational Findings

| ID | Finding | Evidence / Location | Risk & Impact |
| :--- | :--- | :--- | :--- |
| **SEC-01** | **Debug Mode Enabled by Default** | `App/app.py:685-686`: `debug=os.environ.get("FLASK_DEBUG", "1") == "1"` | Defaults to `FLASK_DEBUG="1"`. Running `python app.py` or `run_system.bat` enables Werkzeug's debugger and auto-reloader by default, leaking stack traces/environment context if exposed beyond localhost. |
| **SEC-02** | **Committed Secrets & Runtime DB Without `.gitignore`** | `App/instance/secret_key` (64 hex chars), `App/instance/inventory.db`; zero `.gitignore` in root | Milestone 1 Sec 1.5 specifies GitHub as a remote backup repository. Pushing the repo as-is leaks the live Flask `SECRET_KEY` (enabling session cookie forgery as `user_id=1` owner) and user credential hashes. |
| **SEC-03** | **Missing HTTP Security Headers** | `App/app.py` (no `@bp.after_app_request` / headers middleware); `App/templates/reports.html:10` inline `onclick` | Lacks `Content-Security-Policy`, `X-Frame-Options: DENY` (clickjacking risk), `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `Cache-Control: no-store` on authenticated views (allowing browser back-button cache exposure after logout). |
| **SEC-04** | **No Login Brute-Force Protection / Lockout** | `App/app.py:334-351` (`login()`) | Unlimited password guesses allowed with zero rate limiting, zero temporary lockout, and zero failed-login audit trail. |
| **SEC-05** | **Hardcoded Weak Default Passwords in Repo & Docs** | `App/seed.py:27-28`, `App/run_system.bat:12-13`, `App/generate_m3_doc.py:367`, `Milestone_3` p. 7 | Publishes `ndungu / ndungu2026` and `kamau / staff123` across scripts and reports; `validate_new_user()` (`app.py:314`) enforces only `len >= 6` with no forced password rotation on first login. |
| **SEC-06** | **Incomplete Cookie & Session Lifecycle Controls** | `App/app.py:56-58` | Sets `SESSION_COOKIE_HTTPONLY=True` and `SESSION_COOKIE_SAMESITE="Lax"`, but omits `SESSION_COOKIE_SECURE` (required for PythonAnywhere HTTPS) and `PERMANENT_SESSION_LIFETIME` / inactivity timeout. |
| **SEC-07** | **No Password Reset / Self-Service Password Change** | `App/app.py:639-681` | Owners cannot reset an attendant's forgotten password without deleting the user (destroying `sales.user_id` links); users cannot change their own passwords; no CLI owner password recovery exists. |
| **OPS-01** | **SQLite Locking & Concurrency Fragility** | `App/app.py:102-108`, `App/instance/inventory.db` (`PRAGMA journal_mode` = `delete`) | Uses `DELETE` journal mode (read-only DB check confirmed `journal_mode: delete`), default 5s timeout, no `PRAGMA busy_timeout`, and no `BEGIN IMMEDIATE` on multi-step writes. Concurrent sales/edits risk `sqlite3.OperationalError: database is locked`. |
| **OPS-02** | **No `500` Error Handler & Brittle CSRF Expiry UX** | `App/app.py:69-70, 178-182` | Only `(400, 403, 404, 405)` have custom error pages; unhandled DB/runtime exceptions trigger raw HTTP 500. Expired-session POSTs immediately abort `400`, discarding unsaved form inputs. |
| **OPS-03** | **No Backup / Migration / Production Entrypoint** | `App/` root (`wsgi.py`, `requirements.txt`, backup script absent) | `init_db()` (`app.py:117-122`) runs `CREATE TABLE IF NOT EXISTS` only, providing no schema versioning (`ALTER TABLE`/migration strategy) for Milestone 4 additions (`promotions`, `sale_items`, `stock_movements`). |

---

## 5. Semester Grading Rubric Caveats (`Milestone_Instructions/*.png` & Docs)

### 5.1 Official Grading Rubric Breakdown Observed on Assessment Sheets

Inspection of all four images in `Milestone_Instructions/` reveals the exact Zetech University assessment structure (header handwritten `ADMNO: DSE-01-0145/2025`, `PROJECT TITLE: A DIGITAL INVENTORY SYSTEM FO...`; footer `SUPERVISOR`, `[I]CT DIPLOMA PROJECT CORDINATORS`, `HEAD OF DEPARTMENT/DEAN`):

| Milestone | Scope Required by Assessment Sheet | Documentation Deliverable | Observed Score Allocation |
| :--- | :--- | :--- | :--- |
| **Milestone 1: Project Planning & Analysis** (`Sheet_1.png`) | Statement of Problem, Justification, Objectives; Breakdown of tools and resources to be used; Breakdown of project schedule (Gantt chart) | System Documentation Coverpage and Chapter One | **`Score /10`** |
| **Milestone 2: Project Design** (`Sheet_1.png` + top of `Milestone_3_to_5_Sheet.png`) | UI design: Identify all user screens/interfaces and draw a rough sketch of each; *(middle design bullets cropped because `Sheet_2.png` is an exact duplicate of `Sheet_1.png`)*; ...design and ERD for database design (if DB is applicable in your project) | System Documentation: Chapter Two | **`Score /20`** |
| **Milestone 3: Project Development & Testing (1/2)** (`Milestone_3_to_5_Sheet.png`) | Practically working on the project; Feature-by-feature development and debugging; DB development and integration (if applicable in your project) | System Documentation: Chapter Three | **`Score /20`** |
| **Milestone 4: Project Development & Testing (2/2)** (`Milestone_3_to_5_Sheet.png`) | Practically working on the project; Feature-by-feature development and debugging; DB development and integration (if applicable in your project) | System Documentation: Chapter Three | **`Score /?`** *(denominator cropped at right image edge)* |
| **Milestone 5: Deployment** (`Milestone_3_to_5_Sheet.png` + `Milestone_5_and_6_Sheet.png`) | Launch your app in a simulated or real-world computational environment and deploy to see if it works; Test whether features work in the deployment environment | System Documentation: Chapter Three | **`Score /20`** |
| **Milestone 6: Final Touches on System Documentation** (`Milestone_5_and_6_Sheet.png`) | Preliminary Pages (pages between coverpage and chapter one); Chapter Four: Conclusions and Recommendations; References in APA 7 | Final Complete System Documentation (`TOTAL` cropped at right edge) | **`Score /?`** *(denominator cropped at right image edge)* |

### 5.2 Critical Academic & Rubric Risks to Resolve

1. **Strict Chapter 2 ↔ Chapter 3 Alignment (`Score /20` M2 + `Score /20` M3 + M4):** Supervisors grade Chapter Three against the promises of Chapter One and the blueprints of Chapter Two. Currently:
   - Milestone 1 Table 1.4.1 Row 6 (`Pricing and promotion management`) is unimplemented.
   - Milestone 2 Class Diagram (`Sale.generateReceipt()`, `Sale contains * Product`) is unimplemented.
   - Milestone 2 UI wireframes do not match `App/` layouts and omit half the application's screens, while Milestone 2 Flowchart/DFD/ERD/Use Case omit `attendant` (`kamau`), `promotions`, `sale_items`, and `stock_movements`. Both the new codebase **and** an updated Chapter Two (diagrams + UI screens) must match 1:1.
2. **Milestone 4 (`2/2`) Completeness:** Milestone 3 Sec 3.7 explicitly commits Milestone 4 to *"advanced reporting exports, live environment deployment on PythonAnywhere, and end-user acceptance testing."* The rebuilt system must complete Promotions, Multi-Item POS Cart + `generateReceipt()`, CSV/Print exports, Audit Log, Password/User lifecycle, and genuine multi-test verification covering every `TC-xx` row claimed in Chapter Three.
3. **Milestone 5 Live PythonAnywhere Deployment (`Score /20`):** Milestone 1 Sec 1.5 specifically commits to **PythonAnywhere**. Chapter Three must include WSGI configuration (`wsgi.py`), environment variable setup (`SECRET_KEY`, `FLASK_DEBUG=0`), and verified live deployment test evidence (screenshots + endpoint verification table confirming features work on the live PythonAnywhere URL, not just `127.0.0.1`).
4. **Milestone 1 & Milestone 6 Documentation Integrity Defects:**
   - **Cover Page & Programme Name Conflict:** `Milestone_1_Planning_and_Analysis.pdf` p. 1 leaves `SUBMITTED BY,` blank and lists `DIPLOMA IN COMPUTER SCIENCE` (`AUGUST 2026`), whereas `Milestone_3_Development_and_Testing.pdf` p. 1 lists `AUGUSTIN SANGA`, `DSE-01-0145/2025`, `Diploma in Software Engineering` (`October 2026`). These must be unified accurately (`DSE-01-0145/2025` matches the handwritten `ADMNO` on `Sheet_1.png`).
   - **Milestone 1 Formatting Defects:** Page 12 contains an orphaned caption (`TABLE 1.6.1 PROJECT SCHEDULE BREAKDOWN`) with no table below it, Page 13 is completely blank except page number `7`, and the Gantt chart spans `4-8 May` to `31st July` despite August/October/November milestones.
   - **Milestone 2 Numbering Bug:** `Milestone_2_Design_and_Modeling.pdf` restarts `Heading 1` list numbering at `1`, labeling headings `1. CHAPTER TWO`, `1.1.`, `1.2.`, `FIGURE 1.2.1`–`1.3.6`, contradicting `Figure 2.2.1`–`2.3.6` in `.docx` `Caption`-styled paragraphs.
   - **Milestone 6 Preliminary Pages & APA 7 References:** Milestone 1 pages `i`–`v` (`DECLARATION`, `DEDICATION`, `ACKNOWLEDGEMENT`, `ABSTRACT`, `DEFINITION OF KEY TERMS`, `ABBREVIATIONS AND ACRONYMS`, `Table of contents`, `LIST OF FIGURES`, `LIST OF TABLES`) currently contain `"LEAVE BLANK TILL AFTER COMPLETION"` placeholders—all must be populated in Milestone 6. Furthermore, Chapter One cites **`(Laudon & Laudon, 2022)`** (p. 7) and **`Rashid et al (2025)`** (p. 7 — note missing period/comma/parentheses: should be `(Rashid et al., 2025)` in APA 7), which require a complete **APA 7 References** section at the end of the final consolidated documentation.

---

## 6. Pre-Phase 5 UI, Contrast, Theme & Functional Stress-Test Audit (November 18, 2026)

**Auditor:** `coordinator` & Selenium Automated Browser Driver  
**Target:** Live Flask Server on `http://127.0.0.1:5000`  
**Automated Evidence:** 24 high-resolution viewport screenshots captured in `screenshots/audit/` across all 10 user screens in Light ("Thika Daylight") and Dark ("Wireframe Noir") modes.

### 6.1 Root Cause Analysis of UI, Contrast & Theme Flaws

| Defect ID | Component / Screen | Failure Observed | Root Cause in Codebase | Remediation Applied |
| :--- | :--- | :--- | :--- | :--- |
| **UI-01** | Global `base.html` | Dark mode toggle partially worked; body and footer stayed light grey (`#F8FAFC`) while topbar turned dark, creating a jarring half-baked look. | Line 2 and 57 of `base.html` had `<html class="h-full bg-slate-50 text-slate-900">` and `<body class="min-h-screen bg-slate-50 text-slate-900 ...">` without `dark:bg-slate-950 dark:text-slate-100`. | Added `dark:bg-slate-950 dark:text-slate-100` to both `<html>` and `<body>`, and updated `<footer>` with `dark:bg-slate-900/50 dark:border-slate-800 dark:text-slate-400`. |
| **UI-02** | Global `base.html` | Flash of unstyled theme (FOUC) on page transitions; headers briefly jumped between light and dark modes. | `initTheme()` script was placed at the bottom of `base.html` (line 164), executing *after* the DOM rendered. | Moved immediate IIFE theme initializer into `<head>` before any stylesheet or body rendering. |
| **UI-03** | Inventory (`inventory.html`) | Table, KPI summary cards, filter toolbar, search input, and pagination remained white in dark mode, causing white-on-white text and black headers against dark navbars. | Lines 1–265 had hardcoded `bg-white`, `border-slate-200/80`, and `text-slate-900` with zero `dark:` utility variants. Only the modal at line 267 had dark classes. | Overhauled lines 1–265 with complete dual-token classes: `dark:bg-slate-900`, `dark:border-slate-800`, `dark:text-white`, `dark:text-slate-300`, `dark:bg-slate-800/80` thead, and dark pagination controls. |
| **UI-04** | Auth (`login.html`, `register.html`, `error.html`) | Auth cards and inputs had zero dark mode styling, blinding operators in dark mode and clashing with dark topbars. | Hardcoded light mode containers (`bg-white border-slate-200/80`). | Added full dark mode support across login card, input fields (`dark:bg-slate-800 dark:border-slate-700 dark:text-white`), security notice banners, and error templates. |
| **UI-05** | POS Checkout Engine (`pos_service.py`) | Checkout failed with alert: `Transaction Failed: 'NoneType' object has no attribute 'strip'`. | When cart items contained bulk non-serialized items (e.g. Anker chargers, Oraimo powerbanks), `serial_no` was sent as `null`. Code called `item_in.get("serial_no").strip()` without null checking. | Replaced with `serial_raw = item_in.get("serial_no"); serial_requested = (serial_raw or "").strip()` in `pos_service.py`, and applied matching guards in `pos.py` and `domain/sale.py`. |

### 6.2 Screen-by-Screen Stress-Test Matrix

| Screen / URL | Mode Tested | Controls & Flows Exercised | Result & Evidence |
| :--- | :--- | :--- | :--- |
| **1. Login** (`/login`) | Light + Dark | Credential submission (`Augustin Sanga` / `NdunguAdmin2026!`), password toggle, 5-attempt lockout badge, invite link redirect. | **PASS** — `01_login_light.png`, `01_login_dark.png` |
| **2. Inventory** (`/inventory/`) | Light + Dark | KPI cards (Valuation, SKUs, Low-Stock warnings), search filter, category filter, stock status filter, pagination buttons, Quick Restock intake, "+ Add New Product" modal. | **PASS** — `02_inventory_light.png`, `02_inventory_dark.png`, `02b_inventory_modal.png` |
| **3. Product Detail** (`/inventory/product/1`) | Light + Dark | Metadata & pricing editor form, stock level indicator, hardware serials list, and tamper-evident `stock_movements` audit trail. | **PASS** — `03_product_detail_light.png`, `03_product_detail_dark.png` |
| **4. POS Register** (`/pos/`) | Light + Dark | Omnibar search (`Ctrl+K`), category filter pills, bulk item click-to-add, serialized item modal, live cart total calculation, +16% VAT arithmetic, Cash/M-Pesa tender selection. | **PASS** — `04_pos_register_light.png`, `04_pos_register_dark.png`, `04b_pos_cart_added.png` |
| **5. Receipt View** (`/pos/receipt/1`) | Light + Dark | Thermal 80mm print container, line-item itemization, KES formatted totals, print button (`@media print` clean). | **PASS** — `05_receipt_light.png`, `05_receipt_dark.png` |
| **6. Sales Ledger** (`/sales/`) | Light + Dark | Date range filter, payment method filter, status filter, receipt inspect modal, owner void reversal with inventory restitution, CSV and PDF export triggers. | **PASS** — `06_sales_ledger_light.png`, `06_sales_ledger_dark.png` |
| **7. Promotions** (`/promotions/`) | Light + Dark | Campaign creation modal, discount type validation (`percent` vs `fixed_cents`), target category/product selectors, start/end dates. | **PASS** — `07_promotions_light.png`, `07_promotions_dark.png` |
| **8. BI Reports** (`/reports/`) | Light + Dark | Period tabs (`Today`, `Yesterday`, `This Week`, `This Month`), telemetry summary KPIs, sales by category progress bars, low-stock reorder table, ReportLab PDF export, CSV export. | **PASS** — `08_bi_reports_light.png`, `08_bi_reports_dark.png` |
| **9. Users Admin** (`/users/`) | Light + Dark | Operator accounts table, role badges, single-use 24-hour invite token generator, security audit events log (`auth_events`). | **PASS** — `09_users_admin_light.png`, `09_users_admin_dark.png` |
| **10. Attendant RBAC** (`/inventory/` etc.) | Light + Dark | Logged in as `attendant1`. Verified POS and Inventory access. Verified strict `HTTP 403 Forbidden` on `/promotions/`, `/reports/`, and `/users/`. | **PASS** — `10_attendant_inventory_*.png`, `10b_attendant_*_block.png` |

### 6.3 Automated Verification Status

- **Automated Pytest Suite:** **48 / 48 tests passing** in 23.86 seconds (`tests/test_auth.py`, `tests/test_money.py`, `tests/test_phase2_views.py`, `tests/test_phase3_views.py`, `tests/test_pos_and_inventory.py`, `tests/test_reports_and_exports.py`, `tests/test_wsgi_and_responsive.py`).
- **WCAG 2.1 AA Contrast Ratios:** All dark and light mode tokens exceed the minimum 4.5:1 ratio (Dark Slate on Alabaster = 17.06:1; White on Primary Teal = 5.47:1; Light Slate on Dark Card = 13.98:1).
- **Zero Fabricated Tests:** Every test case maps to an actual running test function in `tests/`.
- **System Readiness:** Ready for Phase 5 live deployment configuration on PythonAnywhere Free Beginner Tier.
