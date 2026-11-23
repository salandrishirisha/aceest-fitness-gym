"""
Comprehensive Pytest Test Suite for ACEest Fitness & Gym Management System.
Validates authentication, client management, program generation, workout logs,
exercises, progress tracking, metrics, and health quality gates.
"""

import pytest
from app import APP_VERSION, create_app


@pytest.fixture
def app(tmp_path):
    """Create and configure a test Flask application with an isolated temporary SQLite DB."""
    test_db = str(tmp_path / "test_aceest.db")
    app = create_app({
        "TESTING": True,
        "DATABASE": test_db
    })
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


class TestSystemEndpoints:
    """Test landing page and health endpoints (Quality Gate for CI/CD & Jenkins)."""

    def test_api_index(self, client):
        response = client.get("/api")
        assert response.status_code == 200
        data = response.get_json()
        assert data["service"] == "ACEest Fitness & Gym Web Application"
        assert data["status"] == "operational"
        assert "/health" in data["endpoints"]

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "UP"
        assert "timestamp" in data


class TestDashboard:
    """Test the server-rendered dashboard UI introduced in v2.0.0."""

    def test_dashboard_renders_empty_stats(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"Dashboard" in response.data
        assert b"Total Members" in response.data
        assert f"Version {APP_VERSION}".encode() in response.data

    def test_dashboard_counts_records(self, client):
        client.post("/api/clients", json={"name": "A", "membership_status": "Active"})
        client.post("/api/clients", json={"name": "B", "membership_status": "Active"})
        client.post("/api/clients", json={"name": "C", "membership_status": "Inactive"})
        workout_id = client.post("/api/workouts", json={"client_name": "A"}).get_json()["id"]
        client.post("/api/workouts", json={"client_name": "B"})
        client.post("/api/exercises", json={"workout_id": workout_id, "name": "Squat"})

        response = client.get("/")
        assert response.status_code == 200
        for count in (b">3</h2>", b">2</h2>", b">1</h2>"):
            assert count in response.data


class TestAuthEndpoints:
    """Test authentication logic."""

    def test_login_success_admin(self, client):
        payload = {"username": "admin", "password": "admin"}
        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert data["username"] == "admin"
        assert data["role"] == "Admin"

    def test_login_invalid_credentials(self, client):
        payload = {"username": "admin", "password": "wrongpassword"}
        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 401
        data = response.get_json()
        assert data["status"] == "error"

    @pytest.mark.parametrize("bad_payload", [
        {},
        {"username": "admin"},
        {"password": "admin"},
        {"username": "", "password": "admin"},
        {"username": "admin", "password": ""}
    ])
    def test_login_missing_fields(self, client, bad_payload):
        response = client.post("/api/auth/login", json=bad_payload)
        assert response.status_code == 400
        assert "Username and password required" in response.get_json()["error"]


class TestClientEndpoints:
    """Test client creation, querying, AI program generation, and membership."""

    def test_get_clients_empty(self, client):
        response = client.get("/api/clients")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_add_client_success(self, client):
        payload = {
            "name": "Bruce Wayne",
            "age": 32,
            "height": 188.0,
            "weight": 95.0,
            "program": "Muscle Gain",
            "calories": 3000,
            "target_weight": 92.0,
            "target_adherence": 90,
            "membership_status": "Active",
            "membership_end": "2026-12-31"
        }
        response = client.post("/api/clients", json=payload)
        assert response.status_code == 201
        data = response.get_json()
        assert "saved successfully" in data["message"]
        assert "id" in data

    def test_add_client_missing_name(self, client):
        response = client.post("/api/clients", json={"age": 25})
        assert response.status_code == 400
        assert "Client name is required" in response.get_json()["error"]

    def test_add_client_duplicate_name(self, client):
        payload = {"name": "Clark Kent", "age": 30}
        client.post("/api/clients", json=payload)

        # Duplicate attempt
        dup_resp = client.post("/api/clients", json=payload)
        assert dup_resp.status_code == 409
        assert "already exists" in dup_resp.get_json()["error"]

    def test_get_client_by_name(self, client):
        client.post("/api/clients", json={"name": "Diana Prince", "age": 28})

        # Existing client
        response = client.get("/api/clients/Diana Prince")
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Diana Prince"
        assert data["age"] == 28

        # Non-existing client
        not_found = client.get("/api/clients/Unknown User")
        assert not_found.status_code == 404

    def test_generate_program_for_client(self, client):
        client.post("/api/clients", json={"name": "Barry Allen"})

        response = client.post("/api/clients/Barry Allen/generate-program")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert data["client"] == "Barry Allen"
        assert "category" in data
        assert "program" in data

    def test_generate_program_client_not_found(self, client):
        response = client.post("/api/clients/NonExistent/generate-program")
        assert response.status_code == 404

    def test_check_client_membership(self, client):
        client.post("/api/clients", json={
            "name": "Arthur Curry",
            "membership_status": "Active",
            "membership_end": "2026-11-01"
        })

        response = client.get("/api/clients/Arthur Curry/membership")
        assert response.status_code == 200
        data = response.get_json()
        assert data["membership_status"] == "Active"
        assert data["membership_end"] == "2026-11-01"

    def test_check_membership_not_found(self, client):
        response = client.get("/api/clients/Nobody/membership")
        assert response.status_code == 404


class TestWorkoutAndExerciseEndpoints:
    """Test workouts and linked exercises."""

    def test_add_and_get_workout(self, client):
        payload = {
            "client_name": "Bruce Wayne",
            "date": "2026-10-12",
            "workout_type": "Chest & Triceps",
            "duration_min": 75,
            "notes": "Felt strong on bench press"
        }
        res_post = client.post("/api/workouts", json=payload)
        assert res_post.status_code == 201
        workout_id = res_post.get_json()["id"]

        # Fetch all
        res_all = client.get("/api/workouts")
        assert res_all.status_code == 200
        assert len(res_all.get_json()) == 1

        # Fetch filtered by client_name
        res_filtered = client.get("/api/workouts?client_name=Bruce Wayne")
        assert res_filtered.status_code == 200
        assert res_filtered.get_json()[0]["id"] == workout_id

    def test_add_workout_missing_client(self, client):
        response = client.post("/api/workouts", json={"workout_type": "Cardio"})
        assert response.status_code == 400
        assert "client_name is required" in response.get_json()["error"]

    def test_add_and_get_exercises(self, client):
        w_resp = client.post("/api/workouts", json={"client_name": "Bruce Wayne"})
        workout_id = w_resp.get_json()["id"]

        ex_payload = {
            "workout_id": workout_id,
            "name": "Barbell Incline Press",
            "sets": 4,
            "reps": 8,
            "weight": 100.0
        }
        res_ex = client.post("/api/exercises", json=ex_payload)
        assert res_ex.status_code == 201

        # Filter by workout_id
        res_get = client.get(f"/api/exercises?workout_id={workout_id}")
        assert res_get.status_code == 200
        assert len(res_get.get_json()) == 1
        assert res_get.get_json()[0]["name"] == "Barbell Incline Press"

    def test_add_exercise_missing_fields(self, client):
        response = client.post("/api/exercises", json={"name": "Squat"})
        assert response.status_code == 400


class TestProgressAndMetricsEndpoints:
    """Test tracking progress and body metrics."""

    def test_add_and_get_progress(self, client):
        prog_payload = {
            "client_name": "Bruce Wayne",
            "week": "Week 1",
            "adherence": 95
        }
        res_post = client.post("/api/progress", json=prog_payload)
        assert res_post.status_code == 201

        res_get = client.get("/api/progress?client_name=Bruce Wayne")
        assert res_get.status_code == 200
        assert len(res_get.get_json()) == 1
        assert res_get.get_json()[0]["adherence"] == 95

    def test_add_progress_missing_fields(self, client):
        res = client.post("/api/progress", json={"client_name": "Bruce Wayne"})
        assert res.status_code == 400

    def test_add_and_get_metrics(self, client):
        metric_payload = {
            "client_name": "Bruce Wayne",
            "date": "2026-10-12",
            "weight": 94.5,
            "waist": 82.0,
            "bodyfat": 12.5
        }
        res_post = client.post("/api/metrics", json=metric_payload)
        assert res_post.status_code == 201

        res_get = client.get("/api/metrics?client_name=Bruce Wayne")
        assert res_get.status_code == 200
        assert len(res_get.get_json()) == 1
        assert res_get.get_json()[0]["bodyfat"] == 12.5

    def test_add_metrics_missing_client(self, client):
        res = client.post("/api/metrics", json={"weight": 80.0})
        assert res.status_code == 400


class TestVersionAndValidation:
    """Test version metadata and payload validation."""

    def test_version_endpoint(self, client):
        response = client.get("/version")
        assert response.status_code == 200
        data = response.get_json()
        assert data["version"] == APP_VERSION
        assert data["track"] == "stable"

    def test_version_track_from_environment(self, client, monkeypatch):
        monkeypatch.setenv("DEPLOYMENT_TRACK", "canary")
        assert client.get("/version").get_json()["track"] == "canary"

    def test_health_reports_version(self, client):
        assert client.get("/health").get_json()["version"] == APP_VERSION

    @pytest.mark.parametrize("payload", [
        {"name": "Tony", "age": "abc"},
        {"name": "Tony", "weight": -5},
        {"name": "Tony", "age": True},
        {"name": 123},
    ])
    def test_add_client_rejects_invalid_values(self, client, payload):
        response = client.post("/api/clients", json=payload)
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_add_progress_rejects_adherence_over_100(self, client):
        payload = {"client_name": "Bruce Wayne", "week": "Week 2", "adherence": 150}
        response = client.post("/api/progress", json=payload)
        assert response.status_code == 400

    def test_add_exercise_rejects_non_numeric_sets(self, client):
        payload = {"workout_id": 1, "name": "Squat", "sets": "many"}
        response = client.post("/api/exercises", json=payload)
        assert response.status_code == 400

    def test_unknown_route_returns_json_404(self, client):
        response = client.get("/does-not-exist")
        assert response.status_code == 404
        assert response.get_json()["error"] == "Resource not found"

    def test_wrong_method_returns_json_405(self, client):
        response = client.delete("/api/clients")
        assert response.status_code == 405


class TestManagementPages:
    """Test the members, workouts and progress pages introduced in v3.0.0."""

    @pytest.mark.parametrize("path, heading, empty_text", [
        ("/members", b"Members", b"No members yet"),
        ("/workouts", b"Workouts", b"No workouts logged yet"),
        ("/progress", b"Progress", b"No progress records yet"),
    ])
    def test_pages_render_empty_state(self, client, path, heading, empty_text):
        response = client.get(path)
        assert response.status_code == 200
        assert heading in response.data
        assert empty_text in response.data

    def test_pages_list_records(self, client):
        client.post("/api/clients", json={"name": "Peter Parker", "membership_status": "Active"})
        client.post("/api/workouts", json={"client_name": "Peter Parker",
                                           "workout_type": "Agility"})
        client.post("/api/progress", json={"client_name": "Peter Parker", "week": "Week 1",
                                           "adherence": 88})
        client.post("/api/metrics", json={"client_name": "Peter Parker", "weight": 70.5})

        assert b"Peter Parker" in client.get("/members").data
        assert b"Agility" in client.get("/workouts").data
        progress_page = client.get("/progress").data
        assert b"88%" in progress_page
        assert b"70.5" in progress_page


class TestClientSummary:
    """Test the aggregated client summary endpoint."""

    def test_summary_aggregates_activity(self, client):
        client.post("/api/clients", json={
            "name": "Steve Rogers", "height": 188, "weight": 100,
            "target_adherence": 80, "membership_status": "Active"
        })
        client.post("/api/workouts", json={"client_name": "Steve Rogers", "duration_min": 45})
        client.post("/api/workouts", json={"client_name": "Steve Rogers", "duration_min": 30})
        client.post("/api/progress", json={"client_name": "Steve Rogers", "week": "W1",
                                           "adherence": 90})
        client.post("/api/progress", json={"client_name": "Steve Rogers", "week": "W2",
                                           "adherence": 80})
        client.post("/api/metrics", json={"client_name": "Steve Rogers", "date": "2026-10-01",
                                          "weight": 95})

        response = client.get("/api/clients/Steve Rogers/summary")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total_workouts"] == 2
        assert data["total_minutes"] == 75
        assert data["average_adherence"] == 85.0
        assert data["on_track"] is True
        assert data["bmi"] == 26.9
        assert data["bmi_category"] == "Overweight"
        assert data["latest_metrics"]["weight"] == 95

    def test_summary_without_activity(self, client):
        client.post("/api/clients", json={"name": "Wanda"})
        data = client.get("/api/clients/Wanda/summary").get_json()
        assert data["total_workouts"] == 0
        assert data["average_adherence"] is None
        assert data["on_track"] is False
        assert data["bmi_category"] == "Unknown"
        assert data["latest_metrics"] is None

    def test_summary_client_not_found(self, client):
        assert client.get("/api/clients/Nobody/summary").status_code == 404


class TestReleaseHeaders:
    """Test release headers used to verify blue-green, canary, A/B and shadow routing."""

    def test_release_headers_on_api_and_pages(self, client):
        for path in ("/health", "/", "/api/clients"):
            response = client.get(path)
            assert response.headers["X-App-Version"] == APP_VERSION
            assert response.headers["X-Deployment-Track"] == "stable"

    def test_track_header_follows_environment(self, client, monkeypatch):
        monkeypatch.setenv("DEPLOYMENT_TRACK", "green")
        response = client.get("/health")
        assert response.headers["X-Deployment-Track"] == "green"
        assert b"green track" in client.get("/").data
