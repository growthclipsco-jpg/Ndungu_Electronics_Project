# Production Deployment Guide — Ndungu Electronics IMS

**Target Environment:** PythonAnywhere Free Beginner Tier  
**Target Domain:** `https://augustinsanga.pythonanywhere.com`  
**System Architecture:** Flask 3.x, Python 3.12 WSGI, Persistent SQLite (`DELETE` journal mode for NFS), ReportLab pure-Python PDF engine.  
**Resource Constraints:** 512 MiB shared disk quota, 1 synchronous web worker, outbound HTTP whitelist.

---

## 1. Pre-Deployment Architecture Verification

Before deploying, verify that the application satisfies all constraints specified in `AGENTS.md` and `implementation.md`:

| Requirement | Implementation Detail | Verification Status |
| :--- | :--- | :--- |
| **WSGI Entrypoint** | `wsgi.py` exposes `application = create_app(PythonAnywhereConfig)` | ✅ Verified via `TC-21` |
| **NFS SQLite Safety** | `PythonAnywhereConfig` forces `PRAGMA journal_mode = DELETE;` (never WAL on NFS) | ✅ Enforced in `app/config.py` |
| **Busy Timeout** | `PRAGMA busy_timeout = 10000;` and `timeout = 30.0` prevents locking errors | ✅ Enforced in `app/db.py` |
| **Lean Production Dependencies** | `requirements.txt` contains only Flask, python-dotenv, and ReportLab (~35 MiB total) | ✅ Segregated from `requirements-dev.txt` |
| **Zero Secret Leakage** | `.gitignore` blocks `.env`, `instance/`, `*.db*`, `logs/`, and `backups/` | ✅ Verified via static security audit |
| **Health Check Endpoint** | `GET /healthz` returns `200 {"status": "ok", "db": "ok"}` | ✅ Live endpoint tested |

---

## 2. Step-by-Step Deployment Instructions

