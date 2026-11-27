#!/usr/bin/env python3
"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Open the mici UI in a window on a PC with fake onroad data, to look at the sidebar and the car data page.

  python selfdrive/ui/sunnypilot/tests/ui_preview.py

Drag with the mouse to swipe (left from the road view reaches the car data page). Keys 1-7 pick a scenario, M switches between metric and imperial units (--metric starts in metric),
N cycles the network between WiFi, LTE and offline (tapping the network icon on the home screen only does something when not on WiFi).
The values animate (lead distance, confidence, steering, driver head, car data).
Add --shots DIR to render every scenario headless and save PNGs of the road view and the car data page.
"""
import argparse
import os
import time

import pyray as rl

from openpilot.cereal import log, messaging
from openpilot.cereal.messaging import PubMaster
from openpilot.common.prefix import OpenpilotPrefix
from openpilot.selfdrive.ui.sunnypilot.demo_data import DIAG_ITEMS, ROAD, animate_item, build_state  # noqa: F401

# name -> (lead car, planner stop, openpilot state enabled, car data items as (key, label, value, unit, valid))
SCENARIOS = {
  rl.KeyboardKey.KEY_ONE: ("engaged, no lead", False, False, True, [("odometer", "Odometer", 54321.0, "km", True),
                                                                       ("today", "Today", 42.0, "km", True), ("drive_time", "Time", 6120.0, "s", True),
                                                                       ("rpm", "Engine RPM", 1800.0, "rpm", True)]),
  rl.KeyboardKey.KEY_TWO: ("lead car", True, False, True, [("odometer", "Odometer", 54321.0, "km", True),
                                                           ("today", "Today", 42.0, "km", True), ("drive_time", "Time", 6120.0, "s", True),
                                                           ("rpm", "Engine RPM", 1800.0, "rpm", True),
                                                           ("engine_temp", "Engine temp", 82.0, "C", True),
                                                           ("lead_distance", "Lead distance", 23.0, "m", True),
                                                           ("friction_brake_force", "Friction brake", 400.0, "N", True)]),
  rl.KeyboardKey.KEY_THREE: ("stop light, engine off", False, True, True, [("odometer", "Odometer", 54321.0, "km", True),
                                                                           ("rpm", "Engine RPM", 0.0, "rpm", True)]),
  rl.KeyboardKey.KEY_FOUR: ("disengaged, car data missing", False, False, False, [("odometer", "Odometer", 0.0, "km", False),
                                                                                 ("rpm", "Engine RPM", 0.0, "rpm", False)]),
  rl.KeyboardKey.KEY_FIVE: ("many items", True, False, True, [
    ("odometer", "Odometer", 54321.0, "km", True), ("today", "Today", 42.0, "km", True), ("drive_time", "Time", 6120.0, "s", True),
    ("rpm", "Engine RPM", 1800.0, "rpm", True),
    ("tire_pressure_guess", "Tire pressure?", 264.0, "kPa", True), ("tire_temperature_guess", "Tire temp?", 25.0, "C", True),
    ("hv", "Hybrid battery", 62.0, "%", True)]),
  # extra fields: fixed model confidence, lateral only (MADS without the car's longitudinal control being openpilot's)
  rl.KeyboardKey.KEY_SIX: ("lateral only, medium confidence", False, False, False, [("odometer", "Odometer", 54321.0, "km", True)], 0.35, True),
  rl.KeyboardKey.KEY_SEVEN: ("lateral only, low confidence", False, False, False, [("odometer", "Odometer", 54321.0, "km", True)], 0.1, True),
  rl.KeyboardKey.KEY_EIGHT: ("lateral only, alert on screen (the RPM hides)", False, False, False,
                             [("odometer", "Odometer", 54321.0, "km", True), ("rpm", "Engine RPM", 1800.0, "rpm", True)], 0.9, True,
                             "Changing Lanes"),
  # a real moment of 16 Nov (route 0x9c, segment 65): model path and lanes, the camera lead and the radar lead (radar dot)
  rl.KeyboardKey.KEY_NINE: ("radar dot, real road", False, False, False, [("odometer", "Odometer", 54321.0, "km", True)], 0.9, True,
                            None, "road"),
}

SCENARIOS["ecu_data"] = ("ECU data", True, False, False, DIAG_ITEMS, 0.9, True)  # steering (lateral only): the hug arrow can show

# radar marker shapes on the same road: far (the recorded car at 69 m) and close (8 m, closing 3 m/s: orange, decimal distance)
CLOSE = {"radar_distance": 8.0, "radar_rel_speed": -3.0, "lead_distance": 8.0, "lead": {"dRel": 8.0, "yRel": 0.13, "vRel": -3.0}}
for _n, _style in enumerate(("bar", "brackets", "chevron")):
  for _m, (_label, _over) in enumerate((("far", None), ("close", CLOSE))):
    SCENARIOS[f"marker_{_style}_{_label}"] = (f"radar marker {_style}, {_label}", False, False, False,
                                              [("odometer", "Odometer", 54321.0, "km", True)], 0.9, True, None, "road", _style, _over)



NETWORKS = [("wifi", log.DeviceState.NetworkType.wifi), ("LTE", log.DeviceState.NetworkType.cell4G),
            ("offline", log.DeviceState.NetworkType.none)]


def send_state(pm: PubMaster, scenario, t: float | None = None, network_type=log.DeviceState.NetworkType.wifi) -> None:
  for msg in build_state(scenario, t, network_type):
    pm.send(msg.which(), msg)


def demo_shots(out_dir: str, layout, ui_state) -> None:
  """The demo build: nothing published, ui_state makes up the data. One road view per situation (mid situation), then the
  car data page and its panels."""
  from openpilot.system.ui.lib.application import gui_app
  from openpilot.selfdrive.ui.sunnypilot import demo_data

  os.makedirs(out_dir, exist_ok=True)
  gui_app.set_show_touches(False)  # the developer touch outlines, off on the car unless ShowDebugInfo is set
  gui_app.set_show_fps(False)
  start = time.monotonic()
  plan = [(demo_data.SITUATION_SECONDS * (n + 0.5), f"demo_{n + 1}_road", layout._car_onroad_layout) for n in range(5)]
  plan += [(demo_data.SITUATION_SECONDS * 5 + 2, "demo_data", layout._car_data_layout)]
  plan += [(demo_data.SITUATION_SECONDS * 5 + 4 + 2 * n, f"demo_panel{n + 1}", layout._car_data_layout) for n in range(5)]
  step = 0
  scrolled = False
  for _ in gui_app.render():
    ui_state.update()
    t = time.monotonic() - start
    when, name, page = plan[step]
    road_view = layout._car_onroad_layout
    if road_view._content_rect.width > 0:
      road_view._calc_frame_matrix(road_view._content_rect)  # no video: set the road projection the camera view would
    layout._scroll_to(page)
    if name.startswith("demo_panel") and not scrolled and t > when - 1.0:
      data = layout._car_data_layout
      n = int(name[-1]) - 1
      if n < len(data._panel_rows):
        data._scroller.scroll_to(data._panel_rows[n].rect.y - data._scroller.rect.y - data._pad)
      scrolled = True
    if t >= when:
      image = rl.load_image_from_screen()
      rl.export_image(image, os.path.join(out_dir, f"{name}.png"))
      rl.unload_image(image)
      print("saved", name, "-", demo_data.demo_situation(t)[0], "| demo on:", ui_state._demo_on, "| started:", ui_state.started)
      step += 1
      scrolled = False
      if step >= len(plan):
        break


def save_shots(out_dir: str, layout, pm: PubMaster, ui_state) -> None:
  from openpilot.system.ui.lib.application import gui_app
  from openpilot.selfdrive.ui.sunnypilot.mici.onroad.radar_dot import STYLE as RADAR_STYLE

  os.makedirs(out_dir, exist_ok=True)
  frame = 0
  plan = []  # (frame to shoot at, scenario index, page name, page widget)
  for idx, scenario in enumerate(SCENARIOS.values(), 1):
    pages = (("road", layout._car_onroad_layout),) if len(scenario) > 9 else (("road", layout._car_onroad_layout), ("data", layout._car_data_layout))
    for page_name, page in pages:
      plan.append((scenario, idx, page_name, page))
    if scenario[0] == "ECU data":  # each group panel of the car data page, scrolled to
      for n in range(1, 6):
        plan.append((scenario, idx, f"data_panel{n}", layout._car_data_layout))
      plan.append((scenario, idx, "hug_arrow_left", layout._car_onroad_layout))  # the oil line next to the left hug arrow
    if scenario[0].startswith("lateral only, medium"):  # steering: the hug screen open, and the arrows with it closed
      plan.append((scenario, idx, "hug_open", layout._car_onroad_layout))
      plan.append((scenario, idx, "hug_arrow_left", layout._car_onroad_layout))
      plan.append((scenario, idx, "hug_arrow_right", layout._car_onroad_layout))
  hug_sides = {"hug_arrow_left": 1, "hug_arrow_right": -1}

  step, wait = 0, 0
  for _ in gui_app.render():
    scenario, idx, page_name, page = plan[step]
    send_state(pm, scenario)
    hug_msg = messaging.new_message('modelDataV2SP')
    hug_msg.modelDataV2SP.hugSide = hug_sides.get(page_name, 0)
    hug_msg.modelDataV2SP.hugAuto = page_name == "hug_arrow_right"
    pm.send('modelDataV2SP', hug_msg)
    ui_state.update()
    road_view = layout._car_onroad_layout
    road_view._model_renderer.radar_dot.style = scenario[9] if len(scenario) > 9 else RADAR_STYLE
    if len(scenario) > 8 and scenario[8] == "road" and road_view._content_rect.width > 0:
      road_view._calc_frame_matrix(road_view._content_rect)  # no video in the preview: set the road projection the camera view would
    hug = getattr(layout._car_onroad_layout, "_hug_screen", None)
    if hug is not None:
      if wait == 0:  # once per shot: a write every frame would never settle
        ui_state.params.put("LanePosition", {"hug_arrow_left": 1}.get(page_name, 0), block=True)
        ui_state.params.put_bool("AutoHug", page_name in ("hug_open", "hug_arrow_right"), block=True)
      if page_name == "hug_open":
        if not hug.is_open:
          hug._state.open(time.monotonic())
        hug._state.touched(time.monotonic())
      else:
        hug._state.close()
    if page_name.startswith("data_panel") and wait == 60:  # scroll_to is relative: once, after the page has laid out
      data = layout._car_data_layout
      n = int(page_name[-1]) - 1
      if n < len(data._panel_rows):
        data._scroller.scroll_to(data._panel_rows[n].rect.y - data._scroller.rect.y - data._pad)
    if wait % 10 == 0:  # the main layout scrolls back to the road view by itself, keep asking for the page
      layout._scroll_to(page)
    wait += 1
    if wait > 120:  # let the swipe animation and the filters settle
      shot = scenario[0].replace("radar marker ", "marker_").replace(", ", "_") if len(scenario) > 9 else f"{idx}_{page_name}"
      path = os.path.join(out_dir, f"{shot}.png")
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
  parser.add_argument("--demo", metavar="DIR", help="run the demo build (demo_data.DEMO) headless for 100 s, a screenshot per situation")
  args = parser.parse_args()

  if args.demo:
    from openpilot.selfdrive.ui.sunnypilot import demo_data
    demo_data.DEMO = True  # before ui_state is created
    args.shots = None

  if args.shots or args.demo:
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
                   "driverMonitoringState", "driverStateV2", "peripheralState", "selfdriveStateSP", "gpsLocationExternal",
                   "modelDataV2SP", "extrinsicsCalibration"])

    if args.shots:
      save_shots(args.shots, layout, pm, ui_state)
      gui_app.close()
      return
    if args.demo:
      demo_shots(args.demo, layout, ui_state)
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
