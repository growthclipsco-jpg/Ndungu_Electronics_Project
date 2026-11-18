"""One-off script: unlock account and reset password for Augustin Sanga."""
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB = "instance/inventory.db"
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# Show current state
rows = db.execute("SELECT user_id, username, role, is_active, failed_login_attempts, locked_until FROM users").fetchall()
print("Current users:")
for r in rows:
    print(f"  [{r['user_id']}] {r['username']} | role={r['role']} | active={r['is_active']} | failed={r['failed_login_attempts']} | locked_until={r['locked_until']}")

# Unlock + reset password
new_hash = generate_password_hash("200 Sanga", method="scrypt")
db.execute(
    "UPDATE users SET failed_login_attempts=0, locked_until=NULL, password_hash=?, is_active=1 WHERE user_id=1",
    (new_hash,)
)
db.commit()
print("\n=== Account unlocked and password reset to '200 Sanga' ===")

# Verify
row = db.execute("SELECT password_hash FROM users WHERE user_id=1").fetchone()
ok = check_password_hash(row["password_hash"], "200 Sanga")
print("Password verification:", "PASS" if ok else "FAIL")
db.close()
