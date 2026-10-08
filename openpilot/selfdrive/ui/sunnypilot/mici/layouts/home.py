"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import math

import pyray as rl

from openpilot.cereal import log
from openpilot.selfdrive.ui.mici.layouts.home import HOME_PADDING, MiciHomeLayout, NetworkIcon
from openpilot.selfdrive.ui.sunnypilot.mici.layouts.power_menu import PowerMenu
from openpilot.selfdrive.ui.sunnypilot.mici.layouts.quick_wifi import QuickWifiConnect
from openpilot.selfdrive.ui.ui_state import ui_state, ChestnutState
from openpilot.system.ui.lib.application import FontWeight, MousePos, gui_app
from openpilot.system.ui.widgets.label import UnifiedLabel


POWER_ICON_SIZE = (36, 38)
POWER_ICON_OPACITY = 0.7
POWER_ICON_PAD = 14  # extra touch area around the icon
ALERTS_PILL_WIDTH = 104  # the pill takes the bottom right corner while there are alerts, the power icon moves left of it


def power_icon_rect(home: rl.Rectangle, has_alerts: bool) -> rl.Rectangle:
  """Bottom right corner of the home screen, in line with the status icons."""
  width, height = POWER_ICON_SIZE
  right = home.x + home.width - HOME_PADDING - (ALERTS_PILL_WIDTH + 12 if has_alerts else 0)
  return rl.Rectangle(right - width, home.y + home.height - 48 + (48 - height) / 2, width, height)


def point_in(rect: rl.Rectangle, x: float, y: float, pad: float = 0.0) -> bool:
  return rect.x - pad <= x <= rect.x + rect.width + pad and rect.y - pad <= y <= rect.y + rect.height + pad


class MiciHomeLayoutSP(MiciHomeLayout):
  def __init__(self):
    super().__init__()
    self._openpilot_label = UnifiedLabel("sunnypilot", font_size=88, font_weight=FontWeight.AUDIOWIDE, max_width=480, wrap_text=False)

    # tapping the network icon connects to a saved network instead of opening settings
    self._network_icon = next(w for w in self._status_bar_layout.widgets if isinstance(w, NetworkIcon))
    self._power_icon = gui_app.texture("icons_mici/settings/device/power.png", *POWER_ICON_SIZE)
    self._quick_wifi = QuickWifiConnect(lambda: ui_state.sm['deviceState'].networkType == log.DeviceState.NetworkType.wifi)

  def _update_state(self):
    super()._update_state()
    self._quick_wifi.update()
    self._network_icon.set_pulsing(self._quick_wifi.connecting)

  def _has_alerts(self) -> bool:
    return bool(self._alert_count_callback and self._alert_count_callback() > 0)

  def _render(self, rect: rl.Rectangle):
    super()._render(rect)
    icon = power_icon_rect(self.rect, self._has_alerts())
    rl.draw_texture_ex(self._power_icon, rl.Vector2(icon.x, icon.y), 0.0, 1.0, rl.Color(255, 255, 255, int(255 * POWER_ICON_OPACITY)))

  def _handle_mouse_release(self, mouse_pos: MousePos):
    if not self._did_long_press and point_in(power_icon_rect(self.rect, self._has_alerts()), mouse_pos.x, mouse_pos.y, POWER_ICON_PAD):
      gui_app.push_widget(PowerMenu())
      return
    icon = self._network_icon.rect
    pad = 14  # a bit larger than the 54x44 icon, but well short of the settings icon next to it
    on_network_icon = (icon.x - pad <= mouse_pos.x <= icon.x + icon.width + pad and
                       icon.y - pad <= mouse_pos.y <= icon.y + icon.height + pad)
    if on_network_icon and not self._did_long_press:
      self._quick_wifi.tap()
      self._did_long_press = False
      return
    super()._handle_mouse_release(mouse_pos)

  def _set_chestnut_visibility(self):
    usb_connected = ui_state.usb_connected
    usb_unknown = ui_state.usb_unknown
    chestnut_state = ui_state.chestnut_state
    loading = chestnut_state == ChestnutState.LOADING

    self._usb_icon.set_visible(usb_connected and usb_unknown)
    self._chestnut_loading_icon.set_opacity(0.35 + 0.65 * (0.5 - 0.5 * math.cos(rl.get_time() * 6.0)))
    self._chestnut_loading_icon.set_visible(not usb_unknown and loading)
    self._chestnut_icon.set_visible(not usb_unknown and not loading and
                                    chestnut_state in (ChestnutState.READY, ChestnutState.ACTIVE))
    self._chestnut_failed_icon.set_visible(not usb_unknown and chestnut_state in (ChestnutState.UNCOMPILED, ChestnutState.FAILED))
