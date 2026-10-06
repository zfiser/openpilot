"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime

from opendbc.sunnypilot.car.car_data import make_car_data_item
from openpilot.sunnypilot.selfdrive.car.daily_distance import DailyDistance, PARAM


class FakeParams:
  def __init__(self, stored=None):
    self.values = {PARAM: stored} if stored is not None else {}
    self.writes = 0

  def get(self, key):
    return self.values.get(key)

  def put(self, key, value):
    self.values[key] = value
    self.writes += 1


class Clock:
  def __init__(self, when: datetime.datetime):
    self.when = when

  def __call__(self):
    return self.when


def odo(value, unit="km", valid=True):
  return [make_car_data_item("odometer", "Odometer", value if valid else None, unit)]


def make(stored=None, when=datetime.datetime(2026, 10, 6, 8, 0), time_valid=True):
  params, clock = FakeParams(stored), Clock(when)
  return DailyDistance(params, now=clock, time_valid=lambda: time_valid), params, clock


class TestDailyDistance:
  def test_first_reading_is_the_baseline(self):
    dd, params, _ = make()
    item = dd.update(odo(10000))
    assert item.key == "today" and item.valid and item.value == 0 and item.unit == "km"
    assert params.values[PARAM] == {"date": "2026-10-06", "start": 10000.0, "unit": "km"}

  def test_counts_up_during_the_day(self):
    dd, params, _ = make()
    dd.update(odo(10000))
    assert dd.update(odo(10042)).value == 42
    assert params.writes == 1  # the baseline is only written once

  def test_survives_a_restart_on_the_same_day(self):
    dd, _, _ = make(stored={"date": "2026-10-06", "start": 10000.0, "unit": "km"})
    assert dd.update(odo(10015)).value == 15

  def test_resets_after_midnight(self):
    dd, params, clock = make(stored={"date": "2026-10-06", "start": 10000.0, "unit": "km"})
    clock.when = datetime.datetime(2026, 10, 7, 0, 0, 1)
    assert dd.update(odo(10090)).value == 0
    assert params.values[PARAM]["date"] == "2026-10-07" and params.values[PARAM]["start"] == 10090.0
    assert dd.update(odo(10095)).value == 5

  def test_unit_change_restarts(self):
    dd, _, _ = make(stored={"date": "2026-10-06", "start": 10000.0, "unit": "km"})
    item = dd.update(odo(6214, unit="mi"))
    assert item.value == 0 and item.unit == "mi"

  def test_odometer_going_backwards_restarts(self):
    dd, _, _ = make(stored={"date": "2026-10-06", "start": 10000.0, "unit": "km"})
    assert dd.update(odo(500)).value == 0

  def test_no_item_without_a_valid_odometer(self):
    dd, params, _ = make()
    assert dd.update(odo(0, valid=False)) is None
    assert dd.update([]) is None
    assert params.writes == 0

  def test_no_item_and_no_write_while_the_clock_is_not_valid(self):
    dd, params, _ = make(time_valid=False)
    assert dd.update(odo(10000)) is None
    assert params.writes == 0

  def test_garbage_in_storage_is_ignored(self):
    for stored in ("nonsense", {"date": "2026-10-06"}, {"start": 1}, 5):
      dd, _, _ = make(stored=stored)
      assert dd.update(odo(10000)).value == 0
