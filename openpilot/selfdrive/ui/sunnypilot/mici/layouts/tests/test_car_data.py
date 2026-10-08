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

MODULE_PATH = Path(__file__).resolve().parents[1] / "car_data.py"


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


def _load():
  """Import car_data.py with the graphics/UI dependencies stubbed, so the logic is testable headless."""
  ui_state = _Obj(started_frame=0, sm=None)
  stubs = {
    "pyray": mock.MagicMock(),
    "openpilot": _stub_module("openpilot"),
    "openpilot.selfdrive": _stub_module("openpilot.selfdrive"),
    "openpilot.selfdrive.ui": _stub_module("openpilot.selfdrive.ui"),
    "openpilot.selfdrive.ui.ui_state": _stub_module("openpilot.selfdrive.ui.ui_state", ui_state=ui_state),
    "openpilot.system": _stub_module("openpilot.system"),
    "openpilot.system.ui": _stub_module("openpilot.system.ui"),
    "openpilot.system.ui.lib": _stub_module("openpilot.system.ui.lib"),
    "openpilot.system.ui.lib.application": _stub_module(
      "openpilot.system.ui.lib.application", FontWeight=mock.MagicMock(), gui_app=_Obj(height=240),
      TextAlignment=mock.MagicMock(), TextAlignmentVertical=mock.MagicMock()),
    "openpilot.system.ui.widgets": _stub_module("openpilot.system.ui.widgets", Widget=_Widget),
    "openpilot.system.ui.widgets.label": _stub_module("openpilot.system.ui.widgets.label", UnifiedLabel=mock.MagicMock()),
    "openpilot.system.ui.widgets.scroller": _stub_module("openpilot.system.ui.widgets.scroller", Scroller=_Widget),
  }
  with mock.patch.dict(sys.modules, stubs):
    spec = importlib.util.spec_from_file_location("car_data_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
  return module, ui_state


class _SM(dict):
  def __init__(self, items, frame: int = 1):
    super().__init__({"carStateSP": _Obj(carData=items)})
    self.recv_frame = {"carStateSP": frame}


class TestCarData(unittest.TestCase):
  def setUp(self):
    self.mod, self.ui_state = _load()

  def test_format_invalid(self):
    assert self.mod.format_value(123.0, "km", False) == "--"

  def test_format_integer_and_thousands(self):
    assert self.mod.format_value(54321.0, "km", True) == "54,321 km"
    assert self.mod.format_value(42.0, "psi", True) == "42 psi"

  def test_format_decimal(self):
    assert self.mod.format_value(13.84, "V", True) == "13.8 V"

  def test_format_no_unit(self):
    assert self.mod.format_value(7.0, "", True) == "7"

  def test_stored_items_same_day(self):
    state = {"date": "2026-10-08", "start": 10000.0, "unit": "km", "last": 10042.0}
    odometer, today = self.mod.stored_items(state, "2026-10-08")
    assert (odometer.key, odometer.value, odometer.unit, odometer.valid) == ("odometer", 10042.0, "km", True)
    assert odometer.label == "Odometer (last known)" and today.label == "Today (last known)"
    assert (today.key, today.value, today.unit, today.valid) == ("today", 42.0, "km", True)

  def test_stored_items_a_new_day_starts_at_zero(self):
    state = {"date": "2026-10-07", "start": 10000.0, "unit": "mi", "last": 10042.0}
    odometer, today = self.mod.stored_items(state, "2026-10-08")
    assert odometer.value == 10042.0 and today.value == 0.0 and today.unit == "mi"

  def test_stored_items_unknown_date_counts_as_today_and_old_format_works(self):
    assert self.mod.stored_items({"date": None, "start": 5.0, "unit": "km", "last": 9.0}, "2026-10-08")[1].value == 4.0
    assert self.mod.stored_items({"date": "2026-10-08", "start": 5.0, "unit": "km"}, "2026-10-08")[1].value == 0.0

  def test_stored_items_garbage(self):
    for bad in (None, "x", 5, {}, {"start": "a", "unit": "km"}):
      assert self.mod.stored_items(bad, "2026-10-08") == []

  def test_voltage_item(self):
    class SMV(_Obj):
      def __getitem__(self, key):
        return self.ps
    item = self.mod.voltage_item(SMV(alive={"peripheralState": True}, ps=_Obj(voltage=12640)))
    assert (item.key, item.label, item.unit, item.valid) == ("battery_12v", "12V battery", "V", True)
    assert abs(item.value - 12.64) < 1e-9

  def test_voltage_item_hidden_when_not_alive_or_implausible(self):
    class SMV(_Obj):
      def __getitem__(self, key):
        return self.ps
    assert self.mod.voltage_item(SMV(alive={"peripheralState": False}, ps=_Obj(voltage=12640))) is None
    assert self.mod.voltage_item(SMV(alive={"peripheralState": True}, ps=_Obj(voltage=0))) is None
    assert self.mod.voltage_item(SMV(alive={}, ps=_Obj(voltage=12640))) is None
    assert self.mod.voltage_item(_Obj()) is None

  def test_page_timeout_follows_the_global_setting(self):
    assert self.mod.page_timeout(150) == 150
    assert self.mod.page_timeout(40) == 40

  def test_page_timeout_default(self):
    assert self.mod.page_timeout(0) == self.mod.CAR_DATA_TIMEOUT == 15
    assert self.mod.page_timeout(None) == 15
    assert self.mod.page_timeout("x") == 15

  def test_today_and_battery_lead_the_first_row(self):
    keys = lambda items: [i.key for i in self.mod.order_items(items)]  # noqa: E731
    items = [_Obj(key=k) for k in ("odometer", "rpm", "battery_12v", "today", "lead")]
    assert keys(items) == ["today", "battery_12v", "odometer", "rpm", "lead"]

  def test_order_with_missing_items(self):
    keys = lambda items: [i.key for i in self.mod.order_items(items)]  # noqa: E731
    assert keys([_Obj(key="odometer"), _Obj(key="battery_12v")]) == ["battery_12v", "odometer"]
    assert keys([_Obj(key="odometer"), _Obj(key="today")]) == ["today", "odometer"]
    assert keys([]) == []

  def test_rows_of(self):
    assert self.mod.rows_of([1, 2, 3, 4, 5]) == [[1, 2], [3, 4], [5]]
    assert self.mod.rows_of([]) == []
    assert self.mod.rows_of([1]) == [[1]]

  def test_items_returned(self):
    items = [_Obj(key="odometer"), _Obj(key="fuel")]
    assert [i.key for i in self.mod.get_items(_SM(items))] == ["odometer", "fuel"]

  def test_stale_message_ignored(self):
    # carStateSP not received since this drive started
    self.ui_state.started_frame = 10
    assert self.mod.get_items(_SM([_Obj(key="odometer")], frame=5)) == []

  def test_missing_service_does_not_raise(self):
    assert self.mod.get_items(_Obj(recv_frame={})) == []


if __name__ == "__main__":
  unittest.main()
