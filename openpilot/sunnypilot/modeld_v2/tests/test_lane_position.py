"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.sunnypilot.modeld_v2.lane_position import (CENTER, LEFT, RIGHT, CAR_WIDTH, SIDE_MARGIN, MAX_SHIFT, HOLD_SECONDS,
                                                          LanePosition, model_lines_to_left_positive, near_lane_line_position, target_shift,
                                                          side_of, level_of, wanted_shifts, migrate_hug_params, DEFAULT_SHIFT)

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


class FakeParams:
  def __init__(self, values):
    self.values = dict(values)

  def get(self, key, return_default=False):
    return self.values.get(key)

  def put(self, key, value):
    self.values[key] = value


class TestLevels:
  def test_side_and_level(self):
    assert [side_of(m) for m in (-2, -1, 0, 1, 2)] == [RIGHT, RIGHT, CENTER, LEFT, LEFT]
    assert [level_of(m) for m in (-2, -1, 0, 1, 2)] == [2, 1, 0, 1, 2]
    assert level_of(5) == 2  # anything above 2 counts as level 2

  def test_each_mode_uses_its_own_distance(self):
    cm = {"HugLeft1Cm": 30, "HugLeft2Cm": 80, "HugRight1Cm": 40, "HugRight2Cm": 60}
    assert wanted_shifts(1, cm.get) == (0.3, 0.3)
    assert wanted_shifts(2, cm.get) == (0.8, 0.8)
    assert wanted_shifts(-1, cm.get) == (0.4, 0.4)
    assert wanted_shifts(-2, cm.get) == (0.6, 0.6)
    assert wanted_shifts(0, cm.get) == (DEFAULT_SHIFT, DEFAULT_SHIFT)

  def test_a_level_2_mode_moves_further_than_level_1(self):
    cm = {"HugLeft1Cm": 30, "HugLeft2Cm": 70}
    lp1, lp2 = LanePosition(), LanePosition()
    for _ in range(round(30 / DT)):
      lp1.update(side_of(1), 1.8, -1.8, 0.9, 0.9, DT, *wanted_shifts(1, cm.get))
      lp2.update(side_of(2), 1.8, -1.8, 0.9, 0.9, DT, *wanted_shifts(2, cm.get))
    assert abs(lp1.offset - 0.3) < 1e-6 and abs(lp2.offset - 0.7) < 1e-6

  def test_old_settings_become_level_2(self):
    p = FakeParams({"HugLeftCm": 50, "HugRightCm": 80})
    migrate_hug_params(p)
    assert p.values["HugLeft2Cm"] == 50 and p.values["HugRight2Cm"] == 80

  def test_migration_keeps_level_2_when_already_set(self):
    p = FakeParams({"HugLeftCm": 50, "HugLeft2Cm": 90})
    migrate_hug_params(p)
    assert p.values["HugLeft2Cm"] == 90 and "HugRight2Cm" not in p.values
