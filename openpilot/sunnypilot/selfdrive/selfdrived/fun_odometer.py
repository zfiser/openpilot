"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

A chime before the odometer shows a "fun" number (60 000, 66 666, 12 345 ...): 1 km before it and again 100 m before it.

The car reports the odometer in whole kilometres (or miles). The first notice comes when the reading turns to one below the
fun number; the distance from then on is counted from the car's speed, so the second notice comes 0.9 km later. After a
start, or a jump of the reading, the position within the kilometre is not known and that kilometre gets no notice.
"""

FAR, NEAR = "far", "near"
NEAR_AT = 0.9  # units after the reading turned to target - 1: 100 m (or 0.1 mi) before the fun number
M_PER_UNIT = {"km": 1000.0, "mi": 1609.344}
SEARCH = 100_000  # a multiple of 10 000 is always within this


UP, DOWN = "1234567890", "9876543210"


def is_fun(n: int) -> bool:
  """Round ten thousands, the same digit everywhere (from 4 digits), and runs up or down (from 5 digits: 12345, 67890,
  65432, 43210, 123456)."""
  if n <= 0:
    return False
  if n % 10_000 == 0:
    return True
  digits = str(n)
  if len(digits) >= 4 and len(set(digits)) == 1:
    return True
  return len(digits) >= 5 and (digits in UP or digits in DOWN)


def next_fun(n: int) -> int:
  """The first fun number above n."""
  for value in range(int(n) + 1, int(n) + SEARCH + 1):
    if is_fun(value):
      return value
  return int(n) + SEARCH


def odometer_from(car_data) -> tuple[int, str] | None:
  """(whole units, unit) from the car data items, None without a valid reading."""
  for item in car_data:
    if item.key == "odometer":
      if not item.valid or item.unit not in M_PER_UNIT:
        return None
      return int(item.value), item.unit
  return None


class FunOdometer:
  """update() returns FAR or NEAR in the one frame a notice is due, otherwise None. target and unit name the fun number."""

  def __init__(self):
    self._reading: int | None = None
    self._since_turn: float | None = None  # units driven since the reading turned, None while unknown
    self._near_done = False
    self.target = 0
    self.unit = "km"

  def update(self, odometer: tuple[int, str] | None, v_ego: float, dt: float) -> str | None:
    if odometer is None:
      return None
    reading, unit = odometer
    if self._reading is None or unit != self.unit:
      self._reading, self.unit, self._since_turn = reading, unit, None  # where in this kilometre is not known
      return None
    if reading != self._reading:
      turned_by_one = reading == self._reading + 1
      self._reading = reading
      self._since_turn = 0.0 if turned_by_one else None
      self._near_done = False
      self.target = next_fun(reading)
      return FAR if turned_by_one and self.target == reading + 1 else None
    if self._since_turn is None:
      return None
    self._since_turn += max(v_ego, 0.0) * dt / M_PER_UNIT[unit]
    if not self._near_done and self.target == reading + 1 and self._since_turn >= NEAR_AT:
      self._near_done = True
      return NEAR
    return None


def notice_text(target: int, unit: str, kind: str) -> str:
  shown = f"{target:,}".replace(",", " ")
  left = ("1 km" if unit == "km" else "1 mi") if kind == FAR else ("100 m" if unit == "km" else "0.1 mi")
  return f"{shown} {unit} in {left}"


FUN = FunOdometer()  # the one used by selfdrived; the alert text reads its target
