import json
import os
import logging
from video_analyzer import AnalysisResult

logger = logging.getLogger(__name__)


def export_json(result: AnalysisResult, output_path: str) -> None:
    data = {
        "video_info": {
            "path": result.video_info.path,
            "filename": os.path.basename(result.video_info.path),
            "fps": result.video_info.fps,
            "total_frames": result.video_info.total_frames,
            "resolution": f"{result.video_info.width}x{result.video_info.height}",
            "duration_seconds": round(result.video_info.duration_seconds, 2),
        },
        "summary": {
            "frames_analyzed": result.total_analyzed,
            "frames_valid": result.valid_frames,
            "frames_invalid": result.invalid_frames,
            "frames_corrupted": result.corrupted_frames,
            "ratio_percent": round(result.ratio, 2),
            "threshold_percent": result.threshold,
            "verdict": "VALID" if result.is_valid else "INVALID",
            "is_short_video_warning": result.is_short_video,
        },
        "intervals_missing_hands": [
            {
                "start_frame": v.start_frame,
                "end_frame": v.end_frame,
                "start_time_sec": round(v.start_time, 2),
                "end_time_sec": round(v.end_time, 2),
            }
            for v in result.violations
        ],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("JSON report saved to %s", output_path)

