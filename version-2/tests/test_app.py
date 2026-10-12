
import sqlite3

import app as app_module


def test_health_endpoint():
    client = app_module.app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "UP",
        "version": "2.0.0",
    }


def test_dashboard_loads_without_database(monkeypatch, tmp_path):
    database = tmp_path / "missing.db"
    monkeypatch.setattr(app_module, "DATABASE", database)

    client = app_module.app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert b"Dashboard" in response.data
    assert b"Total Members" in response.data


def test_dashboard_shows_database_statistics(monkeypatch, tmp_path):
    database = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DATABASE", database)

    conn = sqlite3.connect(str(database))

    conn.execute(
        "CREATE TABLE clients "
        "(id INTEGER PRIMARY KEY, membership_status TEXT)"
    )
    conn.execute(
        "CREATE TABLE workouts (id INTEGER PRIMARY KEY)"
    )
    conn.execute(
        "CREATE TABLE exercises (id INTEGER PRIMARY KEY)"
    )

    conn.executemany(
        "INSERT INTO clients (membership_status) VALUES (?)",
        [("Active",), ("Active",), ("Inactive",)],
    )

    conn.execute("INSERT INTO workouts DEFAULT VALUES")
    conn.execute("INSERT INTO workouts DEFAULT VALUES")
    conn.execute("INSERT INTO exercises DEFAULT VALUES")

    conn.commit()
    conn.close()

    client = app_module.app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert b"Total Members" in response.data
    assert b"Active Memberships" in response.data

    # 3 members, 2 active memberships,
    # 2 workouts, and 1 exercise.
    assert b">3</h2>" in response.data
    assert b">2</h2>" in response.data
    assert b">1</h2>" in response.data