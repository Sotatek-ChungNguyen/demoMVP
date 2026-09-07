import os
import mimetypes
import json
import asyncio
import base64
import time
import uuid
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from visualizer import VideoVisualizer
from reporter import export_json
from hand_detector import FrameHandResult
from video_analyzer import VideoInfo, AnalysisResult, ViolationInterval

import api_service

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(
    title="HandGuard AI - Video Two-Hand Compliance API",
    description="API quét toàn bộ video nhận diện 2 bàn tay, đánh giá hợp lệ với ngưỡng >= 90%",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "HandGuard AI API"}


@app.post("/api/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    threshold: float = Form(90.0),
    strict_left_right: bool = Form(False),
    stride: int = Form(1),
    render_debug: bool = Form(True),
):
    """Tiếp nhận video và bắt đầu tác vụ phân tích không đồng bộ."""
    clean_filename = os.path.basename(file.filename or "video.mp4")
    ext = os.path.splitext(clean_filename)[1].lower()
    if ext not in [".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv"]:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng video không được hỗ trợ: {ext}. Hãy tải lên file .mp4, .mov, .avi, .webm",
        )

    # Save uploaded file
    file_prefix = str(int(asyncio.get_event_loop().time() * 1000))[-6:]
    saved_filename = f"{file_prefix}_{clean_filename}"
    saved_path = os.path.join(api_service.UPLOAD_DIR, saved_filename)

    with open(saved_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            f.write(chunk)

    task_id = api_service.create_task(clean_filename, saved_path)
    api_service.start_analysis_async(
        task_id=task_id,
        video_path=saved_path,
        threshold=threshold,
        strict_left_right=strict_left_right,
        stride=stride,
        render_debug=render_debug,
    )

    return {
        "task_id": task_id,
        "filename": clean_filename,
        "status": "PENDING",
        "threshold": threshold,
        "strict_left_right": strict_left_right,
    }


@app.get("/api/tasks/{task_id}")
def get_task_status(task_id: str):
    task = api_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy task_id")
    return task


@app.get("/api/progress/{task_id}")
async def stream_progress(task_id: str):
    """Server-Sent Events (SSE) stream cập nhật tiến trình phân tích thời gian thực."""
    async def event_generator():
        while True:
            task = api_service.get_task(task_id)
            if not task:
                yield f"data: {json.dumps({'status': 'NOT_FOUND', 'message': 'Không tìm thấy tác vụ'})}\n\n"
                break

            status = task.get("status")
            progress = task.get("progress", {})
            error = task.get("error")

            payload = {
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "error": error,
            }

            if status == "COMPLETED":
                payload["result"] = task.get("result")
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                break
            elif status == "FAILED":
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                break

            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/history")
def get_history():
    return api_service.list_tasks()




@app.get("/api/media/{folder}/{filename}")
async def stream_media(folder: str, filename: str, request: Request):
    """Hỗ trợ stream video với HTTP 206 Partial Content để tua video trên HTML5 player."""
    if folder not in ["uploads", "outputs", "reports"]:
        raise HTTPException(status_code=400, detail="Thư mục không hợp lệ")

    safe_dir = getattr(api_service, f"{folder.upper()[:-1] if folder != 'uploads' else 'UPLOAD'}_DIR", None)
    if not safe_dir:
        safe_dir = os.path.join(api_service.STORAGE_DIR, folder)

    file_path = os.path.join(safe_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File không tồn tại")

    if folder == "reports":
        return FileResponse(file_path, filename=filename, media_type="application/json")

    file_size = os.path.getsize(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "video/mp4"

    range_header = request.headers.get("range")
    if range_header:
        # Example: "bytes=0-1000"
        parts = range_header.replace("bytes=", "").split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        length = end - start + 1

        def iterfile():
            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_left = length
                while bytes_left > 0:
                    read_size = min(64 * 1024, bytes_left)
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    bytes_left -= len(chunk)
                    yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": mime_type,
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)

    # Full file response
    return FileResponse(file_path, media_type=mime_type, filename=filename)


@app.websocket("/ws/live-webcam")
async def live_webcam_ws(websocket: WebSocket):
    """
    WebSocket endpoint nhận diện bàn tay trực tiếp từ webcam browser.
    
    Protocol:
    - Client gửi tin nhắn JSON đầu tiên để cấu hình:
      {"action": "start", "threshold": 90.0, "strict_left_right": false}
    - Sau đó client gửi từng frame dạng binary (JPEG bytes) liên tục.
    - Server trả về JSON với landmarks, tỷ lệ % real-time cho mỗi frame.
    - Client gửi {"action": "stop"} để kết thúc và nhận báo cáo tổng kết.
    """
    await websocket.accept()

    # --- Session state ---
    session_id = str(uuid.uuid4())[:8]
    threshold = 90.0
    strict_left_right = False
    total_frames = 0
    valid_frames = 0
    session_start = time.time()
    violations = []
    in_violation = False
    violation_start_sec = 0.0
    detector = None
    frame_timestamp_ms = 0

    # Video recording state
    debug_filename = f"debug_{session_id}.mp4"
    debug_path = os.path.join(api_service.OUTPUT_DIR, debug_filename)
    orig_filename = f"webcam_{session_id}.mp4"
    orig_path = os.path.join(api_service.UPLOAD_DIR, orig_filename)
    report_filename = f"report_{session_id}.json"
    report_path = os.path.join(api_service.REPORT_DIR, report_filename)

    debug_visualizer = None
    orig_writer = None
    fps = 25.0
    frame_width = 640
    frame_height = 480

    try:
        # 1. Receive configuration message
        config_msg = await websocket.receive_text()
        config = json.loads(config_msg)
        threshold = float(config.get("threshold", 90.0))
        strict_left_right = bool(config.get("strict_left_right", False))

        # 2. Initialize hand detector (run in threadpool to avoid blocking)
        model_path = await asyncio.get_event_loop().run_in_executor(
            None, api_service.ensure_model
        )

        from hand_detector import HandDetector as _HD
        detector = _HD(model_path, strict_left_right=strict_left_right)

        await websocket.send_text(json.dumps({
            "type": "ready",
            "message": "Mô hình đã sẵn sàng, bắt đầu gửi khung hình."
        }))

        # 3. Main receive loop
        while True:
            data = await websocket.receive()

            # --- Handle text control messages ---
            if "text" in data:
                try:
                    msg = json.loads(data["text"])
                    if msg.get("action") == "stop":
                        break
                except json.JSONDecodeError:
                    pass
                continue

            # --- Handle binary frame data ---
            frame_bytes = data.get("bytes")
            if not frame_bytes:
                continue

            # Decode JPEG → numpy array BGR
            np_arr = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                continue

            h, w = frame_bgr.shape[:2]
            frame_width, frame_height = w, h

            # Initialize video recorders on first frame
            if debug_visualizer is None:
                try:
                    debug_visualizer = VideoVisualizer(debug_path, fps, w, h)
                except Exception as e:
                    debug_visualizer = None
                try:
                    orig_writer = VideoVisualizer._create_writer(orig_path, fps, w, h)
                except Exception as e:
                    orig_writer = None

            # Process raw camera frame directly (do not flip on server; mirroring is handled cleanly on client)
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            elapsed_now = time.time() - session_start
            current_ts_ms = max(int(elapsed_now * 1000), frame_timestamp_ms + 1)
            frame_timestamp_ms = current_ts_ms

            # Run detection in threadpool (CPU-bound)
            result = await asyncio.get_event_loop().run_in_executor(
                None, detector.detect, frame_rgb, frame_timestamp_ms
            )

            total_frames += 1
            elapsed = elapsed_now

            if result.is_valid:
                valid_frames += 1
                if in_violation:
                    violations.append({
                        "start_sec": round(violation_start_sec, 2),
                        "end_sec": round(elapsed, 2),
                    })
                    in_violation = False
            else:
                if not in_violation:
                    in_violation = True
                    violation_start_sec = elapsed

            current_ratio = round((valid_frames / total_frames * 100), 2) if total_frames > 0 else 0.0

            # Record frame to original and debug videos (mirrored naturally for playback)
            frame_mirrored = cv2.flip(frame_bgr, 1)
            if orig_writer is not None:
                orig_writer.write(frame_mirrored)

            if debug_visualizer is not None:
                class _MirroredLM:
                    def __init__(self, x, y, z=0.0):
                        self.x = 1.0 - x
                        self.y = y
                        self.z = z

                mirrored_landmarks = []
                for hand_lms in result.landmarks:
                    mirrored_landmarks.append([_MirroredLM(lm.x, lm.y, getattr(lm, "z", 0.0)) for lm in hand_lms])

                mirrored_hand_result = FrameHandResult(
                    hand_count=result.hand_count,
                    handedness_labels=result.handedness_labels,
                    landmarks=mirrored_landmarks,
                    is_valid=result.is_valid,
                    detection_source=result.detection_source,
                )
                drawn_frame = debug_visualizer.draw_frame(
                    frame_mirrored, mirrored_hand_result, total_frames, total_frames, current_ratio
                )
                debug_visualizer.write_frame(drawn_frame)

            # Build landmarks payload (normalized x, y coordinates per hand)
            landmarks_payload = []
            for hand_lms in result.landmarks:
                landmarks_payload.append(
                    [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in hand_lms]
                )

            response = {
                "type": "frame",
                "has_two_hands": result.is_valid,
                "hand_count": result.hand_count,
                "handedness": result.handedness_labels,
                "landmarks": landmarks_payload,
                "total_frames": total_frames,
                "valid_frames": valid_frames,
                "current_ratio": current_ratio,
                "elapsed_sec": round(elapsed, 1),
                "is_session_valid": current_ratio >= threshold,
                "detection_source": result.detection_source,  # HAND_MODEL / POSE_CLASPED / POSE_MOTION / NONE
            }
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        if detector:
            detector.close()
        if debug_visualizer:
            debug_visualizer.close()
        if orig_writer:
            orig_writer.release()

        # Close any open violation interval
        if in_violation:
            elapsed = time.time() - session_start
            violations.append({
                "start_sec": round(violation_start_sec, 2),
                "end_sec": round(elapsed, 2),
            })

        # Calculate session statistics
        elapsed_total = round(time.time() - session_start, 1)
        final_ratio = round((valid_frames / total_frames * 100), 2) if total_frames > 0 else 0.0
        is_valid = final_ratio >= threshold

        # Check if debug video file was created and is > 0 bytes
        has_debug = os.path.exists(debug_path) and os.path.getsize(debug_path) > 0
        has_orig = os.path.exists(orig_path) and os.path.getsize(orig_path) > 0

        debug_video_url = f"/api/media/outputs/{debug_filename}" if has_debug else None
        original_video_url = f"/api/media/uploads/{orig_filename}" if has_orig else None
        report_url = f"/api/media/reports/{report_filename}"

        # Export structured JSON report
        vi_info = VideoInfo(
            path=orig_path if has_orig else "webcam_live",
            fps=fps,
            total_frames=total_frames,
            width=frame_width,
            height=frame_height,
            duration_seconds=elapsed_total,
        )
        violation_intervals = [
            ViolationInterval(
                start_frame=int(v["start_sec"] * fps),
                end_frame=int(v["end_sec"] * fps),
                start_time=v["start_sec"],
                end_time=v["end_sec"],
            )
            for v in violations
        ]
        analysis_res = AnalysisResult(
            video_info=vi_info,
            total_analyzed=total_frames,
            valid_frames=valid_frames,
            invalid_frames=total_frames - valid_frames,
            corrupted_frames=0,
            ratio=final_ratio,
            threshold=threshold,
            is_valid=is_valid,
            is_short_video=total_frames < 10,
            violations=violation_intervals,
        )
        try:
            export_json(analysis_res, report_path)
        except Exception as ex:
            report_url = None

        summary = {
            "type": "session_summary",
            "session_id": session_id,
            "total_frames": total_frames,
            "valid_frames": valid_frames,
            "invalid_frames": total_frames - valid_frames,
            "ratio_percent": final_ratio,
            "threshold_percent": threshold,
            "is_valid": is_valid,
            "verdict": "VALID" if is_valid else "INVALID",
            "duration_sec": elapsed_total,
            "violations": violations,
            "debug_video_url": debug_video_url,
            "original_video_url": original_video_url,
            "report_url": report_url,
        }

        try:
            await websocket.send_text(json.dumps(summary))
        except Exception:
            pass

        # Save to task history
        task_info = {
            "task_id": session_id,
            "filename": f"[Webcam Live] {elapsed_total}s",
            "file_path": orig_path if has_orig else "",
            "status": "COMPLETED",
            "created_at": session_start,
            "progress": {"percent": 100.0, "message": "Phiên live đã hoàn tất"},
            "result": {
                "video_info": {
                    "path": orig_path if has_orig else "webcam_live",
                    "filename": f"[Webcam] {elapsed_total}s",
                    "fps": fps,
                    "total_frames": total_frames,
                    "resolution": f"{frame_width}x{frame_height}",
                    "duration_seconds": elapsed_total,
                },
                "summary": {
                    "frames_analyzed": total_frames,
                    "frames_valid": valid_frames,
                    "frames_invalid": total_frames - valid_frames,
                    "frames_corrupted": 0,
                    "ratio_percent": final_ratio,
                    "threshold_percent": threshold,
                    "verdict": "VALID" if is_valid else "INVALID",
                    "is_short_video_warning": total_frames < 10,
                    "is_valid": is_valid,
                    "debug_video_url": debug_video_url,
                    "original_video_url": original_video_url,
                    "report_url": report_url,
                },
                "intervals_missing_hands": [
                    {
                        "start_frame": int(v["start_sec"] * fps),
                        "end_frame": int(v["end_sec"] * fps),
                        "start_time_sec": v["start_sec"],
                        "end_time_sec": v["end_sec"],
                    }
                    for v in violations
                ],
            },
            "error": None,
        }

        import api_service as _svc
        with _svc.tasks_lock:
            _svc.tasks[session_id] = task_info
        _svc.save_history()


# Mount static assets
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "HandGuard AI API is running. UI files not yet generated."})


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
