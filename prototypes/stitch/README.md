# Ndungu Electronics IMS — Phase 0 UI Prototypes Dossier

**Project:** Ndungu Electronics Inventory Management System (Thika Branch)  
**Academic Context:** Zetech University — Augustin Sanga (`DSE-01-0145/2025`), Diploma in Software Engineering  
**Design System:** Hybrid Thika Daylight (`#F8FAFC` Alabaster Canvas / `#0F766E` Deep Teal / `Plus Jakarta Sans` / `IBM Plex Mono`) + Wireframe Noir Dark Mode  
**Stitch Cloud Project:** [projects/18021985306154218130](https://stitch.withgoogle.com/projects/18021985306154218130)  
**Interactive Local Hub:** [prototypes/stitch/index.html](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/index.html)

---

## 1. Executive Summary & Flow Architecture

Phase 0 delivers a connected 10-screen UI prototype built in Google Stitch. It provides a complete interactive workflow that can be stepped through page-by-page, simulating the daily operations of Ndungu Electronics in Thika, Kenya.

The prototypes strictly adhere to the locked architecture decisions:
- **Currency:** Monospace Kenyan Shillings formatting (`KES 4,892,400.00`) with zero floating-point math (backend mapped to integer cents).
- **Tax Policy:** +16% VAT computed on post-discount subtotal.
- **Tracking Modes:** Visual distinction between `bulk` accessories (cables, adapters) and `serialized` devices (smartphones, TVs, laptops with IMEI/serial tracking).
- **Security & RBAC:** Single-use 24-hour invite links, 15-minute brute-force account lockouts, and owner-only privileges for voids and pricing.

```
       [ S-01: Terminal Login ]
                 │
                 ├── (Users == 0 or Invite Link) ──► [ S-02: Account Setup & Invite ]
                 │
                 ▼
       [ S-03: Inventory Dashboard ] ◄────────────────────────────────┐
                 │                                                    │
                 ├── (Edit / Restock) ──► [ S-04: Product & Serial ]   │
                 │                                                    │
                 ├── (Cashier Sale)   ──► [ S-05: POS Register ]      │
                 │                               │                    │
                 │                               ▼                    │
                 │                     [ S-06: Receipt Drawer ]       │
                 │                               │                    │
                 ├── (Owner Pricing)  ──► [ S-07: Promotions Mgr ]    │
                 │                                                    │
                 ├── (Owner Audit)    ──► [ S-08: Sales & Voids ] ────┘
                 │                               │
                 ├── (Owner BI)       ──► [ S-09: BI Reports & CSV/PDF ]
                 │
                 └── (Owner Admin)    ──► [ S-10: Users & Audit Trail ]
```

---

## 2. Complete Screen Catalog

| Screen Code | File Name | Screen Title | Academic Test Mapping | Primary Role | Key UI & Interaction Features |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **S-01** | [`s01_login.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s01_login.html) | Terminal Login | `TC-01`, `TC-02` | Attendant, Owner | Brute-force lockout alert (5 attempts / 15 min), session token badge (`THK-POS-8842`), password eye toggle. |
| **S-02** | [`s02_register.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s02_register.html) | Account Setup & Invite | `TC-01`, `TC-03` | Owner (First Run) / Attendant | Single-use 24h token intake, Werkzeug scrypt validator (≥8 chars), auto-role assignment. |
| **S-03** | [`s03_inventory_dashboard.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s03_inventory_dashboard.html) | Inventory Dashboard | `TC-04`, `TC-05`, `TC-06`, `TC-15` | Owner, Attendant (Read) | KES 4.89M valuation KPI, bulk vs serialized chips, low-stock threshold warning, multi-select category filter. |
| **S-04** | [`s04_product_detail.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s04_product_detail.html) | Product Edit & Serial Intake | `TC-04`, `TC-05`, `TC-14` | Owner Only | Integer cents price fields, IMEI/serial intake repeater chips, normalized SKU generator, soft archive toggle. |
| **S-05** | [`s05_pos_register.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s05_pos_register.html) | Multi-Item POS Register | `TC-07`, `TC-08`, `TC-10`, `TC-18` | Cashier Attendant, Owner | Volt `Ctrl+K` omnibar, split-pane active cart, serial picker modal, live +16% VAT preview, quick tender buttons. |
| **S-06** | [`s06_receipt_drawer.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s06_receipt_drawer.html) | Receipt Drawer & Thermal Print | `TC-09`, `TC-20`, `TC-22` | Cashier, Customer | Slide-over drawer with backdrop blur, 80mm thermal receipt card, monospace VAT breakdown, `@media print` style. |
| **S-07** | [`s07_promotions_manager.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s07_promotions_manager.html) | Pricing & Promotions Manager | `TC-11`, `TC-12` | Owner Only | BOGO, percentage, and fixed KES off campaign builder; schedule date-pickers; live cart discount simulation. |
| **S-08** | [`s08_sales_ledger.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s08_sales_ledger.html) | Sales Ledger & Void Management | `TC-10`, `TC-13`, `TC-17` | Owner (Void), Attendant (View) | Immutable cashier and SKU snapshots, Owner void authorization modal with required reason and inventory restitution. |
| **S-09** | [`s09_bi_reports.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s09_bi_reports.html) | BI Reports & Low-Stock Reorder | `TC-15`, `TC-16`, `TC-20` | Owner Only | Daily sales telemetry, gross margin KPIs, formula-injection-safe CSV export, pure-Python ReportLab PDF printout. |
| **S-10** | [`s10_users_audit.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/s10_users_audit.html) | Users & Unified Audit Trail | `TC-01`, `TC-03`, `TC-17`, `TC-19` | Owner Only | 24-hour single-use invite link generator, attendant active/inactive toggle, lockout reset, tamper-evident audit table. |

---

## 3. How to Review & View the Prototypes

### Option A: Interactive Connected Review Hub (Recommended)
Open [`prototypes/stitch/index.html`](file:///c:/Users/Sanga/Documents/Ndungu_Electronics_Project/prototypes/stitch/index.html) in any web browser (Chrome, Edge, Firefox).
- **Page-by-page traversal:** Click `Next` / `Prev` or use keyboard arrow keys (`←` / `→`).
- **Mode Switching:** Toggle between **Live DOM** (interactive HTML/CSS) and **Hi-Res PNG** (high-resolution canvas render).
- **State Simulators:** Click `Skeleton` to view the 400ms loading skeleton animation or `Empty` to view the zero-record empty state.
- **Specification Drawer:** Review the academic test mapping, roles, and components for each screen.

### Option B: Cloud Canvas on Google Stitch
Visit the project directly on Google Stitch:
- URL: `https://stitch.withgoogle.com/projects/18021985306154218130`
- Provides an infinite visual canvas where all 10 screens can be inspected, compared, and modified side-by-side.

---

## 4. Phase 0 Quality Checklist

- [x] All 10 screens generated in Google Stitch under project `projects/18021985306154218130`.
- [x] Hybrid Thika Daylight palette applied consistently (`#F8FAFC`, `#0F766E`, `#10B981`, `#EF4444`).
- [x] All 10 HTML files downloaded and verified locally in `prototypes/stitch/`.
- [x] All 10 high-resolution PNG renders decoded and verified in `prototypes/stitch/`.
- [x] Connected interactive review hub created (`prototypes/stitch/index.html`).
- [x] Milestone 3/4 test cases (`TC-01` through `TC-22`) mapped to UI screens.
- [x] Phase 0 deliverable staged for user review prior to Phase 1 backend implementation.
