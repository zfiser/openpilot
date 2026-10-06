"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app, TextAlignment, TextAlignmentVertical
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.label import UnifiedLabel

COLUMNS = 2
TILE_COLOR = rl.Color(255, 255, 255, 18)
LABEL_COLOR = rl.Color(255, 255, 255, 140)
VALUE_COLOR = rl.Color(255, 255, 255, 255)
EMPTY_COLOR = rl.Color(255, 255, 255, 110)
REFERENCE_HEIGHT = 240  # font sizes below are tuned for this screen height


def format_value(value: float, unit: str, valid: bool) -> str:
  """Text shown for one tile, '--' when the car did not provide the value."""
  if not valid:
    return "--"
  text = f"{value:,.0f}" if abs(value) >= 1000 or abs(value - round(value)) < 1e-3 else f"{value:.1f}"
  return f"{text} {unit}".rstrip()


def get_items(sm) -> list:
  """Car data items from carStateSP, empty until the message of the current drive has been received."""
  try:
    if sm.recv_frame["carStateSP"] < ui_state.started_frame:
      return []
    return list(sm["carStateSP"].carData)
  except Exception:
    return []


class MiciCarDataLayout(Widget):
  """Swipe page listing whatever extra car data the brand specific car state extension reports."""

  def __init__(self):
    super().__init__()
    scale = gui_app.height / REFERENCE_HEIGHT
    self._title = UnifiedLabel("car data", int(26 * scale), FontWeight.SEMI_BOLD, LABEL_COLOR)
    self._empty = UnifiedLabel("no car data available", int(30 * scale), FontWeight.MEDIUM, EMPTY_COLOR,
                               alignment=TextAlignment.CENTER, alignment_vertical=TextAlignmentVertical.MIDDLE)
    self._label_size = int(20 * scale)
    self._value_size = int(40 * scale)
    self._tiles: dict[str, tuple[UnifiedLabel, UnifiedLabel]] = {}

  def _tile_labels(self, key: str) -> tuple[UnifiedLabel, UnifiedLabel]:
    if key not in self._tiles:
      self._tiles[key] = (
        UnifiedLabel("", self._label_size, FontWeight.MEDIUM, LABEL_COLOR, wrap_text=False),
        UnifiedLabel("", self._value_size, FontWeight.BOLD, VALUE_COLOR, wrap_text=False),
      )
    return self._tiles[key]

  def _render(self, rect: rl.Rectangle) -> None:
    rl.draw_rectangle_rec(rect, rl.BLACK)
    pad = rect.height * 0.06

    title_height = rect.height * 0.16
    self._title.render(rl.Rectangle(rect.x + pad * 1.5, rect.y + pad, rect.width - pad * 3, title_height))

    items = get_items(ui_state.sm)
    if not items:
      self._empty.render(rl.Rectangle(rect.x, rect.y + title_height, rect.width, rect.height - title_height))
      return

    top = rect.y + pad + title_height
    rows = (len(items) + COLUMNS - 1) // COLUMNS
    tile_w = (rect.width - pad * (COLUMNS + 1)) / COLUMNS
    tile_h = min((rect.y + rect.height - top - pad * rows) / rows, rect.height * 0.34)

    for idx, item in enumerate(items):
      col, row = idx % COLUMNS, idx // COLUMNS
      tile = rl.Rectangle(rect.x + pad + col * (tile_w + pad), top + row * (tile_h + pad), tile_w, tile_h)
      rl.draw_rectangle_rounded(tile, 0.18, 8, TILE_COLOR)

      label, value = self._tile_labels(item.key)
      label.set_text(item.label)
      value.set_text(format_value(item.value, item.unit, item.valid))
      inner = pad * 1.2
      label.render(rl.Rectangle(tile.x + inner, tile.y + inner * 0.6, tile.width - inner * 2, tile.height * 0.32))
      value.render(rl.Rectangle(tile.x + inner, tile.y + tile.height * 0.38, tile.width - inner * 2, tile.height * 0.55))
