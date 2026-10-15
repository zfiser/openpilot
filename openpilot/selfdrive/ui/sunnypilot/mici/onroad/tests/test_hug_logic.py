"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("hug_logic_under_test", Path(__file__).resolve().parents[1] / "hug_logic.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class TestNextMode(unittest.TestCase):
  def test_left_cycles_between_the_two_levels(self):
    assert h.next_mode(0, h.LEFT) == 1
    assert h.next_mode(1, h.LEFT) == 2
    assert h.next_mode(2, h.LEFT) == 1

  def test_right_cycles_between_the_two_levels(self):
    assert h.next_mode(0, h.RIGHT) == -1
    assert h.next_mode(-1, h.RIGHT) == -2
    assert h.next_mode(-2, h.RIGHT) == -1

  def test_switching_sides_starts_at_level_1(self):
    assert h.next_mode(2, h.RIGHT) == -1
    assert h.next_mode(-2, h.LEFT) == 1

  def test_center_turns_it_off(self):
    for mode in (-2, -1, 0, 1, 2):
      assert h.next_mode(mode, h.CENTER) == 0

  def test_columns(self):
    assert [h.column_of(x, 0, 300) for x in (0, 99, 100, 199, 200, 299)] == [h.LEFT, h.LEFT, h.CENTER, h.CENTER, h.RIGHT, h.RIGHT]


class TestPullDown(unittest.TestCase):
  def test_a_drag_down_opens_once(self):
    p = h.PullDown()
    p.press(100, 10)
    assert not p.move(101, 30)
    assert p.move(102, 55)
    assert not p.move(102, 90)  # once per press
    assert p.release()  # the release is not a tap

  def test_a_short_drag_is_a_tap(self):
    p = h.PullDown()
    p.press(100, 10)
    assert not p.move(100, 30)
    assert not p.release()

  def test_a_sideways_drag_is_left_to_the_pages(self):
    p = h.PullDown()
    p.press(100, 10)
    assert not p.move(115, 20)
    assert not p.move(115, 80)  # gone sideways first, a later down movement does not count
    assert not p.release()

  def test_a_drag_up_does_nothing(self):
    p = h.PullDown()
    p.press(100, 100)
    assert not p.move(100, 20)

  def test_cancel(self):
    p = h.PullDown()
    p.press(100, 10)
    p.cancel()
    assert not p.move(100, 80) and not p.release()


class TestScreenState(unittest.TestCase):
  def test_closes_five_seconds_after_the_last_touch(self):
    s = h.HugScreenState()
    s.open(0.0)
    s.update(4.9)
    assert s.is_open
    s.touched(4.0)
    s.update(8.9)
    assert s.is_open
    s.update(9.0)
    assert not s.is_open

  def test_a_second_pull_closes(self):
    s = h.HugScreenState()
    s.toggle(0.0)
    assert s.is_open
    s.toggle(1.0)
    assert not s.is_open

  def test_indicator(self):
    assert h.indicator_text(0) is None
    assert h.indicator_text(1) == "< 1" and h.indicator_text(2) == "< 2"
    assert h.indicator_text(-1) == "1 >" and h.indicator_text(-2) == "2 >"


if __name__ == "__main__":
  unittest.main()
