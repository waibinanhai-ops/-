"""模块 3 中无需 Resolve GUI 的轨道结构单元测试。"""

from __future__ import annotations

import unittest

from resolve.export_xml import expected_track_counts, validate_track_counts


class ExportXmlTests(unittest.TestCase):
    def test_expected_counts_match_two_cameras_and_external_audio(self):
        info = {
            "video_files": {"a": ["a1", "a2"], "b": ["b1"]},
            "audio_files": ["sound1", "sound2", "sound3"],
        }
        video, audio = expected_track_counts(info)  # type: ignore[arg-type]
        self.assertEqual(video, [2, 1])
        self.assertEqual(audio, [2, 1, 1, 1, 1])

    def test_rejects_missing_track_content(self):
        with self.assertRaisesRegex(RuntimeError, "视频轨校验失败"):
            validate_track_counts([2], [2, 1], [2, 1], [2, 1, 1])

    def test_accepts_external_audio_tracks_in_resolve_order(self):
        validate_track_counts(
            [2, 1],
            [1, 1, 1, 2, 1],
            [2, 1],
            [2, 1, 1, 1, 1],
        )


if __name__ == "__main__":
    unittest.main()
