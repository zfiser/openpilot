"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime
import time
from types import SimpleNamespace

import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app, TextAlignment, TextAlignmentVertical
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.label import UnifiedLabel
from openpilot.system.ui.widgets.scroller import Scroller

CAR_DATA_TIMEOUT = 15  # seconds without touching the page before the screen goes back, used while the global timeout is on its default
FIRST_KEYS = ("today", "battery_12v")  # the first row of the page
HIDDEN_KEYS = {"lead_distance", "friction_brake_force"}  # shown on the road view instead
COLUMNS = 2  # tiles per row, the tile size is fixed and the page scrolls when there are more rows than fit
TILE_COLOR = rl.Color(255, 255, 255, 18)
LABEL_COLOR = rl.Color(255, 255, 255, 140)
VALUE_COLOR = rl.Color(255, 255, 255, 255)
EMPTY_COLOR = rl.Color(255, 255, 255, 110)
REFERENCE_HEIGHT = 240  # font sizes below are tuned for this screen height
PAD_RATIO = 0.06  # of the screen height, between tiles and around the page; two rows of tiles fill the screen


def page_timeout(global_timeout) -> int:
  """Interactive timeout of the page: the global Interactivity Timeout setting when it is set, else CAR_DATA_TIMEOUT."""
  try:
    return int(global_timeout) if global_timeout else CAR_DATA_TIMEOUT
  except (TypeError, ValueError):
    return CAR_DATA_TIMEOUT


def format_value(value: float, unit: str, valid: bool) -> str:
  """Text shown for one tile, '--' when the car did not provide the value."""
  if not valid:
    return "--"
  text = f"{value:,.0f}" if abs(value) >= 1000 or abs(value - round(value)) < 1e-3 else f"{value:.1f}"
  return f"{text} {unit}".rstrip()


def order_items(items: list) -> list:
  """'Today' first and the 12 V battery second, so they are the first row; everything else keeps its order."""
  first = [next((i for i in items if i.key == key), None) for key in FIRST_KEYS]
  return [i for i in first if i is not None] + [i for i in items if i.key not in FIRST_KEYS]


def rows_of(items: list, columns: int = COLUMNS) -> list[list]:
  return [items[i:i + columns] for i in range(0, len(items), columns)]


def stored_items(state, today: str) -> list:
  """Last known odometer and the distance of today from the stored DailyOdometer, shown while the car is off.
  A stored day that is not today means nothing was driven yet today."""
  try:
    start = float(state["start"])
    last = float(state.get("last", start))
    unit = str(state["unit"])
    same_day = state.get("date") in (None, today)
  except Exception:
    return []
  return [SimpleNamespace(key="odometer", label="Odometer (last known)", value=last, unit=unit, valid=True),
          SimpleNamespace(key="today", label="Today (last known)", value=max(last - start, 0.0) if same_day else 0.0,
                          unit=unit, valid=True)]


def voltage_item(sm):
  """The 12 V battery of the car as measured by the panda (peripheralState, in millivolts). It also works with the car
  off, as long as the device is powered. None until the panda reports a plausible value."""
  try:
    if not sm.alive["peripheralState"]:
      return None
    millivolts = float(sm["peripheralState"].voltage)
  except Exception:
    return None
  if millivolts < 1000:
    return None
  return SimpleNamespace(key="battery_12v", label="12V battery", value=millivolts / 1000.0, unit="V", valid=True)


def get_items(sm) -> list:
  """Car data items from carStateSP, empty until the message of the current drive has been received."""
  try:
    if sm.recv_frame["carStateSP"] < ui_state.started_frame:
      return []
    return [item for item in sm["carStateSP"].carData if item.key not in HIDDEN_KEYS]
  except Exception:
    return []


