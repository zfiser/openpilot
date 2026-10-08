"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl
from openpilot.selfdrive.ui.mici.onroad import SIDE_PANEL_WIDTH
from openpilot.selfdrive.ui.mici.onroad.confidence_ball import ConfidenceBall
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.gps_speed import gps_speed
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

WHITE = rl.Color(255, 255, 255, 255)
BLACK = rl.Color(0, 0, 0, 255)
TRAFFIC_RED = rl.Color(200, 32, 48, 255)
SPEED_FONT_SIZES = (34, 30, 26, 22)  # biggest that fits the sidebar width, a bit bigger than the icons
SPEED_BOTTOM_MARGIN = 14  # same distance from the bottom edge as the steering wheel icon


class MiciSidebarWidgets(Widget):
  """Static confidence circle on top, a stop light in the middle while the planner wants to stop with no lead car and the
  GPS speed (a number, no unit) in the bottom corner."""

  def __init__(self, confidence_ball: ConfidenceBall):
    super().__init__()
    self._confidence_ball = confidence_ball
    self._speed_font = gui_app.font(FontWeight.BOLD)

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
    self._draw_gps_speed(sidebar)

  def _draw_gps_speed(self, sidebar: rl.Rectangle) -> None:
    speed = gps_speed(ui_state.sm, ui_state.is_metric)
    if speed is None:
      return
    text = str(speed)
    for size in SPEED_FONT_SIZES:
      measured = measure_text_cached(self._speed_font, text, size)
      if measured.x <= sidebar.width - 6:
        break
    pos = rl.Vector2(sidebar.x + (sidebar.width - measured.x) / 2, sidebar.y + sidebar.height - SPEED_BOTTOM_MARGIN - measured.y)
    rl.draw_text_ex(self._speed_font, text, pos, size, 0, WHITE)

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
