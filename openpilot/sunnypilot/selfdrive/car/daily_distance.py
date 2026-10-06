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


class DailyDistance:
  """Distance driven today from the car's own odometer, kept across power cycles and restarted at local midnight.

  The odometer reading of the first drive of the day is stored (as {"date", "start", "unit"}), the tile shows the
  current reading minus that. The date comes from the device clock, so midnight is local to whatever time zone the
  operating system is set to (UTC if none). The odometer only counts whole units, so the value can be off by one.
  """

  def __init__(self, params, now: Callable[[], datetime.datetime] = datetime.datetime.now,
               time_valid: Callable[[], bool] = system_time_valid):
    self._params = params
    self._now = now
    self._time_valid = time_valid
    self._state = self._load()

  def _load(self) -> dict | None:
    try:
      state = self._params.get(PARAM)
      if isinstance(state, dict) and {"date", "start", "unit"} <= state.keys():
        return {"date": str(state["date"]), "start": float(state["start"]), "unit": str(state["unit"])}
    except Exception:
      pass
    return None

  def update(self, items):
    """Returns the 'today' item, or None while the odometer or the clock can't be trusted. Call with the brand's items."""
    odometer = next((i for i in items if i.key == "odometer"), None)
    if odometer is None or not odometer.valid or not self._time_valid():
      return None

    today = self._now().date().isoformat()
    state = self._state
    # a new day, a change of unit or an odometer that went backwards all mean the stored start can't be used
    if state is None or state["date"] != today or state["unit"] != odometer.unit or odometer.value < state["start"]:
      state = {"date": today, "start": float(odometer.value), "unit": odometer.unit}
      self._state = state
      self._params.put(PARAM, state, block=True)  # once a day, wait until it is really stored

    return make_car_data_item("today", "Today", odometer.value - state["start"], odometer.unit)
