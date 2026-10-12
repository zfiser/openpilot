"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from types import SimpleNamespace

import numpy as np

from openpilot.sunnypilot.selfdrive.controls.lib.lane_width import calculate_lane_width

X = np.linspace(0, 100, 33)


def line(y):
  """A model line: y given as a constant or a list over the 33 points."""
  return SimpleNamespace(x=X.tolist(), y=(np.full_like(X, y) if np.isscalar(y) else np.asarray(y)).tolist())


class TestLaneWidth:
  def test_normal_lane(self):
    # left neighbour lane: lines at -5.4 (outer) and -1.8 (the one next to the car)
    assert abs(calculate_lane_width(line(-1.8), line(-5.4)) - 3.6) < 1e-6

  def test_the_right_side_gives_the_same_distance(self):
    assert abs(calculate_lane_width(line(1.8), line(5.5)) - 3.7) < 1e-6

  def test_a_road_edge_closer_than_the_first_line_means_no_lane(self):
    # the shoulder: the road edge sits right beside the outer line
    assert calculate_lane_width(line(-1.8), line(-3.0), line(-2.9)) == 0.0

  def test_a_road_edge_beyond_the_outer_line_keeps_the_lane(self):
    assert abs(calculate_lane_width(line(-1.8), line(-5.4), line(-7.0)) - 3.6) < 1e-6

  def test_a_split_the_gore_near_the_car_does_not_count(self):
    # a wide lane that opens up: narrow for the first 20 m, 3.6 m for the rest. The median looks at the whole length
    outer = np.where(X < 20, -3.2, -5.4)
    assert abs(calculate_lane_width(line(-1.8), line(outer)) - 3.6) < 1e-6

  def test_a_narrow_lane_stays_narrow(self):
    assert abs(calculate_lane_width(line(-1.8), line(-3.9)) - 2.1) < 1e-6

  def test_missing_points_are_no_lane(self):
    assert calculate_lane_width(SimpleNamespace(x=[], y=[]), line(-5.4)) == 0.0
    assert calculate_lane_width(line(-1.8), SimpleNamespace(x=[1.0], y=[-5.0])) == 0.0
    assert abs(calculate_lane_width(line(-1.8), line(-5.4), SimpleNamespace(x=[], y=[])) - 3.6) < 1e-6
