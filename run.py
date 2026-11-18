"""
Local development launcher for Ndungu Electronics IMS.
Respects FLASK_DEBUG from environment (defaults to False for safety).
"""

import os
from app import create_app
from app.config import get_config

if __name__ == "__main__":
    config_cls = get_config()
    app = create_app(config_cls)
    debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Ndungu Electronics IMS on http://127.0.0.1:{port} (Debug={debug_mode})")
    app.run(host="127.0.0.1", port=port, debug=debug_mode)
