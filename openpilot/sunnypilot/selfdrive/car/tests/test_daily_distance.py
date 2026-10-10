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
    self.async_writes = 0  # the running time, not worth waiting for

  def get(self, key):
    return self.values.get(key)

  def put(self, key, value, block=False):
    self.values[key] = dict(value)
    self.writes += 1
    if not block:
      self.async_writes += 1


class Mono:
  def __init__(self):
    self.t = 0.0

  def __call__(self):
    return self.t


class Clock:
  """A time source that can be unknown (None), like the car clock or the device clock before it is set."""

  def __init__(self, when: datetime.datetime):
    self.when = when
    self.valid = True

  def __call__(self):
    return self.when if self.valid else None


def odo(value, unit="km", valid=True):
  return [make_car_data_item("odometer", "Odometer", value if valid else None, unit)]


def make(stored=None, when=datetime.datetime(2026, 10, 6, 8, 0, tzinfo=datetime.UTC)):
  params, clock = FakeParams(stored), Clock(when)
  dd = DailyDistance(params, now=clock, tz=datetime.UTC, mono=Mono())
  return dd, params, clock


def stored(date="2026-10-06", start=10000.0, unit="km", last=None, seconds=0.0):
  return {"date": date, "start": start, "unit": unit, "last": start if last is None else last, "seconds": seconds}


class TestDailyDistance:
  def test_first_reading_is_the_baseline(self):
    dd, params, _ = make()
    item = dd.update(odo(10000))
    assert item.key == "today" and item.valid and item.value == 0 and item.unit == "km"
    assert params.values[PARAM] == stored()

  def test_counts_up_during_the_day_and_keeps_the_last_reading(self):
    dd, params, _ = make()
    dd.update(odo(10000))
    assert dd.update(odo(10042)).value == 42
    assert params.values[PARAM] == stored(last=10042.0)
    assert params.writes == 2  # the baseline and the one new reading, not one write per frame
    dd.update(odo(10042))
    assert params.writes == 2

  def test_survives_a_restart_on_the_same_day(self):
    dd, _, _ = make(stored=stored(last=10010.0))
    assert dd.update(odo(10015)).value == 15

  def test_old_stored_format_without_last_still_loads(self):
    dd, _, _ = make(stored={"date": "2026-10-06", "start": 10000.0, "unit": "km"})
    assert dd.update(odo(10015)).value == 15

  def test_resets_after_midnight(self):
    dd, params, clock = make(stored=stored(last=10080.0))
    clock.when = datetime.datetime(2026, 10, 7, 0, 0, 1, tzinfo=datetime.UTC)
    assert dd.update(odo(10090)).value == 0
    assert params.values[PARAM] == stored(date="2026-10-07", start=10090.0)
    assert dd.update(odo(10095)).value == 5

  def test_unit_change_restarts(self):
    dd, _, _ = make(stored=stored())
    item = dd.update(odo(6214, unit="mi"))
    assert item.value == 0 and item.unit == "mi"

  def test_odometer_going_backwards_restarts(self):
    dd, _, _ = make(stored=stored())
    assert dd.update(odo(500)).value == 0

  def test_no_item_without_a_valid_odometer(self):
    dd, params, _ = make()
    assert dd.update(odo(0, valid=False)) is None
    assert dd.update([]) is None
    assert params.writes == 0

  def test_counts_from_the_first_reading_even_before_the_clock_is_valid(self):
    # the first drive after a fresh start: no GPS time or network yet
    dd, params, clock = make()
    clock.valid = False
    assert dd.update(odo(10000)).value == 0
    assert params.values[PARAM]["date"] is None
    assert dd.update(odo(10007)).value == 7

  def test_takes_todays_date_once_the_clock_is_valid_and_keeps_the_count(self):
    dd, params, clock = make()
    clock.valid = False
    dd.update(odo(10000))
    dd.update(odo(10007))
    clock.valid = True
    assert dd.update(odo(10009)).value == 9
    assert params.values[PARAM] == stored(last=10009.0)

  def test_invalid_clock_does_not_reset_a_known_day(self):
    dd, _, clock = make(stored=stored(last=10020.0))
    clock.valid = False
    assert dd.update(odo(10030)).value == 30

  def test_the_date_follows_the_time_zone(self):
    # 23:30 UTC is already the next day two hours east
    when = datetime.datetime(2026, 10, 6, 23, 30, tzinfo=datetime.UTC)
    params = FakeParams()
    dd = DailyDistance(params, now=lambda: when, tz=datetime.timezone(datetime.timedelta(hours=2)))
    dd.update(odo(10000))
    assert params.values[PARAM]["date"] == "2026-10-07"

  def test_garbage_in_storage_is_ignored(self):
    for bad in ("nonsense", {"date": "2026-10-06"}, {"start": 1}, 5):
      dd, _, _ = make(stored=bad)
      assert dd.update(odo(10000)).value == 0


def make_timed(stored_state=None):
  params, clock, mono = FakeParams(stored_state), Clock(datetime.datetime(2026, 10, 6, 8, 0, tzinfo=datetime.UTC)), Mono()
  return DailyDistance(params, now=clock, tz=datetime.UTC, mono=mono), params, clock, mono


def run(dd, mono, seconds, odometer=10000, step=1.0):
  for _ in range(round(seconds / step)):
    mono.t += step
    dd.update(odo(odometer))


class TestDriveTime:
  def test_no_item_before_the_first_reading(self):
    dd, _, _, _ = make_timed()
    assert dd.drive_time_item() is None
    dd.update(odo(10000, valid=False))
    assert dd.drive_time_item() is None

  def test_counts_the_time_the_car_is_on(self):
    dd, _, _, mono = make_timed()
    dd.update(odo(10000))
    run(dd, mono, 125)
    item = dd.drive_time_item()
    assert item.key == "drive_time" and item.unit == "s" and item.valid and abs(item.value - 125) < 1e-6

  def test_a_stall_counts_one_second_at_most(self):
    dd, _, _, mono = make_timed()
    dd.update(odo(10000))
    mono.t += 900.0
    dd.update(odo(10000))
    assert dd.drive_time_item().value == 1.0

  def test_resets_with_the_new_day(self):
    dd, _, clock, mono = make_timed()
    dd.update(odo(10000))
    run(dd, mono, 300)
    clock.when += datetime.timedelta(days=1)
    dd.update(odo(10050))
    assert dd.drive_time_item().value == 0.0

  def test_the_time_survives_a_restart_on_the_same_day(self):
    dd, params, _, mono = make_timed()
    dd.update(odo(10000))
    run(dd, mono, 130)  # stored at the second 60 and 120
    dd2, _, _, mono2 = make_timed(params.values[PARAM])
    dd2.update(odo(10000))
    assert 119 <= dd2.drive_time_item().value <= 121
    run(dd2, mono2, 30)
    assert 149 <= dd2.drive_time_item().value <= 151

  def test_written_once_a_minute_without_waiting(self):
    dd, params, _, mono = make_timed()
    dd.update(odo(10000))
    params.writes = params.async_writes = 0
    run(dd, mono, 59)
    assert params.writes == 0
    run(dd, mono, 2)
    assert params.async_writes == 1 and params.writes == 1
    run(dd, mono, 50)
    assert params.async_writes == 1

  def test_an_odometer_change_is_written_blocking_with_the_time(self):
    dd, params, _, mono = make_timed()
    dd.update(odo(10000))
    run(dd, mono, 20)
    params.writes = params.async_writes = 0
    dd.update(odo(10001))
    assert params.writes == 1 and params.async_writes == 0
    assert abs(params.values[PARAM]["seconds"] - 20) < 1e-6
