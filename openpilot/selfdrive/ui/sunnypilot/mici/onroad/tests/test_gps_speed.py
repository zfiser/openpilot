"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("gps_speed_under_test", Path(__file__).resolve().parents[1] / "gps_speed.py")
gps_speed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gps_speed)


class _Obj:
  def __init__(self, **kw):
    self.__dict__.update(kw)


class _SM(dict):
  def __init__(self, services: dict, alive: dict | None = None):
    super().__init__({name: _Obj(hasFix=fix, speed=speed) for name, (fix, speed) in services.items()})
    self.alive = alive if alive is not None else dict.fromkeys(services, True)


class TestGpsSpeed(unittest.TestCase):
  def test_metric_and_imperial(self):
    sm = _SM({"gpsLocationExternal": (True, 25.0)})
    assert gps_speed.gps_speed(sm, True) == 90
    assert gps_speed.gps_speed(sm, False) == 56

  def test_rounds(self):
    assert gps_speed.gps_speed(_SM({"gpsLocationExternal": (True, 13.9)}), True) == 50  # 50.04 km/h
    assert gps_speed.gps_speed(_SM({"gpsLocationExternal": (True, 13.95)}), True) == 50

  def test_standstill_noise_is_zero(self):
    assert gps_speed.gps_speed(_SM({"gpsLocationExternal": (True, 0.3)}), True) == 0
    assert gps_speed.gps_speed(_SM({"gpsLocationExternal": (True, 0.0)}), False) == 0

  def test_no_fix_no_speed(self):
    assert gps_speed.gps_speed(_SM({"gpsLocationExternal": (False, 20.0)}), True) is None

  def test_not_publishing_is_ignored(self):
    sm = _SM({"gpsLocationExternal": (True, 20.0)}, alive={"gpsLocationExternal": False})
    assert gps_speed.gps_speed(sm, True) is None

  def test_falls_back_to_the_other_receiver(self):
    sm = _SM({"gpsLocationExternal": (False, 0.0), "gpsLocation": (True, 10.0)})
    assert gps_speed.gps_speed(sm, True) == 36
    sm = _SM({"gpsLocationExternal": (True, 5.0), "gpsLocation": (True, 10.0)})
    assert gps_speed.gps_speed(sm, True) == 18  # the external one wins

  def test_missing_services_do_not_raise(self):
    assert gps_speed.gps_speed(_Obj(alive={}), True) is None
    assert gps_speed.gps_speed({}, True) is None


if __name__ == "__main__":
  unittest.main()
