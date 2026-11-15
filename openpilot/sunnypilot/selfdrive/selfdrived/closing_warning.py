"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Closing warning (the ClosingWarning setting): a chime when the car closes in on the car ahead while the driver controls the
speed: ACC off, or ACC on with the gas pressed.

The distance is the car's own radar, the number on the driving screen (carData "lead_distance", DSU_CRUISE on the RAV4: whole
metres at 5 Hz, no relative speed). openpilot's radarState lead is vision only on this car (stock ACC, no radar tracks): its
relative speed is used when its distance matches the radar (the same car), otherwise the slope of a straight line through
the radar distances of the last second. A jump of more than 4 m is the radar switching cars: the line starts over, and a
jump to a nearer car counts as a cut-in. While not looking, the soft chime comes first and the strong one follows (escalation).

- COLLISION, whatever the driver camera says: the gap would be gone in under COLLISION_TTC at the current closing speed.
- DISTRACTED, only while the driver camera reports the driver not looking: the gap would be gone in under DISTRACTED_TTC, or
  the car follows closer than DISTRACTED_GAP while still closing, or a car cuts in closer than CUT_IN_GAP.

Never while braking, with a blinker on (overtaking), with the wheel turned (junctions) or below MIN_SPEED.
"""
from collections import deque

COLLISION, DISTRACTED = "collision", "distracted"

MIN_SPEED = 30 / 3.6  # m/s
MIN_CLOSING = 1.5  # m/s (5.4 km/h), slower closing never warns (the slope of whole metres is noisy by about 1 m/s)
COLLISION_TTC = 2.0  # s
DISTRACTED_TTC = 3.0  # s
DISTRACTED_GAP = 0.5  # s of following distance
CUT_IN_GAP = 1.0  # s, a lead that appears closer than this
CUT_IN_ABSENT = 1.0  # s without a lead before, so a short radar dropout of the same car is no cut-in
MAX_WHEEL = 30.0  # deg, more is a turn
PERSIST = 0.3  # s, the condition must hold this long (a single radar glitch does not chime)
COOLDOWN = 15.0  # s between two chimes of the same kind
RATE_WINDOW = 1.0  # s of distances for the closing speed
RATE_MIN_SPAN = 0.6  # s, fewer than this gives no closing speed yet
JUMP = 4.0  # m between two readings (5 Hz: 20 m/s): the radar switched to another car, the line starts over
VISION_MATCH = 0.25  # the camera's lead is the same car when its distance is within this share of the radar's (at least 5 m)


class LeadRate:
  """The change of the lead distance in m/s (negative while closing), from a straight line through the last second.
  jumped is True in the frame the radar switched to another car."""

  def __init__(self):
    self._samples: deque[tuple[float, float]] = deque()
    self.last: float | None = None  # the previous reading, None after a frame without a lead
    self.jumped = False

  def update(self, t: float, distance: float | None) -> float | None:
    self.jumped = False
    if distance is None:
      self._samples.clear()
      self.last = None
      return None
    if self.last is not None and abs(distance - self.last) > JUMP:
      self._samples.clear()
      self.jumped = True
    self._samples.append((t, distance))
    self.last = distance
    while self._samples and self._samples[0][0] < t - RATE_WINDOW:
      self._samples.popleft()
    if self._samples[-1][0] - self._samples[0][0] < RATE_MIN_SPAN:
      return None
    n = len(self._samples)
    mt = sum(s[0] for s in self._samples) / n
    md = sum(s[1] for s in self._samples) / n
    var = sum((s[0] - mt) ** 2 for s in self._samples)
    if var <= 0:
      return None
    return sum((s[0] - mt) * (s[1] - md) for s in self._samples) / var


class ClosingWarning:
  def __init__(self):
    self._t = 0.0
    self._held = {COLLISION: 0.0, DISTRACTED: 0.0}
    self._last = {COLLISION: -1e9, DISTRACTED: -1e9}
    self._absent = 0.0  # s without a lead
    self._rate = LeadRate()

  def update(self, v_ego: float, distance: float | None, acc_on: bool, gas: bool, brake: bool, blinker: bool, wheel_deg: float,
             distracted: bool, dt: float, vision_d: float | None = None, vision_v_rel: float = 0.0) -> str | None:
    """COLLISION or DISTRACTED in the one frame a chime is due, otherwise None. distance: radar metres, None without a lead.
    vision_d / vision_v_rel: openpilot's (camera) lead, its smoother relative speed is used when it is the same car."""
    self._t += dt
    previous = self._rate.last
    rate = self._rate.update(self._t, distance)
    # a car that appears after a while without one, or the radar switching to a nearer car, is a cut-in
    cut_in = distance is not None and (self._absent >= CUT_IN_ABSENT or (self._rate.jumped and previous is not None and distance < previous))
    self._absent = 0.0 if distance is not None else self._absent + dt
    if distance is not None and vision_d is not None and abs(vision_d - distance) <= max(5.0, VISION_MATCH * distance):
      rate = vision_v_rel  # the same car: the camera's relative speed is smoother than the slope of whole metres

    driver_controls_speed = (not acc_on) or gas
    if not (driver_controls_speed and distance is not None and v_ego >= MIN_SPEED) or brake or blinker or abs(wheel_deg) > MAX_WHEEL:
      self._held = dict.fromkeys(self._held, 0.0)
      return None

    gap = distance / max(v_ego, 1.0)
    closing = -rate if rate is not None else 0.0
    ttc = distance / closing if closing >= MIN_CLOSING else float("inf")
    cut_in_close = cut_in and gap < CUT_IN_GAP
    want = {
      COLLISION: ttc < COLLISION_TTC,
      DISTRACTED: distracted and (ttc < DISTRACTED_TTC or (closing >= MIN_CLOSING and gap < DISTRACTED_GAP)),
    }
    if cut_in_close and distracted and not want[COLLISION] and self._t - self._last[DISTRACTED] >= COOLDOWN:
      self._last[DISTRACTED] = self._t
      return DISTRACTED  # a cut-in is one moment, no persistence
    for kind in (COLLISION, DISTRACTED):
      held = self._held[kind] + dt if want[kind] else 0.0
      self._held[kind] = held
      if held >= PERSIST and self._t - self._last[kind] >= COOLDOWN:
        self._last[kind] = self._t
        if kind == COLLISION:
          self._last[DISTRACTED] = self._t  # the stronger warning covers the softer one
        return kind
    return None


def radar_distance(car_data) -> float | None:
  """The car's radar lead distance from the car data items, None without a lead or a valid reading."""
  for item in car_data:
    if item.key == "lead_distance":
      return float(item.value) if item.valid else None
  return None
