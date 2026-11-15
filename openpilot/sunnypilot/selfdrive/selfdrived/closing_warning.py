"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Closing warning (the ClosingWarning setting): a chime when the car closes in on the car ahead (radar lead) while the driver
controls the speed: ACC off, or ACC on with the gas pressed.

- COLLISION, whatever the driver camera says: the gap would be gone in under COLLISION_TTC at the current closing speed.
- DISTRACTED, only while the driver camera reports the driver not looking: the gap would be gone in under DISTRACTED_TTC, or
  the car follows closer than DISTRACTED_GAP while still closing, or a car cuts in closer than CUT_IN_GAP.

Never while braking, with a blinker on (overtaking), with the wheel turned (junctions) or below MIN_SPEED. Tuned on 8.1 h of
drives (6-15 Nov 2026): the collision rule fired twice, an overtake and a junction turn, both removed by those exceptions;
the distracted rules ~0.3 times per hour.
"""
COLLISION, DISTRACTED = "collision", "distracted"

MIN_SPEED = 30 / 3.6  # m/s
MIN_CLOSING = 1.0  # m/s (3.6 km/h), slower closing never warns
COLLISION_TTC = 2.0  # s
DISTRACTED_TTC = 3.0  # s
DISTRACTED_GAP = 0.5  # s of following distance
CUT_IN_GAP = 1.0  # s, a lead that appears closer than this
MAX_WHEEL = 30.0  # deg, more is a turn
PERSIST = 0.3  # s, the condition must hold this long (a single radar glitch does not chime)
COOLDOWN = 15.0  # s between two chimes of the same kind


class ClosingWarning:
  def __init__(self):
    self._t = 0.0
    self._held = {COLLISION: 0.0, DISTRACTED: 0.0}
    self._last = {COLLISION: -1e9, DISTRACTED: -1e9}
    self._lead_before = False

  def update(self, v_ego: float, lead_present: bool, d_rel: float, v_rel: float, acc_on: bool, gas: bool, brake: bool,
             blinker: bool, wheel_deg: float, distracted: bool, dt: float) -> str | None:
    """COLLISION or DISTRACTED in the one frame a chime is due, otherwise None. v_rel is negative while closing."""
    self._t += dt
    cut_in = lead_present and not self._lead_before
    self._lead_before = lead_present

    driver_controls_speed = (not acc_on) or gas
    if not (driver_controls_speed and lead_present and v_ego >= MIN_SPEED) or brake or blinker or abs(wheel_deg) > MAX_WHEEL:
      self._held = dict.fromkeys(self._held, 0.0)
      return None

    closing = -v_rel
    ttc = d_rel / closing if closing > 1e-3 else float("inf")
    gap = d_rel / max(v_ego, 1.0)
    want = {
      COLLISION: closing >= MIN_CLOSING and ttc < COLLISION_TTC,
      DISTRACTED: distracted and ((closing >= MIN_CLOSING and (ttc < DISTRACTED_TTC or gap < DISTRACTED_GAP)) or (cut_in and gap < CUT_IN_GAP)),
    }
    for kind in (COLLISION, DISTRACTED):
      held = self._held[kind] + dt if want[kind] else 0.0
      self._held[kind] = held
      # a cut-in is one frame, no persistence; when the collision rule applies too, its stronger warning follows instead
      instant = kind == DISTRACTED and cut_in and gap < CUT_IN_GAP and distracted and not want[COLLISION]
      if (held >= PERSIST or instant) and self._t - self._last[kind] >= COOLDOWN:
        self._last[kind] = self._t
        if kind == COLLISION:
          self._last[DISTRACTED] = self._t  # the stronger warning covers the softer one
        return kind
    return None
