"""Domain logic for programs, BMI and client summaries."""

PROGRAM_TEMPLATES = {
    "Fat Loss": ["Full Body HIIT", "Circuit Training", "Cardio + Weights"],
    "Muscle Gain": ["Push/Pull/Legs", "Upper/Lower Split", "Full Body Strength"],
    "Beginner": ["Full Body 3x/week", "Light Strength + Mobility"]
}


def calculate_bmi(weight_kg, height_cm):
    """Return BMI rounded to one decimal, or None when inputs are missing."""
    if not weight_kg or not height_cm:
        return None
    height_m = height_cm / 100
    return round(weight_kg / (height_m * height_m), 1)


def bmi_category(bmi):
    """Map a BMI value to its WHO category."""
    if bmi is None:
        return "Unknown"
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal"
    if bmi < 30:
        return "Overweight"
    return "Obese"


def client_summary(conn, client):
    """Aggregate a client's profile, workouts, adherence and latest metrics."""
    name = client["name"]
    workouts = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(duration_min), 0) AS minutes "
        "FROM workouts WHERE client_name=?", (name,)
    ).fetchone()
    adherence = conn.execute(
        "SELECT AVG(adherence) AS avg_adherence FROM progress WHERE client_name=?", (name,)
    ).fetchone()
    latest_metric = conn.execute(
        "SELECT date, weight, waist, bodyfat FROM metrics WHERE client_name=? "
        "ORDER BY date DESC, id DESC LIMIT 1", (name,)
    ).fetchone()

    weight = latest_metric["weight"] if latest_metric else client["weight"]
    bmi = calculate_bmi(weight, client["height"])
    avg_adherence = adherence["avg_adherence"]
    target = client["target_adherence"]
    return {
        "client": name,
        "program": client["program"],
        "membership_status": client["membership_status"],
        "bmi": bmi,
        "bmi_category": bmi_category(bmi),
        "total_workouts": workouts["total"],
        "total_minutes": workouts["minutes"],
        "average_adherence": round(avg_adherence, 1) if avg_adherence is not None else None,
        "on_track": (avg_adherence is not None and target is not None
                     and avg_adherence >= target),
        "latest_metrics": dict(latest_metric) if latest_metric else None,
    }
