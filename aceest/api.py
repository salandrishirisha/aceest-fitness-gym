"""REST API blueprint: auth, clients, workouts, exercises, progress and metrics."""

import os
import secrets
import sqlite3
from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request

from . import APP_NAME, APP_VERSION
from .db import db
from .services import PROGRAM_TEMPLATES, client_summary
from .validation import ValidationError, to_number, to_text

bp = Blueprint("api", __name__)

CLIENT_BY_NAME_SQL = "SELECT * FROM clients WHERE name=?"


# ------------------ System Endpoints ------------------


@bp.route("/api")
def index():
    return jsonify({
        "service": "ACEest Fitness & Gym Web Application",
        "version": APP_VERSION,
        "status": "operational",
        "endpoints": [
            "/",
            "/api",
            "/members",
            "/workouts",
            "/progress",
            "/health",
            "/version",
            "/api/auth/login",
            "/api/clients",
            "/api/clients/<name>",
            "/api/clients/<name>/generate-program",
            "/api/clients/<name>/membership",
            "/api/clients/<name>/summary",
            "/api/workouts",
            "/api/exercises",
            "/api/metrics",
            "/api/progress"
        ]
    }), 200


@bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "UP",
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


@bp.route("/version", methods=["GET"])
def version():
    return jsonify({
        "service": APP_NAME,
        "version": APP_VERSION,
        "track": os.environ.get("DEPLOYMENT_TRACK", "stable")
    }), 200


# ------------------ Auth Endpoints ------------------


@bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = to_text(data, "username")
    password = to_text(data, "password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT username, role FROM users WHERE username=? AND password=?",
        (username, password)
    )
    user = cur.fetchone()
    conn.close()

    if user:
        return jsonify({
            "status": "success",
            "username": user["username"],
            "role": user["role"]
        }), 200
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

# ------------------ Client Endpoints ------------------


@bp.route("/api/clients", methods=["GET"])
def get_clients():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients ORDER BY name")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows), 200


@bp.route("/api/clients", methods=["POST"])
def add_client():
    data = request.get_json(silent=True) or {}
    name = to_text(data, "name")
    if not name:
        return jsonify({"error": "Client name is required"}), 400

    age = to_number(data, "age", int)
    height = to_number(data, "height")
    weight = to_number(data, "weight")
    program = data.get("program")
    calories = to_number(data, "calories", int)
    target_weight = to_number(data, "target_weight")
    target_adherence = to_number(data, "target_adherence", int)
    membership_status = data.get("membership_status", "Active")
    membership_end = data.get("membership_end")

    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO clients (
            name, age, height, weight, program, calories,
            target_weight, target_adherence, membership_status, membership_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, age, height, weight, program, calories,
              target_weight, target_adherence, membership_status, membership_end))
        conn.commit()
        new_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": f"Client '{name}' already exists"}), 409

    conn.close()
    return jsonify({
        "message": f"Client {name} saved successfully",
        "id": new_id
    }), 201


