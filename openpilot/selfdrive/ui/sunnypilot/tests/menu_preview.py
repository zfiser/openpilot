#!/usr/bin/env python3
"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Renders the toggles menu and its pages headless and saves a PNG of each:  menu_preview.py OUT_DIR
"""
import os
import sys

import pyray as rl

from openpilot.common.prefix import OpenpilotPrefix


def main() -> None:
  out_dir = sys.argv[1]
  os.makedirs(out_dir, exist_ok=True)
  rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN)
  os.environ["OFFSCREEN"] = "1"

  with OpenpilotPrefix():
    from openpilot.selfdrive.ui.tests.diff.replay import setup_state
    setup_state()

    from openpilot.selfdrive.ui.ui_state import ui_state, device
    from openpilot.system.ui.lib.application import gui_app

    gui_app.init_window("menu preview", fps=60)
    device.set_override_interactive_timeout(99999)

    from openpilot.selfdrive.ui.sunnypilot.mici.layouts import quick_settings as qs
    pages = [("0_menu", qs.TogglesMenu()), ("1_steering", qs.steering_panel()), ("2_lane_change", qs.lane_change_panel()),
             ("3_blinker", qs.blinker_panel()), ("4_screen", qs.screen_panel()), ("5_driving_screen", qs.driving_screen_panel()),
             ("6_other", qs.TogglesLayoutMici())]

    step, wait = 0, 0
    gui_app.push_widget(pages[0][1])
    for _ in gui_app.render():
      ui_state.update()
      wait += 1
      if wait > 50:
        name = pages[step][0]
        image = rl.load_image_from_screen()
        rl.export_image(image, os.path.join(out_dir, f"{name}.png"))
        rl.unload_image(image)
        print("saved", name)
        gui_app.pop_widget()
        step, wait = step + 1, 0
        if step >= len(pages):
          break
        gui_app.push_widget(pages[step][1])
    gui_app.close()


if __name__ == "__main__":
  main()