### Step 1: Open Bash Console on PythonAnywhere
1. Log in to your [PythonAnywhere Dashboard](https://www.pythonanywhere.com/).
2. Navigate to the **Consoles** tab.
3. Under **Start a new console**, click **Bash**.

---

### Step 2: Clone or Pull the Repository
In the PythonAnywhere Bash console:

```bash
cd ~
# If first time deployment:
git clone https://github.com/augustinsanga/Ndungu_Electronics_Project.git
cd ~/Ndungu_Electronics_Project

# If updating existing deployment:
cd ~/Ndungu_Electronics_Project
python scripts/backup_db.py
git pull origin main
```

---

### Step 3: Create Lean Virtual Environment (Disk Quota Safe)
To ensure the deployment remains safely within PythonAnywhere's **512 MiB disk quota**, install **only** the production dependencies with `--no-cache-dir`:

```bash
cd ~/Ndungu_Electronics_Project

# Create Python 3.12 virtualenv
python3.12 -m venv ~/.virtualenvs/ne-ims

# Activate virtualenv
source ~/.virtualenvs/ne-ims/bin/activate

# Install production dependencies only (never install dev dependencies on server)
pip install --no-cache-dir -r requirements.txt

# Clear any cached pip wheels to save disk quota
rm -rf ~/.cache/pip
```

Check disk usage to confirm quota headroom:
```bash
du -sh ~ ~/.virtualenvs/ne-ims
# Total usage will typically be ~80-110 MiB, leaving >400 MiB free!
```

---

### Step 4: Configure the Web App in PythonAnywhere Dashboard

1. Navigate to the **Web** tab in the PythonAnywhere dashboard.
2. If the web app is not yet created, click **Add a new web app**:
   - Choose **Manual configuration** (do NOT choose the Flask wizard, as we use a custom WSGI entrypoint).
   - Select **Python 3.12**.
3. Once the web app is created, configure the sections:

#### A. Code Section
- **Source code:** `/home/augustinsanga/Ndungu_Electronics_Project`
- **Working directory:** `/home/augustinsanga/Ndungu_Electronics_Project`

#### B. Virtualenv Section
- **Path:** `/home/augustinsanga/.virtualenvs/ne-ims`

#### C. WSGI Configuration File
Click the link to edit `/var/www/augustinsanga_pythonanywhere_com_wsgi.py`. Replace its entire contents with:

```python
import os
import sys
from pathlib import Path

# Set environment variables for production security
os.environ["FLASK_ENV"] = "production"
os.environ["SECRET_KEY"] = "prod-ndungu-ims-zetech-dse01-0145-2025-supersecretkey992"
os.environ["DB_JOURNAL_MODE"] = "DELETE"

# Anchor application root directory
PROJECT_ROOT = Path("/home/augustinsanga/Ndungu_Electronics_Project")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import the WSGI application callable
from wsgi import application
```
Click **Save** (top right) and return to the **Web** tab.

#### D. Static Files Mapping Table
In the **Static files** section of the Web tab, configure the mapping so PythonAnywhere serves CSS, JS, and images directly via Nginx without hitting the Flask worker:

| URL | Directory |
| :--- | :--- |
| `/static/` | `/home/augustinsanga/Ndungu_Electronics_Project/app/static` |

#### E. Security Settings
- Enable **Force HTTPS** (toggle switch to ON).

---

### Step 5: Initialize Production Database & Seeding

In your PythonAnywhere Bash console:

```bash
cd ~/Ndungu_Electronics_Project
source ~/.virtualenvs/ne-ims/bin/activate

# Ensure instance directory exists
mkdir -p instance backups

# Run seed script to provision initial database, tables, and owner account
python -c "from app import create_app; from app.config import PythonAnywhereConfig; from app.seed import seed_database; app = create_app(PythonAnywhereConfig); seed_database(app)"
```

This provisions:
- SQLite database at `/home/augustinsanga/Ndungu_Electronics_Project/instance/inventory.db`
- `PRAGMA journal_mode = DELETE`
- Owner Account: `Augustin Sanga`
- Attendant Account: `attendant1`
- 12 initial electronics products (hybrid bulk and serialized units)
- Relative-date sample sales and active promotions

---

### Step 6: Reload and Verify Live Web Application

1. In the PythonAnywhere **Web** tab, click the big green **Reload augustinsanga.pythonanywhere.com** button.
2. Wait ~5 seconds for the worker to reload.
3. Test the live health endpoint:
   ```bash
   curl -i https://augustinsanga.pythonanywhere.com/healthz
   ```
   **Expected Response:**
   ```http
   HTTP/2 200 
   content-type: application/json
   
   {"db":"ok","status":"ok"}
   ```

---

## 3. Post-Deployment Verification Checklist

| Test Item | Verification Procedure | Expected Outcome |
| :--- | :--- | :--- |
| **1. Health Endpoint** | Visit `https://augustinsanga.pythonanywhere.com/healthz` | HTTP 200 `{"db": "ok", "status": "ok"}` |
| **2. HTTPS Security** | Visit `http://augustinsanga.pythonanywhere.com/` | Automatically 301/302 redirects to HTTPS with `Secure; HttpOnly` cookies |
| **3. Owner Login** | Log in with `Augustin Sanga` | Redirects to `/inventory/` with full owner navigation visible |
| **4. Theme Toggle** | Click Dark Mode icon in topbar | UI switches cleanly between Thika Daylight and Wireframe Noir |
| **5. Add Product** | Click `+ Add New Product` on `/inventory/` | Modal opens, accepts metadata/serials, saves to ledger |
| **6. POS Checkout** | Add items on `/pos/`, tender via Cash or M-Pesa | Atomic checkout succeeds, generates thermal 80mm receipt |
| **7. Attendant RBAC** | Log in as `attendant1`, visit `/promotions/` | HTTP 403 Forbidden rendered with Return to Dashboard button |
| **8. Reports & PDF** | Visit `/reports/`, click `Download PDF (A4)` | Downloads valid ReportLab PDF sales telemetry report |

---

## 4. Maintenance & Operational Runbooks

### 4.1 Zero-Downtime Hot Backup
Run before pulling updates or performing schema changes:
```bash
python scripts/backup_db.py
```
*Creates `backups/backup_YYYYMMDD_HHMMSS.db` and automatically prunes to keep at most 5 snapshots.*

### 4.2 30-Day Inactivity Keep-Alive
PythonAnywhere free accounts pause web workers if the account is not accessed for 30 consecutive days (all files and databases remain safe).
- Once a month, log in to PythonAnywhere.
- On the **Web** tab, click **Run until 3 months from today** (or click **Reload**).

### 4.3 Emergency Owner Password Reset
If the owner password is lost:
```bash
python -c "from app import create_app; from app.config import PythonAnywhereConfig; from app.services.auth_service import AuthService; app = create_app(PythonAnywhereConfig); [AuthService.reset_password(1, 'NdunguAdmin2026!')]"
```
