"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("choices_under_test", Path(__file__).resolve().parents[1] / "choices.py")
ch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ch)

LANE = [(-1, "off"), (0, "nudge"), (1, "nudgeless"), (3, "1 s")]


class TestChoices(unittest.TestCase):
  def test_next_wraps_around(self):
    assert ch.next_choice(LANE, -1) == (0, "nudge")
    assert ch.next_choice(LANE, 3) == (-1, "off")

  def test_unknown_current_goes_to_the_first(self):
    assert ch.next_choice(LANE, 7) == (-1, "off")
    assert ch.next_choice(LANE, None) == (-1, "off")

  def test_label(self):
    assert ch.label_for(LANE, 1) == "nudgeless"
    assert ch.label_for(LANE, 7) == "7"
    assert ch.label_for(LANE, None) == "--"

  def test_a_value_set_elsewhere_is_kept_in_the_cycle(self):
    choices = ch.with_current(LANE, 5)
    assert choices[-1] == (5, "5") and len(choices) == len(LANE) + 1
    assert ch.with_current(LANE, 0) == LANE
    assert ch.with_current(LANE, None) == LANE
    assert ch.next_choice(choices, 3) == (5, "5")


if __name__ == "__main__":
  unittest.main()
