"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.selfdrive.ui.mici.layouts.settings.device import EngagedConfirmationCircleButton
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets.scroller import NavScroller


class PowerMenu(NavScroller):
  """Reboot and power off, the same two buttons (and the same slide to confirm) as at the end of the device settings.
  Opened from the power icon on the home screen, swipe down to close it."""

  def __init__(self):
    super().__init__()

    def reboot_callback():
      ui_state.params.put_bool("DoReboot", True, block=True)

    def power_off_callback():
      ui_state.params.put_bool("DoShutdown", True, block=True)

    reboot_btn = EngagedConfirmationCircleButton("reboot", gui_app.texture("icons_mici/settings/device/reboot.png", 64, 70),
                                                 reboot_callback, exit_on_confirm=False)
    power_off_btn = EngagedConfirmationCircleButton("power off", gui_app.texture("icons_mici/settings/device/power.png", 64, 66),
                                                    power_off_callback, exit_on_confirm=False, red=True)
    power_off_btn.set_visible(lambda: not ui_state.ignition)  # same rule as the device settings

    self._scroller.add_widgets([reboot_btn, power_off_btn])
