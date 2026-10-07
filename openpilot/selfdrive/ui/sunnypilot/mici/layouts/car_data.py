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

MAX_ITEMS_TWO_COLUMNS = 4  # up to this many tiles use two columns, up to nine use three, more use four
MAX_ITEMS_THREE_COLUMNS = 9
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


def tile_columns(count: int) -> int:
  return 2 if count <= MAX_ITEMS_TWO_COLUMNS else 3 if count <= MAX_ITEMS_THREE_COLUMNS else 4


def tile_text_sizes(tile_height: float, columns: int, scale: float) -> tuple[int, int]:
  """(label, value) font sizes: follow the tile height, but narrower tiles (more columns) cap the value size."""
  value_cap = {2: 34, 3: 25, 4: 20}[columns] * scale
  label = int(min(17 * scale, max(11 * scale, tile_height * 0.22)))
  value = int(min(value_cap, max(14 * scale, tile_height * 0.42)))
  return label, value


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
    self._scale = scale
    self._tiles: dict[tuple[str, int, int], tuple[UnifiedLabel, UnifiedLabel]] = {}

  def _tile_labels(self, key: str, label_size: int, value_size: int) -> tuple[UnifiedLabel, UnifiedLabel]:
    if (key, label_size, value_size) not in self._tiles:
      self._tiles[(key, label_size, value_size)] = (
        UnifiedLabel("", label_size, FontWeight.MEDIUM, LABEL_COLOR, wrap_text=False),
        UnifiedLabel("", value_size, FontWeight.BOLD, VALUE_COLOR, wrap_text=False),
      )
    return self._tiles[(key, label_size, value_size)]

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
    columns = tile_columns(len(items))
    rows = (len(items) + columns - 1) // columns
    tile_w = (rect.width - pad * (columns + 1)) / columns
    tile_h = min((rect.y + rect.height - top - pad * rows) / rows, rect.height * 0.34)
    label_size, value_size = tile_text_sizes(tile_h, columns, self._scale)

    for idx, item in enumerate(items):
      col, row = idx % columns, idx // columns
      tile = rl.Rectangle(rect.x + pad + col * (tile_w + pad), top + row * (tile_h + pad), tile_w, tile_h)
      rl.draw_rectangle_rounded(tile, 0.18, 8, TILE_COLOR)

      label, value = self._tile_labels(item.key, label_size, value_size)
      label.set_text(item.label)
      value.set_text(format_value(item.value, item.unit, item.valid))
      inner = pad * 1.2 if columns < 4 else pad * 0.8
      label_h = label_size * 1.3
      label.render(rl.Rectangle(tile.x + inner, tile.y + inner * 0.5, tile.width - inner * 2, label_h))
      value_y = tile.y + inner * 0.5 + label_h
      value.render(rl.Rectangle(tile.x + inner, value_y, tile.width - inner * 2, tile.y + tile.height - value_y))
