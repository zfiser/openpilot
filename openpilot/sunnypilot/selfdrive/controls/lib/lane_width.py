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
