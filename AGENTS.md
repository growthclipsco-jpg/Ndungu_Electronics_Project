# AGENTS.md — Production Engineering Guideline Book (Ndungu Electronics IMS)

**Project:** Ndungu Electronics Inventory Management System (Thika)  
**Academic Context:** Zetech University — Augustin Sanga (`DSE-01-0145/2025`), Diploma in Software Engineering  
**Source of Truth:** [implementation.md](file:///C:/Users/Sanga/Documents/Ndungu_Electronics_Project/implementation.md) | **Legacy Forensics:** [audit.md](file:///C:/Users/Sanga/Documents/Ndungu_Electronics_Project/audit.md)  
**Target Hosting:** **PythonAnywhere Free Beginner Tier** (`512 MiB` disk quota, 1 web worker, NFS-backed persistent SQLite)

---

## 1. Golden Rules & Phase Discipline

1. **Follow Locked Phases Sequentially:** Execute `Phase 0 (Google Stitch 10-screen UI)` → `Phase 1 (Core Backend, DB & Auth)` → `Phase 2 (Inventory, Promos & POS)` → `Phase 3 (Reports, Exports & UI)` → `Phase 4 (QA & Selenium E2E)` → `Phase 5 (PythonAnywhere Live Deploy)` → `Phase 6 (Milestones 1–6 Docs)`. Never skip ahead or improvise unapproved architecture changes.
2. **Do Not Modify Legacy `App/`:** Keep `App/` strictly read-only as a forensic baseline and optional legacy DB migration source until cutover.
3. **Zero Fabricated Metrics or Tests:** Every `TC-01`–`TC-22` test case claimed in `implementation.md` and Milestone 3/4 documentation MUST map 1:1 to a real, passing `pytest` function. Never report tests as passing unless observed after the final edit.

---

## 2. Architecture & Code Guardrails (What to Build vs. Avoid)

### 2.1 Database, Concurrency & Money Arithmetic
- **NEVER use `REAL` or `float` for KES currency.** Store all prices, costs, discounts, VAT, and totals as **`INTEGER` cents** (`1 KES = 100 cents`) and compute rounding exclusively via `Decimal(..., ROUND_HALF_UP)` in `app/domain/money.py`.
- **Locked VAT Policy (`Q3 B`):** Apply **`+16% VAT` on top of post-discount subtotal** (`discounted_subtotal = subtotal_cents - discount_cents`; `tax_cents = round_half_up(discounted_subtotal * 0.16)`; `total_cents = discounted_subtotal + tax_cents`).
- **Environment-Aware SQLite Journal Mode (`ADR-01`):**
  - **Local Dev / `pytest`:** `PRAGMA journal_mode = WAL;`
  - **PythonAnywhere Production:** `PRAGMA journal_mode = DELETE;` *(NEVER use `WAL` on PythonAnywhere's networked NFS filesystem, which risks `SQLITE_IOERR` with `-shm` mmap files).*
- **Connection & Transaction Safety:** Always enable `PRAGMA foreign_keys = ON;`, `PRAGMA busy_timeout = 10000;`, and `timeout=30.0`. Wrap all stock-mutating checkouts, restocks, and voids in **`BEGIN IMMEDIATE`** and re-read live `price_cents`, `stock`, and `is_active` *inside* the transaction (avoiding `App/`'s stale pre-update read bug).
- **Relative Seed Dates:** Never hardcode calendar dates in `app/seed.py`. Compute sample sales and promotion windows relative to `datetime.now()` (`today`, `-2d`, `-8d`) so `/inventory` (`Today's sales`) and `/reports` (`This month`) never boot showing `Kes. 0`.

### 2.2 Product Identity, Duplicates & Stock Integrity
- **Hybrid Identity (`ADR-03`):** Every product has a required unique `sku` + `sku_normalized` (`re.sub(r"[^A-Z0-9]", "", value.upper())`) and `tracking_mode IN ('bulk', 'serialized')`. Serialized items (TVs, laptops, smartphones) register individual units in `product_serials` and bind sold serials to `sale_items`.
- **Avoid the Empty-Model Duplicate Trap:** Only warn/block on `(lower(name), lower(brand), lower(model))` when **`model.strip() != ""`**. Distinct generic items with empty `model` (e.g., `HDMI-001` vs. `HDMI-002`) MUST save cleanly.
- **Validation Parity:** Server-side validation must reject `price_cents <= 0` (never allow `Kes. 0` products), enforce `stock` bounds `0..100000` with accurate error messages, enforce string max lengths matching HTML forms, and log every stock mutation in `stock_movements`.
- **Soft Archive Only:** Never hard-delete products or users with transaction history; set `is_active = 0` and store immutable snapshots (`cashier_snapshot`, `sku_snapshot`, `product_name_snapshot`, `promo_name_snapshot`) on `sales` and `sale_items`.

### 2.3 Security, Auth & Request Lifecycle
- **Safe Defaults:** `FLASK_DEBUG` MUST default to `"0"`. `SECRET_KEY` MUST come from environment variables in production (`.env` / PythonAnywhere WSGI) and never be committed. `.gitignore` MUST exclude `.env`, `instance/`, `*.db*`, `logs/`, and `backups/`.
- **Password & Invite Lifecycle (`Q4 A`):** Hash passwords with Werkzeug `scrypt` (`>= 8` chars, letters + numbers). `/register` handles first-run Owner setup (`users == 0`) and **Owner-issued 24-hour single-use Invite Token links** (`/register?token=...`) thereafter; anonymous uninvited `/register` redirects to `/login`.
- **Brute-Force Lockout & RBAC:** Lock accounts for 15 minutes (`HTTP 429`) after 5 failed login attempts, logged in `auth_events`. Protect all catalog mutations, promotions, BI reports, exports, user admin, and sale voids with `@owner_required` (`HTTP 403` for attendants).
- **CSRF & Headers:** Enforce CSRF tokens on every POST form and AJAX header (`X-CSRFToken`), with friendly form-recovery on expired sessions (`OPS-02`). Attach `Content-Security-Policy` (no inline `onclick=`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `Cache-Control: no-store` on authenticated responses.

### 2.4 UI, Typography, Accessibility & Exports
- **Locked Visual System (`Q1 A`):** **Hybrid Thika Daylight** (`#F8FAFC` / `#FFFFFF` / `#0F766E` default, `Plus Jakarta Sans` + `IBM Plex Mono`, slide-over receipt drawer, `@media print` 80mm/A4 stylesheet) + optional **Wireframe Noir** dark-mode CSS token toggle (`#2563EB` WCAG-compliant primary) + **Volt Command** `Ctrl+K` omnibar & split-pane POS cart on `/pos`.
- **Self-Hosted Static Assets:** PythonAnywhere's free tier blocks arbitrary outbound internet access and our CSP restricts external scripts/styles. Bundle fonts, icons, CSS, and JS locally inside `app/static/` (zero external CDN dependencies).
- **Nav & Pagination Hygiene:** Match active navigation states at the blueprint/prefix level (`/products/*` keeps `Inventory` active). Paginate `/inventory` and `/sales` server-side (`25` rows/page) with `COUNT(*)` sharing the exact same `WHERE` clause and allowlisted `ORDER BY` dictionary.
- **Pure-Python Exports (`ADR-07`):** Use **ReportLab** for PDFs (never `WeasyPrint` or C-heavy PDF libraries). Sanitize CSV cells starting with `=`, `+`, `-`, `@`, `\t`, or `\r` by prefixing `'` and emit UTF-8 BOM (`\ufeff`).

---

## 3. PythonAnywhere Free Beginner Tier — How to Fix & Avoid Pitfalls

| Pitfall / Constraint | How to **Avoid** | How to **Fix** If Triggered |
| :--- | :--- | :--- |
| **512 MiB Disk Quota Exceeded** | Split `requirements.txt` (Flask, ReportLab, python-dotenv ONLY) from `requirements-dev.txt` (pytest, selenium, python-docx). Install on server with `pip install --no-cache-dir -r requirements.txt`. Cap `backups/` at 5 snapshots. | Run `du -sh ~/* ~/.cache` in PythonAnywhere Bash; clear `~/.cache/pip`, prune old `backups/`, remove unused files, and run `VACUUM;` on SQLite. |
| **SQLite `database is locked` / `SQLITE_IOERR`** | Set `DB_JOURNAL_MODE=DELETE` on PythonAnywhere, `timeout=30.0`, `busy_timeout=10000`, `BEGIN IMMEDIATE`. Never use `WAL` on NFS. | Stop web app, check `PRAGMA journal_mode;`, switch to `delete`, remove stray `-wal`/`-shm` files, and click **Reload**. |
| **`NoSuchFileOrDirectory` / Wrong CWD** | Anchor all paths via `BASE_DIR = Path(__file__).resolve().parent.parent` in `app/config.py`. | Verify `sys.path` and `DATABASE_PATH` in `wsgi.py` and PythonAnywhere **Error log**. |
| **Static Files 404 / Unstyled Pages** | Map `/static/` URL → `<repo>/app/static` directly in the PythonAnywhere **Web** tab; keep zero undefined CSS classes. | Verify exact case-sensitive Linux path in Web tab Static Files table and click **Reload**. |
| **1-Worker Request Blocking** | Keep queries indexed (`schema.sql` indexes), paginated (`25/page`), and free of blocking sleeps or unbounded exports. | Inspect **Server log** / slow queries, verify indexes exist, and keep PDF/CSV generation scoped to filtered datasets. |
| **30-Day Inactivity App Expiry** | Log into PythonAnywhere monthly and click **Run until 3 months from today** in the Web tab. | Click **Reload** / **Enable** in the Web tab; files and `instance/inventory.db` remain intact. |

---

## 4. Verification & Release Checklist (Before Any Phase Sign-Off)

1. Run full test suite locally: `pytest -v -p no:cacheprovider` — all **22 tests (`TC-01`–`TC-22`)** including 10-thread concurrency (`TC-18`), WSGI/health check (`TC-21`), and Selenium responsive/print checks (`TC-20`, `TC-22`) must pass.
2. Verify `git status` shows zero committed secrets (`.env`, `instance/`, `*.db*`, `logs/`).
3. On PythonAnywhere: run `python scripts/backup_db.py` before `git pull`, verify `du -sh ~` is safely under `512 MiB`, click **Reload**, and confirm `GET /healthz` returns `200 {"status": "ok", "db": "ok"}`.
