"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Pull down on the driving screen: three big buttons over the camera picture, left / center / right. A side button cycles
level 1 <-> level 2 of that side, center turns the hug off. Closes 5 s after the last touch or on the next pull down.
"""
import time

import pyray as rl

from openpilot.selfdrive.ui.sunnypilot.mici.onroad.hug_logic import CENTER, LEFT, RIGHT, HugScreenState, PullDown, column_of, next_mode
from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached

PARAM = "LanePosition"
DISTANCE_KEYS = {(LEFT, 1): "HugLeft1Cm", (LEFT, 2): "HugLeft2Cm", (RIGHT, 1): "HugRight1Cm", (RIGHT, 2): "HugRight2Cm"}
BACKGROUND = rl.Color(0, 0, 0, 175)
BUTTON = rl.Color(255, 255, 255, 30)
ACTIVE = rl.Color(60, 220, 110, 110)
TEXT = rl.Color(255, 255, 255, 255)
DIM = rl.Color(255, 255, 255, 90)
TITLE_SIZE = 40
LINE_SIZE = 26
PAD = 12
READ_EVERY = 0.3  # s


def steering() -> bool:
  return ui_state.status not in (UIStatus.DISENGAGED, UIStatus.LONG_ONLY)


class HugScreen:
  """Drawn by the road view itself (not pushed as a page), so swiping between pages keeps working."""

  def __init__(self):
    self._pull = PullDown()
    self._state = HugScreenState()
    self._mode = 0
    self._distances = {key: 0 for key in DISTANCE_KEYS}
    self._next_read = 0.0
    self._font = gui_app.font(FontWeight.BOLD)
    self._font_line = gui_app.font(FontWeight.MEDIUM)

  @property
  def is_open(self) -> bool:
    return self._state.is_open

  @property
  def mode(self) -> int:
    return self._mode

  def _read(self, force: bool = False) -> None:
    if not force and time.monotonic() < self._next_read:
      return
    self._next_read = time.monotonic() + READ_EVERY
    try:
      self._mode = int(ui_state.params.get(PARAM, return_default=True))
      for side_level, key in DISTANCE_KEYS.items():
        self._distances[side_level] = int(ui_state.params.get(key, return_default=True))
    except Exception:
      self._mode = 0  # a setting the device does not know yet (before the reboot after an update)

  def update(self) -> None:
    self._read()
    self._state.update(time.monotonic())

  # touch, called by the road view
  def mouse_event(self, mouse_event) -> None:
    if mouse_event.left_pressed:
      self._pull.press(mouse_event.pos.x, mouse_event.pos.y)
      if self.is_open:
        self._state.touched(time.monotonic())
    elif mouse_event.left_down and self._pull.move(mouse_event.pos.x, mouse_event.pos.y):
      self._state.toggle(time.monotonic())
      self._read(force=True)

  def cancel_touch(self) -> None:
    self._pull.cancel()

  def take_release(self, x: float, rect: rl.Rectangle) -> bool:
    """True when the release belongs to the hug screen (a pull down or a button), so it must not go to the road view."""
    if self._pull.release():
      return True
    if not self.is_open:
      return False
    self._state.touched(time.monotonic())
    if steering():
      mode = next_mode(self._mode, column_of(x, rect.x, rect.width))
      try:
        ui_state.params.put(PARAM, mode)
        self._mode = mode
        self._next_read = time.monotonic() + 1.0  # show what was pressed, not the value from before the write
      except Exception:
        pass
    return True

  # drawing
  def _text(self, text: str, cx: float, y: float, size: int, color: rl.Color, font=None) -> None:
    font = font or self._font
    measured = measure_text_cached(font, text, size)
    rl.draw_text_ex(font, text, rl.Vector2(cx - measured.x / 2, y), size, 0, color)

  def render(self, rect: rl.Rectangle) -> None:
    if not self.is_open:
      return
    rl.draw_rectangle_rec(rect, BACKGROUND)
    active_steering = steering()
    color = TEXT if active_steering else DIM
    col_w = (rect.width - PAD * 4) / 3
    for i, side in enumerate((LEFT, CENTER, RIGHT)):
      tile = rl.Rectangle(rect.x + PAD + i * (col_w + PAD), rect.y + PAD, col_w, rect.height - 2 * PAD)
      active = (side == CENTER and self._mode == 0) or (side != CENTER and self._mode != 0 and (self._mode > 0) == (side > 0))
      rl.draw_rectangle_rounded(tile, 0.15, 8, ACTIVE if active and active_steering else BUTTON)
      cx = tile.x + tile.width / 2
      if side == CENTER:
        self._text("center", cx, tile.y + tile.height / 2 - TITLE_SIZE / 2, TITLE_SIZE, color)
        if not active_steering:
          self._text("not steering", cx, tile.y + tile.height - LINE_SIZE - PAD, LINE_SIZE, DIM, self._font_line)
        continue
      title = "< left" if side == LEFT else "right >"
      self._text(title, cx, tile.y + PAD * 2, TITLE_SIZE, color)
      current_level = (2 if abs(self._mode) >= 2 else 1) if active else 0
      for row, level in enumerate((1, 2)):
        line = f"{level}: {self._distances[(side, level)]} cm"
        y = tile.y + PAD * 2 + TITLE_SIZE + PAD * 2 + row * (LINE_SIZE + PAD)
        self._text(line, cx, y, LINE_SIZE, color if level == current_level else DIM, self._font_line)
