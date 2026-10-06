"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("rpm_under_test", Path(__file__).resolve().parents[1] / "rpm.py")
rpm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpm)


class _Obj:
  def __init__(self, **kw):
    self.__dict__.update(kw)


class _SM(dict):
  def __init__(self, items, frame: int = 1):
    super().__init__({"carStateSP": _Obj(carData=items)})
    self.recv_frame = {"carStateSP": frame}


def item(key, value, valid=True):
  return _Obj(key=key, value=value, valid=valid)


class TestRpm(unittest.TestCase):
  def test_find(self):
    assert rpm.find_rpm(_SM([item("odometer", 5.0), item("rpm", 1850.0)]), 0) == 1850.0

  def test_find_invalid_or_missing(self):
    assert rpm.find_rpm(_SM([item("rpm", 1850.0, valid=False)]), 0) is None
    assert rpm.find_rpm(_SM([item("odometer", 5.0)]), 0) is None
    assert rpm.find_rpm(_SM([]), 0) is None

  def test_find_stale_message(self):
    assert rpm.find_rpm(_SM([item("rpm", 1850.0)], frame=3), started_frame=10) is None

  def test_find_missing_service(self):
    assert rpm.find_rpm(_Obj(recv_frame={}), 0) is None

  def test_format(self):
    assert rpm.format_rpm(1850.4) == "1,850"
    assert rpm.format_rpm(1854.0) == "1,850"
    assert rpm.format_rpm(1856.0) == "1,860"
    assert rpm.format_rpm(980.0) == "980"
    assert rpm.format_rpm(5200.0) == "5,200"

  def test_hidden_when_engine_off_or_unknown(self):
    assert rpm.format_rpm(0.0) is None
    assert rpm.format_rpm(4.0) is None
    assert rpm.format_rpm(None) is None


if __name__ == "__main__":
  unittest.main()
