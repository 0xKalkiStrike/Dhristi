"""Live-camera device discovery, connect validation, and network info tests."""
from app.video import devices as devsvc


def test_list_video_devices_structure():
    out = devsvc.list_video_devices()
    assert "count" in out and "devices" in out
    assert isinstance(out["devices"], list)


def test_list_bluetooth_devices_has_note():
    out = devsvc.list_bluetooth_devices()
    assert "devices" in out and "note" in out
    assert "video" in out["note"].lower()


def test_probe_invalid_index_is_safe():
    # A very high index should not open; must return ok=False without raising.
    r = devsvc.probe_video_index(99, timeout=6)
    assert r["ok"] is False
    assert r["index"] == 99


def test_network_endpoint(client):
    r = client.get("/api/system/network")
    assert r.status_code == 200
    body = r.json()
    assert "urls" in body and body["urls"]["app"].startswith("http")
    assert "lan_ips" in body


def test_connect_requires_index_for_webcam(client):
    r = client.post("/api/devices/connect", json={"name": "X", "source_type": "webcam", "start": False})
    assert r.status_code == 422


def test_connect_requires_url_for_rtsp(client):
    r = client.post("/api/devices/connect", json={"name": "X", "source_type": "rtsp", "start": False})
    assert r.status_code == 422


def test_connect_rejects_unknown_source(client):
    r = client.post("/api/devices/connect", json={"name": "X", "source_type": "carrier-pigeon", "start": False})
    assert r.status_code == 422
