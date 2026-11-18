# Phase 2 Walkthrough: Multi-Item POS Register, Thermal Receipt & Product Serials

**Document ID:** `NE-WALKTHROUGH-PHASE2`  
**Execution Date:** November 18, 2026  
**System:** Ndungu Electronics Inventory Management System (Thika Main Branch)  
**Academic Context:** Zetech University — Augustin Sanga (`DSE-01-0145/2025`), Diploma in Software Engineering  
**Test Results:** **28 Passed / 28 Tests (100% Green)**  

---

## 1. Overview of Phase 2 Deliverables

Phase 2 transitions the application from a passive catalog viewer into an active retail counter Point-of-Sale (POS) and inventory control system. All UI views strictly match their respective Google Stitch prototypes and implement Rune design guidelines (accessible AA contrast, tabular monospace pricing, stock alerts, and keyboard affordances).

```
[ S-03: Inventory Dashboard ]
       │
       ├── (Click "Details") ──► [ S-04: Product Details & Serial Intake ]
       │                              • Metadata editing (Name, Brand, Model, Category)
       │                              • Pricing in KES (stored as integer cents)
       │                              • Hardware IMEI/Serial registry with live status
       │                              • Audited Stock Movements ledger
       │                              • Owner-only Soft-Archive protection
       │
       └── (Nav: "POS Register") ──► [ S-05: Multi-Item POS Register ]
                                          • Omnibar Search (Ctrl+K shortcut)
                                          • Live stock validation & steppers
                                          • Serial selector modal for serialized hardware
                                          • Live +16% VAT arithmetic (on post-discount subtotal)
                                          • Multi-tender selection (Cash, M-Pesa, Card)
                                          │
                                          ▼ (Authorize Sale)
                                     [ S-06: Slide-Over Thermal Receipt Drawer ]
                                          • Monospace itemized breakdown (IBM Plex Mono)
                                          • Bound hardware serial numbers
                                          • Thermal 80mm @media print stylesheet
```

---

## 2. Key Components Implemented

### 2.1 Multi-Item POS Register (`app/templates/pos.html` - S-05)
* **Catalog Grid & Filters:** Instant search by name, brand, SKU with `Ctrl+K` keybinding, category pill filters, stock health color coding (`emerald` > 5, `amber` 4–5, `rose` <= 3).
* **Active Split-Pane Cart:** Real-time quantity steppers clamped to live stock, serial picker modal for serialized items (smartphones, TVs, laptops), promo coupon code support (`THIKA5`).
* **Locked VAT Arithmetic:** Computed strictly as:
  $$\text{discounted\_subtotal} = \max(0, \text{subtotal} - \text{discount})$$
  $$\text{tax} = \text{round\_half\_up}(\text{discounted\_subtotal} \times 0.16)$$
  $$\text{total} = \text{discounted\_subtotal} + \text{tax}$$
* **Counter Tender:** Multi-payment selector (Cash, M-Pesa reference code, Card) with AJAX submission backed by CSRF token protection.

### 2.2 Slide-Over Thermal Receipt Drawer (`app/templates/receipt.html` - S-06)
* Immediate slide-over preview on checkout completion with option to reprint anytime via `/pos/receipt/<receipt_no>`.
* Itemized listing showing line quantities, unit prices, bound hardware serial numbers, and complete tax breakdown.
* **Thermal 80mm Print Engine:** Pure CSS `@media print` rules set `@page { size: 80mm auto; margin: 2mm; }` and suppress navigation, sidebar, and background clutter for direct thermal receipt roll output.

### 2.3 Product Detail & Serial Intake (`app/templates/product_detail.html` - S-04)
* Full metadata management (name, brand, model, category, integer cents price and cost, reorder threshold, supplier contact).
* Hardware Serial Number registry displaying unit-by-unit tracking (`in_stock`, `sold`, `defective`).
* Audited stock movements table rendering recent deltas with actor snapshots.
* RBAC protected: only the store `owner` can soft-archive products (`is_active = 0`).

### 2.4 Global Base Navigation & Dark Mode (`app/templates/base.html`)
* Header navigation connecting **Inventory** (`/inventory/`) and **POS Register** (`/pos/`).
* Active route detection automatically highlights the current view.
* Dark Mode toggle (`Wireframe Noir`) storing theme preference in `localStorage`.
* Clean status pill showing active cashier username and role badge.

