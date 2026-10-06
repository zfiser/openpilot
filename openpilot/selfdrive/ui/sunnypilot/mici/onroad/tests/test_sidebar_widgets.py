"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

SIDEBAR_PATH = Path(__file__).resolve().parents[1] / "sidebar_widgets.py"


class _Obj:
  def __init__(self, **kw):
    self.__dict__.update(kw)


class _Widget:
  def __init__(self, *args, **kwargs):
    pass


def _stub_module(name: str, **attrs) -> types.ModuleType:
  mod = types.ModuleType(name)
  mod.__dict__.update(attrs)
  return mod


def _load_sidebar():
  """Import sidebar_widgets.py with the graphics/UI dependencies stubbed, so the logic is testable headless."""
  from enum import Enum

  class UIStatus(Enum):
    DISENGAGED = "disengaged"
    ENGAGED = "engaged"
    OVERRIDE = "override"
    LAT_ONLY = "lat_only"
    LONG_ONLY = "long_only"

  ui_state = _Obj(status=UIStatus.DISENGAGED, started_frame=0, sm=None, is_metric=True)
  stubs = {
    "pyray": mock.MagicMock(),
    "openpilot": _stub_module("openpilot"),
    "openpilot.selfdrive": _stub_module("openpilot.selfdrive"),
    "openpilot.selfdrive.ui": _stub_module("openpilot.selfdrive.ui"),
    "openpilot.selfdrive.ui.mici": _stub_module("openpilot.selfdrive.ui.mici"),
    "openpilot.selfdrive.ui.mici.onroad": _stub_module("openpilot.selfdrive.ui.mici.onroad", SIDE_PANEL_WIDTH=60),
    "openpilot.selfdrive.ui.mici.onroad.confidence_ball": _stub_module(
      "openpilot.selfdrive.ui.mici.onroad.confidence_ball", ConfidenceBall=object),
    "openpilot.selfdrive.ui.ui_state": _stub_module("openpilot.selfdrive.ui.ui_state", ui_state=ui_state, UIStatus=UIStatus),
    "openpilot.system": _stub_module("openpilot.system"),
    "openpilot.system.ui": _stub_module("openpilot.system.ui"),
    "openpilot.system.ui.lib": _stub_module("openpilot.system.ui.lib"),
    "openpilot.system.ui.lib.application": _stub_module(
      "openpilot.system.ui.lib.application", FontWeight=mock.MagicMock(), TextAlignment=mock.MagicMock(),
      TextAlignmentVertical=mock.MagicMock()),
    "openpilot.system.ui.widgets": _stub_module("openpilot.system.ui.widgets", Widget=_Widget),
    "openpilot.system.ui.widgets.label": _stub_module("openpilot.system.ui.widgets.label", UnifiedLabel=mock.MagicMock()),
  }
  with mock.patch.dict(sys.modules, stubs):
    spec = importlib.util.spec_from_file_location("sidebar_widgets_under_test", SIDEBAR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
  return module, ui_state, UIStatus


class _SM(dict):
  def __init__(self, lead_present: bool, should_stop: bool, plan_frame: int = 1, d_rel: float = 25.0):
    super().__init__({
      "radarState": _Obj(leadOne=_Obj(present=lead_present, dRel=d_rel)),
      "longitudinalPlan": _Obj(shouldStop=should_stop),
    })
    self.recv_frame = {"longitudinalPlan": plan_frame}


class TestSidebarWidgets(unittest.TestCase):
  def setUp(self):
    self.mod, self.ui_state, self.UIStatus = _load_sidebar()
    self.sidebar = self.mod.MiciSidebarWidgets(confidence_ball=None)

  def test_no_icon_by_default(self):
    self.ui_state.sm = _SM(lead_present=False, should_stop=False)
    assert self.sidebar._indicator_reason() == "none"

  def test_lead(self):
    self.ui_state.sm = _SM(lead_present=True, should_stop=False)
    assert self.sidebar._indicator_reason() == "lead"

  def test_stop_without_lead(self):
    self.ui_state.sm = _SM(lead_present=False, should_stop=True)
    assert self.sidebar._indicator_reason() == "stop"

  def test_lead_wins_over_stop(self):
    # a stopped lead also sets shouldStop, the lead is the reason so no red light should be shown
    self.ui_state.sm = _SM(lead_present=True, should_stop=True)
    assert self.sidebar._indicator_reason() == "lead"

  def test_stale_plan_ignored(self):
    # longitudinalPlan not received since the drive started
    self.ui_state.started_frame = 10
    self.ui_state.sm = _SM(lead_present=False, should_stop=True, plan_frame=5)
    assert self.sidebar._indicator_reason() == "none"

  def test_missing_messages_do_not_raise(self):
    self.ui_state.sm = _Obj(recv_frame={})
    assert self.sidebar._indicator_reason() == "none"

  def test_lead_distance_parts(self):
    assert self.mod.lead_distance_parts(32.4, True) == ("32", "m")
    assert self.mod.lead_distance_parts(32.6, True) == ("33", "m")
    assert self.mod.lead_distance_parts(30.0, False) == ("98", "ft")

  def test_lead_distance_with_lead(self):
    self.ui_state.sm = _SM(lead_present=True, should_stop=False, d_rel=41.7)
    assert abs(self.sidebar._lead_distance() - 41.7) < 1e-6

  def test_lead_distance_without_lead(self):
    self.ui_state.sm = _SM(lead_present=False, should_stop=False, d_rel=41.7)
    assert self.sidebar._lead_distance() is None

  def test_lead_distance_missing_message(self):
    self.ui_state.sm = _Obj(recv_frame={})
    assert self.sidebar._lead_distance() is None


if __name__ == "__main__":
  unittest.main()
