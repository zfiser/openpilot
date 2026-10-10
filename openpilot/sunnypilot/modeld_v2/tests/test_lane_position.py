"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.sunnypilot.modeld_v2.lane_position import (CENTER, LEFT, RIGHT, CAR_WIDTH, SIDE_MARGIN, MAX_SHIFT, HOLD_SECONDS,
                                                          LanePosition, target_shift)

DT = 0.05


def settle(lp, mode, left_y=1.8, right_y=-1.8, left_p=0.9, right_p=0.9, seconds=20.0):
  for _ in range(round(seconds / DT)):
    lp.update(mode, left_y, right_y, left_p, right_p, DT)
  return lp.offset


class TestLanePosition:
  def test_target_leaves_the_margin_to_the_line(self):
    # a 3.6 m lane: 1.8 m to each line, half the car is 0.95 m, the margin 0.4 m: about 0.45 m of room to move
    shift = target_shift(LEFT, 1.8, -1.8)
    assert abs(shift - (1.8 - CAR_WIDTH / 2 - SIDE_MARGIN)) < 1e-9
    assert target_shift(RIGHT, 1.8, -1.8) == -shift

  def test_wide_lane_is_limited(self):
    assert target_shift(LEFT, 3.0, -3.0) == MAX_SHIFT
    assert target_shift(RIGHT, 3.0, -3.0) == -MAX_SHIFT

  def test_narrow_lane_does_not_move(self):
    assert target_shift(LEFT, 1.1, -1.1) == 0.0  # 2.2 m, not a lane
    assert abs(target_shift(LEFT, 1.35, -1.35)) < 1e-9  # 2.7 m: no room left once the margin is kept

  def test_center_is_zero(self):
    assert target_shift(CENTER, 1.8, -1.8) == 0.0

  def test_moves_smoothly_not_in_one_step(self):
    lp = LanePosition()
    first = lp.update(LEFT, 1.8, -1.8, 0.9, 0.9, DT)
    assert 0 < first <= 0.12 * DT + 1e-9
    assert abs(settle(lp, LEFT) - 0.45) < 1e-6

  def test_hugging_right_goes_negative_and_back_to_center(self):
    lp = LanePosition()
    assert settle(lp, RIGHT) < -0.4
    assert abs(settle(lp, CENTER)) < 1e-6

  def test_switching_sides_passes_through_the_center_at_the_same_speed(self):
    lp = LanePosition()
    settle(lp, LEFT)
    lp.update(RIGHT, 1.8, -1.8, 0.9, 0.9, DT)
    assert lp.offset < 0.45  # already on its way over, never a jump

  def test_lines_lost_keeps_the_position_then_returns_to_the_center(self):
    lp = LanePosition()
    settle(lp, LEFT)
    held = settle(lp, LEFT, left_p=0.1, seconds=HOLD_SECONDS - 0.5)
    assert abs(held - 0.45) < 1e-6
    assert abs(settle(lp, LEFT, left_p=0.1, seconds=20.0)) < 1e-6

  def test_lines_back_before_the_hold_ends_keep_the_mode(self):
    lp = LanePosition()
    settle(lp, LEFT)
    settle(lp, LEFT, right_p=0.1, seconds=2.0)
    assert abs(settle(lp, LEFT, seconds=2.0) - 0.45) < 1e-6
