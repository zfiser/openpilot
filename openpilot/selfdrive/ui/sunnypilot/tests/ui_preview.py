#!/usr/bin/env python3
"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Open the mici UI in a window on a PC with fake onroad data, to look at the sidebar and the car data page.

  python selfdrive/ui/sunnypilot/tests/ui_preview.py

Drag with the mouse to swipe (left from the road view reaches the car data page). Keys 1-5 pick a scenario.
Add --shots DIR to render every scenario headless and save PNGs of the road view and the car data page.
"""
import argparse
import os

import pyray as rl

from openpilot.cereal import log, messaging
from openpilot.cereal.messaging import PubMaster
from openpilot.common.prefix import OpenpilotPrefix

# name -> (lead car, planner stop, openpilot state enabled, car data items as (key, label, value, unit, valid))
SCENARIOS = {
  rl.KeyboardKey.KEY_ONE: ("engaged, no lead", False, False, True, [("odometer", "Odometer", 54321.0, "km", True)]),
  rl.KeyboardKey.KEY_TWO: ("lead car", True, False, True, [("odometer", "Odometer", 54321.0, "km", True)]),
  rl.KeyboardKey.KEY_THREE: ("stop light", False, True, True, [("odometer", "Odometer", 54321.0, "km", True)]),
  rl.KeyboardKey.KEY_FOUR: ("disengaged, odometer missing", False, False, False, [("odometer", "Odometer", 0.0, "km", False)]),
  rl.KeyboardKey.KEY_FIVE: ("many items", True, False, True, [
    ("odometer", "Odometer", 54321.0, "km", True), ("tire_fl", "Tire FL", 36.5, "psi", True),
    ("tire_fr", "Tire FR", 35.0, "psi", True), ("battery", "12V battery", 13.84, "V", True),
    ("hv", "Hybrid battery", 62.0, "%", True), ("temp", "Outside temp", -3.0, "C", True)]),
}


def send_state(pm: PubMaster, scenario) -> None:
  _, lead, stop, enabled, items = scenario

  ds = messaging.new_message('deviceState')
  ds.deviceState.started = True
  ds.deviceState.networkType = log.DeviceState.NetworkType.wifi
  ps = messaging.new_message('pandaStates', 1)
  ps.pandaStates[0].pandaType = log.PandaState.PandaType.dos
  ps.pandaStates[0].ignitionLine = True
  pm.send('deviceState', ds)
  pm.send('pandaStates', ps)

  ss = messaging.new_message('selfdriveState')
  ss.selfdriveState.enabled = enabled
  ss.selfdriveState.active = enabled
  ss.selfdriveState.state = log.SelfdriveState.OpenpilotState.enabled if enabled else log.SelfdriveState.OpenpilotState.disabled
  pm.send('selfdriveState', ss)

  rs = messaging.new_message('radarState')
  rs.radarState.leadOne.present = lead
  rs.radarState.leadOne.dRel = 32.4
  pm.send('radarState', rs)

  lp = messaging.new_message('longitudinalPlan')
  lp.longitudinalPlan.shouldStop = stop
  pm.send('longitudinalPlan', lp)

  cs = messaging.new_message('carStateSP')
  data = cs.carStateSP.init('carData', len(items))
  for out, (key, label, value, unit, valid) in zip(data, items, strict=True):
    out.key, out.label, out.value, out.unit, out.valid = key, label, value, unit, valid
  pm.send('carStateSP', cs)


def save_shots(out_dir: str, layout, pm: PubMaster, ui_state) -> None:
  from openpilot.system.ui.lib.application import gui_app

  os.makedirs(out_dir, exist_ok=True)
  frame = 0
  plan = []  # (frame to shoot at, scenario index, page name, page widget)
  for idx, scenario in enumerate(SCENARIOS.values(), 1):
    for page_name, page in (("road", layout._car_onroad_layout), ("data", layout._car_data_layout)):
      plan.append((scenario, idx, page_name, page))

  step, wait = 0, 0
  for _ in gui_app.render():
    scenario, idx, page_name, page = plan[step]
    send_state(pm, scenario)
    ui_state.update()
    if wait % 10 == 0:  # the main layout scrolls back to the road view by itself, keep asking for the page
      layout._scroll_to(page)
    wait += 1
    if wait > 120:  # let the swipe animation and the filters settle
      path = os.path.join(out_dir, f"{idx}_{page_name}.png")
      image = rl.load_image_from_screen()
      rl.export_image(image, path)
      rl.unload_image(image)
      print("saved", path, "-", scenario[0])
      step, wait = step + 1, 0
      if step >= len(plan):
        break
    frame += 1


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--shots", metavar="DIR", help="render all scenarios headless and save PNGs")
  args = parser.parse_args()

  if args.shots:
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN)
    os.environ["OFFSCREEN"] = "1"

  with OpenpilotPrefix():
    from openpilot.selfdrive.ui.tests.diff.replay import setup_state
    setup_state()

    from openpilot.selfdrive.ui.ui_state import ui_state, device
    from openpilot.system.ui.lib.application import gui_app

    gui_app.init_window("ui preview", fps=60)

    from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
    layout = MiciMainLayout()
    device.set_override_interactive_timeout(99999)

    pm = PubMaster(["deviceState", "pandaStates", "selfdriveState", "radarState", "longitudinalPlan", "carStateSP"])

    if args.shots:
      save_shots(args.shots, layout, pm, ui_state)
      gui_app.close()
      return

    scenario = SCENARIOS[rl.KeyboardKey.KEY_ONE]
    print("scenarios:", ", ".join(f"{i}={v[0]}" for i, v in enumerate(SCENARIOS.values(), 1)))

    for _ in gui_app.render():
      for key, value in SCENARIOS.items():
        if rl.is_key_pressed(key):
          scenario = value
          print("scenario:", value[0])
      send_state(pm, scenario)
      ui_state.update()


if __name__ == "__main__":
  if "--shots" not in __import__("sys").argv:
    os.environ.setdefault("SHOW_TOUCHES", "1")
  main()
