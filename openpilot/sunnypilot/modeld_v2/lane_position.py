"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
LEFT, CENTER, RIGHT = 1, 0, -1  # the LanePosition setting, the sign is the side of the offset (positive moves the car left)
CAR_WIDTH = 1.9  # m, body width
SIDE_MARGIN = 0.15  # m, the least that is kept between the side of the car and the lane line it hugs, whatever the setting says
MAX_SHIFT = 0.90  # m, never move further than this from the center of the lane
DEFAULT_SHIFT = 0.70  # m, how far the car moves towards the line (the HugLeftCm and HugRightCm settings)
MIN_LINE_PROB = 0.5  # both lane lines must be at least this sure, the lane width comes from them
MIN_LANE_WIDTH = 3.1  # m, in a narrower lane the car stays centered (also covers a mistake of the model)
RATE = 0.12  # m/s, how fast the car moves sideways towards the target
HOLD_SECONDS = 3.0  # keep the position for this long when the lane lines are lost, then go back to the center


# LanePosition: the sign is the side (positive left), the size the level (1 or 2), 0 is the center
HUG_KEYS = {(LEFT, 1): "HugLeft1Cm", (LEFT, 2): "HugLeft2Cm", (RIGHT, 1): "HugRight1Cm", (RIGHT, 2): "HugRight2Cm"}
OLD_HUG_KEYS = {"HugLeft2Cm": "HugLeftCm", "HugRight2Cm": "HugRightCm"}  # the settings of the one level version become level 2


def side_of(mode: int) -> int:
  return LEFT if mode > 0 else RIGHT if mode < 0 else CENTER


def level_of(mode: int) -> int:
  return 0 if mode == 0 else (2 if abs(mode) >= 2 else 1)


def wanted_shifts(mode: int, read_cm) -> tuple[float, float]:
  """The wanted shift towards the left and the right line in metres for this mode; read_cm(key) returns a setting in cm."""
  side = side_of(mode)
  if side == CENTER:
    return DEFAULT_SHIFT, DEFAULT_SHIFT
  shift = int(read_cm(HUG_KEYS[(side, level_of(mode))])) / 100.0
  return shift, shift


def migrate_hug_params(params) -> None:
  """Once: a distance set in the one level version becomes the level 2 distance (nothing happens when level 2 is set)."""
  for new, old in OLD_HUG_KEYS.items():
    if params.get(new) is None and params.get(old) is not None:
      params.put(new, int(params.get(old)))


def near_lane_line_position(y_points, count: int = 3) -> float:
  """Mean position of the first few points of a lane line, the ones closest to the car. y_points can be a capnp list, which
  does not support slicing, so the points are read by index."""
  n = min(count, len(y_points))
  if n == 0:
    raise ValueError("lane line without points")
  return sum(float(y_points[i]) for i in range(n)) / n


def model_lines_to_left_positive(left_line_y: float, right_line_y: float) -> tuple[float, float]:
  """The model reports y positive to the right (the left lane line is about -1.8, the right one +1.8), this module counts
  positive to the left like the camera offset does."""
  return -left_line_y, -right_line_y


def target_shift(mode: int, left_y: float, right_y: float, left_shift: float = DEFAULT_SHIFT, right_shift: float = DEFAULT_SHIFT) -> float:
  """Offset from the center of the lane: the wanted shift of the chosen side, but never closer to the line than SIDE_MARGIN.
  left_y and right_y are the positions of the two lane lines next to the car (left positive), the lane width is their
  difference, so it does not depend on the camera offset that is applied."""
  if mode == CENTER:
    return 0.0
  width = left_y - right_y
  if width < MIN_LANE_WIDTH:
    return 0.0
  room = max(width / 2 - CAR_WIDTH / 2 - SIDE_MARGIN, 0.0)
  wanted = left_shift if mode == LEFT else right_shift
  shift = min(max(wanted, 0.0), room, MAX_SHIFT)
  return shift if mode == LEFT else -shift


class LanePosition:
  """Moves the car towards the left or right lane line on request, as far as the model's own lane width allows, and back to
  the center. offset is the part to add to the camera offset (metres, positive moves the car left)."""

  def __init__(self):
    self.offset = 0.0
    self._lost = 0.0

  def update(self, mode: int, left_y: float, right_y: float, left_prob: float, right_prob: float, dt: float,
             left_shift: float = DEFAULT_SHIFT, right_shift: float = DEFAULT_SHIFT) -> float:
    lines_ok = left_prob >= MIN_LINE_PROB and right_prob >= MIN_LINE_PROB
    if mode == CENTER:
      target = 0.0
      self._lost = 0.0
    elif lines_ok:
      target = target_shift(mode, left_y, right_y, left_shift, right_shift)
      self._lost = 0.0
    else:
      self._lost += dt
      target = self.offset if self._lost <= HOLD_SECONDS else 0.0
    step = RATE * dt
    self.offset += min(max(target - self.offset, -step), step)
    return self.offset
