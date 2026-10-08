"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("lead_distance_under_test", Path(__file__).resolve().parents[1] / "lead_distance.py")
ld = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ld)



class _SM(dict):
  def __init__(self, items, recv=10):
    super().__init__({"carStateSP": SimpleNamespace(carData=items)})
    self.recv_frame = {"carStateSP": recv}


def _item(key, value, valid=True):
  return SimpleNamespace(key=key, value=value, valid=valid)


class TestLeadDistance(unittest.TestCase):
  def test_reads_the_item(self):
    assert ld.lead_distance(_SM([_item("rpm", 900.0), _item("lead_distance", 23.4)]), 5) == 23

  def test_invalid_or_missing_is_none(self):
    assert ld.lead_distance(_SM([_item("lead_distance", 0.0, valid=False)]), 5) is None
    assert ld.lead_distance(_SM([_item("rpm", 900.0)]), 5) is None

  def test_message_from_a_previous_drive_is_ignored(self):
    assert ld.lead_distance(_SM([_item("lead_distance", 20.0)], recv=3), 5) is None

  def test_broken_state_is_none(self):
    assert ld.lead_distance(object(), 0) is None

  def _run(self, distances, step=0.2):
    trend = ld.LeadTrend()
    return [trend.update(d, i * step) for i, d in enumerate(distances)]

  def test_closing(self):
    assert self._run([30, 30, 29, 29, 28, 28, 27])[-1] == ld.CLOSING

  def test_opening(self):
    assert self._run([20, 20, 21, 21, 22, 22, 23])[-1] == ld.OPENING

  def test_stable_with_one_metre_jitter_inside_the_threshold(self):
    assert set(self._run([25, 25, 25, 25.4, 25, 25, 25])) == {ld.STABLE}

  def test_needs_some_history(self):
    assert self._run([30, 25])[-1] == ld.STABLE

  def test_lead_lost_resets(self):
    trend = ld.LeadTrend()
    for i, d in enumerate([30, 29, 28, 27, 26, 25]):
      trend.update(d, i * 0.2)
    assert trend.update(None, 1.2) == ld.STABLE
    assert trend.update(10, 1.4) == ld.STABLE  # new lead, no old history to compare with

  def test_old_samples_age_out(self):
    trend = ld.LeadTrend()
    for i in range(10):
      trend.update(30 - i, i * 0.2)  # closing
    results = [trend.update(21, 2.0 + i * 0.2) for i in range(8)]
    assert results[-1] == ld.STABLE  # constant for more than a window now


if __name__ == "__main__":
  unittest.main()
