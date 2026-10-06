"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl
from openpilot.selfdrive.ui.mici.onroad import SIDE_PANEL_WIDTH
from openpilot.selfdrive.ui.mici.onroad.confidence_ball import ConfidenceBall
from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus
from openpilot.system.ui.widgets import Widget

WHITE = rl.Color(255, 255, 255, 255)
BLACK = rl.Color(0, 0, 0, 255)
BLUE = rl.Color(112, 192, 216, 255)
TRAFFIC_RED = rl.Color(200, 32, 48, 255)
STEER_ACTIVE = rl.Color(0, 255, 38, 255)
STEER_PAUSED = rl.Color(137, 146, 141, 255)
STEER_OFF = rl.Color(70, 70, 70, 255)


def _v(x: float, y: float) -> rl.Vector2:
  return rl.Vector2(float(x), float(y))


def _draw_line(x1: float, y1: float, x2: float, y2: float, thickness: float, color: rl.Color) -> None:
  rl.draw_line_ex(_v(x1, y1), _v(x2, y2), thickness, color)


def _draw_quad_outline(points: tuple[tuple[float, float], ...], thickness: float, color: rl.Color) -> None:
  for idx, start in enumerate(points):
    end = points[(idx + 1) % len(points)]
    _draw_line(start[0], start[1], end[0], end[1], thickness, color)


