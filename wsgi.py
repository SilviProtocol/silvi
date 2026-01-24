#!/usr/bin/env python3
"""
WSGI Entry Point for Production Deployment
=========================================
This file provides the WSGI interface for production deployment with Gunicorn.
"""

import os
import sys

# Add the project directory to the Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

from . import app

# This is what Gunicorn will look for
application = app

if __name__ == "__main__":
    # For direct execution (development)
    app.run(host='0.0.0.0', port=8000, debug=False)