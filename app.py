"""WSGI entry point for the ACEest Fitness & Gym application."""

import os

from aceest import APP_NAME, APP_VERSION, create_app

__all__ = ["APP_NAME", "APP_VERSION", "app", "create_app"]

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
