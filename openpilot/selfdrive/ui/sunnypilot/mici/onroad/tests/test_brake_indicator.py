"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("brake_indicator_under_test", Path(__file__).resolve().parents[1] / "brake_indicator.py")
bi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bi)


class _SM(dict):
  def __init__(self, items, recv=10):
    super().__init__({"carStateSP": SimpleNamespace(carData=items)})
    self.recv_frame = {"carStateSP": recv}


def _item(value, valid=True, key="friction_brake_force"):
  return SimpleNamespace(key=key, value=value, valid=valid)


class TestBrakeIndicator(unittest.TestCase):
  def test_force_means_friction_braking(self):
    assert bi.friction_braking(_SM([_item(400.0)]), 5)

  def test_zero_force_is_regen_or_no_braking(self):
    assert not bi.friction_braking(_SM([_item(0.0)]), 5)

  def test_invalid_or_missing_item(self):
    assert not bi.friction_braking(_SM([_item(400.0, valid=False)]), 5)
    assert not bi.friction_braking(_SM([_item(400.0, key="rpm")]), 5)

  def test_old_message_and_broken_state(self):
    assert not bi.friction_braking(_SM([_item(400.0)], recv=3), 5)
    assert not bi.friction_braking(object(), 0)


if __name__ == "__main__":
  unittest.main()
