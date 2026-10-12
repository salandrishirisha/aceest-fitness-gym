
import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(
    os.environ.get(
        "ACEEST_DB",
        str(BASE_DIR.parent / "aceest_fitness.db"),
    )
)

app = Flask(__name__)


def get_dashboard_stats():
    """Read summary statistics from the existing Version 1 database."""
    stats = {
        "total_clients": 0,
        "active_members": 0,
        "total_workouts": 0,
        "total_exercises": 0,
    }

    if not DATABASE.exists():
        return stats

    conn = sqlite3.connect(str(DATABASE))
    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM clients")
        stats["total_clients"] = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM clients "
            "WHERE membership_status = 'Active'"
        )
        stats["active_members"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM workouts")
        stats["total_workouts"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM exercises")
        stats["total_exercises"] = cur.fetchone()[0]

    except sqlite3.Error:
        app.logger.exception("Could not read dashboard statistics")
    finally:
        conn.close()

    return stats


@app.route("/")
def dashboard():
    return render_template("index.html", stats=get_dashboard_stats())


@app.route("/health")
def health():
    return jsonify({"status": "UP", "version": "2.0.0"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
