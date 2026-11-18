"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from types import SimpleNamespace

import numpy as np

from openpilot.selfdrive.ui.sunnypilot.mici.onroad.radar_dot import AMBER, ORANGE, RADAR_TO_CAMERA, RED, RadarDot, danger_color, \
  dot_point, fit_box, project, radar_lead_distance, radius


def item(key, value, valid=True):
  return SimpleNamespace(key=key, value=value, valid=valid)


PATH = np.array([[x, 0.02 * x, -0.01 * x] for x in np.linspace(0, 150, 31)], dtype=np.float32)  # bends a little to the left


class TestRadarDot:
  def test_raw_radar_before_the_dashboard(self):
    assert radar_lead_distance([item("lead_distance", 69.0), item("radar_distance", 69.2)]) == 69.2
    assert radar_lead_distance([item("lead_distance", 69.0)]) == 69.0  # no raw data from this car
    assert radar_lead_distance([item("lead_distance", 69.0), item("radar_distance", 0.0, False)]) is None  # the radar: no lead
    assert radar_lead_distance([]) is None

  def test_on_the_path_without_a_matching_camera_lead(self):
    p = dot_point(50.0, PATH, 0.0, 1.35, None)
    x = 50.0 + RADAR_TO_CAMERA
    assert np.allclose(p, [x, 0.02 * x, -0.01 * x + 1.35], atol=1e-4)
    p = dot_point(50.0, PATH, 0.0, 1.35, (20.0, 1.5))  # the camera lead is another car (20 m): ignored
    assert abs(p[1] - 0.02 * x) < 1e-4

  def test_camera_offset_for_the_same_car(self):
    p = dot_point(69.2, PATH, 0.08, 1.35, (64.7, 0.5))  # within 25 %: the camera's sideways offset, 0.5 m to the right
    assert abs(p[1] - (-0.5 + 0.08)) < 1e-6

  def test_project(self):
    T = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    assert project(T, np.array([2.0, 4.0, 2.0])) == (1.0, 2.0)
    assert project(T, np.array([2.0, 4.0, -1.0])) is None  # behind the camera

  def test_radius_shrinks_with_distance(self):
    assert radius(5.0) == radius(10.0) > radius(60.0) > radius(130.0) == radius(200.0)

  def test_draw_never_raises(self):
    dot = RadarDot(SimpleNamespace(get=lambda k, return_default=True: True))
    dot.draw(SimpleNamespace(), {})  # broken inputs: nothing drawn, no exception

  def test_danger_color(self):
    assert danger_color(40.0, None) == AMBER and danger_color(40.0, 2.0) == AMBER  # no speed, or pulling away
    assert danger_color(40.0, -5.0) == AMBER  # 8 s
    assert danger_color(15.0, -5.0) == ORANGE  # 3 s
    assert danger_color(8.0, -5.0) == RED  # 1.6 s

  def test_fit_box(self):
    rect = SimpleNamespace(x=0.0, y=0.0, width=500.0, height=240.0)
    big = np.array([[-100, 300], [600, 300], [600, -50], [-100, -50]], dtype=np.float32)
    out = fit_box(big, rect)
    assert out[:, 0].max() - out[:, 0].min() <= 300.0 + 1e-3
    assert out[:, 0].min() >= 0 and out[:, 0].max() <= 500 and out[:, 1].min() >= 0 and out[:, 1].max() <= 240
    small = np.array([[200, 120], [260, 120], [260, 80], [200, 80]], dtype=np.float32)
    assert np.allclose(fit_box(small, rect), small)
