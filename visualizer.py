import cv2
import logging
import numpy as np
from hand_detector import FrameHandResult

logger = logging.getLogger(__name__)

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]

COLOR_LEFT = (255, 165, 0)
COLOR_RIGHT = (0, 255, 128)
COLOR_VALID = (0, 200, 0)
COLOR_INVALID = (0, 0, 220)
COLOR_HUD_BG = (40, 40, 40)


class VideoVisualizer:
    def __init__(self, output_path: str, fps: float, width: int, height: int):
        self.width = width
        self.height = height
        self.writer = self._create_writer(output_path, fps, width, height)
        if self.writer is None:
            raise RuntimeError(f"Cannot create video writer for {output_path}")

    @staticmethod
    def _create_writer(path: str, fps: float, w: int, h: int):
        for fourcc_str in ["avc1", "H264", "mp4v"]:
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            writer = cv2.VideoWriter(path, fourcc, fps, (w, h))
            if writer.isOpened():
                return writer
        return None

    def draw_frame(self, frame: np.ndarray, result: FrameHandResult,
                   frame_idx: int, total_frames: int,
                   cumulative_ratio: float) -> np.ndarray:
        vis = frame.copy()
        self._draw_landmarks(vis, result)
        self._draw_hud(vis, result, frame_idx, total_frames, cumulative_ratio)
        return vis

    def _draw_landmarks(self, frame: np.ndarray, result: FrameHandResult):
        h, w = frame.shape[:2]
        for i, hand_lms in enumerate(result.landmarks):
            color = COLOR_LEFT if i < len(result.handedness_labels) and result.handedness_labels[i] == "Left" else COLOR_RIGHT
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lms]
            for p1, p2 in HAND_CONNECTIONS:
                if p1 < len(pts) and p2 < len(pts):
                    cv2.line(frame, pts[p1], pts[p2], color, 2)
            for pt in pts:
                cv2.circle(frame, pt, 4, color, -1)

    def _draw_hud(self, frame: np.ndarray, result: FrameHandResult,
                  frame_idx: int, total: int, ratio: float):
        from hand_tracker import DetectionSource
        src = getattr(result, "detection_source", DetectionSource.HAND_MODEL.value)

        if result.is_valid:
            if src == DetectionSource.POSE_CLASPED.value:
                badge_text = "HOP LE - 2 TAY CHAP NHAU"
                badge_color = (255, 200, 0)   # Xanh lam (Cyan)
            elif src == DetectionSource.POSE_MOTION.value:
                badge_text = "HOP LE - CHUYEN DONG NHANH"
                badge_color = (0, 200, 255)   # Vàng
            else:
                badge_text = "V DU 2 TAY"
                badge_color = COLOR_VALID
        else:
            badge_text = "X THIEU TAY (VI PHAM)"
            badge_color = COLOR_INVALID

        cv2.rectangle(frame, (10, 10), (320, 100), COLOR_HUD_BG, -1)
        cv2.rectangle(frame, (10, 10), (320, 100), badge_color, 2)
        cv2.putText(frame, badge_text, (18, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, badge_color, 2)
        progress = f"Frame {frame_idx + 1}/{total}"
        cv2.putText(frame, progress, (18, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        ratio_text = f"Ty le dat: {ratio:.1f}%"
        cv2.putText(frame, ratio_text, (18, 88),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


    def write_frame(self, frame: np.ndarray):
        self.writer.write(frame)

    def close(self):
        if self.writer:
            self.writer.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()