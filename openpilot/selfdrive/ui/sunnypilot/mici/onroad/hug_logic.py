"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

The logic of the pull down hug screen and of the hug arrows on the driving screen, without any drawing: which mode a button
press gives, when a drag is a pull down, when the screen closes by itself and where the arrows are. The modes are the
LanePosition setting read by the model process (see sunnypilot/modeld_v2/lane_position.py): the sign is the side (positive
left), the size the level 1 or 2, 0 the center. AutoHug is the automatic hug (sunnypilot/modeld_v2/auto_hug.py).
"""
LEFT, CENTER, RIGHT = 1, 0, -1
PULL_DOWN_MIN = 40.0  # px down before a drag opens (or closes) the screen
SIDEWAYS_MAX = 12.0  # px sideways, beyond that the page scroller takes the drag
CLOSE_AFTER = 5.0  # s after the last touch


def next_mode(current: int, pressed: int) -> int:
  """Left or right: from anywhere else level 1 of that side, then level 1 <-> level 2. Center: 0."""
  if pressed == CENTER:
    return 0
  if (current > 0) == (pressed > 0) and current != 0:
    level = 1 if abs(current) >= 2 else 2
  else:
    level = 1
  return level * pressed


def column_of(x: float, left: float, width: float) -> int:
  """The button under x: the left third, the middle third or the right third."""
  third = width / 3.0
  if x < left + third:
    return LEFT
  if x < left + 2 * third:
    return CENTER
  return RIGHT


class PullDown:
  """Turns a press and the following movement into one pull down. A release after a pull down is not a tap."""

  def __init__(self, min_down: float = PULL_DOWN_MIN, max_sideways: float = SIDEWAYS_MAX):
    self._min_down = min_down
    self._max_sideways = max_sideways
    self._start: tuple[float, float] | None = None
    self._fired = False

  def press(self, x: float, y: float) -> None:
    self._start = (x, y)
    self._fired = False

  def move(self, x: float, y: float) -> bool:
    """True once per press, when the drag has gone far enough down and not too far sideways."""
    if self._start is None or self._fired:
      return False
    dx, dy = x - self._start[0], y - self._start[1]
    if abs(dx) >= self._max_sideways:
      self._start = None  # a sideways swipe, the pages scroll
      return False
    if dy >= self._min_down:
      self._fired = True
      return True
    return False

  def release(self) -> bool:
    """True when this press was a pull down, so the release must not count as a tap."""
    fired = self._fired
    self._start, self._fired = None, False
    return fired

  def cancel(self) -> None:
    self._start, self._fired = None, False


class HugScreenState:
  """Open or closed, closing CLOSE_AFTER seconds after the last touch."""

  def __init__(self, close_after: float = CLOSE_AFTER):
    self._close_after = close_after
    self.is_open = False
    self._last_touch = 0.0

  def open(self, now: float) -> None:
    self.is_open = True
    self._last_touch = now

  def close(self) -> None:
    self.is_open = False

  def toggle(self, now: float) -> None:
    if self.is_open:
      self.close()
    else:
      self.open(now)

  def touched(self, now: float) -> None:
    self._last_touch = now

  def update(self, now: float) -> None:
    if self.is_open and now - self._last_touch >= self._close_after:
      self.is_open = False


def press(current_mode: int, auto_on: bool, column: int) -> tuple[int, bool]:
  """A button of the pull down screen -> (LanePosition, AutoHug). Left / right: a manual hug, which turns the automatic one
  off so the two never fight. Middle: the automatic hug on or off, both from the center."""
  if column == CENTER:
    return 0, not auto_on
  return next_mode(current_mode, column), False


# the arrow on the driving screen while the car hugs a line: tall and narrow, at the edge of the camera picture on that side
ARROW_WIDTH = 34.0
ARROW_HEIGHT = 136.0  # starts below the engine rpm in the top left corner (centred in the 240 px screen: top at 52 px)
ARROW_MARGIN = 16.0  # px from the edge of the camera picture
ARROW_TOUCH_WIDTH = 140.0  # px from the edge, the arrow is easy to hit while driving
ARROW_TOUCH_HEIGHT = 280.0


def arrow_box(side: int, x: float, y: float, width: float, height: float) -> tuple[float, float, float, float]:
  """(left, top, width, height) of the arrow of this side in the camera picture rectangle (x, y, width, height)."""
  top = y + (height - ARROW_HEIGHT) / 2
  left = x + ARROW_MARGIN if side == LEFT else x + width - ARROW_MARGIN - ARROW_WIDTH
  return left, top, ARROW_WIDTH, ARROW_HEIGHT


def arrow_points(side: int, x: float, y: float, width: float, height: float) -> tuple[tuple[float, float], ...]:
  """The three points of the chevron, the tip on the outside: '<' on the left, '>' on the right."""
  left, top, w, h = arrow_box(side, x, y, width, height)
  tip_x, back_x = (left, left + w) if side == LEFT else (left + w, left)
  return (back_x, top), (tip_x, top + h / 2), (back_x, top + h)


def arrow_hit(side: int, px: float, py: float, x: float, y: float, width: float, height: float) -> bool:
  if side == CENTER:
    return False
  if abs(py - (y + height / 2)) > ARROW_TOUCH_HEIGHT / 2:
    return False
  return x <= px <= x + ARROW_TOUCH_WIDTH if side == LEFT else x + width - ARROW_TOUCH_WIDTH <= px <= x + width


CANCEL_MANUAL, PAUSE_AUTO = "cancel_manual", "pause_auto"


def arrow_tap(manual_mode: int, auto_on: bool) -> str | None:
  """What a tap on the arrow does: a manual hug ends (centered), an automatic one pauses until the next lane change."""
  if manual_mode != 0:
    return CANCEL_MANUAL
  if auto_on:
    return PAUSE_AUTO
  return None
