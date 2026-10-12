"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.sunnypilot.modeld_v2.lane_position import (CENTER, LEFT, RIGHT, CAR_WIDTH, SIDE_MARGIN, MAX_SHIFT, HOLD_SECONDS,
                                                          LanePosition, model_lines_to_left_positive, near_lane_line_position, target_shift)

DT = 0.05


def settle(lp, mode, left_y=1.8, right_y=-1.8, left_p=0.9, right_p=0.9, seconds=20.0):
  for _ in range(round(seconds / DT)):
    lp.update(mode, left_y, right_y, left_p, right_p, DT)
  return lp.offset


class TestLanePosition:
  def test_wanted_shift_when_there_is_room(self):
    # a 3.6 m lane: 1.8 m to each line, half the car is 0.95 m: 0.85 m of room, minus the 0.15 m margin = 0.70 m
    assert abs(target_shift(LEFT, 1.8, -1.8) - 0.70) < 1e-9
    assert abs(target_shift(RIGHT, 1.8, -1.8) + 0.70) < 1e-9
    assert abs(target_shift(LEFT, 1.8, -1.8, left_shift=0.4, right_shift=0.5) - 0.4) < 1e-9
    assert abs(target_shift(RIGHT, 1.8, -1.8, left_shift=0.4, right_shift=0.5) + 0.5) < 1e-9

  def test_never_closer_to_the_line_than_the_margin(self):
    shift = target_shift(LEFT, 1.7, -1.7, left_shift=0.9)  # 3.4 m lane, 0.9 m wanted
    assert abs(shift - (1.7 - CAR_WIDTH / 2 - SIDE_MARGIN)) < 1e-9
    assert shift < 0.9

  def test_wide_lane_is_limited(self):
    assert target_shift(LEFT, 3.0, -3.0, left_shift=2.0) == MAX_SHIFT
    assert target_shift(RIGHT, 3.0, -3.0, right_shift=2.0) == -MAX_SHIFT
    assert target_shift(LEFT, 3.0, -3.0, left_shift=-1.0) == 0.0

  def test_narrow_lane_does_not_move(self):
    assert target_shift(LEFT, 1.1, -1.1) == 0.0  # 2.2 m, not a lane
    assert target_shift(LEFT, 1.45, -1.45) == 0.0  # 2.9 m: too narrow to hug
    assert target_shift(LEFT, 1.6, -1.6) > 0.2  # 3.2 m: wide enough, the room decides

  def test_center_is_zero(self):
    assert target_shift(CENTER, 1.8, -1.8) == 0.0

  def test_moves_smoothly_not_in_one_step(self):
    lp = LanePosition()
    first = lp.update(LEFT, 1.8, -1.8, 0.9, 0.9, DT)
    assert 0 < first <= 0.12 * DT + 1e-9
    lp2 = LanePosition()
    for _ in range(round(30 / DT)):
      lp2.update(RIGHT, 1.8, -1.8, 0.9, 0.9, DT, left_shift=0.2, right_shift=0.3)
    assert abs(lp2.offset + 0.3) < 1e-6  # each side has its own value
    assert abs(settle(lp, LEFT) - 0.70) < 1e-6

  def test_hugging_right_goes_negative_and_back_to_center(self):
    lp = LanePosition()
    assert settle(lp, RIGHT) < -0.65
    assert abs(settle(lp, CENTER)) < 1e-6

  def test_switching_sides_passes_through_the_center_at_the_same_speed(self):
    lp = LanePosition()
    settle(lp, LEFT)
    lp.update(RIGHT, 1.8, -1.8, 0.9, 0.9, DT)
    assert lp.offset < 0.70  # already on its way over, never a jump

  def test_lines_lost_keeps_the_position_then_returns_to_the_center(self):
    lp = LanePosition()
    settle(lp, LEFT)
    held = settle(lp, LEFT, left_p=0.1, seconds=HOLD_SECONDS - 0.5)
    assert abs(held - 0.70) < 1e-6
    assert abs(settle(lp, LEFT, left_p=0.1, seconds=20.0)) < 1e-6

  def test_lines_back_before_the_hold_ends_keep_the_mode(self):
    lp = LanePosition()
    settle(lp, LEFT)
    settle(lp, LEFT, right_p=0.1, seconds=2.0)
    assert abs(settle(lp, LEFT, seconds=2.0) - 0.70) < 1e-6


class _NoSlice:
  """Like a capnp list: indexing and length work, slicing does not."""

  def __init__(self, values):
    self._values = values

  def __len__(self):
    return len(self._values)

  def __getitem__(self, i):
    if not isinstance(i, int):
      raise TypeError("an integer is required")
    return self._values[i]


class TestNearLaneLine:
  def test_reads_a_list_that_cannot_be_sliced(self):
    assert abs(near_lane_line_position(_NoSlice([1.7, 1.8, 1.9, 2.5])) - 1.8) < 1e-9

  def test_fewer_points_than_asked(self):
    assert near_lane_line_position(_NoSlice([1.5, 2.5])) == 2.0

  def test_no_points_is_an_error(self):
    try:
      near_lane_line_position(_NoSlice([]))
    except ValueError:
      return
    raise AssertionError("expected ValueError")


class TestModelFrame:
  def test_real_lane_lines_give_a_shift(self):
    # values from a recorded drive: left line -1.93, right line +1.55 (y positive to the right)
    left, right = model_lines_to_left_positive(-1.93, 1.55)
    assert (left, right) == (1.93, -1.55)
    assert target_shift(LEFT, left, right) > 0.2
    assert target_shift(RIGHT, left, right) < -0.2

  def test_without_the_conversion_the_lane_would_look_negative(self):
    assert target_shift(LEFT, -1.93, 1.55) == 0.0  # what the first version did: never moved
