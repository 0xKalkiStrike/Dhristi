"""API endpoint & integration tests (TestClient)."""
import uuid




def test_health(client):
    r = client.get("/api/system/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["ai_runtime"] in ("CPU", "GPU")
    assert "database" in body


def test_root_info(client):
    # "/" serves the built SPA when present; API info lives at /api.
    r = client.get("/api")
    assert r.status_code == 200
    assert r.json()["name"] == "DRISHTI-V"


def test_camera_crud(client):
    # create
    r = client.post("/api/cameras", json={"name": "Test Cam", "zone": "Zone A", "source_type": "file"})
    assert r.status_code == 201
    cam = r.json()
    cid = cam["camera_id"]
    assert cid.startswith("CAM-")

    # list
    r = client.get("/api/cameras")
    assert any(c["camera_id"] == cid for c in r.json())

    # get
    r = client.get(f"/api/cameras/{cid}")
    assert r.status_code == 200

    # update
    r = client.patch(f"/api/cameras/{cid}", json={"location": "Main Road"})
    assert r.json()["location"] == "Main Road"

    # delete
    r = client.delete(f"/api/cameras/{cid}")
    assert r.status_code == 200


def test_camera_not_found(client):
    r = client.get("/api/cameras/CAM-999")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


def test_calibration_validation(client):
    cid = f"CAM-CAL-{uuid.uuid4().hex[:6]}"
    client.post("/api/cameras", json={"camera_id": cid, "name": "Cal Cam", "source_type": "file"})
    # invalid dual-line -> 422
    r = client.post(f"/api/calibration/{cid}", json={"method": "dual_line", "real_distance_m": 0})
    assert r.status_code == 422

    # valid dual-line
    r = client.post(f"/api/calibration/{cid}", json={
        "method": "dual_line", "line_a": [[400, 0], [400, 720]], "line_b": [[880, 0], [880, 720]],
        "real_distance_m": 24.0, "speed_limit_kmh": 60})
    assert r.status_code == 200

    # test calibration with synthetic track
    r = client.post(f"/api/calibration/{cid}/test", json=None)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["measurement"]["speed_kmh"] > 0


def test_search_empty(client):
    r = client.get("/api/vehicles/search", params={"plate": "ZZZZ"})
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_analytics_summary(client):
    r = client.get("/api/analytics/summary")
    assert r.status_code == 200
    body = r.json()
    assert "average_speed_kmh" in body
    assert "speed_distribution" in body


def test_demo_setup(client):
    r = client.post("/api/demo/setup")
    assert r.status_code == 200
    assert len(r.json()["cameras"]) >= 4


def test_camera_frame_and_stream(client):
    cid = f"CAM-STRM-{uuid.uuid4().hex[:6]}"
    r = client.post("/api/cameras", json={"camera_id": cid, "name": "Stream Cam", "source_type": "file"})
    assert r.status_code == 201

    r_frame = client.get(f"/api/cameras/{cid}/frame.jpg")
    assert r_frame.status_code == 200

    r_stream = client.get(f"/api/cameras/{cid}/stream")
    assert r_stream.status_code == 200
    assert "multipart/x-mixed-replace" in r_stream.headers.get("content-type", "")


