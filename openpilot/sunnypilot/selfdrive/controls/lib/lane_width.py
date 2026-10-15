"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Width of the lane next to the car, ported from StarPilot (starpilot/common/starpilot_utilities.py, calculate_lane_width).
"""
import numpy as np


def calculate_lane_width(lane_line1, lane_line2, road_edge=None) -> float:
  """Median distance between two lane lines along the length of the second one, in metres. 0 when the road edge is closer
  to the second line than the first line is: there is no lane, only the shoulder or the gore. The lines are the usual model
  lines with x and y lists (modelV2.laneLines and roadEdges)."""
  line1_x, line1_y = np.asarray(lane_line1.x), np.asarray(lane_line1.y)
  line2_x, line2_y = np.asarray(lane_line2.x), np.asarray(lane_line2.y)
  if len(line1_x) < 2 or len(line2_x) < 2:
    return 0.0

  line1_y_at_line2 = np.interp(line2_x, line1_x, line1_y)
  distance_to_lane = np.median(np.abs(line2_y - line1_y_at_line2))

  if road_edge is None or len(road_edge.x) < 2:
    return float(distance_to_lane)

  edge_y_at_line2 = np.interp(line2_x, np.asarray(road_edge.x), np.asarray(road_edge.y))
  distance_to_road_edge = np.median(np.abs(line2_y - edge_y_at_line2))
  if distance_to_road_edge < distance_to_lane:
    return 0.0
  return float(distance_to_lane)


UPDATE_EVERY = 4  # frames, like StarPilot: the width is measured every 4th model frame
DEFAULT_MIN_LANE_WIDTH = 2.8  # m, the RoadEdgeMinLaneWidth setting
NOTICE_AFTER = 3.0  # s after the blinker before "no lane" is shown: a lane that is just opening up often comes in time


class WaitNotice:
  """Whether to show the "no lane" notice: only once the lane change has waited NOTICE_AFTER seconds since the blinker.
  The wait itself is not changed, only the notice is postponed."""

  def __init__(self, notice_after: float = NOTICE_AFTER):
    self._notice_after = notice_after
    self._waited = 0.0

  def update(self, pre_lane_change: bool, waiting_for_lane: bool, dt: float) -> bool:
    if not pre_lane_change:
      self._waited = 0.0
      return False
    self._waited += dt
    return waiting_for_lane and self._waited >= self._notice_after


class AdjacentLaneWidth:
  """Width of the lane on the left and on the right of the car, refreshed every few frames. 0 means no lane."""

  def __init__(self):
    self.left = 0.0
    self.right = 0.0
    self._frame = 0

  def update(self, lane_lines, road_edges) -> tuple[float, float]:
    if self._frame % UPDATE_EVERY == 0:
      self.left = calculate_lane_width(lane_lines[0], lane_lines[1], road_edges[0] if len(road_edges) > 0 else None)
      self.right = calculate_lane_width(lane_lines[3], lane_lines[2], road_edges[1] if len(road_edges) > 1 else None)
    self._frame += 1
    return self.left, self.right
