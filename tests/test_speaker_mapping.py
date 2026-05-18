"""Tests for speaker line parsing and name substitution."""

from __future__ import annotations

import unittest

from meeting_assistant.services.speaker_mapping import (
    apply_speaker_mapping,
    extract_speaker_keys,
    first_time_range_sec_by_speaker,
    parse_timestamp_to_seconds,
)


class TestSpeakerMapping(unittest.TestCase):
    def test_extract_first_seen_order(self) -> None:
        text = (
            "SPEAKER_01 [00:01 - 00:02]: Second first line order bug.\n"
            "SPEAKER_00 [00:00 - 00:01]: First.\n"
        )
        keys = extract_speaker_keys(text)
        self.assertEqual(keys, ["SPEAKER_01", "SPEAKER_00"])

    def test_apply_replaces_line_prefix_only(self) -> None:
        raw = (
            "SPEAKER_00 [00:00 - 00:05]: Hello\n"
            "SPEAKER_01 [00:05 - 00:10]: Mention SPEAKER_00 in text.\n"
        )
        mapped = apply_speaker_mapping(
            raw, {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
        )
        self.assertTrue(mapped.startswith("Alice ["))
        self.assertIn("Mention SPEAKER_00 in text.", mapped)

    def test_parse_timestamp_mm_ss(self) -> None:
        self.assertEqual(parse_timestamp_to_seconds("00:05"), 5.0)
        self.assertEqual(parse_timestamp_to_seconds("01:30"), 90.0)

    def test_parse_timestamp_hh_mm_ss(self) -> None:
        self.assertEqual(parse_timestamp_to_seconds("01:02:03"), 3600 + 120 + 3)

    def test_first_time_range_per_speaker(self) -> None:
        text = (
            "SPEAKER_00 [00:00 - 00:15]: First.\n\n"
            "SPEAKER_01 [00:15 - 00:22]: Second.\n\n"
            "SPEAKER_00 [01:00 - 01:05]: Later same speaker — ignored for range map.\n"
        )
        ranges = first_time_range_sec_by_speaker(text)
        self.assertEqual(ranges["SPEAKER_00"], (0.0, 15.0))
        self.assertEqual(ranges["SPEAKER_01"], (15.0, 22.0))

    def test_first_time_range_hour_format(self) -> None:
        text = "SPEAKER_00 [01:00:00 - 01:00:10]: Long meeting.\n\n"
        ranges = first_time_range_sec_by_speaker(text)
        self.assertEqual(ranges["SPEAKER_00"], (3600.0, 3610.0))


if __name__ == "__main__":
    unittest.main()