@bp.route("/api/clients/<string:name>", methods=["GET"])
def get_client_by_name(name):
    conn = db()
    cur = conn.cursor()
    cur.execute(CLIENT_BY_NAME_SQL, (name,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": f"Client '{name}' not found"}), 404
    return jsonify(dict(row)), 200


@bp.route("/api/clients/<string:name>/generate-program", methods=["POST"])
def generate_program_for_client(name):
    conn = db()
    cur = conn.cursor()
    cur.execute(CLIENT_BY_NAME_SQL, (name,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": f"Client '{name}' not found"}), 404

    category = secrets.choice(list(PROGRAM_TEMPLATES.keys()))
    program_detail = secrets.choice(PROGRAM_TEMPLATES[category])
    cur.execute("UPDATE clients SET program=? WHERE name=?", (program_detail, name))
    conn.commit()
    conn.close()
    return jsonify({
        "status": "success",
        "client": name,
        "category": category,
        "program": program_detail
    }), 200


@bp.route("/api/clients/<string:name>/membership", methods=["GET"])
def check_client_membership(name):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT membership_status, membership_end FROM clients WHERE name=?", (name,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": f"Client '{name}' not found"}), 404
    return jsonify({
        "client": name,
        "membership_status": row["membership_status"],
        "membership_end": row["membership_end"]
    }), 200


@bp.route("/api/clients/<string:name>/summary", methods=["GET"])
def get_client_summary(name):
    conn = db()
    try:
        client = conn.execute(CLIENT_BY_NAME_SQL, (name,)).fetchone()
        if not client:
            return jsonify({"error": f"Client '{name}' not found"}), 404
        return jsonify(client_summary(conn, client)), 200
    finally:
        conn.close()


# ------------------ Workout Endpoints ------------------


@bp.route("/api/workouts", methods=["GET"])
def get_workouts():
    client_name = request.args.get("client_name")
    conn = db()
    cur = conn.cursor()
    if client_name:
        cur.execute(
            "SELECT * FROM workouts WHERE client_name=? ORDER BY date DESC",
            (client_name,)
        )
    else:
        cur.execute("SELECT * FROM workouts ORDER BY date DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows), 200


@bp.route("/api/workouts", methods=["POST"])
def add_workout():
    data = request.get_json(silent=True) or {}
    client_name = to_text(data, "client_name")
    if not client_name:
        return jsonify({"error": "client_name is required"}), 400

    workout_date = data.get("date", date.today().isoformat())
    workout_type = data.get("workout_type", "Strength")
    duration_min = to_number(data, "duration_min", int, default=60)
    notes = data.get("notes", "")

    conn = db()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO workouts (client_name, date, workout_type, duration_min, notes)
    VALUES (?, ?, ?, ?, ?)
    """, (client_name, workout_date, workout_type, duration_min, notes))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({
        "message": "Workout recorded",
        "id": new_id
    }), 201

# ------------------ Exercise Endpoints ------------------


@bp.route("/api/exercises", methods=["GET"])
def get_exercises():
    workout_id = request.args.get("workout_id")
    conn = db()
    cur = conn.cursor()
    if workout_id:
        cur.execute("SELECT * FROM exercises WHERE workout_id=?", (workout_id,))
    else:
        cur.execute("SELECT * FROM exercises")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows), 200


@bp.route("/api/exercises", methods=["POST"])
def add_exercise():
    data = request.get_json(silent=True) or {}
    workout_id = data.get("workout_id")
    name = to_text(data, "name")
    sets = to_number(data, "sets", int, default=3)
    reps = to_number(data, "reps", int, default=10)
    weight = to_number(data, "weight", default=0.0)

    if not workout_id or not name:
        return jsonify({"error": "workout_id and exercise name are required"}), 400

    conn = db()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO exercises (workout_id, name, sets, reps, weight)
    VALUES (?, ?, ?, ?, ?)
    """, (workout_id, name, sets, reps, weight))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({
        "message": "Exercise recorded",
        "id": new_id
    }), 201

# ------------------ Progress Endpoints ------------------


@bp.route("/api/progress", methods=["GET"])
def get_progress():
    client_name = request.args.get("client_name")
    conn = db()
    cur = conn.cursor()
    if client_name:
        cur.execute("SELECT * FROM progress WHERE client_name=? ORDER BY id", (client_name,))
    else:
        cur.execute("SELECT * FROM progress ORDER BY id")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows), 200


@bp.route("/api/progress", methods=["POST"])
def add_progress():
    data = request.get_json(silent=True) or {}
    client_name = to_text(data, "client_name")
    week = to_text(data, "week")
    adherence = to_number(data, "adherence", int, default=0)
    if adherence > 100:
        raise ValidationError("adherence must be <= 100")

    if not client_name or not week:
        return jsonify({"error": "client_name and week are required"}), 400

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO progress (client_name, week, adherence) VALUES (?, ?, ?)",
        (client_name, week, adherence)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({
        "message": "Progress recorded",
        "id": new_id
    }), 201

# ------------------ Metrics Endpoints ------------------


@bp.route("/api/metrics", methods=["GET"])
def get_metrics():
    client_name = request.args.get("client_name")
    conn = db()
    cur = conn.cursor()
    if client_name:
        cur.execute(
            "SELECT * FROM metrics WHERE client_name=? ORDER BY date DESC",
            (client_name,)
        )
    else:
        cur.execute("SELECT * FROM metrics ORDER BY date DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(rows), 200


@bp.route("/api/metrics", methods=["POST"])
def add_metrics():
    data = request.get_json(silent=True) or {}
    client_name = to_text(data, "client_name")
    if not client_name:
        return jsonify({"error": "client_name is required"}), 400

    metric_date = data.get("date", date.today().isoformat())
    weight = to_number(data, "weight", default=0.0)
    waist = to_number(data, "waist", default=0.0)
    bodyfat = to_number(data, "bodyfat", default=0.0)

    conn = db()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO metrics (client_name, date, weight, waist, bodyfat)
    VALUES (?, ?, ?, ?, ?)
    """, (client_name, metric_date, weight, waist, bodyfat))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({
        "message": "Metrics recorded",
        "id": new_id
    }), 201
