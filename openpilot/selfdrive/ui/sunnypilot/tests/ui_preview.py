#!/usr/bin/env python3
"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Open the mici UI in a window on a PC with fake onroad data, to look at the sidebar and the car data page.

  python selfdrive/ui/sunnypilot/tests/ui_preview.py

Drag with the mouse to swipe (left from the road view reaches the car data page). Keys 1-5 pick a scenario, M switches between metric and imperial units (--metric starts in metric),
N cycles the network between WiFi, LTE and offline (tapping the network icon on the home screen only does something when not on WiFi).
The values animate (lead distance, confidence, steering, driver head, car data).
Add --shots DIR to render every scenario headless and save PNGs of the road view and the car data page.
"""
import argparse
import math
import os
import time

import pyray as rl

from openpilot.cereal import log, messaging
from openpilot.cereal.messaging import PubMaster
from openpilot.common.prefix import OpenpilotPrefix

# name -> (lead car, planner stop, openpilot state enabled, car data items as (key, label, value, unit, valid))
SCENARIOS = {
  rl.KeyboardKey.KEY_ONE: ("engaged, no lead", False, False, True, [("odometer", "Odometer", 54321.0, "km", True),
                                                                       ("today", "Today", 42.0, "km", True),
                                                                       ("rpm", "Engine RPM", 1800.0, "rpm", True)]),
  rl.KeyboardKey.KEY_TWO: ("lead car", True, False, True, [("odometer", "Odometer", 54321.0, "km", True),
                                                           ("today", "Today", 42.0, "km", True),
                                                           ("rpm", "Engine RPM", 1800.0, "rpm", True)]),
  rl.KeyboardKey.KEY_THREE: ("stop light, engine off", False, True, True, [("odometer", "Odometer", 54321.0, "km", True),
                                                                           ("rpm", "Engine RPM", 0.0, "rpm", True)]),
  rl.KeyboardKey.KEY_FOUR: ("disengaged, car data missing", False, False, False, [("odometer", "Odometer", 0.0, "km", False),
                                                                                 ("rpm", "Engine RPM", 0.0, "rpm", False)]),
  rl.KeyboardKey.KEY_FIVE: ("many items", True, False, True, [
    ("odometer", "Odometer", 54321.0, "km", True), ("today", "Today", 42.0, "km", True),
    ("rpm", "Engine RPM", 1800.0, "rpm", True), ("tire_temp_fl", "Tire FL temp", 32.0, "C", True), ("tire_temp_fr", "Tire FR temp", 33.5, "C", True),
    ("battery", "12V battery", 13.84, "V", True), ("hv", "Hybrid battery", 62.0, "%", True)]),
}


def animate_item(item, t: float):
  """Make the fake car data move a little so the page looks alive, odometer counts up, the rest wobbles."""
  key, label, value, unit, valid = item
  if key == "rpm" and value == 0.0:
    return item  # engine off stays off
  wobble = {"odometer": 0.0, "battery": 0.25 * math.sin(t * 1.3), "rpm": 600.0 * math.sin(t * 0.8),
            "tire_temp_fl": 1.5 * math.sin(t * 0.3), "tire_temp_fr": 1.5 * math.sin(t * 0.35),
            "hv": 3.0 * math.sin(t * 0.2)}.get(key, 0.0)
  return key, label, value + wobble + (t * 0.01 if key == "odometer" else 0.0), unit, valid


NETWORKS = [("wifi", log.DeviceState.NetworkType.wifi), ("LTE", log.DeviceState.NetworkType.cell4G),
            ("offline", log.DeviceState.NetworkType.none)]


def send_state(pm: PubMaster, scenario, t: float | None = None, network_type=log.DeviceState.NetworkType.wifi) -> None:
  """t is seconds since start for animated values, None gives fixed values (used for the screenshots)."""
  _, lead, stop, enabled, items = scenario
  moving = enabled and not stop
  if t is not None:
    items = [animate_item(item, t) for item in items]
  lead_distance = 32.4 if t is None else 32.0 + 18.0 * math.sin(t * 0.5)
  confidence = 0.9 if t is None else 0.5 + 0.5 * math.sin(t * 0.3)  # sweeps the circle from green over orange to red
  steering_angle = 0.0 if t is None else 25.0 * math.sin(t * 0.4)
  head_yaw = 0.0 if t is None else 0.6 * math.sin(t * 0.6)  # driver looks around, radians
  head_pitch = 0.0 if t is None else 0.25 * math.sin(t * 0.9)

  ds = messaging.new_message('deviceState')
  ds.deviceState.started = True
  ds.deviceState.networkType = network_type
  ds.deviceState.networkStrength = log.DeviceState.NetworkStrength.good
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
  rs.radarState.leadOne.dRel = lead_distance
  pm.send('radarState', rs)

  car = messaging.new_message('carState')
  car.carState.vEgo = 20.0 if moving else 0.0
  car.carState.standstill = not moving
  car.carState.steeringAngleDeg = steering_angle
  car.carState.cruiseState.available = True
  car.carState.cruiseState.enabled = enabled
  car.carState.cruiseState.speed = 27.0
  pm.send('carState', car)

  mv = messaging.new_message('modelV2')
  mv.modelV2.meta.disengagePredictions.brakeDisengageProbs = [1.0 - confidence]
  mv.modelV2.meta.disengagePredictions.steerOverrideProbs = [0.0]
  pm.send('modelV2', mv)

  dm = messaging.new_message('driverMonitoringState')
  dm.driverMonitoringState.activePolicy = log.DriverMonitoringState.MonitoringPolicy.vision
  dm.driverMonitoringState.visionPolicyState.faceDetected = True
  dm.driverMonitoringState.visionPolicyState.awarenessPercent = 100.0
  dm.driverMonitoringState.visionPolicyState.pose.yaw = head_yaw
  dm.driverMonitoringState.visionPolicyState.pose.pitch = head_pitch
  pm.send('driverMonitoringState', dm)
  pm.send('driverStateV2', messaging.new_message('driverStateV2'))

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
  parser.add_argument("--metric", action="store_true", help="start with the metric unit setting on (distances in m, not ft)")
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

    def set_metric(value: bool) -> None:
      ui_state.params.put_bool("IsMetric", value)
      ui_state.is_metric = value  # ui_state only re-reads the param every few seconds
    set_metric(args.metric)

    from openpilot.selfdrive.ui.mici.layouts.main import MiciMainLayout
    layout = MiciMainLayout()
    device.set_override_interactive_timeout(99999)

    pm = PubMaster(["deviceState", "pandaStates", "selfdriveState", "radarState", "longitudinalPlan", "carStateSP", "carState", "modelV2",
                   "driverMonitoringState", "driverStateV2"])

    if args.shots:
      save_shots(args.shots, layout, pm, ui_state)
      gui_app.close()
      return

    scenario = SCENARIOS[rl.KeyboardKey.KEY_TWO]  # starts with a lead car so the distance in the bottom corner shows
    print("scenarios:", ", ".join(f"{i}={v[0]}" for i, v in enumerate(SCENARIOS.values(), 1)))

    start = time.monotonic()
    network_idx = 0
    for _ in gui_app.render():
      for key, value in SCENARIOS.items():
        if rl.is_key_pressed(key):
          scenario = value
          print("scenario:", value[0])
      if rl.is_key_pressed(rl.KeyboardKey.KEY_M):
        set_metric(not ui_state.is_metric)
        print("metric:", ui_state.is_metric)
      if rl.is_key_pressed(rl.KeyboardKey.KEY_N):
        network_idx = (network_idx + 1) % len(NETWORKS)
        print("network:", NETWORKS[network_idx][0])
      send_state(pm, scenario, time.monotonic() - start, NETWORKS[network_idx][1])
      ui_state.update()


if __name__ == "__main__":
  if "--shots" not in __import__("sys").argv:
    os.environ.setdefault("SHOW_TOUCHES", "1")
  main()
