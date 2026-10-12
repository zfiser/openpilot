"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime
import json
import os
import time
from collections.abc import Callable

from opendbc.sunnypilot.car.car_data import make_car_data_item
from openpilot.common.time_helpers import system_time_valid

PARAM = "DailyOdometer"
LIVE_PATH = "/dev/shm/daily_odometer_live.json"  # RAM, not the disk: lost when the device powers off
LIVE_INTERVAL = 10.0  # s, how often the running values go to the RAM file
MAX_STEP = 1.0  # s, a longer gap between two updates (a stall) counts as one second


def device_now() -> datetime.datetime | None:
  """The device clock as an aware datetime, None while it is not valid (no GPS fix or network yet)."""
  return datetime.datetime.now().astimezone() if system_time_valid() else None


def read_live(path: str = LIVE_PATH) -> dict | None:
  """The running values of the current day from the RAM file, None when there are none."""
  try:
    with open(path) as f:
      live = json.load(f)
    return live if isinstance(live, dict) else None
  except Exception:
    return None


class DailyDistance:
  """Distance driven today: the current odometer reading minus the reading of the first drive of the day.

  At the first odometer reading after the start (as soon as the date is known): when the stored entry is from today, its
  start reading is used, nothing is written. Otherwise the current reading becomes today's start and is written, the only
  write to the disk of the day. The date is then fixed for the rest of the drive: a drive across midnight keeps counting
  into the day it started on. The date comes from `now`: the car's own clock when it reports one (car_clock.py), else the
  device clock, in the time zone of the operating system (UTC if none). The odometer counts whole units only.

  The running values (last reading and the time the car was on today) live in memory and every few seconds in a small file
  in RAM, so the car data page can show them with the car off and the time continues on the next drive. They are not
  written to the disk: after the device powers off the time starts again at 0, the distance does not depend on them.
  """

  def __init__(self, params, now: Callable[[], datetime.datetime | None] = device_now, tz: datetime.tzinfo | None = None,
               mono: Callable[[], float] = time.monotonic, live_path: str = LIVE_PATH):
    self._params = params
    self._now = now  # returns an aware datetime, or None when no valid time is known
    self._tz = tz  # None means the time zone of the operating system
    self._mono = mono
    self._live_path = live_path
    self._stored = self._load()
    self._baseline: dict | None = None  # decided once per start
    self._seconds = 0.0
    self._last_mono: float | None = None
    self._last_live_write = float("-inf")

  def _load(self) -> dict | None:
    try:
      state = self._params.get(PARAM)
      if isinstance(state, dict) and {"date", "start", "unit"} <= state.keys() and state["date"] is not None:
        return {"date": str(state["date"]), "start": float(state["start"]), "unit": str(state["unit"])}
    except Exception:
      pass
    return None

  def _new_baseline(self, date: str, odometer) -> None:
    self._baseline = {"date": date, "start": float(odometer.value), "unit": odometer.unit}
    self._seconds = 0.0
    self._params.put(PARAM, self._baseline, block=False)  # in the car loop: never wait for the disk

  def _write_live(self, last: float) -> None:
    live = {**self._baseline, "last": last, "seconds": self._seconds}
    try:
      tmp = self._live_path + ".tmp"
      with open(tmp, "w") as f:
        json.dump(live, f)
      os.replace(tmp, self._live_path)  # the file is complete or not there
    except Exception:
      pass

  def update(self, items):
    """Returns the 'today' item, None while there is no valid odometer reading or the date is not known yet."""
    odometer = next((i for i in items if i.key == "odometer"), None)
    if odometer is None or not odometer.valid:
      return None

    now_mono = self._mono()
    step = min(now_mono - self._last_mono, MAX_STEP) if self._last_mono is not None else 0.0
    self._last_mono = now_mono

    if self._baseline is None:
      current = self._now()
      if current is None:
        return None  # wait for a clock, the day decides whether the stored start applies
      today = current.astimezone(self._tz).date().isoformat()
      stored = self._stored
      if stored is not None and stored["date"] == today and stored["unit"] == odometer.unit and odometer.value >= stored["start"]:
        self._baseline = stored
        live = read_live(self._live_path)
        if live is not None and live.get("date") == today and live.get("start") == stored["start"]:
          self._seconds = max(float(live.get("seconds", 0.0)), 0.0)  # the time continues from the last drive today
      else:
        self._new_baseline(today, odometer)  # the one write of the day
      step = 0.0
    elif odometer.unit != self._baseline["unit"] or odometer.value < self._baseline["start"]:
      self._new_baseline(self._baseline["date"], odometer)  # the units were switched on the dash, the start can't be used

    self._seconds += step
    if now_mono - self._last_live_write >= LIVE_INTERVAL:
      self._last_live_write = now_mono
      self._write_live(float(odometer.value))

    return make_car_data_item("today", "Today", odometer.value - self._baseline["start"], odometer.unit)

  def drive_time_item(self):
    """Seconds the car was on today as a car data item, None before the day is decided. Call after update()."""
    if self._baseline is None:
      return None
    return make_car_data_item("drive_time", "Time", self._seconds, "s")
