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
    self.async_writes = 0  # the tenths, not worth waiting for

  def get(self, key):
    return self.values.get(key)

  def put(self, key, value, block=False):
    self.values[key] = dict(value)
    self.writes += 1
    if not block:
      self.async_writes += 1


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
  return DailyDistance(params, now=clock, tz=datetime.UTC), params, clock


def stored(date="2026-10-06", start=10000.0, unit="km", last=None):
  return {"date": date, "start": start, "unit": unit, "last": start if last is None else last}


class TestDailyDistance:
  def test_first_reading_is_the_baseline(self):
    dd, params, _ = make()
    item = dd.update(odo(10000))
    assert item.key == "today" and item.valid and item.value == 0 and item.unit == "km"
    assert params.values[PARAM] == stored()
    assert params.async_writes == 0, "the daily baseline must be written with block=True so it survives a power cut"

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


class Mono:
  def __init__(self):
    self.t = 0.0

  def __call__(self):
    return self.t


def make_moving(stored_state=None):
  params, clock, mono = FakeParams(stored_state), Clock(datetime.datetime(2026, 10, 6, 8, 0, tzinfo=datetime.UTC)), Mono()
  return DailyDistance(params, now=clock, tz=datetime.UTC, mono=mono), params, mono


def drive(dd, mono, odometer, metres, speed=20.0, step=0.1):
  """Drive the given distance at a constant speed, the odometer reading is whatever the caller reports."""
  item = None
  for _ in range(round(metres / (speed * step))):
    mono.t += step
    item = dd.update(odo(odometer), speed)
  return item


class TestDailyDistanceTenths:
  def test_without_speed_it_is_whole_units(self):
    dd, _, _ = make()
    dd.update(odo(10000))
    assert dd.update(odo(10003)).value == 3

  def test_counts_tenths_before_the_first_tick(self):
    dd, _, mono = make_moving()
    dd.update(odo(10000), 0.0)
    value = drive(dd, mono, 10000, 300).value
    assert abs(value - 0.3 * 0.987) < 0.01

  def test_first_tick_anchors_on_the_distance_driven(self):
    dd, _, mono = make_moving()
    dd.update(odo(10000), 0.0)
    drive(dd, mono, 10000, 400)  # the car was 0.6 km into the unit when the day started
    first = dd.update(odo(10001), 20.0).value
    assert abs(first - 0.395) < 0.02  # not 1.0 (odometer minus start): only 400 m were driven

  def test_following_ticks_add_whole_units_and_the_speed_fills_in_between(self):
    dd, _, mono = make_moving()
    dd.update(odo(10000), 0.0)
    drive(dd, mono, 10000, 400)
    dd.update(odo(10001), 20.0)
    drive(dd, mono, 10001, 500)
    value = dd.update(odo(10001), 20.0).value
    assert abs(value - (0.395 + 0.4935)) < 0.03
    drive(dd, mono, 10001, 480)
    after_tick = dd.update(odo(10002), 20.0).value
    assert abs(after_tick - 1.395) < 0.03  # snaps to anchor + exactly one unit

  def test_never_more_than_one_unit_ahead_of_the_anchor(self):
    dd, _, mono = make_moving()
    dd.update(odo(10000), 0.0)
    drive(dd, mono, 10000, 400)
    dd.update(odo(10001), 20.0)
    value = drive(dd, mono, 10001, 3000).value  # the odometer tick never came, the speed integration must not run away
    assert value <= 0.395 + 1.0 + 1e-6

  def test_stored_value_for_the_page_follows_in_tenths(self):
    dd, params, mono = make_moving()
    dd.update(odo(10000), 0.0)
    drive(dd, mono, 10000, 450)
    assert abs(params.values[PARAM]["today"] - 0.4) < 0.11

  def test_restart_keeps_the_anchor(self):
    dd, params, mono = make_moving()
    dd.update(odo(10000), 0.0)
    drive(dd, mono, 10000, 400)
    dd.update(odo(10001), 20.0)
    dd2, _, mono2 = make_moving(params.values[PARAM])
    value = dd2.update(odo(10001), 0.0).value
    assert abs(value - 0.395) < 0.02

  def test_restart_before_any_tick_estimates_the_middle_of_the_unit(self):
    dd, params, mono = make_moving()
    dd.update(odo(10000), 0.0)
    drive(dd, mono, 10000, 200)
    dd2, _, _ = make_moving(params.values[PARAM])
    dd2.update(odo(10000), 0.0)
    assert abs(dd2.update(odo(10001), 20.0).value - 0.5) < 1e-9

  def test_a_stall_is_not_integrated(self):
    dd, _, mono = make_moving()
    dd.update(odo(10000), 0.0)
    mono.t += 600.0  # the process was frozen for ten minutes
    assert dd.update(odo(10000), 30.0).value < 0.031  # one second at most (30 m), not 18 km

  def test_tenths_are_written_once_a_minute_without_waiting(self):
    dd, params, mono = make_moving()
    dd.update(odo(10000), 0.0)
    params.writes = params.async_writes = 0
    drive(dd, mono, 10000, 300)  # 15 s at 20 m/s, 0.3 km: the first tenth is written at once, the rest waits a minute
    assert params.async_writes == 1 and params.writes == 1
    drive(dd, mono, 10000, 500)  # 25 s more, still inside the minute
    assert params.async_writes == 1
    mono.t += 61.0
    dd.update(odo(10000), 20.0)
    assert params.async_writes == 2
    assert 0.3 <= params.values[PARAM]["today"] <= 0.8

  def test_a_tick_is_written_blocking_with_the_exact_tenths(self):
    dd, params, mono = make_moving()
    dd.update(odo(10000), 0.0)
    drive(dd, mono, 10000, 400)
    before = params.async_writes
    dd.update(odo(10001), 20.0)
    assert params.async_writes == before
    assert params.values[PARAM]["today"] == round(params.values[PARAM]["anchor"], 1)
