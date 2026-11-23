"""ACEest Fitness & Gym Management System - Flask application factory."""

import os

from flask import Flask, jsonify

from .db import DB_NAME, init_db
from .validation import ValidationError

APP_NAME = "ACEest Fitness & Gym"
APP_VERSION = "3.0.0"


def create_app(test_config=None):
    """Create and configure the ACEest Flask application."""
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "aceest-secret-key-2026"),
        DATABASE=os.environ.get("ACEEST_DB", DB_NAME)
    )
    if test_config:
        app.config.update(test_config)

    init_db(app.config["DATABASE"])

    from . import api, web
    app.register_blueprint(api.bp)
    app.register_blueprint(web.bp)

    @app.context_processor
    def inject_release_info():
        return {"version": APP_VERSION, "track": os.environ.get("DEPLOYMENT_TRACK", "stable")}

    @app.errorhandler(ValidationError)
    def handle_validation_error(err):
        return jsonify({"error": str(err)}), 400

    @app.errorhandler(404)
    def handle_not_found(_err):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(_err):
        return jsonify({"error": "Method not allowed"}), 405

    return app
