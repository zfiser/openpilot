"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl
from openpilot.selfdrive.ui.mici.onroad import SIDE_PANEL_WIDTH
from openpilot.selfdrive.ui.mici.onroad.confidence_ball import ConfidenceBall
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, TextAlignment, TextAlignmentVertical
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.label import UnifiedLabel

WHITE = rl.Color(255, 255, 255, 255)
BLACK = rl.Color(0, 0, 0, 255)
TRAFFIC_RED = rl.Color(200, 32, 48, 255)
WHITE_DIM = rl.Color(255, 255, 255, 150)
M_TO_FT = 3.28084


def lead_distance_parts(d_rel: float, is_metric: bool) -> tuple[str, str]:
  """Number and unit shown for the gap to the lead car."""
  if is_metric:
    return str(round(d_rel)), "m"
  return str(round(d_rel * M_TO_FT)), "ft"


def _v(x: float, y: float) -> rl.Vector2:
  return rl.Vector2(float(x), float(y))


def _draw_line(x1: float, y1: float, x2: float, y2: float, thickness: float, color: rl.Color) -> None:
  rl.draw_line_ex(_v(x1, y1), _v(x2, y2), thickness, color)


def _draw_quad_outline(points: tuple[tuple[float, float], ...], thickness: float, color: rl.Color) -> None:
  for idx, start in enumerate(points):
    end = points[(idx + 1) % len(points)]
    _draw_line(start[0], start[1], end[0], end[1], thickness, color)


class MiciSidebarWidgets(Widget):
  """Static confidence circle on top, single car when there is a lead / stop light in the middle, distance to the lead car at the bottom."""

  def __init__(self, confidence_ball: ConfidenceBall):
    super().__init__()
    self._confidence_ball = confidence_ball
    self._distance_value = UnifiedLabel("", 28, FontWeight.BOLD, WHITE, alignment=TextAlignment.CENTER,
                                        alignment_vertical=TextAlignmentVertical.BOTTOM, wrap_text=False, elide=False)
    self._distance_unit = UnifiedLabel("", 16, FontWeight.MEDIUM, WHITE_DIM, alignment=TextAlignment.CENTER,
                                       alignment_vertical=TextAlignmentVertical.TOP, wrap_text=False, elide=False)

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
    distance_slot = rl.Rectangle(sidebar.x, sidebar.y + slot_height * 2, sidebar.width, sidebar.height - slot_height * 2)

    self._confidence_ball.render_static(confidence_slot, max(16, min(20, int(slot_height * 0.28))))
    self._draw_indicator(indicator_slot)
    self._draw_lead_distance(distance_slot)

  def _lead_distance(self) -> float | None:
    try:
      lead = ui_state.sm["radarState"].leadOne
      return float(lead.dRel) if lead.present else None
    except Exception:
      return None

  def _draw_lead_distance(self, rect: rl.Rectangle) -> None:
    d_rel = self._lead_distance()
    if d_rel is None:
      return

    value, unit = lead_distance_parts(d_rel, ui_state.is_metric)
    self._distance_value.set_text(value)
    self._distance_unit.set_text(unit)
    half = rect.height / 2
    self._distance_value.render(rl.Rectangle(rect.x, rect.y + half * 0.4, rect.width, half * 0.9))
    self._distance_unit.render(rl.Rectangle(rect.x, rect.y + half * 1.3, rect.width, half * 0.6))

  def _indicator_reason(self) -> str:
    # a lead is the reason for slowing or stopping when there is one, so it wins over the stop light
    try:
      if ui_state.sm["radarState"].leadOne.present:
        return "lead"
      if ui_state.sm.recv_frame["longitudinalPlan"] >= ui_state.started_frame and ui_state.sm["longitudinalPlan"].shouldStop:
        return "stop"
    except Exception:
      pass
    return "none"

  def _draw_indicator(self, rect: rl.Rectangle) -> None:
    reason = self._indicator_reason()
    if reason == "lead":
      self._draw_lead_icon(rect)
    elif reason == "stop":
      self._draw_stop_light_icon(rect)

  def _draw_lead_icon(self, rect: rl.Rectangle) -> None:
    self._draw_car(rect.x + rect.width / 2, rect.y + rect.height / 2, 46, 24, WHITE, TRAFFIC_RED)

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
