"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Pull down on the driving screen: three big buttons over the camera picture, left / auto / right. A side button cycles
level 1 <-> level 2 of that side (and turns the automatic hug off), the middle one turns the automatic hug on or off.
Closes 5 s after the last touch or on the next pull down.

While the car hugs a line, a tall narrow arrow sits at that edge of the camera picture ('<' left, '>' right). A tap on it
ends a manual hug, or pauses the automatic one until the next lane change.
"""
import time

import pyray as rl

from openpilot.selfdrive.ui.sunnypilot.mici.onroad.hug_logic import (CANCEL_MANUAL, CENTER, LEFT, PAUSE_AUTO, RIGHT, HugScreenState,
                                                                     PullDown, arrow_hit, arrow_points, arrow_tap, column_of, press)
from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached

PARAM = "LanePosition"
AUTO_PARAM = "AutoHug"
PAUSE_PARAM = "AutoHugPause"
DISTANCE_KEYS = {(LEFT, 1): "HugLeft1Cm", (LEFT, 2): "HugLeft2Cm", (RIGHT, 1): "HugRight1Cm", (RIGHT, 2): "HugRight2Cm"}
BACKGROUND = rl.Color(0, 0, 0, 175)
BUTTON = rl.Color(255, 255, 255, 30)
ACTIVE = rl.Color(60, 220, 110, 110)
TEXT = rl.Color(255, 255, 255, 255)
DIM = rl.Color(255, 255, 255, 90)
ARROW_COLOR = rl.Color(60, 220, 110, 255)
ARROW_SHADOW = rl.Color(0, 0, 0, 160)
ARROW_THICKNESS = 9.0
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
    self._auto = False
    self._distances = {key: 0 for key in DISTANCE_KEYS}
    self._next_read = 0.0
    self._press_pos: tuple[float, float] | None = None
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
      self._auto = bool(ui_state.params.get_bool(AUTO_PARAM))
      for side_level, key in DISTANCE_KEYS.items():
        self._distances[side_level] = int(ui_state.params.get(key, return_default=True))
    except Exception:
      self._mode, self._auto = 0, False  # a setting the device does not know yet (before the reboot after an update)

  def update(self) -> None:
    self._read()
    self._state.update(time.monotonic())

  def hug_side(self) -> int:
    """The side the car hugs now, from the model process (manual or automatic), CENTER when unknown."""
    try:
      sm = ui_state.sm
      if not steering() or sm.recv_frame["modelDataV2SP"] < ui_state.started_frame:
        return CENTER
      side = int(sm["modelDataV2SP"].hugSide)
      return LEFT if side > 0 else RIGHT if side < 0 else CENTER
    except Exception:
      return CENTER

  # touch, called by the road view
  def mouse_event(self, mouse_event) -> None:
    if mouse_event.left_pressed:
      self._press_pos = (mouse_event.pos.x, mouse_event.pos.y)
      self._pull.press(mouse_event.pos.x, mouse_event.pos.y)
      if self.is_open:
        self._state.touched(time.monotonic())
    elif mouse_event.left_down and self._pull.move(mouse_event.pos.x, mouse_event.pos.y):
      self._state.toggle(time.monotonic())
      self._read(force=True)

  def cancel_touch(self) -> None:
    self._pull.cancel()
    self._press_pos = None

  def _put(self, mode: int, auto: bool) -> None:
    try:
      if auto != self._auto:
        ui_state.params.put_bool(AUTO_PARAM, auto)
      if mode != self._mode:
        ui_state.params.put(PARAM, mode)
      self._mode, self._auto = mode, auto
      self._next_read = time.monotonic() + 1.0  # show what was pressed, not the value from before the write
    except Exception:
      pass

  def _arrow_tapped(self, pos, content: rl.Rectangle) -> bool:
    side = self.hug_side()
    if side == CENTER or self._press_pos is None:
      return False
    box = (content.x, content.y, content.width, content.height)
    if not (arrow_hit(side, pos.x, pos.y, *box) and arrow_hit(side, self._press_pos[0], self._press_pos[1], *box)):
      return False
    action = arrow_tap(self._mode, self._auto)
    try:
      if action == CANCEL_MANUAL:
        self._put(0, self._auto)
      elif action == PAUSE_AUTO:
        ui_state.params.put_bool(PAUSE_PARAM, True)
    except Exception:
      pass
    return True

  def take_release(self, pos, rect: rl.Rectangle, content: rl.Rectangle) -> bool:
    """True when the release belongs to the hug screen (a pull down, a button or an arrow), so it must not go to the road
    view."""
    if self._pull.release():
      return True
    if not self.is_open:
      tapped = self._arrow_tapped(pos, content)
      self._press_pos = None
      return tapped
    self._press_pos = None
    self._state.touched(time.monotonic())
    column = column_of(pos.x, rect.x, rect.width)
    if column == CENTER or steering():  # the automatic hug can be set any time, a manual one only while steering
      self._put(*press(self._mode, self._auto, column))
    return True

  # drawing
  def _text(self, text: str, cx: float, y: float, size: int, color: rl.Color, font=None) -> None:
    font = font or self._font
    measured = measure_text_cached(font, text, size)
    rl.draw_text_ex(font, text, rl.Vector2(cx - measured.x / 2, y), size, 0, color)

  def _draw_arrow(self, side: int, content: rl.Rectangle) -> None:
    a, b, c = (rl.Vector2(x, y) for x, y in arrow_points(side, content.x, content.y, content.width, content.height))
    for color, thickness in ((ARROW_SHADOW, ARROW_THICKNESS + 6), (ARROW_COLOR, ARROW_THICKNESS)):
      rl.draw_line_ex(a, b, thickness, color)
      rl.draw_line_ex(b, c, thickness, color)
      rl.draw_circle_v(b, thickness / 2, color)  # a round tip instead of a gap between the two lines

  def render(self, rect: rl.Rectangle, content=None) -> None:  # content: the camera picture rectangle (rl.Rectangle)
    if not self.is_open:
      side = self.hug_side()
      if side != CENTER and content is not None:
        self._draw_arrow(side, content)
      return
    rl.draw_rectangle_rec(rect, BACKGROUND)
    active_steering = steering()
    color = TEXT if active_steering else DIM
    col_w = (rect.width - PAD * 4) / 3
    for i, side in enumerate((LEFT, CENTER, RIGHT)):
      tile = rl.Rectangle(rect.x + PAD + i * (col_w + PAD), rect.y + PAD, col_w, rect.height - 2 * PAD)
      cx = tile.x + tile.width / 2
      if side == CENTER:
        rl.draw_rectangle_rounded(tile, 0.15, 8, ACTIVE if self._auto else BUTTON)
        self._text("auto", cx, tile.y + tile.height / 2 - TITLE_SIZE, TITLE_SIZE, TEXT)
        self._text("ON" if self._auto else "OFF", cx, tile.y + tile.height / 2 + PAD / 2, TITLE_SIZE, TEXT if self._auto else DIM)
        if not active_steering:
          self._text("not steering", cx, tile.y + tile.height - LINE_SIZE - PAD, LINE_SIZE, DIM, self._font_line)
        continue
      active = self._mode != 0 and (self._mode > 0) == (side > 0)
      rl.draw_rectangle_rounded(tile, 0.15, 8, ACTIVE if active and active_steering else BUTTON)
      title = "< left" if side == LEFT else "right >"
      self._text(title, cx, tile.y + PAD * 2, TITLE_SIZE, color)
      current_level = (2 if abs(self._mode) >= 2 else 1) if active else 0
      for row, level in enumerate((1, 2)):
        line = f"{level}: {self._distances[(side, level)]} cm"
        y = tile.y + PAD * 2 + TITLE_SIZE + PAD * 2 + row * (LINE_SIZE + PAD)
        self._text(line, cx, y, LINE_SIZE, color if level == current_level else DIM, self._font_line)
