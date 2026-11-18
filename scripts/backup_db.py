"""
Database Hot-Backup Utility for Ndungu Electronics IMS
Uses sqlite3.Connection.backup() for lock-free, zero-downtime hot backups.
Enforces quota hygiene for PythonAnywhere 512 MiB disk limits by retaining
at most 5 rolling snapshots in backups/.
"""

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "instance" / "inventory.db"
BACKUP_DIR = BASE_DIR / "backups"
MAX_SNAPSHOTS = 5


def perform_backup():
    if not DB_PATH.exists():
        print(f"[ERROR] Live database not found at: {DB_PATH}")
        sys.exit(1)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"backup_{timestamp}.db"

    print(f"[*] Initiating SQLite hot-backup from: {DB_PATH.name}")
    print(f"[*] Target destination: {backup_file}")

    source_conn = None
    dest_conn = None

    try:
        source_conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
        dest_conn = sqlite3.connect(str(backup_file))

        # Perform atomic lock-free hot backup via SQLite online backup API
        with dest_conn:
            source_conn.backup(dest_conn, pages=100, sleep=0.01)

        size_kb = backup_file.stat().st_size / 1024
        print(f"[SUCCESS] Hot-backup completed successfully ({size_kb:.1f} KB).")

    except Exception as e:
        print(f"[FAIL] Backup failed: {e}")
        if backup_file.exists():
            backup_file.unlink(missing_ok=True)
        sys.exit(1)

    finally:
        if source_conn:
            source_conn.close()
        if dest_conn:
            dest_conn.close()

    # Retention Pruning: Keep at most MAX_SNAPSHOTS
    prune_old_snapshots()


def prune_old_snapshots():
    snapshots = sorted(BACKUP_DIR.glob("backup_*.db"), key=lambda p: p.stat().st_mtime)
    excess = len(snapshots) - MAX_SNAPSHOTS

    if excess > 0:
        print(f"[*] Pruning {excess} old snapshot(s) to enforce {MAX_SNAPSHOTS}-file quota cap...")
        for old_file in snapshots[:excess]:
            try:
                old_file.unlink()
                print(f"  [-] Pruned: {old_file.name}")
            except Exception as e:
                print(f"  [!] Failed to prune {old_file.name}: {e}")
    else:
        print(f"[*] Current snapshot count: {len(snapshots)} / {MAX_SNAPSHOTS} (within quota limits).")


if __name__ == "__main__":
    perform_backup()
