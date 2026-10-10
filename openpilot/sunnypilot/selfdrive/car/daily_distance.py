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
MAX_STEP = 1.0  # s, a longer gap between two updates (a stall) counts as one second
TIME_SAVE_INTERVAL = 60.0  # s, how often the time is stored, not worth waiting for


def device_now() -> datetime.datetime | None:
  """The device clock as an aware datetime, None while it is not valid (no GPS fix or network yet)."""
  return datetime.datetime.now().astimezone() if system_time_valid() else None


class DailyDistance:
  """Distance driven today from the car's own odometer, kept across power cycles and restarted at local midnight.

  Stored as {"date", "start", "unit", "last"}: the odometer reading of the first drive of the day, the last reading seen
  (so the car data page can still show the numbers with the car off) and the unit. The tile shows the current reading
  minus the start. The date comes from `now`: the car's own clock when it reports one (car_clock.py), else the device
  clock. Either is converted to the time zone of the operating system (UTC if none), so midnight is local to that zone.
  The odometer only counts whole units, so the value can be off by one.

  The time the car was on today is kept in the same entry ("seconds", reset together with the start): every update with a
  valid odometer adds the time since the last one, so it counts the time the car process runs with the car on. It is stored
  once a minute and with every odometer change, so a power cut loses at most a minute.

  Neither clock may be known for the first minutes after a start (no car clock frame yet, no GPS fix or network).
  Counting starts anyway with the date unknown (None) and takes today's date as soon as a clock is available, so a
  first drive is not lost.
  """

  def __init__(self, params, now: Callable[[], datetime.datetime | None] = device_now, tz: datetime.tzinfo | None = None,
               mono: Callable[[], float] = time.monotonic):
    self._params = params
    self._mono = mono
    self._last_mono: float | None = None
    self._last_time_save = float("-inf")
    self._now = now  # returns an aware datetime, or None when no valid time is known
    self._tz = tz  # None means the time zone of the operating system
    self._state = self._load()

  def _load(self) -> dict | None:
    try:
      state = self._params.get(PARAM)
      if isinstance(state, dict) and {"date", "start", "unit"} <= state.keys():
        start = float(state["start"])
        date = state["date"]
        return {"date": None if date is None else str(date), "start": start, "unit": str(state["unit"]),
                "last": float(state.get("last", start)), "seconds": max(float(state.get("seconds", 0.0)), 0.0)}
    except Exception:
      pass
    return None

  def _save(self, block: bool = True) -> None:
    # a new day, a new odometer unit or an odometer change are rare, wait until they are really stored
    self._params.put(PARAM, self._state, block=block)

  def update(self, items):
    """Returns the 'today' item, or None while there is no valid odometer reading. Call with the brand's items."""
    odometer = next((i for i in items if i.key == "odometer"), None)
    if odometer is None or not odometer.valid:
      return None

    now_mono = self._mono()
    step = min(now_mono - self._last_mono, MAX_STEP) if self._last_mono is not None else 0.0
    self._last_mono = now_mono

    current = self._now()
    today = current.astimezone(self._tz).date().isoformat() if current is not None else None
    state = self._state
    # a new day, a change of unit or an odometer that went backwards all mean the stored start can't be used
    if (state is None or (today is not None and state["date"] not in (None, today)) or
        state["unit"] != odometer.unit or odometer.value < state["start"]):
      self._state = {"date": today, "start": float(odometer.value), "unit": odometer.unit, "last": float(odometer.value),
                     "seconds": 0.0}
      self._last_time_save = now_mono
      self._save()
    else:
      changed = False
      if today is not None and state["date"] is None:
        state["date"] = today  # counting started before the clock was valid, assume that was today
        changed = True
      if odometer.value != state["last"]:
        state["last"] = float(odometer.value)
        changed = True
      state["seconds"] = state.get("seconds", 0.0) + step
      if changed:
        self._last_time_save = now_mono
        self._save()
      elif now_mono - self._last_time_save >= TIME_SAVE_INTERVAL:
        self._last_time_save = now_mono
        self._save(block=False)

    return make_car_data_item("today", "Today", odometer.value - self._state["start"], odometer.unit)

  def drive_time_item(self):
    """Seconds the car was on today as a car data item, None before the first odometer reading. Call after update()."""
    if self._state is None:
      return None
    return make_car_data_item("drive_time", "Time", self._state.get("seconds", 0.0), "s")
