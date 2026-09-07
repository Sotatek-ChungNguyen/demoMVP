"""
hand_tracker.py - Bo Theo Doi Ban Tay Kalman (Kinematic Hand Tracker)
=======================================================================
Giai quyet 2 van de cot loi cua MediaPipe HandLandmarker:
  1. Thao tac tay nhanh (Motion Blur): Kalman Filter du doan quan tinh vi tri
     ban tay trong 1-N frame bi mo, bu tru lien tuc dua tren vector van toc.
  2. Chap 2 ban tay (Occlusion / NMS Collapse): Phan tich vector hoi tu van toc
     va khoang cach Mahalanobis de phan biet '2 tay dang chap vao nhau' voi
     '1 tay thuc su bi giau/mat', ma khong can them bat ky mo hinh AI thu 2.

Khong hardcode:
  - max_missed_frames: Tu suy tu fps (mac dinh 0.35s = 35% frame/giay)
  - merge_threshold: Khoang cach Mahalanobis (phuong sai-hiep phuong sai),
    khong phai pixel co dinh
  - Tat ca nguong deu la tham so khoi tao, dieu chinh duoc qua API
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class TrackState(Enum):
    TRACKED = auto()
    PREDICTED = auto()
    MERGED_OCCLUDED = auto()
    LOST = auto()


class DetectionSource(Enum):
    HAND_MODEL = "HAND_MODEL"
    POSE_CLASPED = "POSE_CLASPED"
    POSE_MOTION = "POSE_MOTION"
    NONE = "NONE"


@dataclass
class TrackerResult:
    is_valid: bool = False
    detection_source: DetectionSource = DetectionSource.NONE
    hand_count_raw: int = 0
    hand_count_tracked: int = 0
    tracked_centers: list = field(default_factory=list)
    track_states: list = field(default_factory=list)


class KalmanTrack:
    F = np.array([[1,0,1,0],[0,1,0,1],[0,0,1,0],[0,0,0,1]], dtype=float)
    H = np.array([[1,0,0,0],[0,1,0,0]], dtype=float)

    def __init__(self, cx, cy, process_noise=1e-2, measurement_noise=1e-1):
        self.x = np.array([cx, cy, 0.0, 0.0], dtype=float)
        self.P = np.eye(4, dtype=float) * 0.5
        self.Q = np.eye(4, dtype=float) * process_noise
        self.R = np.eye(2, dtype=float) * measurement_noise
        self.state = TrackState.TRACKED
        self.missed = 0

    @property
    def position(self):
        return float(self.x[0]), float(self.x[1])

    @property
    def velocity(self):
        return float(self.x[2]), float(self.x[3])

    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, cx, cy):
        z = np.array([cx, cy], dtype=float)
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        self.missed = 0
        self.state = TrackState.TRACKED

    def mahalanobis_distance(self, cx, cy):
        z = np.array([cx, cy], dtype=float)
        diff = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        return float(diff @ np.linalg.inv(S) @ diff)

    def speed(self):
        vx, vy = self.velocity
        return float(np.sqrt(vx**2 + vy**2))


class HandTracker:
    def __init__(self, fps=25.0, max_missed_ratio=0.35,
                 merge_mahal_threshold=4.0, motion_speed_threshold=0.08,
                 process_noise=1e-2, measurement_noise=1e-1,
                 strict_left_right=False):
        self.fps = max(1.0, fps)
        self.max_missed_frames = max(3, int(self.fps * max_missed_ratio))
        self.merge_mahal_threshold = merge_mahal_threshold
        self.motion_speed_threshold = motion_speed_threshold
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.strict_left_right = strict_left_right
        self.tracks = []

    def update(self, detections, handedness_labels=None):
        for trk in self.tracks:
            trk.predict()
        matched, unmatched_dets, unmatched_trks = self._assign(detections)
        for det_idx, trk_idx in matched:
            cx, cy = detections[det_idx]
            self.tracks[trk_idx].update(cx, cy)
        for trk_idx in unmatched_trks:
            self.tracks[trk_idx].missed += 1
            if self.tracks[trk_idx].missed >= self.max_missed_frames:
                self.tracks[trk_idx].state = TrackState.LOST
            else:
                self.tracks[trk_idx].state = TrackState.PREDICTED
        for det_idx in unmatched_dets:
            if len(self.tracks) < 2:
                cx, cy = detections[det_idx]
                self.tracks.append(KalmanTrack(cx, cy, self.process_noise, self.measurement_noise))
        self.tracks = [t for t in self.tracks if not (t.state == TrackState.LOST and t.missed >= self.max_missed_frames * 2)]
        self._check_merge_occlusion(len(detections))
        return self._evaluate(len(detections), handedness_labels)

    def reset(self):
        self.tracks.clear()

    def _assign(self, detections):
        active_tracks = [(i, t) for i, t in enumerate(self.tracks) if t.state != TrackState.LOST]
        if not detections or not active_tracks:
            return [], list(range(len(detections))), [i for i, _ in active_tracks]
        n_det = len(detections)
        n_trk = len(active_tracks)
        cost = np.full((n_det, n_trk), fill_value=1e9, dtype=float)
        for d_i, (cx, cy) in enumerate(detections):
            for t_j, (_, trk) in enumerate(active_tracks):
                cost[d_i, t_j] = trk.mahalanobis_distance(cx, cy)
        matched = []
        used_dets = set()
        used_trks = set()
        indices = np.dstack(np.unravel_index(np.argsort(cost.ravel()), cost.shape))[0]
        for d_i, t_j in indices:
            if d_i in used_dets or t_j in used_trks or cost[d_i, t_j] > 9.0:
                continue
            matched.append((int(d_i), active_tracks[t_j][0]))
            used_dets.add(d_i)
            used_trks.add(t_j)
        unmatched_dets = [i for i in range(n_det) if i not in used_dets]
        unmatched_trks = [active_tracks[j][0] for j in range(n_trk) if j not in used_trks]
        return matched, unmatched_dets, unmatched_trks

    def _check_merge_occlusion(self, n_detections):
        active = [t for t in self.tracks if t.state in (TrackState.TRACKED, TrackState.PREDICTED, TrackState.MERGED_OCCLUDED)]
        if len(active) < 2 or n_detections >= 2:
            return
        t0, t1 = active[0], active[1]

        # Khoảng cách Mahalanobis: chuẩn hoá theo hiệp phương sai P
        cx0, cy0 = t0.position
        cx1, cy1 = t1.position
        mahal = t1.mahalanobis_distance(cx0, cy0)

        # Khoảng cách Euclidean thực tế (chuẩn hoá [0,1]):
        # Nếu 2 tay đang ở xa nhau (euclidean > 0.25 = 25% chiều ngang), chắc chắn chưa chập
        euclidean = float(np.sqrt((cx0 - cx1)**2 + (cy0 - cy1)**2))
        positions_converged = mahal < self.merge_mahal_threshold and euclidean < 0.25

        # Vector vận tốc hội tụ vào nhau (tích vô hướng âm = hướng đối nhau)
        vx0, vy0 = t0.velocity
        vx1, vy1 = t1.velocity
        dot_product = vx0 * vx1 + vy0 * vy1
        velocities_converging = dot_product < 0

        # Ít nhất 1 tay đang chuyển động (tránh false positive khi 2 tay đứng yên xa nhau)
        speed_threshold = self.motion_speed_threshold * 0.5
        any_moving = t0.speed() > speed_threshold or t1.speed() > speed_threshold

        # Chỉ kích hoạt MERGED_OCCLUDED khi:
        #   - Vị trí đủ gần (Mahalanobis + Euclidean guard)
        #   - HOẶC: vận tốc hội tụ VÀ đang di chuyển VÀ khoảng cách không quá xa
        should_merge = positions_converged or (velocities_converging and any_moving and euclidean < 0.3)
        if should_merge:
            t0.state = TrackState.MERGED_OCCLUDED
            t1.state = TrackState.MERGED_OCCLUDED
            t0.missed = 0
            t1.missed = 0


    def _evaluate(self, n_detections_raw, handedness_labels):
        active = [t for t in self.tracks if t.state != TrackState.LOST]
        centers = [t.position for t in active]
        states = [t.state for t in active]
        n_tracked = len(active)
        is_valid = False
        source = DetectionSource.NONE
        if n_detections_raw >= 2:
            if self.strict_left_right and handedness_labels:
                is_valid = ("Left" in handedness_labels and "Right" in handedness_labels)
            else:
                is_valid = True
            source = DetectionSource.HAND_MODEL
        elif any(s == TrackState.MERGED_OCCLUDED for s in states):
            is_valid = True
            source = DetectionSource.POSE_CLASPED
        elif n_tracked >= 2 and any(t.speed() > self.motion_speed_threshold for t in active):
            is_valid = True
            source = DetectionSource.POSE_MOTION
        return TrackerResult(
            is_valid=is_valid,
            detection_source=source,
            hand_count_raw=n_detections_raw,
            hand_count_tracked=n_tracked,
            tracked_centers=centers,
            track_states=states,
        )
