"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Smoother lane changes: while the car changes lane, the curvature the model asks for may only change at a lower rate than
the stock lateral jerk limit. Ported from the lane change smoothing of StarPilot (selfdrive/controls/controlsd.py).
"""
import math

MAX_LATERAL_JERK = 5.0  # m/s^3, the stock limit in drive_helpers.py
STOCK_PACE = 10  # the setting value that leaves the stock behaviour, no limit applied
DEFAULT_PACE = 5
LANE_WIDTH = 3.5  # m, used to work out how fast a lane change has to be for the chosen pace
HEADROOM = 1.3
SMOOTH_RELEASE_T = 2.0  # s, after the lane change the limit is released over this time instead of at once

# While the model unwinds the lane change curvature (the end of the maneuver), the limit may rise up to this factor, in
# proportion to how far the command lags behind the model, so the car does not glide past the new lane center.
ARREST_JERK_FLOOR = 0.6
ARREST_PURSUIT_TAU = 0.2  # s
ARREST_GAP_DEADBAND = 5e-5  # 1/m
ARREST_RISE_TAU = 0.2  # s


def pace_to_jerk_factor(pace: int) -> float:
  """1 (smoothest) to 9: the fraction of the stock jerk limit that is allowed during a lane change, from a sine shaped lane
  change of one lane width in 3 s (pace 9) to 8 s (pace 1). 10 is stock and gives 1.0."""
  pace = max(1, min(STOCK_PACE, int(pace)))
  if pace >= STOCK_PACE:
    return 1.0
  target_time = 3.0 + (STOCK_PACE - pace) * 5.0 / 9.0
  required_jerk = math.pi ** 3 * LANE_WIDTH / target_time ** 3
  return min(1.0, required_jerk * HEADROOM / MAX_LATERAL_JERK)


class LaneChangeSmoother:
  def __init__(self):
    self._release = 0.0  # seconds of the taper left
    self._entry_sign = 0.0  # the side the lane change started to steer towards
    self._factor = 1.0

  def update(self, pace: int, in_lane_change: bool, v_ego: float, new_curvature: float, prev_curvature: float, dt: float) -> float:
    """The factor to multiply the stock jerk limit with: 1.0 outside a lane change and with the stock setting."""
    if pace >= STOCK_PACE:
      self._release, self._entry_sign, self._factor = 0.0, 0.0, 1.0
      return 1.0

    set_jerk = pace_to_jerk_factor(pace)
    jerk_factor = 1.0
    if in_lane_change:
      self._release = SMOOTH_RELEASE_T
      if self._entry_sign == 0.0 and abs(new_curvature - prev_curvature) > 2e-4:
        self._entry_sign = math.copysign(1.0, new_curvature - prev_curvature)
    else:
      self._release = max(self._release - dt, 0.0)
      if self._release <= 0.0:
        self._entry_sign = 0.0

    if self._release > 0.0:
      release = 1.0 - self._release / SMOOTH_RELEASE_T  # 0 during the maneuver, 1 when the taper is over
      jerk_factor = set_jerk + (1.0 - set_jerk) * release
      step = new_curvature - prev_curvature
      unwinding = (self._entry_sign != 0.0 and abs(step) > ARREST_GAP_DEADBAND and math.copysign(1.0, step) == -self._entry_sign)
      if unwinding:
        gap = max(abs(step) - ARREST_GAP_DEADBAND, 0.0)
        gap_factor = (gap / ARREST_PURSUIT_TAU) * max(v_ego, 1.0) ** 2 / MAX_LATERAL_JERK
        arrest_cap = ARREST_JERK_FLOOR + (1.0 - ARREST_JERK_FLOOR) * release
        jerk_factor = max(jerk_factor, min(arrest_cap, jerk_factor + gap_factor))
      if jerk_factor > self._factor:
        jerk_factor = self._factor + (1.0 - math.exp(-dt / ARREST_RISE_TAU)) * (jerk_factor - self._factor)  # rises smoothly
    self._factor = jerk_factor
    return jerk_factor