class MiciSidebarWidgets(Widget):
  """Static confidence circle on top, lead car / stop light in the middle, steering status at the bottom."""

  def __init__(self, confidence_ball: ConfidenceBall):
    super().__init__()
    self._confidence_ball = confidence_ball

  def _render(self, rect: rl.Rectangle) -> None:
    sidebar = rl.Rectangle(
      rect.x + rect.width - SIDE_PANEL_WIDTH,
      rect.y,
      SIDE_PANEL_WIDTH,
      rect.height,
    )
    rl.draw_rectangle(int(sidebar.x), int(sidebar.y), int(sidebar.width), int(sidebar.height), BLACK)

    slot_height = sidebar.height / 3
    confidence_slot = rl.Rectangle(sidebar.x, sidebar.y, sidebar.width, slot_height)
    indicator_slot = rl.Rectangle(sidebar.x, sidebar.y + slot_height, sidebar.width, slot_height)
    steering_slot = rl.Rectangle(sidebar.x, sidebar.y + slot_height * 2, sidebar.width, sidebar.height - slot_height * 2)

    self._confidence_ball.render_static(confidence_slot, max(16, min(20, int(slot_height * 0.28))))
    self._draw_indicator(indicator_slot)
    self._draw_steering_status(steering_slot)

  def _indicator_reason(self) -> str:
    # a lead is the reason for slowing or stopping when there is one, so it wins over the stop light
    try:
      if ui_state.sm["radarState"].leadOne.present:
        return "lead"
      if ui_state.sm.recv_frame["longitudinalPlan"] >= ui_state.started_frame and ui_state.sm["longitudinalPlan"].shouldStop:
        return "stop"
    except Exception:
      pass
    return "chill"

  def _draw_indicator(self, rect: rl.Rectangle) -> None:
    reason = self._indicator_reason()
    if reason == "lead":
      self._draw_lead_icon(rect)
    elif reason == "stop":
      self._draw_stop_light_icon(rect)
    else:
      self._draw_chill_icon(rect)

  def _draw_chill_icon(self, rect: rl.Rectangle) -> None:
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height / 2
    stroke = 3

    _draw_line(cx - 14, cy - 15, cx + 14, cy - 15, stroke, WHITE)
    _draw_line(cx - 16, cy - 13, cx - 16, cy + 1, stroke, WHITE)
    _draw_line(cx + 16, cy - 13, cx + 16, cy + 1, stroke, WHITE)
    _draw_line(cx - 19, cy + 3, cx + 19, cy + 3, stroke, WHITE)
    _draw_line(cx - 21, cy - 3, cx - 21, cy + 10, stroke, WHITE)
    _draw_line(cx + 21, cy - 3, cx + 21, cy + 10, stroke, WHITE)
    _draw_line(cx - 21, cy + 10, cx + 21, cy + 10, stroke, WHITE)
    _draw_line(cx - 14, cy + 6, cx + 14, cy + 6, 2, BLUE)
    _draw_line(cx - 14, cy + 12, cx - 17, cy + 19, stroke, WHITE)
    _draw_line(cx + 14, cy + 12, cx + 17, cy + 19, stroke, WHITE)

  def _draw_lead_icon(self, rect: rl.Rectangle) -> None:
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height / 2
    self._draw_car(cx, cy - 13, 31, 18, WHITE, TRAFFIC_RED)
    self._draw_car(cx, cy + 12, 43, 22, WHITE, TRAFFIC_RED)
    _draw_line(cx - 11, cy - 1, cx - 11, cy + 3, 2, rl.Color(255, 255, 255, 130))
    _draw_line(cx + 11, cy - 1, cx + 11, cy + 3, 2, rl.Color(255, 255, 255, 130))

  @staticmethod
  def _draw_car(cx: float, cy: float, width: float, height: float, color: rl.Color, accent: rl.Color) -> None:
    top = cy - height / 2
    bottom = cy + height / 2
    body = (
      (cx - width * 0.34, top + height * 0.10),
      (cx + width * 0.34, top + height * 0.10),
      (cx + width * 0.50, bottom - height * 0.04),
      (cx - width * 0.50, bottom - height * 0.04),
    )
    windshield = (
      (cx - width * 0.22, top + height * 0.24),
      (cx + width * 0.22, top + height * 0.24),
      (cx + width * 0.32, top + height * 0.50),
      (cx - width * 0.32, top + height * 0.50),
    )
    _draw_quad_outline(body, 3, color)
    _draw_quad_outline(windshield, 2, color)
    _draw_line(cx - width * 0.56, top + height * 0.46, cx - width * 0.50, top + height * 0.46, 2, color)
    _draw_line(cx + width * 0.50, top + height * 0.46, cx + width * 0.56, top + height * 0.46, 2, color)
    _draw_line(cx - width * 0.32, bottom - height * 0.22, cx - width * 0.16, bottom - height * 0.22, 2, accent)
    _draw_line(cx + width * 0.16, bottom - height * 0.22, cx + width * 0.32, bottom - height * 0.22, 2, accent)

  def _draw_stop_light_icon(self, rect: rl.Rectangle) -> None:
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height / 2
    housing = rl.Rectangle(cx - 12, cy - 27, 24, 54)
    rl.draw_rectangle_rounded_lines_ex(housing, 0.35, 8, 3, WHITE)
    for bulb_y in (cy - 16, cy, cy + 16):
      rl.draw_circle_lines(int(cx), int(bulb_y), 6, WHITE)
    rl.draw_circle_lines(int(cx), int(cy - 16), 7, TRAFFIC_RED)
    rl.draw_circle(int(cx), int(cy - 16), 4, TRAFFIC_RED)

  @staticmethod
  def _steering_color() -> rl.Color:
    # ui_state.status already folds in MADS: paused/overriding is reported as override
    if ui_state.status in (UIStatus.ENGAGED, UIStatus.LAT_ONLY):
      return STEER_ACTIVE
    if ui_state.status == UIStatus.OVERRIDE:
      return STEER_PAUSED
    return STEER_OFF

  def _draw_steering_status(self, rect: rl.Rectangle) -> None:
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height / 2
    color = self._steering_color()
    radius = 17

    rl.draw_ring(_v(cx, cy), radius - 3, radius, 0, 360, 40, color)
    rl.draw_circle(int(cx), int(cy), 4, color)
    _draw_line(cx - radius + 2, cy, cx - 4, cy, 3, color)
    _draw_line(cx + 4, cy, cx + radius - 2, cy, 3, color)
    _draw_line(cx, cy + 4, cx, cy + radius - 2, 3, color)
