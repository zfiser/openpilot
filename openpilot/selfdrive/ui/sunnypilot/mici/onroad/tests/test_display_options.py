"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("display_options_under_test", Path(__file__).resolve().parents[1] / "display_options.py")
do = importlib.util.module_from_spec(spec)
spec.loader.exec_module(do)


class _Params:
  def __init__(self, values):
    self.values = values
    self.reads = 0

  def get(self, key, return_default=False):
    assert return_default, "an unset setting must read as its default (on), not as off"
    self.reads += 1
    if isinstance(self.values.get(key), Exception):
      raise self.values[key]
    return self.values.get(key, True)


class TestDisplayOptions(unittest.TestCase):
  def test_on_until_read_and_follows_the_settings(self):
    t = [0.0]
    params = _Params({k: True for k in do.KEYS} | {do.RPM: False})
    opts = do.DisplayOptions(params, now=lambda: t[0])
    assert opts.enabled(do.GPS_SPEED) and not opts.enabled(do.RPM)

  def test_reads_at_most_once_a_second(self):
    t = [0.0]
    params = _Params({k: True for k in do.KEYS})
    opts = do.DisplayOptions(params, now=lambda: t[0])
    for _ in range(100):
      opts.enabled(do.GPS_SPEED)
    assert params.reads == len(do.KEYS)
    t[0] = 1.5
    params.values[do.GPS_SPEED] = False
    assert not opts.enabled(do.GPS_SPEED)
    assert params.reads == 2 * len(do.KEYS)

  def test_a_broken_setting_keeps_the_item_on(self):
    params = _Params({do.BRAKE_DOT: RuntimeError("x")})
    assert do.DisplayOptions(params, now=lambda: 0.0).enabled(do.BRAKE_DOT)

  def test_unknown_key_is_on(self):
    assert do.DisplayOptions(_Params({}), now=lambda: 0.0).enabled("Other")


if __name__ == "__main__":
  unittest.main()
