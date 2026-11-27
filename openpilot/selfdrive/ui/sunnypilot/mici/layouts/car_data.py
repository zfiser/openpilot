"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import datetime
import json
import time
from types import SimpleNamespace

import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app, TextAlignment, TextAlignmentVertical
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.label import UnifiedLabel
from openpilot.system.ui.widgets.scroller import Scroller
from openpilot.selfdrive.ui.sunnypilot.mici.layouts.diag_panels import PREFIX as DIAG_PREFIX, build_panels

CAR_DATA_TIMEOUT = 15  # seconds without touching the page before the screen goes back, used while the global timeout is on its default
ONE_DECIMAL_KEYS: set[str] = set()  # keys shown with one decimal place, none: the odometer only counts whole units
# The tiles that are always on the page, in this order (today and the 12 V battery are the first row). They show '--' while
# there is no data, with the car off, without a lead car and so on, so the page keeps its layout.
STANDARD_TILES = (("today", "Today", "km"), ("battery_12v", "12V battery", "V"), ("cabin", "Cabin", "C"),
                  ("engine_temp", "Engine temp", "C"), ("odometer", "Odometer", "km"))  # the time of today is in "today"
DURATION_KEYS = {"drive_time"}  # seconds, shown as h:mm
HIDDEN_KEYS = {"lead_distance", "friction_brake_force", "radar_distance", "radar_rel_speed", "rpm"}  # driving screen / warnings only
GEARBOX_SOURCE = "diag_transaxle_oil"  # shown after the engine temperature: 89/72 C (read once a minute, ECU data)
GEARBOX_LABEL = "Engine / gearbox"
CABIN_SOURCE = "diag_cabin"  # the cabin tile shows the climate ECU's cabin temperature (read once a minute, ECU data)
LAST_USEFUL_KEY = "odometer"  # after everything else that is useful, before the experimental tiles
EXPERIMENTAL_PREFIXES = ("watch_", "tire_")  # RawCanWatch tiles and tire guesses, always after the useful tiles
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


def format_value(value: float, unit: str, valid: bool, decimals: int | None = None) -> str:
  """Text shown for one tile, '--' when the car did not provide the value. decimals fixes the number of decimal places."""
  if not valid:
    return "--"
  if decimals is not None:
    text = f"{value:,.{decimals}f}"
  else:
    text = f"{value:,.0f}" if abs(value) >= 1000 or abs(value - round(value)) < 1e-3 else f"{value:.1f}"
  return f"{text} {unit}".rstrip()


def complete_items(items: list) -> list:
  """The items plus a tile without a value for every standard tile that has none."""
  have = {i.key for i in items}
  missing = [SimpleNamespace(key=key, label=label, value=0.0, unit=unit, valid=False)
             for key, label, unit in STANDARD_TILES if key not in have]
  return [*items, *missing]


