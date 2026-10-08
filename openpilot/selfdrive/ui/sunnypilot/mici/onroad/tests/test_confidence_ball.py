"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import sys
import types
import unittest
from enum import Enum
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[4] / "mici" / "onroad" / "confidence_ball.py"


class _Widget:
  def __init__(self, *args, **kwargs):
    pass


class _Filter:
  def __init__(self, x0, rc, dt):
    self.x = x0

  def update(self, value):
    self.x = value


def _stub_module(name: str, **attrs) -> types.ModuleType:
  mod = types.ModuleType(name)
  mod.__dict__.update(attrs)
  return mod


def _load():
  class UIStatus(Enum):
    DISENGAGED = "disengaged"
    ENGAGED = "engaged"
    OVERRIDE = "override"
    LAT_ONLY = "lat_only"
    LONG_ONLY = "long_only"

  class Color(tuple):  # a real class so annotations like `rl.Color | None` work, equal to a plain (r, g, b, a) tuple
    def __new__(cls, r, g, b, a):
      return tuple.__new__(cls, (r, g, b, a))

  rl = mock.MagicMock()
  rl.Color = Color
  ui_state = types.SimpleNamespace(status=UIStatus.ENGAGED)
  stubs = {
    "pyray": rl,
    "openpilot": _stub_module("openpilot"),
    "openpilot.selfdrive": _stub_module("openpilot.selfdrive"),
    "openpilot.selfdrive.ui": _stub_module("openpilot.selfdrive.ui"),
    "openpilot.selfdrive.ui.mici": _stub_module("openpilot.selfdrive.ui.mici"),
    "openpilot.selfdrive.ui.mici.onroad": _stub_module("openpilot.selfdrive.ui.mici.onroad", SIDE_PANEL_WIDTH=60),
    "openpilot.selfdrive.ui.ui_state": _stub_module("openpilot.selfdrive.ui.ui_state", ui_state=ui_state, UIStatus=UIStatus),
    "openpilot.system": _stub_module("openpilot.system"),
    "openpilot.system.ui": _stub_module("openpilot.system.ui"),
    "openpilot.system.ui.widgets": _stub_module("openpilot.system.ui.widgets", Widget=_Widget),
    "openpilot.system.ui.lib": _stub_module("openpilot.system.ui.lib"),
    "openpilot.system.ui.lib.application": _stub_module("openpilot.system.ui.lib.application", gui_app=types.SimpleNamespace(target_fps=60)),
    "openpilot.common": _stub_module("openpilot.common"),
    "openpilot.common.filter_simple": _stub_module("openpilot.common.filter_simple", FirstOrderFilter=_Filter),
    "openpilot.selfdrive.ui.sunnypilot": _stub_module("openpilot.selfdrive.ui.sunnypilot"),
    "openpilot.selfdrive.ui.sunnypilot.mici": _stub_module("openpilot.selfdrive.ui.sunnypilot.mici"),
    "openpilot.selfdrive.ui.sunnypilot.mici.onroad": _stub_module("openpilot.selfdrive.ui.sunnypilot.mici.onroad"),
    "openpilot.selfdrive.ui.sunnypilot.mici.onroad.confidence_ball": _stub_module(
      "openpilot.selfdrive.ui.sunnypilot.mici.onroad.confidence_ball", ConfidenceBallSP=type("ConfidenceBallSP", (), {})),
  }
  with mock.patch.dict(sys.modules, stubs):
    spec = importlib.util.spec_from_file_location("confidence_ball_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
  return module, ui_state, UIStatus


class TestConfidenceBall(unittest.TestCase):
  def setUp(self):
    self.mod, self.ui_state, self.UIStatus = _load()
    self.ball = self.mod.ConfidenceBall()

  def at(self, status, confidence):
    self.ui_state.status = status
    self.ball._confidence_filter.x = confidence

  def test_zones(self):
    assert [self.mod.confidence_zone(c) for c in (0.9, 0.51, 0.5, 0.3, 0.21, 0.2, 0.0, -0.5)] == \
           ["high", "high", "medium", "medium", "medium", "low", "low", "low"]

  def test_no_border_when_confident_or_not_engaged(self):
    for status in (self.UIStatus.ENGAGED, self.UIStatus.LAT_ONLY, self.UIStatus.LONG_ONLY):
      self.at(status, 0.9)
      assert self.ball.border_color() is None
    for status in (self.UIStatus.DISENGAGED, self.UIStatus.OVERRIDE):
      for confidence in (0.9, 0.35, 0.1):
        self.at(status, confidence)
        assert self.ball.border_color() is None

  def test_orange_then_red_border_for_lower_confidence_in_every_engaged_mode(self):
    for status in (self.UIStatus.ENGAGED, self.UIStatus.LAT_ONLY, self.UIStatus.LONG_ONLY):
      self.at(status, 0.35)
      assert self.ball.border_color() == self.mod.BORDER_ORANGE
      self.at(status, 0.1)
      assert self.ball.border_color() == self.mod.BORDER_RED

  def test_circle_uses_traffic_light_colours_in_lateral_only(self):
    green = ((0, 255, 204, 255), (0, 255, 38, 255))
    orange = ((255, 200, 0, 255), (255, 115, 0, 255))
    red = ((255, 0, 21, 255), (255, 0, 89, 255))
    for status in (self.UIStatus.ENGAGED, self.UIStatus.LAT_ONLY, self.UIStatus.LONG_ONLY):
      for confidence, colours in ((0.9, green), (0.35, orange), (0.1, red)):
        self.at(status, confidence)
        assert self.ball._dot_colors() == colours, (status, confidence)

  def test_override_and_disengaged_keep_their_colours(self):
    self.at(self.UIStatus.OVERRIDE, 0.9)
    assert self.ball._dot_colors() == ((255, 255, 255, 255), (82, 82, 82, 255))
    self.at(self.UIStatus.DISENGAGED, 0.9)
    assert self.ball._dot_colors() == ((50, 50, 50, 255), (13, 13, 13, 255))


if __name__ == "__main__":
  unittest.main()
