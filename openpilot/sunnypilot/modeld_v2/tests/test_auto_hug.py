"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.sunnypilot.modeld_v2.auto_hug import (AutoHug, HOLD_SECONDS, LEFTMOST, MIDDLE, RIGHTMOST, UNKNOWN, edge_distances,
                                                     lane_of)
from openpilot.sunnypilot.modeld_v2.lane_position import CENTER, LEFT, RIGHT

DT = 0.05
FAST = 33.0  # m/s, 120 km/h
# metres from the own lane line to the road edge, as measured on the highway drive
LEFT_LANE = (1.5, 6.5)
RIGHT_LANE = (6.5, 2.5)
MIDDLE_LANE = (5.5, 5.5)


def run(ah, edges, seconds, v=FAST, changing=False):
  side = None
  for _ in range(round(seconds / DT)):
    side = ah.update(edges[0], edges[1], v, changing, DT)
  return side


class TestAutoHug:
  def test_lane_of(self):
    assert lane_of(False, True) == LEFTMOST
    assert lane_of(True, False) == RIGHTMOST
    assert lane_of(True, True) == MIDDLE
    assert lane_of(False, False) == UNKNOWN

  def test_edge_distances(self):
    # model y positive to the right: left line -1.8, right line 1.8, left edge -3.3, right edge 7.0
    left, right = edge_distances(-1.8, 1.8, -3.3, 7.0)
    assert abs(left - 1.5) < 1e-9 and abs(right - 5.2) < 1e-9

  def test_hugs_the_side_of_the_edge_lane_after_the_hold(self):
    ah = AutoHug()
    assert run(ah, LEFT_LANE, HOLD_SECONDS - 0.5) == CENTER
    assert run(ah, LEFT_LANE, 1.0) == LEFT
    ah = AutoHug()
    assert run(ah, RIGHT_LANE, HOLD_SECONDS + 0.5) == RIGHT
    ah = AutoHug()
    assert run(ah, MIDDLE_LANE, 20) == CENTER

  def test_a_shoulder_as_wide_as_a_lane_is_not_hugged(self):
    ah = AutoHug()
    assert run(ah, (6.5, 4.6), 20) == CENTER  # 4.6 m to the right edge: counts as a lane, so the middle

  def test_the_band_keeps_the_answer(self):
    ah = AutoHug()
    run(ah, LEFT_LANE, 10)
    assert run(ah, (1.5, 4.2), 10) == LEFT  # between 4.0 and 4.5 m: still a lane on the right

  def test_only_from_50_kmh(self):
    ah = AutoHug()
    assert run(ah, LEFT_LANE, 10, v=12.0) == CENTER  # 43 km/h, never started
    assert run(ah, LEFT_LANE, 1, v=FAST) == LEFT
    assert run(ah, LEFT_LANE, 1, v=12.0) == LEFT  # 43 km/h, above the stop speed
    assert run(ah, LEFT_LANE, 1, v=10.5) == CENTER  # 38 km/h

  def test_centered_while_openpilot_changes_lanes_and_found_again_after(self):
    ah = AutoHug()
    run(ah, LEFT_LANE, 10)
    assert run(ah, LEFT_LANE, 3, changing=True) == CENTER
    assert run(ah, RIGHT_LANE, 1) == CENTER  # the old answer is gone
    assert run(ah, RIGHT_LANE, HOLD_SECONDS) == RIGHT

  def test_a_lane_change_without_openpilot_centers_quickly(self):
    ah = AutoHug()
    run(ah, LEFT_LANE, 10)
    assert run(ah, RIGHT_LANE, 1.5) == CENTER  # no 5 s of hugging the old side
    assert run(ah, RIGHT_LANE, HOLD_SECONDS) == RIGHT

  def test_short_flicker_keeps_hugging(self):
    ah = AutoHug()
    run(ah, LEFT_LANE, 10)
    assert run(ah, MIDDLE_LANE, 0.5) == LEFT
    assert run(ah, LEFT_LANE, 1) == LEFT

  def test_pause_lasts_until_the_lane_changes(self):
    ah = AutoHug()
    run(ah, LEFT_LANE, 10)
    ah.pause()
    assert run(ah, LEFT_LANE, 60) == CENTER
    run(ah, RIGHT_LANE, HOLD_SECONDS + 1)
    assert not ah.paused
    assert run(ah, RIGHT_LANE, 1) == RIGHT

  def test_pause_ends_after_a_lane_change_of_openpilot(self):
    ah = AutoHug()
    run(ah, LEFT_LANE, 10)
    ah.pause()
    run(ah, LEFT_LANE, 3, changing=True)
    run(ah, LEFT_LANE, 0.1)
    assert not ah.paused

  def test_reset(self):
    ah = AutoHug()
    run(ah, LEFT_LANE, 10)
    ah.pause()
    ah.reset()
    assert not ah.paused and ah.lane == UNKNOWN
    assert run(ah, RIGHT_LANE, HOLD_SECONDS + 0.5) == RIGHT