class _TileRow(Widget):
  """A fixed size row with up to two tiles, the fonts do not shrink when there are many rows."""

  def __init__(self, width: float, height: float, pad: float, scale: float, label_cache: dict):
    super().__init__()
    self.set_rect(rl.Rectangle(0, 0, width, height))
    self._pad = pad
    self._label_size = int(17 * scale)
    self._value_size = int(34 * scale)
    self._cache = label_cache
    self._items: list = []

  def set_items(self, items: list) -> None:
    self._items = items

  def _labels(self, key: str) -> tuple[UnifiedLabel, UnifiedLabel]:
    if key not in self._cache:
      self._cache[key] = (UnifiedLabel("", self._label_size, FontWeight.MEDIUM, LABEL_COLOR, wrap_text=False),
                          UnifiedLabel("", self._value_size, FontWeight.BOLD, VALUE_COLOR, wrap_text=False))
    return self._cache[key]

  def _render(self, rect: rl.Rectangle) -> None:
    pad = self._pad
    tile_w = (rect.width - pad * (COLUMNS + 1)) / COLUMNS
    inner = pad * 1.2
    label_h = self._label_size * 1.3
    value_h = self._value_size * 1.2
    top = max((rect.height - label_h - value_h) / 2, inner * 0.5)
    for col, item in enumerate(self._items):
      tile = rl.Rectangle(rect.x + pad + col * (tile_w + pad), rect.y, tile_w, rect.height)
      rl.draw_rectangle_rounded(tile, 0.18, 8, TILE_COLOR)

      label, value = self._labels(item.key)
      label.set_text(item.label)
      value.set_text(format_value(item.value, item.unit, item.valid))
      label.render(rl.Rectangle(tile.x + inner, tile.y + top, tile.width - inner * 2, label_h))
      value_y = tile.y + top + label_h
      value.render(rl.Rectangle(tile.x + inner, value_y, tile.width - inner * 2, tile.y + tile.height - value_y))


class MiciCarDataLayout(Scroller):
  """Swipe page listing whatever extra car data the brand specific car state extension reports. Tiles keep their size,
  more tiles than fit make the page scroll vertically."""

  def __init__(self):
    height = gui_app.height
    self._width = gui_app.width
    self._scale = height / REFERENCE_HEIGHT
    self._pad = height * PAD_RATIO
    self._tile_height = (height - 3 * self._pad) / 2  # two rows fill the screen, more rows scroll
    super().__init__(horizontal=False, spacing=int(self._pad), pad=int(self._pad), scroll_indicator=False, edge_shadows=False)

    self._empty = UnifiedLabel("no car data available", int(30 * self._scale), FontWeight.MEDIUM, EMPTY_COLOR,
                               alignment=TextAlignment.CENTER, alignment_vertical=TextAlignmentVertical.MIDDLE)
    self._rows: list[_TileRow] = []
    self._label_cache: dict = {}
    self._has_items = False
    self._stored: list = []
    self._stored_time = -10.0

  def _stored_items(self) -> list:
    if time.monotonic() - self._stored_time > 2.0:
      self._stored_time = time.monotonic()
      try:
        self._stored = stored_items(ui_state.params.get("DailyOdometer"), datetime.date.today().isoformat())
      except Exception:
        self._stored = []
    return self._stored

  def _update_state(self) -> None:
    items = get_items(ui_state.sm) or self._stored_items()
    if (battery := voltage_item(ui_state.sm)) is not None:
      items = [*items, battery]
    items = order_items(items)
    self._has_items = bool(items)

    rows = rows_of(items)
    while len(self._rows) < len(rows):
      row = _TileRow(self._width, self._tile_height, self._pad, self._scale, self._label_cache)
      self._rows.append(row)
      self._scroller.add_widget(row)
    while len(self._rows) > len(rows):
      self._scroller.items.remove(self._rows.pop())
    for row, chunk in zip(self._rows, rows, strict=True):
      row.set_items(chunk)

  def _render(self, rect: rl.Rectangle) -> None:
    rl.draw_rectangle_rec(rect, rl.BLACK)
    if not self._has_items:
      self._empty.render(rect)
      return
    self._scroller.render(rect)
