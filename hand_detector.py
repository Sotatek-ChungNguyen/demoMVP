from dataclasses import dataclass, field
import logging
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from hand_tracker import HandTracker, DetectionSource

logger = logging.getLogger(__name__)


@dataclass
class FrameHandResult:
    hand_count: int = 0
    handedness_labels: list[str] = field(default_factory=list)
    landmarks: list = field(default_factory=list)
    is_valid: bool = False
    # Nguồn xác nhận hợp lệ: HAND_MODEL / POSE_CLASPED / POSE_MOTION / NONE
    detection_source: str = DetectionSource.HAND_MODEL.value


class HandDetector:
    def __init__(self, model_path: str, strict_left_right: bool = False,
                 min_detection_confidence: float = 0.3,
                 min_presence_confidence: float = 0.25,
                 min_tracking_confidence: float = 0.25,
                 fps: float = 25.0):
        self.model_path = model_path
        self.strict_left_right = strict_left_right

        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            # Hạ ngưỡng confidence để MediaPipe bám được tay mờ khi chuyển động nhanh
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_timestamp_ms = -1

        # Khởi tạo Kalman Hand Tracker (cực nhẹ, không tốn thêm CPU đáng kể)
        self._tracker = HandTracker(
            fps=fps,
            strict_left_right=strict_left_right,
        )

    def detect(self, frame: np.ndarray, timestamp_ms: int) -> FrameHandResult:
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        hand_count = len(result.hand_landmarks)
        handedness_labels = []
        for hand_cat_list in result.handedness:
            if hand_cat_list:
                handedness_labels.append(hand_cat_list[0].category_name)

        # Tính tọa độ tâm (cx, cy) chuẩn hoá [0,1] cho mỗi bàn tay
        # dùng trung bình 21 landmark của từng bàn tay
        detections: list[tuple[float, float]] = []
        for hand_lms in result.hand_landmarks:
            xs = [lm.x for lm in hand_lms]
            ys = [lm.y for lm in hand_lms]
            detections.append((float(np.mean(xs)), float(np.mean(ys))))

        # Cập nhật Kalman Tracker → nhận TrackerResult thông minh
        tracker_result = self._tracker.update(detections, handedness_labels)

        return FrameHandResult(
            hand_count=hand_count,
            handedness_labels=handedness_labels,
            landmarks=result.hand_landmarks,
            is_valid=tracker_result.is_valid,
            detection_source=tracker_result.detection_source.value,
        )

    def reset_tracker(self):
        """Reset tracker khi bắt đầu phiên mới (live webcam)."""
        self._tracker.reset()

    def close(self):
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
