"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.selfdrive.ui.mici.onroad.hud_renderer import HudRenderer
from openpilot.selfdrive.ui.sunnypilot.mici.onroad import display_options
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.rpm import find_rpm, format_rpm
from openpilot.selfdrive.ui.sunnypilot.mici.layouts.diag_panels import oil_temp_text
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.hug_logic import ARROW_MARGIN, ARROW_WIDTH, LEFT
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.hug_screen import current_hug_side
from openpilot.selfdrive.ui.sunnypilot.onroad.blind_spot_indicators import BlindSpotIndicators
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached

RPM_FONT_SIZE = 30
RPM_UNIT_FONT_SIZE = 22
RPM_UNIT_GAP = 6  # between the number and the unit
RPM_SMOOTHING_TAU = 0.25  # seconds, an exponential average, higher is smoother but slower to follow
RPM_TOP_OFFSET = 12  # distance of the text from the top edge of the road view
RPM_LEFT_OFFSET = 16  # distance of the number from the left edge of the road view (the hug arrow uses the same margin)
RPM_COLOR = rl.Color(255, 255, 255, 255)  # white with a black outline, readable in sunlight
RPM_OUTLINE_COLOR = rl.Color(0, 0, 0, 255)
RPM_OUTLINE = 2  # px
OIL_FONT_SIZE = 30  # the engine oil temperature, on its own line under the rpm (as big as the rpm number, readable while driving)
OIL_LINE_GAP = 1  # px between the rpm line and the oil line
OIL_ICON_W, OIL_ICON_GAP = 12, 6  # px, the small thermometer in front of the number
OIL_COLOR = rl.Color(255, 255, 255, 255)
OIL_ARROW_CLEAR = ARROW_MARGIN + ARROW_WIDTH + 12  # px from the left edge: the oil line starts here while the left hug arrow shows
RPM_OUTLINE_OFFSETS = [(dx * RPM_OUTLINE, dy * RPM_OUTLINE) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


class HudRendererSP(HudRenderer):
  def __init__(self):
    super().__init__()
    self.blind_spot_indicators = BlindSpotIndicators()
    self._rpm_filter = FirstOrderFilter(0.0, RPM_SMOOTHING_TAU, 1 / gui_app.target_fps)
    self._rpm_font = gui_app.font(FontWeight.BOLD)
    self._rpm_text: str | None = None
    self._oil_text: str | None = None  # "oil 92°", read from the engine ECU once a minute (diag_oil_temp)
    self._options = display_options.DisplayOptions(ui_state.params)
    self._sp_engaged: bool = False

  def _update_state(self) -> None:
    super()._update_state()
    self.blind_spot_indicators.update()

    rpm = find_rpm(ui_state.sm, ui_state.started_frame) if self._options.enabled(display_options.RPM) else None
    if rpm is None or rpm <= 0:
      self._rpm_filter.x = 0.0  # engine off or unknown, hide the text
      self._rpm_text = None
    else:
      if self._rpm_filter.x <= 0:
        self._rpm_filter.x = rpm  # engine just started, take the real value instead of counting up from zero
      self._rpm_text = format_rpm(self._rpm_filter.update(rpm))
    try:
      started = ui_state.sm.recv_frame["carStateSP"] >= ui_state.started_frame
      self._oil_text = oil_temp_text(ui_state.sm["carStateSP"].carData) if started else None
    except Exception:
      self._oil_text = None

    sp_engaged = ui_state.engaged
    if sp_engaged != self._sp_engaged:
      self._chestnut_fade_time = rl.get_time() if sp_engaged else 0
    self._sp_engaged = sp_engaged

  def _render(self, rect: rl.Rectangle) -> None:
    super()._render(rect)
    self.blind_spot_indicators.render(rect)
    self._draw_rpm(rect)

  def _draw_rpm(self, rect: rl.Rectangle) -> None:
    """Engine RPM, top left. Not drawn while the engine is off or the car does not report it, nor while an alert is on
    screen (changing lane, pay attention and so on), as the alert uses the same place."""
    if (self._rpm_text is None and self._oil_text is None) or not self._can_draw_top_icons:
      return
    # the number starts at the left margin, the unit follows on its right and its bottom lines up with the number; the oil
    # temperature goes on the next line with a small thermometer, or on the first line while the rpm is not shown
    pos = rl.Vector2(rect.x + RPM_LEFT_OFFSET, rect.y + RPM_TOP_OFFSET)
    number_h = measure_text_cached(self._rpm_font, "0", RPM_FONT_SIZE).y
    parts = []
    oil_y = pos.y
    if self._rpm_text is not None:
      size = measure_text_cached(self._rpm_font, self._rpm_text, RPM_FONT_SIZE)
      unit_y = pos.y + number_h - measure_text_cached(self._rpm_font, "rpm", RPM_UNIT_FONT_SIZE).y - 2
      parts += [(self._rpm_text, rl.Vector2(pos.x, pos.y), RPM_FONT_SIZE, RPM_COLOR),
                ("rpm", rl.Vector2(pos.x + size.x + RPM_UNIT_GAP, unit_y), RPM_UNIT_FONT_SIZE, RPM_COLOR)]
      oil_y = pos.y + number_h + OIL_LINE_GAP
    if self._oil_text is not None:
      oil_h = measure_text_cached(self._rpm_font, self._oil_text, OIL_FONT_SIZE).y
      oil_x = rect.x + OIL_ARROW_CLEAR if current_hug_side() == LEFT else pos.x  # the left arrow's top end is right there
      self._draw_thermometer(oil_x, oil_y + oil_h * 0.12, oil_h * 0.78)
      parts.append((self._oil_text, rl.Vector2(oil_x + OIL_ICON_W + OIL_ICON_GAP, oil_y), OIL_FONT_SIZE, OIL_COLOR))
    for text, text_pos, font_size, color in parts:
      for dx, dy in RPM_OUTLINE_OFFSETS:
        rl.draw_text_ex(self._rpm_font, text, rl.Vector2(text_pos.x + dx, text_pos.y + dy), font_size, 0, RPM_OUTLINE_COLOR)
      rl.draw_text_ex(self._rpm_font, text, text_pos, font_size, 0, color)

  def _draw_thermometer(self, x: float, y: float, height: float) -> None:
    """A tiny thermometer (stem and bulb), white with the same black outline as the text."""
    bulb_r = OIL_ICON_W / 2
    stem_w = OIL_ICON_W * 0.45
    cx = x + bulb_r
    stem = rl.Rectangle(cx - stem_w / 2, y, stem_w, height - bulb_r)
    bulb = rl.Vector2(cx, y + height - bulb_r)
    o = RPM_OUTLINE
    rl.draw_rectangle_rounded(rl.Rectangle(stem.x - o, stem.y - o, stem.width + 2 * o, stem.height + 2 * o), 1.0, 6, RPM_OUTLINE_COLOR)
    rl.draw_circle_v(bulb, bulb_r + o, RPM_OUTLINE_COLOR)
    rl.draw_rectangle_rounded(stem, 1.0, 6, OIL_COLOR)
    rl.draw_circle_v(bulb, bulb_r, OIL_COLOR)

  def _has_blind_spot_detected(self) -> bool:

    return self.blind_spot_indicators.detected
