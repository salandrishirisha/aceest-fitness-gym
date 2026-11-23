"""Server-rendered dashboard and management pages."""

import sqlite3

from flask import Blueprint, current_app, render_template

from .db import db

bp = Blueprint("web", __name__)

STAT_QUERIES = {
    "total_clients": "SELECT COUNT(*) FROM clients",
    "active_members": "SELECT COUNT(*) FROM clients WHERE membership_status = 'Active'",
    "total_workouts": "SELECT COUNT(*) FROM workouts",
    "total_exercises": "SELECT COUNT(*) FROM exercises",
}


def get_dashboard_stats():
    """Summarise members, memberships, workouts and exercises for the dashboard."""
    stats = dict.fromkeys(STAT_QUERIES, 0)
    conn = db()
    try:
        for key, sql in STAT_QUERIES.items():
            stats[key] = conn.execute(sql).fetchone()[0]
    except sqlite3.Error:
        current_app.logger.exception("Could not read dashboard statistics")
    finally:
        conn.close()
    return stats


def fetch_rows(sql):
    conn = db()
    try:
        return [dict(row) for row in conn.execute(sql).fetchall()]
    finally:
        conn.close()


@bp.route("/")
def dashboard():
    return render_template("index.html", active="dashboard", stats=get_dashboard_stats())


@bp.route("/members")
def members():
    rows = fetch_rows("SELECT * FROM clients ORDER BY name")
    return render_template("members.html", active="members", clients=rows)


@bp.route("/workouts")
def workouts():
    rows = fetch_rows("SELECT * FROM workouts ORDER BY date DESC, id DESC")
    return render_template("workouts.html", active="workouts", workouts=rows)


@bp.route("/progress")
def progress():
    progress_rows = fetch_rows("SELECT * FROM progress ORDER BY client_name, id")
    metric_rows = fetch_rows("SELECT * FROM metrics ORDER BY date DESC, id DESC")
    return render_template("progress.html", active="progress",
                           progress=progress_rows, metrics=metric_rows)
