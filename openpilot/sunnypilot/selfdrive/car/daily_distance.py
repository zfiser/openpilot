"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime
from collections.abc import Callable

from opendbc.sunnypilot.car.car_data import make_car_data_item
from openpilot.common.time_helpers import system_time_valid

PARAM = "DailyOdometer"


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

  Neither clock may be known for the first minutes after a start (no car clock frame yet, no GPS fix or network).
  Counting starts anyway with the date unknown (None) and takes today's date as soon as a clock is available, so a
  first drive is not lost.
  """

  def __init__(self, params, now: Callable[[], datetime.datetime | None] = device_now, tz: datetime.tzinfo | None = None):
    self._params = params
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
                "last": float(state.get("last", start))}
    except Exception:
      pass
    return None

  def _save(self) -> None:
    self._params.put(PARAM, self._state, block=True)  # rare (a new day or a new odometer unit), wait until it is really stored

  def update(self, items):
    """Returns the 'today' item, or None while there is no valid odometer reading. Call with the brand's items."""
    odometer = next((i for i in items if i.key == "odometer"), None)
    if odometer is None or not odometer.valid:
      return None

    current = self._now()
    today = current.astimezone(self._tz).date().isoformat() if current is not None else None
    state = self._state
    # a new day, a change of unit or an odometer that went backwards all mean the stored start can't be used
    if (state is None or (today is not None and state["date"] not in (None, today)) or
        state["unit"] != odometer.unit or odometer.value < state["start"]):
      self._state = {"date": today, "start": float(odometer.value), "unit": odometer.unit, "last": float(odometer.value)}
      self._save()
    else:
      changed = False
      if today is not None and state["date"] is None:
        state["date"] = today  # counting started before the clock was valid, assume that was today
        changed = True
      if odometer.value != state["last"]:
        state["last"] = float(odometer.value)
        changed = True
      if changed:
        self._save()

    return make_car_data_item("today", "Today", odometer.value - self._state["start"], odometer.unit)
