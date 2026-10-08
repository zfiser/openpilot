"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import time

import pyray as rl
from openpilot.selfdrive.ui.mici.onroad import SIDE_PANEL_WIDTH
from openpilot.selfdrive.ui.mici.onroad.confidence_ball import ConfidenceBall
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.brake_indicator import friction_braking
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.gps_speed import gps_speed
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.lead_distance import CLOSING, OPENING, LeadTrend, lead_distance
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

WHITE = rl.Color(255, 255, 255, 255)
BLACK = rl.Color(0, 0, 0, 255)
TRAFFIC_RED = rl.Color(200, 32, 48, 255)
LEAD_CLOSING = rl.Color(255, 64, 64, 255)
LEAD_OPENING = rl.Color(64, 220, 96, 255)
SPEED_FONT_SIZE = 56  # digits a bit taller than the 50 px icons, three digits spill left over the road view
SPEED_RIGHT_MARGIN = 10
LEAD_FONT_SIZE = 32  # small, sits right above the GPS speed
LEAD_GAP = 0
BRAKE_DOT_RADIUS = 5  # a 10 px dot
BRAKE_DOT_GAP = 9  # between the dot and the GPS speed digits
BRAKE_DOT_COLOR = rl.Color(255, 90, 0, 255)
SPEED_BOTTOM_MARGIN = 10  # the text box has some padding below the digits, this lines them up with the wheel icon


class MiciSidebarWidgets(Widget):
  """Static confidence circle on top, a stop light in the middle while the planner wants to stop with no lead car and the
  GPS speed (a number, no unit) in the bottom corner."""

  def __init__(self, confidence_ball: ConfidenceBall):
    super().__init__()
    self._confidence_ball = confidence_ball
    self._speed_font = gui_app.font(FontWeight.BOLD)
    self._lead_trend = LeadTrend()
    self._speed_left = 0.0  # left edge and vertical centre of the GPS speed digits, where the brake dot goes next to
    self._speed_center_y = 0.0

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

    self._confidence_ball.render_static(confidence_slot, max(16, min(20, int(slot_height * 0.28))))
    if self._stop_light_visible():
      self._draw_stop_light_icon(indicator_slot)
    self._draw_gps_speed(rect)
    self._draw_lead_distance(rect)
    self._draw_brake_dot(rect)

  def _draw_gps_speed(self, rect: rl.Rectangle) -> None:
    """Right aligned in the bottom right corner of the screen, a number without a unit."""
    speed = gps_speed(ui_state.sm, ui_state.is_metric)
    text = str(speed) if speed is not None else "0"  # the dot keeps its place without a GPS fix
    measured = measure_text_cached(self._speed_font, text, SPEED_FONT_SIZE)
    pos = rl.Vector2(rect.x + rect.width - SPEED_RIGHT_MARGIN - measured.x, rect.y + rect.height - SPEED_BOTTOM_MARGIN - measured.y)
    self._speed_left = pos.x
    self._speed_center_y = pos.y + measured.y * 0.55
    if speed is None:
      return
    rl.draw_text_ex(self._speed_font, text, pos, SPEED_FONT_SIZE, 0, WHITE)

  def _draw_lead_distance(self, rect: rl.Rectangle) -> None:
    """Metres to the lead above the GPS speed, red while the gap shrinks, green while it grows."""
    distance = lead_distance(ui_state.sm, ui_state.started_frame)
    trend = self._lead_trend.update(distance, time.monotonic())
    if distance is None:
      return
    color = LEAD_CLOSING if trend == CLOSING else LEAD_OPENING if trend == OPENING else WHITE
    text = str(distance)
    measured = measure_text_cached(self._speed_font, text, LEAD_FONT_SIZE)
    speed_height = measure_text_cached(self._speed_font, "0", SPEED_FONT_SIZE).y
    pos = rl.Vector2(rect.x + rect.width - SPEED_RIGHT_MARGIN - measured.x,
                     rect.y + rect.height - SPEED_BOTTOM_MARGIN - speed_height - LEAD_GAP - measured.y)
    rl.draw_text_ex(self._speed_font, text, pos, LEAD_FONT_SIZE, 0, color)

  def _draw_brake_dot(self, rect: rl.Rectangle) -> None:
    """A dot left of the GPS speed digits while the friction brakes (not regen) are slowing the car. It is kept out of the
    middle of the sidebar, where the stop light icon shows up when stopping for a light, which is when the brakes are on."""
    if not friction_braking(ui_state.sm, ui_state.started_frame):
      return
    rl.draw_circle_v(rl.Vector2(self._speed_left - BRAKE_DOT_GAP - BRAKE_DOT_RADIUS, self._speed_center_y), BRAKE_DOT_RADIUS, BRAKE_DOT_COLOR)

  def _stop_light_visible(self) -> bool:
    # a stopped lead car also sets shouldStop, that is a car and not a red light, so a lead hides the icon
    try:
      if ui_state.sm["radarState"].leadOne.present:
        return False
      return bool(ui_state.sm.recv_frame["longitudinalPlan"] >= ui_state.started_frame and ui_state.sm["longitudinalPlan"].shouldStop)
    except Exception:
      return False

  def _draw_stop_light_icon(self, rect: rl.Rectangle) -> None:
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height / 2
    housing = rl.Rectangle(cx - 12, cy - 27, 24, 54)
    rl.draw_rectangle_rounded_lines_ex(housing, 0.35, 8, 3, WHITE)
    for bulb_y in (cy - 16, cy, cy + 16):
      rl.draw_circle_lines(int(cx), int(bulb_y), 6, WHITE)
    rl.draw_circle_lines(int(cx), int(cy - 16), 7, TRAFFIC_RED)
    rl.draw_circle(int(cx), int(cy - 16), 4, TRAFFIC_RED)
