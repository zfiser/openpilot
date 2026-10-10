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

MODULE_PATH = Path(__file__).resolve().parents[1] / "quick_settings.py"


class _Base:
  def __init__(self, *args, **kwargs):
    pass


def _stub(name: str, **attrs) -> types.ModuleType:
  mod = types.ModuleType(name)
  mod.__dict__.update(attrs)
  return mod


def _load():
  stubs = {
    "openpilot.selfdrive.ui.mici.layouts.settings.toggles": _stub("t", TogglesLayoutMici=_Base),
    "openpilot.selfdrive.ui.mici.widgets.button": _stub("b", BigButton=_Base),
    "openpilot.selfdrive.ui.mici.widgets.dialog": _stub("d", BigConfirmationDialog=_Base),
    "openpilot.selfdrive.ui.sunnypilot.mici.widgets.param_buttons": _stub("p", BigBoolParam=_Base, BigChoiceParam=_Base),
    "openpilot.selfdrive.ui.ui_state": _stub("u", ui_state=types.SimpleNamespace(is_metric=True)),
    "openpilot.system.ui.lib.application": _stub("a", gui_app=mock.MagicMock()),
    "openpilot.system.ui.widgets": _stub("w", Widget=_Base),
    "openpilot.system.ui.widgets.scroller": _stub("s", NavScroller=_Base),
  }
  with mock.patch.dict(sys.modules, stubs):
    spec = importlib.util.spec_from_file_location("quick_settings_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
  return module


class TestQuickSettings(unittest.TestCase):
  def setUp(self):
    self.m = _load()

  def test_choice_lists_have_unique_values_and_labels(self):
    for name in ("LANE_CHANGE_CHOICES", "LANE_CHANGE_SMOOTHING_CHOICES", "STEERING_ON_BRAKE_CHOICES", "BLINKER_DELAY_CHOICES", "OFF_ON_CHOICES",
                 "TIMEOUT_CHOICES", "ONROAD_BRIGHTNESS_CHOICES", "SCREEN_SAVER_CHOICES"):
      choices = getattr(self.m, name)
      assert len({v for v, _ in choices}) == len(choices), name
      assert len({label for _, label in choices}) == len(choices), name

  def test_values_match_what_the_settings_mean(self):
    assert dict(self.m.LANE_CHANGE_CHOICES)[-1] == "off" and dict(self.m.LANE_CHANGE_CHOICES)[0] == "nudge"
    assert dict(self.m.LANE_CHANGE_SMOOTHING_CHOICES)[10] == "10 stock" and dict(self.m.LANE_CHANGE_SMOOTHING_CHOICES)[5] == "5 default"
    assert dict(self.m.STEERING_ON_BRAKE_CHOICES) == {0: "remain active", 1: "pause", 2: "disengage"}
    assert dict(self.m.ONROAD_BRIGHTNESS_CHOICES)[22] == "100 %" and dict(self.m.ONROAD_BRIGHTNESS_CHOICES)[4] == "10 %"
    assert (0, "default") in self.m.TIMEOUT_CHOICES and (120, "2 m") in self.m.TIMEOUT_CHOICES

  def test_blinker_speed_unit(self):
    assert self.m.blinker_speed_choices(True)[1] == (20, "20 km/h")
    assert self.m.blinker_speed_choices(False)[1] == (20, "20 mph")

  def test_lazy_builds_once(self):
    built = []
    self.m.gui_app = mock.MagicMock()

    def make():
      built.append(1)
      return object()

    open_panel = self.m.lazy(make)
    open_panel()
    open_panel()
    assert len(built) == 1 and self.m.gui_app.push_widget.call_count == 2


if __name__ == "__main__":
  unittest.main()
