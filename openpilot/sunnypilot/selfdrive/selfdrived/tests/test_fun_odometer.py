"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from types import SimpleNamespace

from openpilot.sunnypilot.selfdrive.selfdrived.fun_odometer import FAR, NEAR, FunOdometer, is_fun, next_fun, notice_text, odometer_from

DT = 0.01
V = 25.0  # m/s, 90 km/h: 1 km in 40 s


def drive(fo, start, km, v=V):
  """Drive km kilometres from the reading start (whole km), return the notices with the reading they came at."""
  out = []
  dist = 0.0
  for _ in range(round(km * 1000 / (v * DT))):
    dist += v * DT
    notice = fo.update((start + int(dist / 1000), "km"), v, DT)
    if notice:
      out.append((notice, start + int(dist / 1000), round(dist % 1000)))
  return out


class TestFunNumbers:
  def test_fun(self):
    for n in (60000, 70000, 100000, 66666, 11111, 1111, 222222, 12345, 67890, 65432, 43210, 123456, 98765):
      assert is_fun(n), n
    for n in (60001, 61234, 1234, 12346, 13579, 60006, 0, 999):
      assert not is_fun(n), n

  def test_next_after_60000(self):
    found, n = [], 60000
    for _ in range(4):
      n = next_fun(n)
      found.append(n)
    assert found == [65432, 66666, 67890, 70000]


class TestFunOdometer:
  def test_notices_at_1_km_and_100_m(self):
    fo = FunOdometer()
    notices = drive(fo, 65429, 3.5)  # passes 65 432
    assert [(k, r) for k, r, _ in notices] == [(FAR, 65431), (NEAR, 65431)]
    near_at = notices[1][2]
    assert 895 <= near_at <= 905  # 100 m before the turn to 65 432
    assert fo.target == 66666 and fo.unit == "km"  # after passing 65 432 the next one is ahead

  def test_no_notice_in_the_first_kilometre_after_a_start(self):
    fo = FunOdometer()
    assert drive(fo, 65431, 0.95) == []  # started at 65 431: where in it is not known

  def test_a_jump_gives_no_notice(self):
    fo = FunOdometer()
    fo.update((65000, "km"), V, DT)
    assert fo.update((65431, "km"), V, DT) is None
    assert drive(fo, 65431, 0.95) == []

  def test_invalid_reading(self):
    fo = FunOdometer()
    assert fo.update(None, V, DT) is None
    items = [SimpleNamespace(key="odometer", value=60123.0, unit="km", valid=False)]
    assert odometer_from(items) is None
    items[0].valid = True
    assert odometer_from(items) == (60123, "km")
    assert odometer_from([SimpleNamespace(key="rpm", value=1.0, unit="rpm", valid=True)]) is None

  def test_text(self):
    assert notice_text(70000, "km", FAR) == "70 000 km in 1 km"
    assert notice_text(70000, "km", NEAR) == "70 000 km in 100 m"
    assert notice_text(66666, "mi", NEAR) == "66 666 mi in 0.1 mi"
