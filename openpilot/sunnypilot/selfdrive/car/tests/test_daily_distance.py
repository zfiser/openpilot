"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime
import os
import tempfile

from opendbc.sunnypilot.car.car_data import make_car_data_item
from openpilot.sunnypilot.selfdrive.car.daily_distance import DailyDistance, PARAM, read_live

DAY = datetime.datetime(2026, 10, 6, 8, 0, tzinfo=datetime.UTC)


class FakeParams:
  def __init__(self, stored=None):
    self.values = {PARAM: stored} if stored is not None else {}
    self.writes = 0
    self.blocking_writes = 0

  def get(self, key):
    return self.values.get(key)

  def put(self, key, value, block=False):
    self.values[key] = dict(value)
    self.writes += 1
    self.blocking_writes += bool(block)


class Clock:
  def __init__(self, when):
    self.when = when

  def __call__(self):
    return self.when


class Mono:
  def __init__(self):
    self.t = 0.0

  def __call__(self):
    return self.t


def odo(value, unit="km", valid=True):
  return [make_car_data_item("odometer", "Odometer", value if valid else None, unit)]


class Env:
  """A device: the stored setting, a clock, a monotonic clock and the RAM file, kept across restarts of the car process."""

  def __init__(self, stored=None, when=DAY):
    self.params = FakeParams(stored)
    self.clock = Clock(when)
    self.dir = tempfile.TemporaryDirectory()
    self.live = os.path.join(self.dir.name, "live.json")

  def start(self):
    self.mono = Mono()
    return DailyDistance(self.params, now=self.clock, tz=datetime.UTC, mono=self.mono, live_path=self.live)

  def drive(self, dd, seconds, odometer, step=1.0):
    item = None
    for _ in range(round(seconds / step)):
      self.mono.t += step
      item = dd.update(odo(odometer))
    return item


class TestDailyDistance:
  def test_first_start_of_the_day_writes_the_start_once(self):
    env = Env()
    dd = env.start()
    assert dd.update(odo(10000)).value == 0
    assert env.params.values[PARAM] == {"date": "2026-10-06", "start": 10000.0, "unit": "km"}
    assert env.drive(dd, 60, 10042).value == 42
    assert env.params.writes == 1 and env.params.blocking_writes == 0

  def test_a_later_start_on_the_same_day_only_reads(self):
    env = Env()
    env.drive(env.start(), 10, 10000)
    dd = env.start()  # car off and on again
    assert dd.update(odo(10030)).value == 30
    assert env.params.writes == 1

  def test_the_next_day_writes_a_new_start(self):
    env = Env()
    env.drive(env.start(), 10, 10000)
    env.clock.when += datetime.timedelta(days=1)
    dd = env.start()
    assert dd.update(odo(10100)).value == 0
    assert env.params.values[PARAM]["date"] == "2026-10-07" and env.params.writes == 2

  def test_a_drive_across_midnight_counts_into_the_day_it_started(self):
    env = Env(when=datetime.datetime(2026, 10, 6, 23, 50, tzinfo=datetime.UTC))
    dd = env.start()
    dd.update(odo(10000))
    env.clock.when += datetime.timedelta(minutes=20)  # 00:10 the next day, still driving
    assert env.drive(dd, 60, 10025).value == 25
    assert env.params.writes == 1 and env.params.values[PARAM]["date"] == "2026-10-06"

  def test_waits_for_the_date_before_deciding(self):
    env = Env(stored={"date": "2026-10-06", "start": 10000.0, "unit": "km"})
    env.clock.when = None
    dd = env.start()
    assert dd.update(odo(10010)) is None and dd.drive_time_item() is None
    assert env.params.writes == 0
    env.clock.when = DAY
    assert dd.update(odo(10010)).value == 10 and env.params.writes == 0

  def test_no_item_without_a_valid_odometer(self):
    env = Env()
    assert env.start().update(odo(0, valid=False)) is None
    assert env.params.writes == 0

  def test_an_old_entry_without_a_date_is_not_today(self):
    env = Env(stored={"date": None, "start": 9000.0, "unit": "km", "last": 9500.0})
    assert env.start().update(odo(10000)).value == 0
    assert env.params.writes == 1

  def test_a_unit_change_starts_over(self):
    env = Env()
    dd = env.start()
    dd.update(odo(10000))
    assert dd.update(odo(6214, unit="mi")).value == 0
    assert env.params.writes == 2

  def test_garbage_in_storage_is_ignored(self):
    env = Env(stored={"nonsense": 1})
    assert env.start().update(odo(10000)).value == 0


class TestDriveTime:
  def test_counts_the_time_and_continues_after_a_restart(self):
    env = Env()
    dd = env.start()
    dd.update(odo(10000))
    env.drive(dd, 125, 10002)
    assert abs(dd.drive_time_item().value - 125) < 1e-6
    dd2 = env.start()
    dd2.update(odo(10002))
    assert 115 <= dd2.drive_time_item().value <= 125  # from the RAM file, written every few seconds
    assert env.params.writes == 1  # the running values never go to the disk

  def test_a_new_day_starts_the_time_at_zero(self):
    env = Env()
    dd = env.start()
    dd.update(odo(10000))
    env.drive(dd, 300, 10005)
    env.clock.when += datetime.timedelta(days=1)
    dd2 = env.start()
    dd2.update(odo(10050))
    assert dd2.drive_time_item().value == 0.0

  def test_without_the_ram_file_the_time_starts_again(self):
    env = Env()
    dd = env.start()
    dd.update(odo(10000))
    env.drive(dd, 60, 10001)
    os.remove(env.live)  # the device was powered off
    dd2 = env.start()
    assert dd2.update(odo(10003)).value == 3  # the distance comes from the stored start
    assert dd2.drive_time_item().value == 0.0

  def test_a_stall_counts_one_second_at_most(self):
    env = Env()
    dd = env.start()
    dd.update(odo(10000))
    env.mono.t += 900.0
    dd.update(odo(10000))
    assert dd.drive_time_item().value == 1.0

  def test_the_ram_file_has_the_values_for_the_page(self):
    env = Env()
    dd = env.start()
    dd.update(odo(10000))
    env.drive(dd, 30, 10004)
    live = read_live(env.live)
    assert live["date"] == "2026-10-06" and live["start"] == 10000.0 and live["last"] == 10004.0 and 15 <= live["seconds"] <= 30
