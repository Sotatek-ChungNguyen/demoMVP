import os
import time
import uuid
import json
import logging
import threading
from typing import Dict, Any, Optional

import cv2

from model_manager import ensure_model
from hand_detector import HandDetector
from video_analyzer import VideoAnalyzer, AnalysisResult
from visualizer import VideoVisualizer
from reporter import export_json

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uploads")
OUTPUT_DIR = os.path.join(STORAGE_DIR, "outputs")
REPORT_DIR = os.path.join(STORAGE_DIR, "reports")
HISTORY_FILE = os.path.join(STORAGE_DIR, "history.json")

for d in [UPLOAD_DIR, OUTPUT_DIR, REPORT_DIR]:
    os.makedirs(d, exist_ok=True)

# In-memory store of tasks
tasks: Dict[str, Dict[str, Any]] = {}
tasks_lock = threading.Lock()


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                for item in history_data:
                    tasks[item["task_id"]] = item
        except Exception as e:
            logger.error("Failed to load history: %s", e)


def save_history():
    try:
        with tasks_lock:
            history_list = [
                task for task in tasks.values()
                if task.get("status") in ["COMPLETED", "FAILED"]
            ]
            # Keep last 50 tasks
            history_list = sorted(history_list, key=lambda x: x.get("created_at", 0), reverse=True)[:50]
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Failed to save history: %s", e)


load_history()


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with tasks_lock:
        return tasks.get(task_id)


def list_tasks():
    with tasks_lock:
        return sorted(list(tasks.values()), key=lambda x: x.get("created_at", 0), reverse=True)


def create_task(filename: str, file_path: str) -> str:
    task_id = str(uuid.uuid4())[:8]
    task_info = {
        "task_id": task_id,
        "filename": filename,
        "file_path": file_path,
        "status": "PENDING",
        "created_at": time.time(),
        "progress": {
            "frame": 0,
            "total_frames": 0,
            "percent": 0.0,
            "valid_count": 0,
            "current_ratio": 0.0,
            "message": "Đang chuẩn bị phân tích..."
        },
        "result": None,
        "error": None,
    }
    with tasks_lock:
        tasks[task_id] = task_info
    return task_id


def run_analysis_worker(
    task_id: str,
    video_path: str,
    threshold: float = 90.0,
    strict_left_right: bool = False,
    stride: int = 1,
    render_debug: bool = True,
):
    try:
        with tasks_lock:
            tasks[task_id]["status"] = "PROCESSING"
            tasks[task_id]["progress"]["message"] = "Đang kiểm tra mô hình MediaPipe..."

        model_path = ensure_model()

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Không thể mở file video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        with tasks_lock:
            tasks[task_id]["progress"]["total_frames"] = total_frames
            tasks[task_id]["progress"]["message"] = "Đang quét từng khung hình..."

        vis = None
        debug_video_filename = None
        debug_video_path = None
        if render_debug:
            debug_video_filename = f"debug_{task_id}.mp4"
            debug_video_path = os.path.join(OUTPUT_DIR, debug_video_filename)
            try:
                vis = VideoVisualizer(debug_video_path, fps, width, height)
            except Exception as e:
                logger.warning("Không thể khởi tạo VideoVisualizer: %s", e)
                vis = None
                debug_video_path = None

        def on_progress(frame_idx, total, valid_count, current_ratio):
            pct = round((frame_idx / total * 100) if total > 0 else 0, 1)
            with tasks_lock:
                tasks[task_id]["progress"] = {
                    "frame": frame_idx,
                    "total_frames": total,
                    "percent": pct,
                    "valid_count": valid_count,
                    "current_ratio": round(current_ratio, 2),
                    "message": f"Đang phân tích khung hình {frame_idx}/{total} ({pct}%)"
                }

        with HandDetector(model_path, strict_left_right=strict_left_right) as detector:
            analyzer = VideoAnalyzer(detector, threshold=threshold, stride=stride)
            result = analyzer.analyze(video_path, progress_callback=on_progress, visualizer=vis)

        if vis:
            vis.close()

        report_filename = f"report_{task_id}.json"
        report_path = os.path.join(REPORT_DIR, report_filename)
        export_json(result, report_path)

        with open(report_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)

        report_data["summary"]["threshold_percent"] = threshold
        report_data["summary"]["is_valid"] = result.is_valid
        report_data["summary"]["debug_video_url"] = f"/api/media/outputs/{debug_video_filename}" if debug_video_path else None
        report_data["summary"]["original_video_url"] = f"/api/media/uploads/{os.path.basename(video_path)}"
        report_data["summary"]["report_url"] = f"/api/media/reports/{report_filename}"

        with tasks_lock:
            tasks[task_id]["status"] = "COMPLETED"
            tasks[task_id]["progress"]["percent"] = 100.0
            tasks[task_id]["progress"]["message"] = "Hoàn tất phân tích!"
            tasks[task_id]["result"] = report_data

        save_history()

    except Exception as e:
        logger.exception("Lỗi khi xử lý tác vụ %s: %s", task_id, e)
        with tasks_lock:
            tasks[task_id]["status"] = "FAILED"
            tasks[task_id]["error"] = str(e)
            tasks[task_id]["progress"]["message"] = f"Lỗi: {str(e)}"
        save_history()


def start_analysis_async(
    task_id: str,
    video_path: str,
    threshold: float = 90.0,
    strict_left_right: bool = False,
    stride: int = 1,
    render_debug: bool = True,
):
    thread = threading.Thread(
        target=run_analysis_worker,
        args=(task_id, video_path, threshold, strict_left_right, stride, render_debug),
        daemon=True,
    )
    thread.start()
    return thread


