"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
LEFT, CENTER, RIGHT = 1, 0, -1  # the LanePosition setting, the sign is the side of the offset (positive moves the car left)
CAR_WIDTH = 1.9  # m, body width
SIDE_MARGIN = 0.40  # m kept between the side of the car and the lane line it hugs
MAX_SHIFT = 0.60  # m, never move further than this from the center of the lane
MIN_LINE_PROB = 0.5  # both lane lines must be at least this sure, the lane width comes from them
MIN_LANE_WIDTH = 2.6  # m, narrower than this is not a lane (a mistake of the model), stay centered
RATE = 0.12  # m/s, how fast the car moves sideways towards the target
HOLD_SECONDS = 3.0  # keep the position for this long when the lane lines are lost, then go back to the center


def near_lane_line_position(y_points, count: int = 3) -> float:
  """Mean position of the first few points of a lane line, the ones closest to the car. y_points can be a capnp list, which
  does not support slicing, so the points are read by index."""
  n = min(count, len(y_points))
  if n == 0:
    raise ValueError("lane line without points")
  return sum(float(y_points[i]) for i in range(n)) / n


def target_shift(mode: int, left_y: float, right_y: float) -> float:
  """Offset from the center of the lane that leaves SIDE_MARGIN between the car and the line on the chosen side.
  left_y and right_y are the positions of the two lane lines next to the car (left positive), the lane width is their
  difference, so it does not depend on the camera offset that is applied."""
  if mode == CENTER:
    return 0.0
  width = left_y - right_y
  if width < MIN_LANE_WIDTH:
    return 0.0
  shift = min(max(width / 2 - CAR_WIDTH / 2 - SIDE_MARGIN, 0.0), MAX_SHIFT)
  return shift if mode == LEFT else -shift


class LanePosition:
  """Moves the car towards the left or right lane line on request, as far as the model's own lane width allows, and back to
  the center. offset is the part to add to the camera offset (metres, positive moves the car left)."""

  def __init__(self):
    self.offset = 0.0
    self._lost = 0.0

  def update(self, mode: int, left_y: float, right_y: float, left_prob: float, right_prob: float, dt: float) -> float:
    lines_ok = left_prob >= MIN_LINE_PROB and right_prob >= MIN_LINE_PROB
    if mode == CENTER:
      target = 0.0
      self._lost = 0.0
    elif lines_ok:
      target = target_shift(mode, left_y, right_y)
      self._lost = 0.0
    else:
      self._lost += dt
      target = self.offset if self._lost <= HOLD_SECONDS else 0.0
    step = RATE * dt
    self.offset += min(max(target - self.offset, -step), step)
    return self.offset