def format_hours_minutes(seconds: float) -> str:
  """Seconds as 1h42m, or 42m under an hour."""
  minutes = int(max(seconds, 0.0) // 60)
  return f"{minutes // 60}h{minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"


def merge_today(items: list) -> list:
  """The time driven today goes into the "today" tile (42 km/1h42m), the separate time item is dropped."""
  time_item = next((i for i in items if i.key == "drive_time"), None)
  if time_item is None:
    return items
  out = []
  for i in items:
    if i.key == "drive_time":
      continue
    if i.key == "today":
      i = SimpleNamespace(key=i.key, label=i.label, value=i.value, unit=i.unit, valid=i.valid,
                          seconds=time_item.value if time_item.valid else None)
    out.append(i)
  return out


def today_text(item) -> str:
  if not item.valid:
    return "--"
  distance = format_value(item.value, item.unit, True).replace(" ", "")
  seconds = getattr(item, "seconds", None)
  return distance if seconds is None else f"{distance}/{format_hours_minutes(seconds)}"


def merge_gearbox(items: list) -> list:
  """The transaxle oil temperature goes into the engine temperature tile (89°/72°C)."""
  gearbox = next((i for i in items if i.key == GEARBOX_SOURCE and i.valid), None)
  if gearbox is None:
    return items
  engine = next((i for i in items if i.key == "engine_temp"), None)
  unit = engine.unit if engine is not None else "C"
  celsius = float(gearbox.value)
  tile = SimpleNamespace(key="engine_temp", label=GEARBOX_LABEL, value=engine.value if engine is not None else 0.0, unit=unit,
                         valid=engine is not None and engine.valid, gearbox=celsius * 9 / 5 + 32 if unit == "F" else celsius)
  return [*(i for i in items if i.key != "engine_temp"), tile]


def engine_text(item) -> str:
  """89°/72°C with the gearbox, else the engine alone; '--' for a value the car did not give."""
  gearbox = getattr(item, "gearbox", None)
  if gearbox is None:
    return format_value(item.value, item.unit, item.valid)
  engine = f"{item.value:.0f}°" if item.valid else "--"
  return f"{engine}/{gearbox:.0f}°{item.unit}"


def format_duration(seconds: float) -> str:
  """Seconds as hours:minutes, for example 1:25 and 0:07."""
  minutes = int(max(seconds, 0.0) // 60)
  return f"{minutes // 60}:{minutes % 60:02d}"


def order_items(items: list) -> list:
  """Standard tiles first in their fixed order (so 'today' and the 12 V battery are the first row, RPM and the engine
  temperature the second), then whatever else the car reports, the odometer, and the experimental tiles last."""
  standard_keys = [key for key, _, _ in STANDARD_TILES if key != LAST_USEFUL_KEY]
  standard = [next(i for i in items if i.key == key) for key in standard_keys if any(i.key == key for i in items)]
  last_useful = [i for i in items if i.key == LAST_USEFUL_KEY]
  experimental = [i for i in items if i.key.startswith(EXPERIMENTAL_PREFIXES)]
  other = [i for i in items if i.key not in (*standard_keys, LAST_USEFUL_KEY) and not i.key.startswith(EXPERIMENTAL_PREFIXES)]
  return standard + other + last_useful + experimental


def rows_of(items: list, columns: int = COLUMNS) -> list[list]:
  return [items[i:i + columns] for i in range(0, len(items), columns)]


LIVE_PATH = "/dev/shm/daily_odometer_live.json"  # the running values of the car process, in RAM (see daily_distance.py)


def read_live(path: str = LIVE_PATH) -> dict | None:
  try:
    with open(path) as f:
      live = json.load(f)
    return live if isinstance(live, dict) else None
  except Exception:
    return None


def stored_items(state, today: str, live: dict | None = None) -> list:
  """Last known odometer, the distance and the time of today, shown while the car is off. The start of the day comes from
  the stored DailyOdometer, the last reading and the time from the RAM file of the car process when it belongs to the same
  day. A stored day that is not today means nothing was driven yet today."""
  try:
    start = float(state["start"])
    unit = str(state["unit"])
    same_day = state.get("date") in (None, today)
    matching = isinstance(live, dict) and live.get("date") == state.get("date") and float(live.get("start", -1)) == start
    source = live if matching else state
    last = float(source.get("last", start))
    seconds = max(float(source.get("seconds", 0.0)), 0.0) if same_day else 0.0
  except Exception:
    return []
  today = max(last - start, 0.0)
  return [SimpleNamespace(key="odometer", label="Odometer", value=last, unit=unit, valid=True),
          SimpleNamespace(key="today", label="Today", value=today if same_day else 0.0, unit=unit, valid=True),
          SimpleNamespace(key="drive_time", label="Time", value=seconds, unit="s", valid=True)]


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


GREEN = rl.Color(70, 210, 110, 255)
RED = rl.Color(255, 90, 90, 255)
CHARGING_COLOR, DRAINING_COLOR = GREEN, RED
AMPS_IDLE = 0.5  # A, a smaller 12 V current is shown white (neither charging nor draining), as on the 12 V battery panel


PAIR_SIZE = 30  # font size of the label / value lines of a panel (at the 240 px reference height); read in a moving car
PAIR_LINE = 1.36  # line height in font sizes
TITLE_SIZE, BIG_SIZE = 26, 40
TYRE_NAME, TYRE_TEMP, TYRE_PRESSURE = 24, 40, 30  # the pressure goes under the temperature, both large


def _text_width(font, text: str, size: float) -> float:
  return measure_text_cached(font, text, int(size)).x


class _PanelRow(Widget):
  """One group of values read from the car's ECUs (diag_panels.py): a title, an optional big line, then label / value
  lines (two columns where they fit, else one), or for the tyres a 2 x 2 grid laid out like the car. The panel is as tall
  as its content (at least two tile rows); the page scrolls."""

  def __init__(self, width: float, height: float, pad: float, scale: float):
    super().__init__()
    self.set_rect(rl.Rectangle(0, 0, width, height))
    self._min_height = height
    self._pad = pad
    self._scale = scale
    self._panel = None
    self._columns = 1
    self._font = gui_app.font(FontWeight.MEDIUM)
    self._bold = gui_app.font(FontWeight.BOLD)

  # geometry, shared by the height and the drawing
  def _inner(self, width: float) -> tuple[float, float, float]:
    """(left, width, right edge of values) of the content, relative to the row."""
    pad = self._pad
    left = pad + pad * 1.2
    right = width - pad - pad * 2.0
    return left, right - left, right

  def _fits_two_columns(self, panel) -> bool:
    s, gap = self._scale, self._pad * 1.5
    _, inner_w, _ = self._inner(self._rect.width)
    col_w = (inner_w - gap) / 2
    size = PAIR_SIZE * s
    need = max((_text_width(self._font, label, size) + _text_width(self._bold, value, size) + self._pad
                for label, value in panel.pairs), default=0.0)
    return need <= col_w

  def set_panel(self, panel) -> None:
    self._panel = panel
    s, pad = self._scale, self._pad
    self._columns = 2 if panel.pairs and self._fits_two_columns(panel) else 1
    content = pad * 0.9 + TITLE_SIZE * 1.25 * s + (BIG_SIZE * 1.2 * s if panel.big else 0.0) + pad
    if panel.grid:
      content += 2 * (TYRE_NAME + TYRE_TEMP + TYRE_PRESSURE) * 1.12 * s
    elif panel.pairs:
      rows = (len(panel.pairs) + self._columns - 1) // self._columns
      content += rows * PAIR_SIZE * PAIR_LINE * s
    self.set_rect(rl.Rectangle(self._rect.x, self._rect.y, self._rect.width, max(self._min_height, content)))

  def _text(self, text: str, x: float, y: float, size: float, color: rl.Color, bold: bool = False, right: float | None = None) -> None:
    font = self._bold if bold else self._font
    size = int(size)  # measured and drawn at the same size, else a right-aligned value loses its last glyph
    if right is not None:
      x = right - measure_text_cached(font, text, size).x
    rl.draw_text_ex(font, text, rl.Vector2(round(x), round(y)), size, 0, color)  # whole pixels: no clipped last glyph

  def _render(self, rect: rl.Rectangle) -> None:
    p = self._panel
    if p is None:
      return
    s, pad = self._scale, self._pad
    tile = rl.Rectangle(rect.x + pad, rect.y, rect.width - 2 * pad, rect.height)
    rl.draw_rectangle_rounded(tile, 0.06, 8, TILE_COLOR)
    left, inner_w, right = self._inner(rect.width)
    x, y = rect.x + left, tile.y + pad * 0.9
    right_edge = rect.x + right
    self._text(p.title, x, y, TITLE_SIZE * s, LABEL_COLOR)
    y += TITLE_SIZE * 1.25 * s
    if p.big:
      color = GREEN if p.state == "charging" else RED if p.state == "draining" else VALUE_COLOR
      self._text(p.big, x, y, BIG_SIZE * s, color, bold=True)
      y += BIG_SIZE * 1.2 * s
    if p.grid:
      cell_w = inner_w / 2
      cell_h = (TYRE_NAME + TYRE_TEMP + TYRE_PRESSURE) * 1.12 * s
      for i, (name, pressure, temp) in enumerate(p.grid):
        cx, cy = x + (i % 2) * cell_w, y + (i // 2) * cell_h
        # the temperature is the news (the dash shows the pressures): big and white, the pressure under it
        self._text(name, cx, cy, TYRE_NAME * s, LABEL_COLOR)
        self._text(temp, cx, cy + TYRE_NAME * 1.1 * s, TYRE_TEMP * s, VALUE_COLOR, bold=True)
        self._text(pressure, cx, cy + (TYRE_NAME + TYRE_TEMP) * 1.1 * s, TYRE_PRESSURE * s, LABEL_COLOR)
      return
    size = PAIR_SIZE * s
    line = size * PAIR_LINE
    gap = pad * 1.5  # between the two columns
    columns = self._columns
    col_w = (inner_w - gap * (columns - 1)) / columns
    for i, (label, value) in enumerate(p.pairs):
      cx, cy = x + (i % columns) * (col_w + gap), y + (i // columns) * line
      self._text(label, cx, cy, size, LABEL_COLOR)
      alone = i == len(p.pairs) - 1 and i % columns == 0  # an odd last item has the whole row
      self._text(value, cx, cy, size, VALUE_COLOR, bold=True, right=right_edge if alone else cx + col_w)


class _TileRow(Widget):
  """A fixed size row with up to two tiles, the fonts do not shrink when there are many rows."""

  def __init__(self, width: float, height: float, pad: float, scale: float, label_cache: dict):
    super().__init__()
    self.set_rect(rl.Rectangle(0, 0, width, height))
    self._pad = pad
    self._label_size = int(22 * scale)
    self._value_size = int(35 * scale)
    self._value_font = gui_app.font(FontWeight.BOLD)
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
      if item.key == "today":
        text = today_text(item)
      elif item.key == "engine_temp":
        text = engine_text(item)
      elif item.key in DURATION_KEYS:
        text = format_duration(item.value) if item.valid else "--"
      else:
        text = format_value(item.value, item.unit, item.valid, 1 if item.key in ONE_DECIMAL_KEYS else None)
      amps = getattr(item, "amps", None)  # the 12 V battery: the current after the voltage, green charging / red draining
      amps_text = f"{abs(amps):.1f}A" if amps is not None and item.valid else None
      gap = self._value_size * 0.3
      text_w = tile.width - inner * 2
      size = self._value_size  # a long value (a long day: 123km/10h05m) gets a smaller font rather than being cut
      while size > self._value_size * 0.6 and self._width_of(text, amps_text, size, gap) > text_w:
        size -= 1
      value.set_text(text)
      value.set_font_size(size)
      label.render(rl.Rectangle(tile.x + inner, tile.y + top, tile.width - inner * 2, label_h))
      value_y = tile.y + top + label_h
      value.render(rl.Rectangle(tile.x + inner, value_y, tile.width - inner * 2, tile.y + tile.height - value_y))
      if amps_text is not None:
        color = CHARGING_COLOR if amps > AMPS_IDLE else DRAINING_COLOR if amps < -AMPS_IDLE else VALUE_COLOR
        x = tile.x + inner + measure_text_cached(self._value_font, text, size).x + gap
        rl.draw_text_ex(self._value_font, amps_text, rl.Vector2(round(x), round(value_y)), size, 0, color)  # top, as the label

  def _width_of(self, text: str, amps_text: str | None, size: int, gap: float) -> float:
    w = measure_text_cached(self._value_font, text, size).x
    return w + gap + measure_text_cached(self._value_font, amps_text, size).x if amps_text else w


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
    self._panel_rows: list[_PanelRow] = []
    self._layout_key: tuple = ()
    self._label_cache: dict = {}
    self._has_items = False
    self._stored: list = []
    self._stored_time = -10.0

  def _stored_items(self) -> list:
    if time.monotonic() - self._stored_time > 2.0:
      self._stored_time = time.monotonic()
      try:
        self._stored = stored_items(ui_state.params.get("DailyOdometer"), datetime.date.today().isoformat(), read_live())
      except Exception:
        self._stored = []
    return self._stored

  def _update_state(self) -> None:
    items = get_items(ui_state.sm) or self._stored_items()
    if (battery := voltage_item(ui_state.sm)) is not None:
      items = [*items, battery]
    panels = build_panels(items)  # the values read from the ECUs, one full-screen panel per group after the tiles
    amps = next((i for i in items if i.key == "diag_12v_a" and i.valid), None)
    if amps is not None:  # the 12 V tile shows the battery current read from the hybrid ECU next to the voltage
      items = [SimpleNamespace(key=i.key, label=i.label, value=i.value, unit=i.unit, valid=i.valid, amps=float(amps.value))
               if i.key == "battery_12v" else i for i in items]
    cabin = next((i for i in items if i.key == CABIN_SOURCE), None)
    if cabin is not None:
      items = [*items, SimpleNamespace(key="cabin", label="Cabin", value=cabin.value, unit="C", valid=cabin.valid)]
    items = merge_gearbox(items)
    items = order_items(complete_items(merge_today([i for i in items if not i.key.startswith(DIAG_PREFIX)])))
    self._has_items = bool(items)

    rows = rows_of(items)
    while len(self._rows) < len(rows):
      self._rows.append(_TileRow(self._width, self._tile_height, self._pad, self._scale, self._label_cache))
    del self._rows[len(rows):]
    while len(self._panel_rows) < len(panels):
      self._panel_rows.append(_PanelRow(self._width, self._tile_height * 2 + self._pad, self._pad, self._scale))
    del self._panel_rows[len(panels):]
    layout_key = (len(rows), len(panels))
    if layout_key != self._layout_key:  # rebuild the scroller only when the number of rows or panels changes
      self._layout_key = layout_key
      self._scroller.items.clear()
      for widget in (*self._rows, *self._panel_rows):
        self._scroller.add_widget(widget)
    for row, chunk in zip(self._rows, rows, strict=True):
      row.set_items(chunk)
    for row, panel in zip(self._panel_rows, panels, strict=True):
      row.set_panel(panel)

  def _render(self, rect: rl.Rectangle) -> None:
    rl.draw_rectangle_rec(rect, rl.BLACK)
    if not self._has_items:
      self._empty.render(rect)
      return
    self._scroller.render(rect)
