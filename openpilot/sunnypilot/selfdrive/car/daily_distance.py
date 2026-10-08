"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime
import time
from collections.abc import Callable

from opendbc.sunnypilot.car.car_data import make_car_data_item
from openpilot.common.time_helpers import system_time_valid

PARAM = "DailyOdometer"
UNIT_METRES = {"km": 1000.0, "mi": 1609.344}
SPEED_SCALE = 0.987  # the integrated vEgo came out 1.3% above the odometer in the 2026-10 drives (1013 m per km tick)
MAX_STEP = 1.0  # s, a longer gap between two updates (a stall) is not integrated


def device_now() -> datetime.datetime | None:
  """The device clock as an aware datetime, None while it is not valid (no GPS fix or network yet)."""
  return datetime.datetime.now().astimezone() if system_time_valid() else None


class DailyDistance:
  """Distance driven today from the car's own odometer, kept across power cycles and restarted at local midnight.

  Stored as {"date", "start", "unit", "last"}: the odometer reading of the first drive of the day, the last reading seen
  (so the car data page can still show the numbers with the car off) and the unit. The tile shows the current reading
  minus the start. The date comes from `now`: the car's own clock when it reports one (car_clock.py), else the device
  clock. Either is converted to the time zone of the operating system (UTC if none), so midnight is local to that zone.
  The odometer only counts whole units. With the speed given to update(), the value gets tenths: every odometer tick is an
  exact whole unit, so the distance is anchored at the last tick and the speed is integrated from there. The first tick of
  the day anchors on the integrated distance since the start, as the position inside the first unit is not known. Without
  the speed, or when a restart lost the part since the first reading, the value can be off by one.

  Neither clock may be known for the first minutes after a start (no car clock frame yet, no GPS fix or network).
  Counting starts anyway with the date unknown (None) and takes today's date as soon as a clock is available, so a
  first drive is not lost.
  """

  def __init__(self, params, now: Callable[[], datetime.datetime | None] = device_now, tz: datetime.tzinfo | None = None,
               mono: Callable[[], float] = time.monotonic):
    self._params = params
    self._mono = mono
    self._last_mono: float | None = None
    self._since = 0.0  # distance integrated since the last odometer tick (or since the first reading), in odometer units
    self._since_valid = False  # True when that integration really covers everything since the first reading of the day
    self._now = now  # returns an aware datetime, or None when no valid time is known
    self._tz = tz  # None means the time zone of the operating system
    self._state = self._load()

  def _load(self) -> dict | None:
    try:
      state = self._params.get(PARAM)
      if isinstance(state, dict) and {"date", "start", "unit"} <= state.keys():
        start = float(state["start"])
        date = state["date"]
        loaded = {"date": None if date is None else str(date), "start": start, "unit": str(state["unit"]),
                  "last": float(state.get("last", start))}
        if state.get("anchor") is not None:
          loaded["anchor"] = float(state["anchor"])
        if state.get("today") is not None:
          loaded["today"] = float(state["today"])
        return loaded
    except Exception:
      pass
    return None

  def _save(self) -> None:
    self._params.put(PARAM, self._state, block=True)  # rare (a new day or a new odometer unit), wait until it is really stored

  def _integrate(self, v_ego: float | None, unit: str) -> None:
    now = self._mono()
    if v_ego is not None and self._last_mono is not None and unit in UNIT_METRES:
      self._since += max(v_ego, 0.0) * min(now - self._last_mono, MAX_STEP) * SPEED_SCALE / UNIT_METRES[unit]
    self._last_mono = now

  def update(self, items, v_ego: float | None = None):
    """Returns the 'today' item, or None while there is no valid odometer reading. Call with the brand's items and the
    speed of the car in m/s (without it the value is whole units)."""
    odometer = next((i for i in items if i.key == "odometer"), None)
    if odometer is None or not odometer.valid:
      return None
    self._integrate(v_ego, odometer.unit)

    current = self._now()
    today = current.astimezone(self._tz).date().isoformat() if current is not None else None
    state = self._state
    # a new day, a change of unit or an odometer that went backwards all mean the stored start can't be used
    if (state is None or (today is not None and state["date"] not in (None, today)) or
        state["unit"] != odometer.unit or odometer.value < state["start"]):
      self._state = {"date": today, "start": float(odometer.value), "unit": odometer.unit, "last": float(odometer.value)}
      self._since, self._since_valid = 0.0, True
      self._save()
    else:
      changed = False
      if today is not None and state["date"] is None:
        state["date"] = today  # counting started before the clock was valid, assume that was today
        changed = True
      if odometer.value != state["last"]:
        ticks = odometer.value - state["last"]
        state["last"] = float(odometer.value)
        if v_ego is not None:
          if "anchor" in state:
            state["anchor"] += ticks
          elif self._since_valid and ticks == 1:
            state["anchor"] = min(self._since, 1.0)  # the first tick, everything driven since the first reading
          else:
            state["anchor"] = odometer.value - state["start"] - 0.5  # the part before is not known, take the middle
          self._since, self._since_valid = 0.0, True
        changed = True
      if changed:
        self._save()

    state = self._state
    value = odometer.value - state["start"]
    if v_ego is not None:
      if "anchor" in state:
        value = state["anchor"] + min(self._since, 1.0)
      elif self._since_valid:
        value = min(self._since, 1.0)
      if abs(value - state.get("today", -1.0)) >= 0.1:
        state["today"] = round(value, 1)  # what the page shows while the car is off
        self._save()
    return make_car_data_item("today", "Today", value, odometer.unit)
