from dataclasses import dataclass, field
import logging
import cv2
from tqdm import tqdm
from hand_detector import HandDetector, FrameHandResult

logger = logging.getLogger(__name__)


@dataclass
class ViolationInterval:
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float


@dataclass
class VideoInfo:
    path: str
    fps: float
    total_frames: int
    width: int
    height: int
    duration_seconds: float


@dataclass
class AnalysisResult:
    video_info: VideoInfo
    total_analyzed: int = 0
    valid_frames: int = 0
    invalid_frames: int = 0
    corrupted_frames: int = 0
    ratio: float = 0.0
    threshold: float = 90.0
    is_valid: bool = False
    is_short_video: bool = False
    violations: list[ViolationInterval] = field(default_factory=list)


class VideoAnalyzer:
    def __init__(self, detector: HandDetector, threshold: float = 90.0, stride: int = 1):
        self.detector = detector
        self.threshold = threshold
        self.stride = max(1, stride)

    def analyze(self, video_path: str, progress_callback=None, visualizer=None) -> AnalysisResult:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0.0

        video_info = VideoInfo(
            path=video_path, fps=fps, total_frames=total_frames,
            width=width, height=height, duration_seconds=duration,
        )

        if total_frames == 0:
            cap.release()
            return AnalysisResult(
                video_info=video_info, threshold=self.threshold,
                is_valid=False, is_short_video=True,
            )
        valid_count = 0
        analyzed_count = 0
        corrupted_count = 0
        frame_idx = 0
        in_violation = False
        violation_start = -1
        violations: list[ViolationInterval] = []

        pbar = tqdm(total=total_frames, desc="Scanning", unit="frame")
        last_result = None
        while True:
            ret, frame = cap.read()
            if not ret:
                if frame_idx < total_frames:
                    corrupted_count += 1
                    frame_idx += 1
                    pbar.update(1)
                    continue
                break

            if frame_idx % self.stride == 0:
                ts_ms = int(frame_idx * 1000.0 / fps)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self.detector.detect(rgb, ts_ms)
                last_result = result
                analyzed_count += 1

                if result.is_valid:
                    valid_count += 1
                    if in_violation:
                        violations.append(ViolationInterval(
                            start_frame=violation_start, end_frame=frame_idx - 1,
                            start_time=violation_start / fps,
                            end_time=(frame_idx - 1) / fps,
                        ))
                        in_violation = False
                else:
                    if not in_violation:
                        in_violation = True
                        violation_start = frame_idx
            else:
                result = last_result

            cur_ratio = (valid_count / analyzed_count * 100) if analyzed_count > 0 else 0.0

            if visualizer is not None and result is not None:
                drawn = visualizer.draw_frame(frame, result, frame_idx, total_frames, cur_ratio)
                visualizer.write_frame(drawn)

            frame_idx += 1
            pbar.update(1)

            if progress_callback:
                progress_callback(frame_idx, total_frames, valid_count, cur_ratio)

        pbar.close()
        cap.release()

        if in_violation:
            violations.append(ViolationInterval(
                start_frame=violation_start, end_frame=frame_idx - 1,
                start_time=violation_start / fps,
                end_time=(frame_idx - 1) / fps,
            ))

        ratio = (valid_count / analyzed_count * 100) if analyzed_count > 0 else 0.0

        return AnalysisResult(
            video_info=video_info,
            total_analyzed=analyzed_count,
            valid_frames=valid_count,
            invalid_frames=analyzed_count - valid_count,
            corrupted_frames=corrupted_count,
            ratio=ratio,
            threshold=self.threshold,
            is_valid=ratio >= self.threshold,
            is_short_video=analyzed_count < 10,
            violations=violations,
        )