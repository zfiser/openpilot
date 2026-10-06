"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.selfdrive.ui.mici.onroad.hud_renderer import HudRenderer
from openpilot.selfdrive.ui.sunnypilot.mici.onroad.rpm import find_rpm, format_rpm
from openpilot.selfdrive.ui.sunnypilot.onroad.blind_spot_indicators import BlindSpotIndicators
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached

RPM_FONT_SIZE = 30
RPM_UNIT_FONT_SIZE = 22
RPM_UNIT_GAP = 6  # between the number and the unit
RPM_SMOOTHING_TAU = 0.25  # seconds, an exponential average, higher is smoother but slower to follow
RPM_TOP_OFFSET = 12  # distance of the text from the top edge of the road view
RPM_OPACITY = 0.6
RPM_COLOR = rl.Color(255, 255, 255, int(255 * RPM_OPACITY))


class HudRendererSP(HudRenderer):
  def __init__(self):
    super().__init__()
    self.blind_spot_indicators = BlindSpotIndicators()
    self._rpm_filter = FirstOrderFilter(0.0, RPM_SMOOTHING_TAU, 1 / gui_app.target_fps)
    self._rpm_font = gui_app.font(FontWeight.BOLD)
    self._rpm_text: str | None = None

  def _update_state(self) -> None:
    super()._update_state()
    self.blind_spot_indicators.update()

    rpm = find_rpm(ui_state.sm, ui_state.started_frame)
    if rpm is None or rpm <= 0:
      self._rpm_filter.x = 0.0  # engine off or unknown, hide the text
      self._rpm_text = None
    else:
      if self._rpm_filter.x <= 0:
        self._rpm_filter.x = rpm  # engine just started, take the real value instead of counting up from zero
      self._rpm_text = format_rpm(self._rpm_filter.update(rpm))

  def _render(self, rect: rl.Rectangle) -> None:
    super()._render(rect)
    self.blind_spot_indicators.render(rect)
    self._draw_rpm(rect)

  def _draw_rpm(self, rect: rl.Rectangle) -> None:
    """Engine RPM, top centre. Not drawn while the engine is off or the car does not report it."""
    if self._rpm_text is None:
      return
    # only the number is centred, the unit hangs off its right side and its bottom lines up with the number
    size = measure_text_cached(self._rpm_font, self._rpm_text, RPM_FONT_SIZE)
    unit_size = measure_text_cached(self._rpm_font, "rpm", RPM_UNIT_FONT_SIZE)
    pos = rl.Vector2(rect.x + rect.width / 2 - size.x / 2, rect.y + RPM_TOP_OFFSET)
    unit_pos = rl.Vector2(pos.x + size.x + RPM_UNIT_GAP, pos.y + size.y - unit_size.y - 2)
    rl.draw_text_ex(self._rpm_font, self._rpm_text, pos, RPM_FONT_SIZE, 0, RPM_COLOR)
    rl.draw_text_ex(self._rpm_font, "rpm", unit_pos, RPM_UNIT_FONT_SIZE, 0, RPM_COLOR)

  def _has_blind_spot_detected(self) -> bool:

    return self.blind_spot_indicators.detected
