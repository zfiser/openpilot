"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime

from openpilot.sunnypilot.selfdrive.car.car_clock import CLOCK_ADDRESS, MAX_AGE, CarClock, parse_car_time

# 2026-10-07 16:46:23, the frame seen in the recording
FRAME = bytes.fromhex("0000261007164623")
UTC = datetime.UTC


class Mono:
  def __init__(self):
    self.t = 1000.0

  def __call__(self):
    return self.t


def frames(address=CLOCK_ADDRESS, data=FRAME, bus=0):
  return [(0, [(address, data, bus)])]


class TestParse:
  def test_real_frame(self):
    assert parse_car_time(FRAME) == datetime.datetime(2026, 10, 7, 16, 46, 23, tzinfo=UTC)

  def test_not_bcd(self):
    assert parse_car_time(bytes.fromhex("000026100716462A")) is None
    assert parse_car_time(bytes.fromhex("00002610071646FF")) is None

  def test_impossible_date_or_time(self):
    assert parse_car_time(bytes.fromhex("0000261307164623")) is None  # month 13
    assert parse_car_time(bytes.fromhex("0000261032164623")) is None  # day 32
    assert parse_car_time(bytes.fromhex("0000261007246000")) is None  # hour 24, minute 60
    assert parse_car_time(bytes.fromhex("0000260230000000")) is None  # 30 February

  def test_year_out_of_range(self):
    assert parse_car_time(bytes.fromhex("0000000101000000")) is None  # all zero style placeholder (year 2000)

  def test_short_frame(self):
    assert parse_car_time(FRAME[:6]) is None


class TestCarClock:
  def test_no_frame_no_time(self):
    assert CarClock(mono=Mono()).now() is None

  def test_time_runs_on_between_frames(self):
    mono = Mono()
    clock = CarClock(mono=mono)
    clock.update(frames())
    assert clock.now() == datetime.datetime(2026, 10, 7, 16, 46, 23, tzinfo=UTC)
    mono.t += 2.5
    assert clock.now() == datetime.datetime(2026, 10, 7, 16, 46, 25, 500000, tzinfo=UTC)

  def test_stale_clock_is_not_trusted(self):
    mono = Mono()
    clock = CarClock(mono=mono)
    clock.update(frames())
    mono.t += MAX_AGE + 0.1
    assert clock.now() is None

  def test_other_addresses_and_buses_are_ignored(self):
    clock = CarClock(mono=Mono())
    clock.update(frames(address=0x676))
    clock.update(frames(bus=2))
    assert clock.now() is None

  def test_garbage_frame_keeps_the_previous_time(self):
    mono = Mono()
    clock = CarClock(mono=mono)
    clock.update(frames())
    clock.update(frames(data=bytes.fromhex("00002610FF164623")))
    assert clock.now() == datetime.datetime(2026, 10, 7, 16, 46, 23, tzinfo=UTC)
