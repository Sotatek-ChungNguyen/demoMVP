import unittest
import os
import json
import tempfile
import numpy as np
import cv2
from unittest.mock import MagicMock
from video_analyzer import VideoAnalyzer, AnalysisResult, VideoInfo, ViolationInterval
from hand_detector import FrameHandResult
from reporter import export_json


def _create_test_video(path: str, num_frames: int = 30, fps: float = 30.0,
                       width: int = 320, height: int = 240):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (i * 8 % 256, 100, 150)
        writer.write(frame)
    writer.release()


class TestVideoAnalyzerWithMock(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.video_path = os.path.join(self.tmpdir, "test.mp4")

    def _make_mock_detector(self, valid_pattern: list[bool]):
        detector = MagicMock()
        self._call_count = 0
        pattern = valid_pattern

        def side_effect(frame, ts):
            idx = self._call_count % len(pattern)
            self._call_count += 1
            return FrameHandResult(
                hand_count=2 if pattern[idx] else 1,
                handedness_labels=["Left", "Right"] if pattern[idx] else ["Left"],
                landmarks=[],
                is_valid=pattern[idx],
            )
        detector.detect = MagicMock(side_effect=side_effect)
        return detector

    def test_all_valid_100_percent(self):
        _create_test_video(self.video_path, num_frames=100)
        detector = self._make_mock_detector([True] * 100)
        analyzer = VideoAnalyzer(detector, threshold=90.0)
        result = analyzer.analyze(self.video_path)
        self.assertEqual(result.valid_frames, 100)
        self.assertAlmostEqual(result.ratio, 100.0)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.violations), 0)

    def test_exactly_90_percent_is_valid(self):
        n = 100
        _create_test_video(self.video_path, num_frames=n)
        pattern = [True] * 90 + [False] * 10
        detector = self._make_mock_detector(pattern)
        analyzer = VideoAnalyzer(detector, threshold=90.0)
        result = analyzer.analyze(self.video_path)
        self.assertEqual(result.valid_frames, 90)
        self.assertAlmostEqual(result.ratio, 90.0)
        self.assertTrue(result.is_valid)

    def test_below_threshold_invalid(self):
        n = 100
        _create_test_video(self.video_path, num_frames=n)
        pattern = [True] * 89 + [False] * 11
        detector = self._make_mock_detector(pattern)
        analyzer = VideoAnalyzer(detector, threshold=90.0)
        result = analyzer.analyze(self.video_path)
        self.assertAlmostEqual(result.ratio, 89.0)
        self.assertFalse(result.is_valid)

    def test_violation_intervals_tracked(self):
        n = 30
        _create_test_video(self.video_path, num_frames=n)
        pattern = [True]*5 + [False]*5 + [True]*10 + [False]*3 + [True]*7
        detector = self._make_mock_detector(pattern)
        analyzer = VideoAnalyzer(detector, threshold=50.0)
        result = analyzer.analyze(self.video_path)
        self.assertEqual(len(result.violations), 2)
        self.assertEqual(result.violations[0].start_frame, 5)
        self.assertEqual(result.violations[0].end_frame, 9)
        self.assertEqual(result.violations[1].start_frame, 20)
        self.assertEqual(result.violations[1].end_frame, 22)

    def test_zero_frames_video(self):
        _create_test_video(self.video_path, num_frames=5)
        detector = self._make_mock_detector([True] * 5)
        analyzer = VideoAnalyzer(detector, threshold=90.0)
        result = analyzer.analyze(self.video_path)
        self.assertTrue(result.is_short_video)

    def test_stride_skips_frames(self):
        _create_test_video(self.video_path, num_frames=30)
        detector = self._make_mock_detector([True] * 30)
        analyzer = VideoAnalyzer(detector, threshold=90.0, stride=3)
        result = analyzer.analyze(self.video_path)
        self.assertEqual(result.total_analyzed, 10)

    def test_file_not_found(self):
        detector = self._make_mock_detector([True])
        analyzer = VideoAnalyzer(detector, threshold=90.0)
        with self.assertRaises(FileNotFoundError):
            analyzer.analyze("/nonexistent/video.mp4")


class TestJsonExport(unittest.TestCase):
    def test_export_creates_valid_json(self):
        tmpdir = tempfile.mkdtemp()
        json_path = os.path.join(tmpdir, "report.json")
        vi = VideoInfo("test.mp4", 30.0, 100, 640, 480, 3.33)
        result = AnalysisResult(
            video_info=vi, total_analyzed=100, valid_frames=95,
            invalid_frames=5, ratio=95.0, threshold=90.0, is_valid=True,
            violations=[ViolationInterval(50, 54, 1.67, 1.8)],
        )
        export_json(result, json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["summary"]["verdict"], "VALID")
        self.assertEqual(len(data["intervals_missing_hands"]), 1)


if __name__ == "__main__":
    unittest.main()