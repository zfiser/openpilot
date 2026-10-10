"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.sunnypilot.selfdrive.controls.lib.lane_change_smoothing import (LaneChangeSmoother, pace_to_jerk_factor, MAX_LATERAL_JERK,
                                                                               SMOOTH_RELEASE_T, STOCK_PACE)

DT = 0.01
V = 30.0


def clip(prev, new, factor, v=V):
  rate = MAX_LATERAL_JERK * factor / v ** 2
  return min(max(new, prev - rate * DT), prev + rate * DT)


class TestPace:
  def test_stock_is_one(self):
    assert pace_to_jerk_factor(STOCK_PACE) == 1.0
    assert pace_to_jerk_factor(99) == 1.0

  def test_default_pace_matches_starpilot(self):
    assert abs(pace_to_jerk_factor(5) - 0.146) < 0.002  # about 0.73 m/s^3

  def test_smoother_means_a_lower_limit(self):
    factors = [pace_to_jerk_factor(p) for p in range(1, 11)]
    assert factors == sorted(factors) and factors[0] < factors[4] < factors[-1] == 1.0
    assert all(0 < f <= 1.0 for f in factors)

  def test_out_of_range_is_clamped(self):
    assert pace_to_jerk_factor(0) == pace_to_jerk_factor(1)


class TestSmoother:
  def test_no_limit_outside_a_lane_change(self):
    s = LaneChangeSmoother()
    for _ in range(100):
      assert s.update(5, False, V, 0.001, 0.0, DT) == 1.0

  def test_stock_setting_never_limits(self):
    s = LaneChangeSmoother()
    assert s.update(STOCK_PACE, True, V, 0.01, 0.0, DT) == 1.0

  def test_limits_the_whole_lane_change(self):
    s = LaneChangeSmoother()
    factor = s.update(5, True, V, 0.002, 0.0, DT)
    assert abs(factor - pace_to_jerk_factor(5)) < 1e-9
    for _ in range(300):
      assert s.update(5, True, V, 0.002, 0.0005, DT) == factor

  def test_the_limit_is_released_over_two_seconds_after_the_lane_change(self):
    s = LaneChangeSmoother()
    low = s.update(5, True, V, 0.002, 0.0, DT)
    steps = round(SMOOTH_RELEASE_T / DT)
    values = [s.update(5, False, V, 0.0, 0.0, DT) for _ in range(steps + 5)]
    assert values[0] >= low and values[0] < 1.0
    assert values == sorted(values)  # rises, never drops
    halfway = low + (1 - low) * 0.5
    assert halfway - 0.12 < values[steps // 2] <= halfway  # the straight ramp, a little behind it from the 0.2 s rise filter
    assert values[-1] == 1.0
    assert s.update(5, False, V, 0.0, 0.0, DT) == 1.0

  def test_unwinding_against_the_entry_direction_gets_more_authority(self):
    s = LaneChangeSmoother()
    s.update(5, True, V, 0.003, 0.0, DT)  # steers left, remembers the direction
    plain = s.update(5, True, V, 0.003, 0.003, DT)  # no unwinding yet
    boosted = 0.0
    for _ in range(100):
      boosted = s.update(5, True, V, 0.0, 0.003, DT)  # model comes back, the command lags 3e-3
    assert boosted > plain * 3
    assert boosted <= 0.6 + 1e-9

  def test_a_lane_change_is_smooth_and_the_curvature_follows_the_model(self):
    # the model asks for a quick 0.004 1/m step, the commanded curvature may only rise with the limited rate
    s = LaneChangeSmoother()
    cmd, peak_rate, t = 0.0, 0.0, 0.0
    while cmd < 0.003999 and t < 20:
      factor = s.update(5, True, V, 0.004, cmd, DT)
      new = clip(cmd, 0.004, factor)
      peak_rate = max(peak_rate, (new - cmd) / DT)
      cmd, t = new, t + DT
    stock_rate = MAX_LATERAL_JERK / V ** 2
    assert peak_rate < stock_rate * 0.2  # about 15% of the stock rate
    assert 3.0 < t < 12.0  # takes seconds, not the 0.7 s the stock limit allows
