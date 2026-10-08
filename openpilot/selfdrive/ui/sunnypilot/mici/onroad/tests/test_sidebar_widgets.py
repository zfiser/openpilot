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
      TextAlignmentVertical=mock.MagicMock(), gui_app=mock.MagicMock()),
    "openpilot.system.ui.lib.text_measure": _stub_module("openpilot.system.ui.lib.text_measure", measure_text_cached=mock.MagicMock()),
    "openpilot.selfdrive.ui.sunnypilot.mici.onroad.gps_speed": _stub_module(
      "openpilot.selfdrive.ui.sunnypilot.mici.onroad.gps_speed", gps_speed=mock.MagicMock(return_value=None)),
    "openpilot.selfdrive.ui.sunnypilot.mici.onroad.brake_indicator": _stub_module(
      "openpilot.selfdrive.ui.sunnypilot.mici.onroad.brake_indicator", friction_braking=mock.MagicMock(return_value=False)),
    "openpilot.selfdrive.ui.sunnypilot.mici.onroad.lead_distance": _stub_module(
      "openpilot.selfdrive.ui.sunnypilot.mici.onroad.lead_distance", CLOSING=-1, OPENING=1, LeadTrend=mock.MagicMock(),
      lead_distance=mock.MagicMock(return_value=None)),
    "openpilot.selfdrive.ui.sunnypilot": _stub_module("openpilot.selfdrive.ui.sunnypilot"),
    "openpilot.selfdrive.ui.sunnypilot.mici": _stub_module("openpilot.selfdrive.ui.sunnypilot.mici"),
    "openpilot.selfdrive.ui.sunnypilot.mici.onroad": _stub_module("openpilot.selfdrive.ui.sunnypilot.mici.onroad"),
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

  def test_no_stop_light_by_default(self):
    self.ui_state.sm = _SM(lead_present=False, should_stop=False)
    assert not self.sidebar._stop_light_visible()

  def test_stop_light_when_the_planner_stops_without_a_lead(self):
    self.ui_state.sm = _SM(lead_present=False, should_stop=True)
    assert self.sidebar._stop_light_visible()

  def test_a_lead_car_hides_the_stop_light(self):
    # a stopped lead also sets shouldStop, that is a car and not a red light
    self.ui_state.sm = _SM(lead_present=True, should_stop=True)
    assert not self.sidebar._stop_light_visible()

  def test_stale_plan_ignored(self):
    # longitudinalPlan not received since the drive started
    self.ui_state.started_frame = 10
    self.ui_state.sm = _SM(lead_present=False, should_stop=True, plan_frame=5)
    assert not self.sidebar._stop_light_visible()

  def test_missing_messages_do_not_raise(self):
    self.ui_state.sm = _Obj(recv_frame={})
    assert not self.sidebar._stop_light_visible()


if __name__ == "__main__":
  unittest.main()
