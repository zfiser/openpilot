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

  def test_side_buttons_turn_auto_off(self):
    assert h.press(0, True, h.LEFT) == (1, False)
    assert h.press(1, False, h.LEFT) == (2, False)
    assert h.press(2, True, h.RIGHT) == (-1, False)

  def test_middle_button_toggles_auto_from_the_center(self):
    assert h.press(0, False, h.CENTER) == (0, True)
    assert h.press(0, True, h.CENTER) == (0, False)
    assert h.press(-2, False, h.CENTER) == (0, True)  # a manual hug ends when auto goes on

  def test_arrow_shape_and_place(self):
    x, y, w, hgt = 0.0, 0.0, 400.0, 240.0
    (bx1, by1), (tx, ty), (bx2, by2) = h.arrow_points(h.LEFT, x, y, w, hgt)
    assert tx < bx1 == bx2 and ty == hgt / 2  # '<', tip on the outside
    assert by2 - by1 == h.ARROW_HEIGHT and by2 - by1 > 3 * h.ARROW_WIDTH  # tall and narrow
    (rb, _), (rt, _), _ = h.arrow_points(h.RIGHT, x, y, w, hgt)
    assert rt > rb and rt == w - h.ARROW_MARGIN  # '>' at the right edge

  def test_arrow_hit(self):
    box = (0.0, 0.0, 400.0, 240.0)
    assert h.arrow_hit(h.LEFT, 30, 120, *box)
    assert not h.arrow_hit(h.LEFT, 370, 120, *box)
    assert h.arrow_hit(h.RIGHT, 370, 120, *box)
    assert not h.arrow_hit(h.CENTER, 30, 120, *box)

  def test_arrow_tap(self):
    assert h.arrow_tap(1, False) == h.CANCEL_MANUAL
    assert h.arrow_tap(-2, True) == h.CANCEL_MANUAL
    assert h.arrow_tap(0, True) == h.PAUSE_AUTO
    assert h.arrow_tap(0, False) is None


if __name__ == "__main__":
  unittest.main()
