import math
import pyray as rl
from openpilot.selfdrive.ui.mici.onroad import SIDE_PANEL_WIDTH
from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.lib.application import gui_app
from openpilot.common.filter_simple import FirstOrderFilter

from openpilot.selfdrive.ui.sunnypilot.mici.onroad.confidence_ball import ConfidenceBallSP


def draw_circle_gradient(center_x: float, center_y: float, radius: int,
                         top: rl.Color, bottom: rl.Color) -> None:
  # Draw a square with the gradient
  rl.draw_rectangle_gradient_v(int(center_x - radius), int(center_y - radius),
                               radius * 2, radius * 2,
                               top, bottom)

  # Paint over square with a ring
  outer_radius = math.ceil(radius * math.sqrt(2)) + 1
  rl.draw_ring(rl.Vector2(int(center_x), int(center_y)), radius, outer_radius,
               0.0, 360.0,
               20, rl.BLACK)


BORDER_ORANGE = rl.Color(255, 140, 0, 255)
BORDER_RED = rl.Color(255, 0, 21, 255)


def confidence_zone(confidence: float) -> str:
  """The same thresholds the circle colours use: green above 50%, orange above 20%, red below."""
  return "high" if confidence > 0.5 else "medium" if confidence > 0.2 else "low"


class ConfidenceBall(Widget, ConfidenceBallSP):
  def __init__(self, demo: bool = False):
    Widget.__init__(self)
    ConfidenceBallSP.__init__(self)
    self._demo = demo
    self._confidence_filter = FirstOrderFilter(-0.5, 0.5, 1 / gui_app.target_fps)

  def update_filter(self, value: float):
    self._confidence_filter.update(value)

  def _update_state(self):
    if self._demo:
      return

    # animate status dot in from bottom
    if ui_state.status == UIStatus.DISENGAGED:
      self._confidence_filter.update(-0.5)
    elif ui_state.status == UIStatus.OVERRIDE:
      return  # the driver is steering or pedalling, keep the confidence from just before
    elif ui_state.status in (UIStatus.LAT_ONLY, UIStatus.LONG_ONLY):
      self._confidence_filter.update(1 - max(self.get_animate_status_probs() or [1]))
    else:
      self._confidence_filter.update((1 - max(ui_state.sm['modelV2'].meta.disengagePredictions.brakeDisengageProbs or [1])) *
                                                        (1 - max(ui_state.sm['modelV2'].meta.disengagePredictions.steerOverrideProbs or [1])))

  def _dot_colors(self) -> tuple[rl.Color, rl.Color]:
    # confidence zones, also in lateral only, longitudinal only and while overriding (traffic light colours, not the flat mode colours)
    if ui_state.status in (UIStatus.ENGAGED, UIStatus.LAT_ONLY, UIStatus.LONG_ONLY, UIStatus.OVERRIDE) or self._demo:
      zone = confidence_zone(self._confidence_filter.x)
      if zone == "high":
        top_dot_color = rl.Color(0, 255, 204, 255)
        bottom_dot_color = rl.Color(0, 255, 38, 255)
      elif zone == "medium":
        top_dot_color = rl.Color(255, 200, 0, 255)
        bottom_dot_color = rl.Color(255, 115, 0, 255)
      else:
        top_dot_color = rl.Color(255, 0, 21, 255)
        bottom_dot_color = rl.Color(255, 0, 89, 255)

    else:
      top_dot_color = rl.Color(50, 50, 50, 255)
      bottom_dot_color = rl.Color(13, 13, 13, 255)

    return top_dot_color, bottom_dot_color

  def border_color(self) -> "rl.Color | None":  # a string, rl.Color is a function in pyray and cannot be used with |
    """Colour of a 1 px frame around the whole screen while the confidence is lower, None when it is high or not engaged."""
    if ui_state.status not in (UIStatus.ENGAGED, UIStatus.LAT_ONLY, UIStatus.LONG_ONLY):
      return None
    return {"medium": BORDER_ORANGE, "low": BORDER_RED}.get(confidence_zone(self._confidence_filter.x))

  def render_static(self, rect: rl.Rectangle, radius: int = 20) -> None:
    self._update_state()
    top_dot_color, bottom_dot_color = self._dot_colors()
    draw_circle_gradient(rect.x + rect.width / 2,
                         rect.y + rect.height / 2,
                         radius,
                         top_dot_color,
                         bottom_dot_color)

  def _render(self, _):
    content_rect = rl.Rectangle(
      self.rect.x + self.rect.width - SIDE_PANEL_WIDTH,
      self.rect.y,
      SIDE_PANEL_WIDTH,
      self.rect.height,
    )

    status_dot_radius = 24
    dot_height = (1 - self._confidence_filter.x) * (content_rect.height - 2 * status_dot_radius) + status_dot_radius
    dot_height = self._rect.y + dot_height

    top_dot_color, bottom_dot_color = self._dot_colors()

    draw_circle_gradient(content_rect.x + content_rect.width - status_dot_radius,
                         dot_height, status_dot_radius,
                         top_dot_color, bottom_dot_color)
