"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Automatic hug (the AutoHug setting): from 50 km/h, hug the left lane line in the left-most lane, the right lane line in the
right-most lane and stay centered in any lane in between.

Which lane: the distance from the car's own lane line to the road edge on that side. Next to the left-most lane the left road
edge is only the shoulder away (1-2 m), with a lane in between it is a lane plus the shoulder (5-8 m). The width of the lane
next to the car (AdjacentLaneWidth) does not work for this: the model reports a 3 m hard shoulder as a lane. Checked against
the video of a 144 minute highway drive (6 Nov 2026): 16 of 17 frames right, the 17th said middle, never the wrong side.
"""
from openpilot.sunnypilot.modeld_v2.lane_position import CENTER, LEFT, RIGHT

LANE_ON = 4.5  # m from the own lane line to the road edge: from here on there is a lane on that side
LANE_OFF = 4.0  # m, below this there is none any more (in between the last answer stays)
HOLD_SECONDS = 2.0  # the lane answer must stay the same this long before the hug side changes (after a lane change too)
DISAGREE_SECONDS = 1.0  # back to the center while the lane seen now has differed from the held one this long (a lane change
                        # without openpilot, or the lanes are changing), until the new answer is held
MIN_SPEED = 13.9  # m/s (50 km/h): starts hugging from here on (was 80 km/h until 2026-11-14)
STOP_SPEED = 11.1  # m/s (40 km/h), stops hugging below this

LEFTMOST, MIDDLE, RIGHTMOST, UNKNOWN = "leftmost", "middle", "rightmost", "unknown"
SIDE_OF_LANE = {LEFTMOST: LEFT, RIGHTMOST: RIGHT}


def lane_of(lane_left: bool, lane_right: bool) -> str:
  if lane_right and not lane_left:
    return LEFTMOST
  if lane_left and not lane_right:
    return RIGHTMOST
  if lane_left and lane_right:
    return MIDDLE
  return UNKNOWN  # no lane on either side: a one lane road, or the model is unsure


class SideLane:
  """Whether there is a lane on one side, from the distance to the road edge, with a band in between that keeps the answer."""

  def __init__(self):
    self.present = False

  def update(self, edge_distance: float) -> bool:
    if edge_distance >= LANE_ON:
      self.present = True
    elif edge_distance < LANE_OFF:
      self.present = False
    return self.present


class AutoHug:
  """Picks the side to hug. update() returns LEFT, RIGHT or CENTER (the LanePosition sides) every model frame.

  pause(): the driver cancelled the hug by tapping the arrow. The car stays centered until the lane changes (the lane answer
  becomes a different one, or a lane change of openpilot finishes), then the automatic hug carries on."""

  def __init__(self):
    self._left = SideLane()
    self._right = SideLane()
    self.lane = UNKNOWN  # the held answer
    self._candidate = UNKNOWN
    self._candidate_time = 0.0
    self._fast = False
    self._paused_in: str | None = None  # the lane the pause was made in, None while not paused
    self._was_changing = False
    self._disagree_time = 0.0

  @property
  def paused(self) -> bool:
    return self._paused_in is not None

  def pause(self) -> None:
    self._paused_in = self.lane

  def reset(self) -> None:
    """Off, or openpilot is not steering: start from scratch next time (a pause ends too)."""
    self.__init__()

  def update(self, left_edge_distance: float, right_edge_distance: float, v_ego: float, lane_changing: bool, dt: float) -> int:
    """left/right_edge_distance: metres from the own lane line to the road edge on that side (positive).
    lane_changing: openpilot is changing lanes (from the blinker until it is done)."""
    if v_ego >= MIN_SPEED:
      self._fast = True
    elif v_ego < STOP_SPEED:
      self._fast = False

    finished_change = self._was_changing and not lane_changing
    self._was_changing = lane_changing
    if finished_change:
      self.lane = UNKNOWN  # the answer was about the old lane, the new one is found again (HOLD_SECONDS)
      self._paused_in = None

    seen = lane_of(self._left.update(left_edge_distance), self._right.update(right_edge_distance))
    if seen == self._candidate and not finished_change:
      self._candidate_time += dt
    else:
      self._candidate, self._candidate_time = seen, 0.0
    if self._candidate_time >= HOLD_SECONDS and self._candidate != self.lane:
      self.lane = self._candidate

    if self._paused_in is not None and self.lane != self._paused_in:
      self._paused_in = None  # a different lane: the driver changed lanes (with or without openpilot)

    self._disagree_time = 0.0 if seen == self.lane else self._disagree_time + dt
    if not self._fast or lane_changing or self.paused or self._disagree_time > DISAGREE_SECONDS:
      return CENTER
    return SIDE_OF_LANE.get(self.lane, CENTER)


def edge_distances(left_line_y: float, right_line_y: float, left_edge_y: float, right_edge_y: float) -> tuple[float, float]:
  """Model y (positive to the right) of the own lane lines and of the road edges, near the car -> metres from each own line to
  the road edge on its side."""
  return left_line_y - left_edge_y, right_edge_y - right_line_y