---

## 3. Security & Software Engineering Compliance

Per academic and enterprise guidelines:
1. **Zero Credential or Session Exposure:**
   - Password hashes are never sent to templates or returned in JSON responses.
   - User sessions are stored strictly server-side; cookie has `HttpOnly` and `SameSite=Lax`.
   - Security headers enforced on every request:
     - `Content-Security-Policy: default-src 'self' ...`
     - `X-Frame-Options: DENY`
     - `X-Content-Type-Options: nosniff`
     - `Cache-Control: no-store, no-cache, must-revalidate` on all authenticated endpoints.
2. **CSRF Enforcement:**
   - All mutating requests (`POST /pos/checkout`, `POST /inventory/product/<id>`, `POST /inventory/product/<id>/archive`) require valid CSRF tokens verified via HMAC constant-time comparison.
3. **Atomic Concurrency & Financial Integrity:**
   - Database operations use SQLite `BEGIN IMMEDIATE` locks, eliminating checkout race conditions.
   - All currency values are stored as integer cents to avoid floating-point rounding drift.

---

## 4. Automated Test Verification Results

All 28 tests pass under `pytest -v`:

```
tests/test_money.py::test_tc14_integer_cents_conversion PASSED           [  3%]
tests/test_money.py::test_tc14_to_kes_decimal PASSED                     [  7%]
tests/test_money.py::test_tc14_format_kes PASSED                         [ 10%]
tests/test_money.py::test_tc14_vat_calculation_locked_policy PASSED      [ 14%]
tests/test_money.py::test_tc14_money_arithmetic_and_immutability PASSED  [ 17%]
tests/test_money.py::test_tc14_no_float_storage_in_db PASSED             [ 21%]
tests/test_auth.py::test_tc01_successful_login_and_logout PASSED         [ 25%]
tests/test_auth.py::test_tc01_brute_force_lockout_after_five_attempts PASSED [ 28%]
tests/test_auth.py::test_tc02_rbac_owner_required_decorator PASSED       [ 32%]
tests/test_auth.py::test_tc17_security_headers_and_csrf_protection PASSED [ 35%]
tests/test_auth.py::test_tc19_scrypt_password_verification PASSED        [ 39%]
tests/test_pos_and_inventory.py::test_tc03_inventory_crud PASSED         [ 42%]
tests/test_pos_and_inventory.py::test_tc04_hybrid_tracking_serialized_serials PASSED [ 46%]
tests/test_pos_and_inventory.py::test_tc05_smart_duplicate_detection_empty_model_safe PASSED [ 50%]
tests/test_pos_and_inventory.py::test_tc06_low_stock_threshold_alerts PASSED [ 53%]
tests/test_pos_and_inventory.py::test_tc07_multi_item_checkout_and_stock_deduction PASSED [ 57%]
tests/test_pos_and_inventory.py::test_tc08_over_stock_block_and_rollback PASSED [ 60%]
tests/test_pos_and_inventory.py::test_tc10_vat_arithmetic_on_checkout PASSED [ 64%]
tests/test_pos_and_inventory.py::test_tc13_owner_void_reversal_and_stock_restitution PASSED [ 67%]
tests/test_pos_and_inventory.py::test_tc18_concurrent_checkout_race_safety PASSED [ 71%]
tests/test_phase2_views.py::test_pos_register_requires_login PASSED      [ 75%]
tests/test_phase2_views.py::test_pos_register_view_loads_for_owner PASSED [ 78%]
tests/test_phase2_views.py::test_pos_register_view_loads_for_attendant PASSED [ 82%]
tests/test_phase2_views.py::test_pos_get_serials_endpoint PASSED         [ 85%]
tests/test_phase2_views.py::test_pos_checkout_ajax_flow PASSED           [ 89%]
tests/test_phase2_views.py::test_product_detail_and_update PASSED        [ 92%]
tests/test_phase2_views.py::test_product_archive_rbac_attendant_forbidden PASSED [ 96%]
tests/test_phase2_views.py::test_product_archive_owner_success PASSED    [100%]

============================= 28 passed in 35.24s =============================
```
