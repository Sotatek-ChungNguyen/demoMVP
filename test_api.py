"""
HandGuard AI - API End-to-End Test Suite
Tests luong upload video thuc te qua POST /api/analyze
"""
import io
import time
import numpy as np
from fastapi.testclient import TestClient
import app
import api_service

client = TestClient(app.app)


def create_minimal_mp4_bytes() -> bytes:
    """
    Tao 1 file MP4 hop le toi thieu bang OpenCV VideoWriter.
    """
    try:
        import cv2
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, 10.0, (64, 48))
        for _ in range(15):
            frame = np.zeros((48, 64, 3), dtype=np.uint8)
            writer.write(frame)
        writer.release()
        with open(path, "rb") as f:
            data = f.read()
        os.remove(path)
        return data
    except Exception as e:
        raise RuntimeError(f"Khong the tao MP4 test: {e}")


def test_api_endpoints():
    print("\n=== HandGuard AI - API End-to-End Tests ===\n")

    print("1. Testing GET /api/health ...")
    r = client.get("/api/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    print("   -> OK:", r.json())

    print("2. Testing GET / (Single Page App) ...")
    r = client.get("/")
    assert r.status_code == 200, f"Index failed: {r.text}"
    assert "HandGuard" in r.text
    print("   -> OK: Index HTML served properly")

    print("3. Testing GET /static/style.css ...")
    r = client.get("/static/style.css")
    assert r.status_code == 200, f"CSS failed: {r.text}"
    print("   -> OK: CSS static file served properly")

    print("4. Testing POST /api/analyze with real video upload ...")
    video_bytes = create_minimal_mp4_bytes()
    files = {"file": ("test_video.mp4", io.BytesIO(video_bytes), "video/mp4")}
    data = {
        "threshold": "90.0",
        "strict_left_right": "false",
        "stride": "1",
        "render_debug": "false",
    }
    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 200, f"Analyze failed: {r.text}"
    resp = r.json()
    task_id = resp["task_id"]
    assert task_id
    print(f"   -> OK: Task created with ID {task_id}")

    print("5. Testing GET /api/tasks/{task_id} (initial status) ...")
    r = client.get(f"/api/tasks/{task_id}")
    assert r.status_code == 200
    assert r.json()["task_id"] == task_id
    print("   -> OK:", r.json()["status"])

    print("6. Waiting for task completion (polling) ...")
    status = None
    task_info = None
    for _ in range(60):
        time.sleep(1)
        res = client.get(f"/api/tasks/{task_id}")
        assert res.status_code == 200
        task_info = res.json()
        status = task_info["status"]
        pct = task_info["progress"]["percent"]
        print(f"   [Task {task_id}] Status: {status} | Progress: {pct}%")
        if status in ["COMPLETED", "FAILED"]:
            break

    assert status == "COMPLETED", f"Task did not complete: {task_info.get('error')}"
    result = task_info["result"]
    assert "summary" in result
    print("   -> OK: Result received:", result["summary"])

    print("7. Testing GET /api/history ...")
    r = client.get("/api/history")
    assert r.status_code == 200
    assert len(r.json()) > 0
    print(f"   -> OK: History contains {len(r.json())} item(s)")

    print("\n=== ALL API END-TO-END TESTS PASSED SUCCESSFULLY! ===\n")


if __name__ == "__main__":
    test_api_endpoints()
