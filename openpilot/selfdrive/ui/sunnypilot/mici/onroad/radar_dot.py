"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Radar marker (the ShowRadarDot setting, "radar marker" in the toggles): where the car's radar has its lead, brackets by default.

The radar gives the distance only (radar_distance, the raw 0.05 m value, or the dashboard lead_distance when the car sends no
raw data), no sideways position. When openpilot's camera lead is the same car (its distance within 25 % / 5 m of the radar's)
the dot takes the camera's sideways offset, otherwise it sits on the predicted path at that distance.

Shapes (STYLE): "dot" (on the road under the car), "bar" (a car-wide strip on the road at its rear bumper), "brackets" (corner
marks around the car's rear, 1.8 x 1.5 m) and "chevron" (a triangle on the road under the car). The colour follows the radar's
own closing speed: amber, orange under ORANGE_TTC s to contact, red under RED_TTC s (when "CAR AHEAD" would fire).
Car space as the stock lead bar: x forward, y sideways, z down (the road is at path z + camera height).
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
AMBER = rl.Color(255, 190, 0, 255)
ORANGE = rl.Color(255, 120, 0, 255)
RED = rl.Color(255, 40, 40, 255)
ORANGE_TTC, RED_TTC = 4.0, 2.0  # s to contact at the radar's closing speed
MIN_CLOSING = 1.5  # m/s, slower is no closing (the warning's limit)
CAR_WIDTH, CAR_HEIGHT = 1.8, 1.5  # m, the box of the brackets and the width of the bar
STYLES = ("dot", "bar", "brackets", "chevron")
STYLE = "brackets"  # chosen 2026-11-18 from the preview (marker_*.png)


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


def radar_rel_speed(car_data) -> float | None:
  for item in car_data:
    if item.key == "radar_rel_speed":
      return float(item.value) if item.valid else None
  return None


def danger_color(distance: float, rel_speed: float | None) -> rl.Color:
  """Amber, orange or red by time to contact; amber without the radar's own speed."""
  if rel_speed is None or -rel_speed < MIN_CLOSING:
    return AMBER
  ttc = distance / -rel_speed
  return RED if ttc < RED_TTC else ORANGE if ttc < ORANGE_TTC else AMBER


def box_corners(point: np.ndarray) -> np.ndarray:
  """The car's rear as 4 car space points (road left, road right, top right, top left) around the road point under it."""
  x, y, z = point
  w = CAR_WIDTH / 2
  return np.array([[x, y - w, z], [x, y + w, z], [x, y + w, z - CAR_HEIGHT], [x, y - w, z - CAR_HEIGHT]], dtype=np.float32)


def bar_corners(point: np.ndarray, path: np.ndarray, z_offset: float) -> np.ndarray:
  """A car-wide strip on the road from the rear bumper back towards us (as the stock lead bar), 4 car space points."""
  x, y, _ = point
  xs = np.array([x, x - min(4.0, 0.2 * x)])
  zs = np.interp(xs, path[:, 0], path[:, 2]) + z_offset
  w = CAR_WIDTH / 2
  return np.array([[xs[0], y - w, zs[0]], [xs[0], y + w, zs[0]], [xs[1], y + w, zs[1]], [xs[1], y - w, zs[1]]], dtype=np.float32)


def project_all(transform: np.ndarray, points: np.ndarray) -> np.ndarray | None:
  p = transform @ points.T
  if (p[2] <= 1e-3).any():
    return None
  return (p[:2] / p[2]).T


MAX_BOX_WIDTH = 0.6  # share of the road view, a close car keeps readable brackets instead of ones past the screen edge


def fit_box(pts: np.ndarray, rect) -> np.ndarray:
  """Shrink the bracket box (screen points) around its centre to at most MAX_BOX_WIDTH of the view, then move it inside."""
  centre = pts.mean(axis=0)
  width = pts[:, 0].max() - pts[:, 0].min()
  limit = MAX_BOX_WIDTH * rect.width
  if width > limit:
    pts = centre + (pts - centre) * (limit / width)
  dx = max(rect.x - pts[:, 0].min(), 0.0) - max(pts[:, 0].max() - (rect.x + rect.width), 0.0)
  dy = max(rect.y - pts[:, 1].min(), 0.0) - max(pts[:, 1].max() - (rect.y + rect.height), 0.0)
  return pts + np.array([dx, dy], dtype=np.float32)


def _tri(a, b, c, color) -> None:
  """raylib draws a triangle only in one winding order: draw both."""
  rl.draw_triangle(a, b, c, color)
  rl.draw_triangle(a, c, b, color)


def radius(distance: float) -> float:
  return float(np.interp(distance, [10.0, 130.0], [RADIUS_NEAR, RADIUS_FAR]))


class RadarDot:
  def __init__(self, params, style: str = STYLE):
    self._options = DisplayOptions(params)
    self.style = style

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
      if not rect.x <= x <= rect.x + rect.width:
        return
      below = y > rect.y + rect.height  # a close car: the road under it is under the screen edge
      if self.style == "dot" and (below or y < rect.y):
        return
      color = danger_color(distance, radar_rel_speed(sm["carStateSP"].carData))
      offset = np.array([rect.x, rect.y], dtype=np.float32)
      if self.style == "bar":
        pts = project_all(renderer._car_space_transform, bar_corners(point, path, renderer._path_offset_z))
        if pts is not None:
          self._draw_bar(pts + offset, color)
      elif self.style == "brackets":
        pts = project_all(renderer._car_space_transform, box_corners(point))
        if pts is not None:
          self._draw_brackets(fit_box(pts + offset, rect), color)
      elif self.style == "chevron":
        size = radius(distance) * 1.6
        self._draw_chevron(x, min(y, rect.y + rect.height - size - 4.0), size, color)  # pinned to the bottom edge when close
      else:
        r = radius(distance)
        rl.draw_circle_v(rl.Vector2(x, y), r + 2.0, OUTLINE)
        rl.draw_circle_v(rl.Vector2(x, y), r, COLOR)
    except Exception:
      pass

  @staticmethod
  def _draw_bar(pts: np.ndarray, color: rl.Color) -> None:
    far_l, far_r, near_r, near_l = (rl.Vector2(float(p[0]), float(p[1])) for p in pts)
    # at least a few px deep, so a far car still shows a strip
    if near_l.y - far_l.y < 4.0:
      near_l, near_r = rl.Vector2(near_l.x, far_l.y + 4.0), rl.Vector2(near_r.x, far_r.y + 4.0)
    _tri(far_l, near_l, near_r, color)
    _tri(far_l, near_r, far_r, color)
    rl.draw_line_ex(far_l, far_r, 2.0, OUTLINE)

  @staticmethod
  def _draw_brackets(pts: np.ndarray, color: rl.Color) -> None:
    bl, br, tr, tl = pts
    w, h = br[0] - bl[0], bl[1] - tl[1]
    lw = float(np.clip(w * 0.06, 2.0, 5.0))
    for (cx, cy), (dx, dy) in (((tl[0], tl[1]), (1, 1)), ((tr[0], tr[1]), (-1, 1)), ((br[0], br[1]), (-1, -1)), ((bl[0], bl[1]), (1, -1))):
      corner = rl.Vector2(float(cx), float(cy))
      rl.draw_line_ex(corner, rl.Vector2(float(cx + dx * w * 0.28), float(cy)), lw, color)
      rl.draw_line_ex(corner, rl.Vector2(float(cx), float(cy + dy * h * 0.28)), lw, color)

  @staticmethod
  def _draw_chevron(x: float, y: float, size: float, color: rl.Color) -> None:
    apex, left, right = rl.Vector2(x, y), rl.Vector2(x - size * 1.1, y + size), rl.Vector2(x + size * 1.1, y + size)
    pad = 2.0
    outline = (rl.Vector2(x, y - pad * 1.5), rl.Vector2(left.x - pad * 1.5, left.y + pad), rl.Vector2(right.x + pad * 1.5, right.y + pad))
    _tri(*outline, OUTLINE)
    _tri(apex, left, right, color)
