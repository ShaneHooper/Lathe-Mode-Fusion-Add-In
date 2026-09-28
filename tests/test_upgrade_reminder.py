"""The monthly-prompt decision, without Fusion.

Run from the repository root:  python -m unittest discover tests
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "GSendLatheMode", "lib"))

import upgrade_reminder as ur  # noqa: E402

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


class NextAction(unittest.TestCase):
    def test_first_run_is_never_a_prompt(self):
        self.assertEqual(ur.next_action({"installed": None, "last_shown": None}, NOW),
                         ur.FIRST_RUN)

    def test_a_fresh_install_waits_a_full_interval(self):
        state = {"installed": NOW - 29 * DAY, "last_shown": None}
        self.assertEqual(ur.next_action(state, NOW), ur.WAIT)
        state = {"installed": NOW - 30 * DAY, "last_shown": None}
        self.assertEqual(ur.next_action(state, NOW), ur.SHOW)

    def test_a_prompt_restarts_the_clock(self):
        state = {"installed": NOW - 400 * DAY, "last_shown": NOW - 10 * DAY}
        self.assertEqual(ur.next_action(state, NOW), ur.WAIT)
        state = {"installed": NOW - 400 * DAY, "last_shown": NOW - 31 * DAY}
        self.assertEqual(ur.next_action(state, NOW), ur.SHOW)

    def test_a_reinstall_after_a_prompt_uses_the_later_stamp(self):
        state = {"installed": NOW - 5 * DAY, "last_shown": NOW - 45 * DAY}
        self.assertEqual(ur.next_action(state, NOW), ur.WAIT)

    def test_a_stamp_from_the_future_counts_as_due(self):
        state = {"installed": NOW - 100 * DAY, "last_shown": NOW + 400 * DAY}
        self.assertEqual(ur.next_action(state, NOW), ur.SHOW)


class StateFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = ur.state_path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_path_lands_in_the_gsend_folder_under_appdata(self):
        self.assertEqual(
            self.path,
            os.path.join(self.tmp.name, "G-SEND.IO", "lathe_mode_reminder.json"))

    def test_missing_and_corrupt_files_read_as_never(self):
        self.assertEqual(ur.load_state(self.path),
                         {"installed": None, "last_shown": None})
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as handle:
            handle.write("{not json")
        self.assertEqual(ur.load_state(self.path),
                         {"installed": None, "last_shown": None})
        with open(self.path, "w") as handle:
            json.dump({"installed_utc": "yesterday-ish"}, handle)
        self.assertEqual(ur.load_state(self.path),
                         {"installed": None, "last_shown": None})

    def test_first_launch_records_install_and_shows_nothing(self):
        self.assertEqual(ur.decide_and_record(self.path, NOW), ur.FIRST_RUN)
        state = ur.load_state(self.path)
        self.assertEqual(state["installed"], NOW)
        self.assertIsNone(state["last_shown"])
        # Same day, launched again: still nothing, and nothing rewritten.
        self.assertEqual(ur.decide_and_record(self.path, NOW + timedelta(hours=3)),
                         ur.WAIT)
        self.assertEqual(ur.load_state(self.path)["installed"], NOW)

    def test_a_month_later_it_shows_once_and_then_waits(self):
        ur.decide_and_record(self.path, NOW)
        later = NOW + 30 * DAY
        self.assertEqual(ur.decide_and_record(self.path, later), ur.SHOW)
        self.assertEqual(ur.load_state(self.path)["last_shown"], later)
        self.assertEqual(ur.decide_and_record(self.path, later + DAY), ur.WAIT)
        self.assertEqual(ur.decide_and_record(self.path, later + 30 * DAY), ur.SHOW)

    def test_the_shown_stamp_is_written_before_any_dialog_could_open(self):
        # decide_and_record is the only thing the Fusion half calls before
        # arming the dialog, so the stamp must already be on disk when it
        # returns SHOW.
        ur.save_state(self.path, installed=NOW - 60 * DAY)
        self.assertEqual(ur.decide_and_record(self.path, NOW), ur.SHOW)
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["last_shown_utc"], NOW.isoformat())

    def test_the_file_is_written_whole_with_no_leftover_scratch(self):
        ur.save_state(self.path, installed=NOW, last_shown=NOW)
        self.assertFalse(os.path.exists(self.path + ".tmp"))
        with open(self.path, encoding="utf-8") as handle:
            raw = json.load(handle)
        self.assertEqual(set(raw), {"installed_utc", "last_shown_utc"})


if __name__ == "__main__":
    unittest.main()
