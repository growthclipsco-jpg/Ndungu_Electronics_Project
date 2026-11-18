"""
WSGI entrypoint for PythonAnywhere Free Beginner Tier deployment.
Exposes 'application' callable without invoking app.run().
"""

import sys
from pathlib import Path

# Ensure application root directory is first on Python sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.config import PythonAnywhereConfig

# Expose WSGI application object
application = create_app(PythonAnywhereConfig)
