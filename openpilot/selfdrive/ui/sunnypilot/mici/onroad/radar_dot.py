"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Radar dot (the ShowRadarDot setting): a yellow dot on the road where the car's radar has its lead.

The radar gives the distance only (radar_distance, the raw 0.05 m value, or the dashboard lead_distance when the car sends no
raw data), no sideways position. When openpilot's camera lead is the same car (its distance within 25 % / 5 m of the radar's)
the dot takes the camera's sideways offset, otherwise it sits on the predicted path at that distance.
"""
import numpy as np
import pyray as rl

from openpilot.selfdrive.ui.sunnypilot.mici.onroad.display_options import RADAR_DOT, DisplayOptions
from openpilot.selfdrive.ui.ui_state import ui_state

RADAR_TO_CAMERA = 1.52  # m, the radar is ahead of the camera (same value as radard)
VISION_MATCH = 0.25  # the camera lead is the same car within this share of the distance (at least VISION_MATCH_MIN m)
VISION_MATCH_MIN = 5.0
RADIUS_NEAR, RADIUS_FAR = 14.0, 6.0  # px at 10 m and at 130 m
COLOR = rl.Color(255, 214, 0, 255)
OUTLINE = rl.Color(0, 0, 0, 160)


def radar_lead_distance(car_data) -> float | None:
  """The radar lead distance in metres: the raw radar item when the car sends it, else the dashboard number, None without."""
  raw = dashboard = None
  raw_seen = False
  for item in car_data:
    if item.key == "radar_distance":
      raw_seen = True
      raw = float(item.value) if item.valid else None
    elif item.key == "lead_distance":
      dashboard = float(item.value) if item.valid else None
  return raw if raw_seen else dashboard


def dot_point(distance: float, path: np.ndarray, camera_offset: float, z_offset: float,
              vision: tuple[float, float] | None) -> np.ndarray:
  """The dot in car space (x forward, y left, z): at distance + RADAR_TO_CAMERA from the camera. vision = (dRel, yRel) of the
  camera lead, used for the sideways position when it is the same car; else the path's y at that distance."""
  x = distance + RADAR_TO_CAMERA
  if vision is not None and abs(vision[0] - distance) <= max(VISION_MATCH_MIN, VISION_MATCH * distance):
    y = -vision[1] + camera_offset  # yRel is positive to the right, car space y to the left (as the stock lead bar)
  else:
    y = float(np.interp(x, path[:, 0], path[:, 1]))  # the path points already carry the camera offset
  z = float(np.interp(x, path[:, 0], path[:, 2])) + z_offset
  return np.array([x, y, z], dtype=np.float32)


def project(transform: np.ndarray, point: np.ndarray) -> tuple[float, float] | None:
  """Screen position of a car space point (renderer rect coordinates), None when behind the camera."""
  p = transform @ point
  if p[2] <= 1e-3:
    return None
  return float(p[0] / p[2]), float(p[1] / p[2])


def radius(distance: float) -> float:
  return float(np.interp(distance, [10.0, 130.0], [RADIUS_NEAR, RADIUS_FAR]))


class RadarDot:
  def __init__(self, params):
    self._options = DisplayOptions(params)

  def draw(self, renderer, sm) -> None:
    """Called by the mici model renderer after the path. Never raises: the driving screen must keep drawing."""
    try:
      started = ui_state.started_frame  # received during this drive (as the other driving screen extras), not sm.valid
      if not self._options.enabled(RADAR_DOT) or sm.recv_frame["carStateSP"] < started:
        return
      distance = radar_lead_distance(sm["carStateSP"].carData)
      path = renderer._path.raw_points
      if distance is None or distance <= 0 or len(path) == 0:
        return
      lead = sm["radarState"].leadOne if sm.recv_frame["radarState"] >= started else None
      vision = (lead.dRel, lead.yRel) if lead is not None and lead.present else None
      point = dot_point(distance, path, renderer._camera_offset, renderer._path_offset_z, vision)
      screen = project(renderer._car_space_transform, point)
      if screen is None:
        return
      rect = renderer._rect
      x, y = rect.x + screen[0], rect.y + screen[1]
      if not (rect.x <= x <= rect.x + rect.width and rect.y <= y <= rect.y + rect.height):
        return
      r = radius(distance)
      rl.draw_circle_v(rl.Vector2(x, y), r + 2.0, OUTLINE)
      rl.draw_circle_v(rl.Vector2(x, y), r, COLOR)
    except Exception:
      pass
