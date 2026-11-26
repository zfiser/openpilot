"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.

Fake onroad data for the mici UI: the message builder of the PC preview (tests/ui_preview.py) and the demo build (DEMO).
With DEMO = True the UI shows the driving screen and the car data page with animated values while the car is off; real
ignition always ends it (ui_state.py). Only the UI reads these messages, nothing is published.
"""
import json
import math
import os
import random

from openpilot.cereal import custom, log, messaging

DEMO = True  # the demo build (branch mici-sidebar-car-data-demo); the main branch has False

ROAD = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_road.json")))  # a real road of 16 Nov

# the values read from the ECUs (diag_*), as answered by the car on 24 Nov (analysis 2026-11-23_diag, probe 1 and 2)
DIAG_ITEMS = [("rpm", "Engine RPM", 1850.0, "rpm", True), ("engine_temp", "Engine temp", 17.0, "C", True),
              ("odometer", "Odometer", 54321.0, "km", True), ("today", "Today", 42.0, "km", True), ("drive_time", "Time", 6120.0, "s", True),
              ("diag_oil_temp", "Oil", 18.0, "C", True), ("diag_coolant", "Coolant", 17.5, "C", True),
              ("diag_transaxle_oil", "Transaxle oil", 17.0, "C", True), ("diag_mg_inverter", "Motor inverter", 15.0, "C", True),
              ("diag_gen_inverter", "Generator inverter", 14.0, "C", True), ("diag_inverter_coolant", "Inverter coolant", 19.0, "C", True),
              ("diag_rear_inverter_coolant", "Rear inverter coolant", 12.0, "C", True), ("diag_boost_upper", "Boost upper", 17.0, "C", True),
              ("diag_boost_lower", "Boost lower", 17.0, "C", True), ("diag_cabin", "Cabin", 16.0, "C", True),
              ("diag_ac_power", "A/C power", 0.0, "kW", True), ("diag_12v_v", "12V", 14.48, "V", True),
              ("diag_12v_a", "12V current", 5.87, "A", True), ("diag_12v_temp", "12V temp", 11.9, "C", True),
              ("diag_12v_smooth", "12V smoothed", 14.14, "V", True), ("diag_12v_relay", "12V before relay", 11.29, "V", True),
              ("diag_aux_v", "Aux", 14.38, "V", True),
              *[(f"diag_hv_temp{i}", f"HV {i}", t, "C", True) for i, t in enumerate((15.35, 15.71, 15.05, 15.05, 15.76, 15.25), 1)],
              *[(f"diag_tire_p_{w}", w, p, "kPa", True) for w, p in (("fl", 253.4), ("fr", 250.0), ("rl", 251.7), ("rr", 253.4))],
              *[(f"diag_tire_t_{w}", w, t, "C", True) for w, t in (("fl", 13.0), ("fr", 13.0), ("rl", 14.0), ("rr", 13.0))]]


def animate_item(item, t: float):
  """Make the fake car data move a little so the page looks alive, odometer counts up, the rest wobbles."""
  key, label, value, unit, valid = item
  if key == "rpm" and value == 0.0:
    return item  # engine off stays off
  wobble = {"odometer": 0.0, "rpm": 600.0 * math.sin(t * 0.8),
            "hv": 3.0 * math.sin(t * 0.2), "lead_distance": 8.0 * math.sin(t * 0.6),  # gap shrinks and grows, shows both trend colours
            "tire_pressure_guess": 1.5 * math.sin(t * 0.2), "tire_temperature_guess": 1.0 * math.sin(t * 0.15)}.get(key, 0.0)
  return key, label, value + wobble + (t * 0.01 if key == "odometer" else 0.0), unit, valid


def build_state(scenario, t: float | None = None, network_type=log.DeviceState.NetworkType.wifi) -> list:
  """The messages of one frame of a scenario. t is seconds since start for animated values, None gives fixed values
  (used for the screenshots)."""
  msgs: list = []
  _, lead, stop, enabled, items, *extra = scenario
  fixed_confidence = extra[0] if extra else None
  lat_only = bool(extra[1]) if len(extra) > 1 else False
  alert_text = extra[2] if len(extra) > 2 else None  # a message that covers the top of the road view
  road = len(extra) > 3 and extra[3] == "road"  # the recorded road of demo_road.json
  R = dict(ROAD, **extra[5]) if len(extra) > 5 and extra[5] else ROAD  # a road scene with other radar / lead values
  if road:
    items = list(items) + [("lead_distance", "Lead distance", R["lead_distance"], "m", True),
                           ("radar_distance", "Radar distance", R["radar_distance"], "m", True),
                           ("radar_rel_speed", "Radar rel speed", R["radar_rel_speed"], "m/s", True)]
  moving = (enabled or lat_only) and not stop
  if t is not None:
    items = [animate_item(item, t) for item in items]
  lead_distance = 32.4 if t is None else 32.0 + 18.0 * math.sin(t * 0.5)
  confidence = fixed_confidence if fixed_confidence is not None else (0.9 if t is None else 0.5 + 0.5 * math.sin(t * 0.3))  # sweeps green, orange, red
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
  msgs.append(ds)
  msgs.append(ps)

  periph = messaging.new_message('peripheralState')
  periph.peripheralState.pandaType = log.PandaState.PandaType.dos
  periph.peripheralState.voltage = int((12640 if t is None else 12700 + 600 * math.sin(t * 0.3)))  # millivolts
  msgs.append(periph)

  ss = messaging.new_message('selfdriveState')
  ss.selfdriveState.enabled = enabled
  ss.selfdriveState.active = enabled
  ss.selfdriveState.state = log.SelfdriveState.OpenpilotState.enabled if enabled else log.SelfdriveState.OpenpilotState.disabled
  if alert_text:
    ss.selfdriveState.alertText1 = alert_text
    ss.selfdriveState.alertSize = log.SelfdriveState.AlertSize.mid
    ss.selfdriveState.alertStatus = log.SelfdriveState.AlertStatus.userPrompt
  msgs.append(ss)

  ssp = messaging.new_message('selfdriveStateSP')
  mads = ssp.selfdriveStateSP.mads
  mads.available = True
  mads.enabled = lat_only
  mads.active = lat_only
  mads.state = (custom.ModularAssistiveDrivingSystem.ModularAssistiveDrivingSystemState.enabled if lat_only
                else custom.ModularAssistiveDrivingSystem.ModularAssistiveDrivingSystemState.disabled)
  msgs.append(ssp)

  rs = messaging.new_message('radarState')
  rs.radarState.leadOne.present = lead or road
  rs.radarState.leadOne.dRel = R["lead"]["dRel"] if road else lead_distance
  if road:
    rs.radarState.leadOne.yRel = R["lead"]["yRel"]
    rs.radarState.leadOne.vRel = R["lead"]["vRel"]
  msgs.append(rs)

  gps = messaging.new_message('gpsLocationExternal')
  gps.gpsLocationExternal.hasFix = True
  gps.gpsLocationExternal.speed = (25.0 if moving else 0.0) + (0.0 if t is None else 3.0 * math.sin(t * 0.5))
  msgs.append(gps)

  car = messaging.new_message('carState')
  car.carState.vEgo = ROAD["vEgo"] if road else (20.0 if moving else 0.0)
  car.carState.standstill = not moving
  car.carState.steeringAngleDeg = steering_angle
  car.carState.cruiseState.available = True
  car.carState.cruiseState.enabled = enabled
  car.carState.cruiseState.speed = 27.0
  msgs.append(car)

  mv = messaging.new_message('modelV2')
  # lateral only looks at the steering override probability, fully engaged at the product of both
  mv.modelV2.meta.disengagePredictions.brakeDisengageProbs = [0.0 if lat_only else 1.0 - confidence]
  mv.modelV2.meta.disengagePredictions.steerOverrideProbs = [1.0 - confidence if lat_only else 0.0]
  if road:
    for k in "xyz":
      setattr(mv.modelV2.position, k, ROAD["position"][k])
    lanes = mv.modelV2.init("laneLines", len(ROAD["laneLines"]))
    for out, line in zip(lanes, ROAD["laneLines"], strict=True):
      out.x, out.y, out.z = line["x"], line["y"], line["z"]
    mv.modelV2.laneLineProbs = ROAD["laneLineProbs"]
    mv.modelV2.roadEdgeStds = [0.4, 0.4]  # not in the fixture; any confident value
    edges = mv.modelV2.init("roadEdges", len(ROAD["roadEdges"]))
    for out, line in zip(edges, ROAD["roadEdges"], strict=True):
      out.x, out.y, out.z = line["x"], line["y"], line["z"]
  msgs.append(mv)

  cal = messaging.new_message('extrinsicsCalibration')
  cal.extrinsicsCalibration.rpyCalib = ROAD["rpyCalib"] if road else [0.0, 0.0, 0.0]
  cal.extrinsicsCalibration.height = ROAD["height"]
  cal.extrinsicsCalibration.calStatus = log.ExtrinsicsCalibration.Status.calibrated
  msgs.append(cal)

  dm = messaging.new_message('driverMonitoringState')
  dm.driverMonitoringState.activePolicy = log.DriverMonitoringState.MonitoringPolicy.vision
  dm.driverMonitoringState.visionPolicyState.faceDetected = True
  dm.driverMonitoringState.visionPolicyState.awarenessPercent = 100.0
  dm.driverMonitoringState.visionPolicyState.pose.yaw = head_yaw
  dm.driverMonitoringState.visionPolicyState.pose.pitch = head_pitch
  msgs.append(dm)
  msgs.append(messaging.new_message('driverStateV2'))

  lp = messaging.new_message('longitudinalPlan')
  lp.longitudinalPlan.shouldStop = stop
  msgs.append(lp)

  cs = messaging.new_message('carStateSP')
  data = cs.carStateSP.init('carData', len(items))
  for out, (key, label, value, unit, valid) in zip(data, items, strict=True):
    out.key, out.label, out.value, out.unit, out.valid = key, label, value, unit, valid
  msgs.append(cs)
  return msgs


# ***** the demo build: a slow loop through driving situations, every value wandering *****
SITUATION_SECONDS = 20.0
HUG_LEFT, HUG_RIGHT = 1, -1


def _wander(key: str, t: float, amplitude: float) -> float:
  """A smooth pseudo random movement of one value: two sines with periods and phases fixed per key."""
  rnd = random.Random(key)
  f1, f2, p1, p2 = rnd.uniform(0.05, 0.2), rnd.uniform(0.3, 0.7), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3)
  return amplitude * (0.7 * math.sin(t * f1 + p1) + 0.3 * math.sin(t * f2 + p2))


WANDER = {"rpm": 700.0, "engine_temp": 6.0, "diag_oil_temp": 8.0, "diag_coolant": 6.0, "diag_transaxle_oil": 6.0,
          "diag_mg_inverter": 5.0, "diag_gen_inverter": 5.0, "diag_inverter_coolant": 4.0, "diag_rear_inverter_coolant": 3.0,
          "diag_boost_upper": 4.0, "diag_boost_lower": 4.0, "diag_cabin": 1.5,
          "diag_ac_power": 0.6, "diag_12v_v": 0.25, "diag_12v_a": 8.0, "diag_12v_temp": 1.0,
          "diag_12v_smooth": 0.15, "diag_12v_relay": 0.2, "diag_aux_v": 0.2}
WARM = {"diag_oil_temp": 70.0, "diag_coolant": 70.0, "diag_transaxle_oil": 45.0, "diag_mg_inverter": 30.0, "diag_gen_inverter": 30.0,
        "diag_inverter_coolant": 25.0, "diag_rear_inverter_coolant": 20.0, "diag_boost_upper": 25.0, "diag_boost_lower": 25.0,
        "engine_temp": 70.0, "diag_cabin": 5.0, "diag_ac_power": 0.8,
        "diag_tire_t_fl": 12.0, "diag_tire_t_fr": 12.0, "diag_tire_t_rl": 10.0, "diag_tire_t_rr": 10.0, "diag_hv_temp1": 10.0,
        "diag_hv_temp2": 10.0, "diag_hv_temp3": 10.0, "diag_hv_temp4": 10.0, "diag_hv_temp5": 10.0, "diag_hv_temp6": 10.0}


def demo_items(t: float) -> list:
  """The car data items (tiles and ECU panels), warmed up from the 24 Nov values and wandering."""
  out = []
  for key, label, value, unit, valid in DIAG_ITEMS:
    v = value + WARM.get(key, 0.0) + _wander(key, t, WANDER.get(key, 1.0 if key.startswith("diag_") else 0.0))
    if key.startswith(("diag_ac_power", "rpm")):
      v = max(v, 0.0)
    if key == "odometer":
      v = value + t * 0.02
    out.append((key, label, v, unit, valid))
  return out


def demo_situation(t: float) -> tuple[str, tuple, int]:
  """(name, scenario for build_state, hug side) of the loop at t seconds."""
  n = int(t // SITUATION_SECONDS) % 5
  phase = (t % SITUATION_SECONDS) / SITUATION_SECONDS
  items = demo_items(t)
  far = 55.0 + 25.0 * math.sin(t * 0.2)
  if n == 1:  # catching up on a slower car: brackets amber -> orange -> red, decimal distance under 10 m
    d = max(30.0 - 24.0 * phase, 6.0)
    lead = {"radar_distance": d, "radar_rel_speed": -4.0 if d > 6.0 else 0.0, "lead_distance": d,
            "lead": {"dRel": d, "yRel": 0.1, "vRel": -4.0}}
    return "closing in", ("demo closing", False, False, False, items, None, True, None, "road", "brackets", lead), 0
  lead = {"radar_distance": far, "radar_rel_speed": 1.5 * math.cos(t * 0.2), "lead_distance": far,
          "lead": {"dRel": far, "yRel": 0.2 * math.sin(t * 0.3), "vRel": 1.5 * math.cos(t * 0.2)}}
  if n == 0:
    return "lateral only", ("demo lateral", False, False, False, items, None, True, None, "road", "brackets", lead), 0
  if n == 2:
    return "hug left", ("demo hug left", False, False, False, items, None, True, None, "road", "brackets", lead), HUG_LEFT
  if n == 3:
    alert = "Car ahead" if phase < 0.25 else None
    return "car ahead alert", ("demo alert", False, False, False, items, None, True, alert, "road", "brackets", lead), HUG_RIGHT
  return "engaged", ("demo engaged", True, False, True, items, None, False, None, "road", "brackets", lead), 0


def demo_messages(t: float) -> list:
  """All messages of the demo at t seconds since it started."""
  name, scenario, hug = demo_situation(t)
  phase = (t % SITUATION_SECONDS) / SITUATION_SECONDS
  # a calm driver and a confident model (the preview sweeps both to their red ends); one short low-confidence moment
  confidence = 0.35 if name == "car ahead alert" and 0.5 < phase < 0.65 else 0.85 + 0.1 * math.sin(t * 0.3)
  scenario = scenario[:5] + (confidence,) + scenario[6:]
  out = build_state(scenario, t)
  for m in out:
    if m.which() == "driverMonitoringState":
      m.driverMonitoringState.visionPolicyState.pose.yaw = 0.08 * math.sin(t * 0.5)
      m.driverMonitoringState.visionPolicyState.pose.pitch = 0.04 * math.sin(t * 0.7)
  hug_msg = messaging.new_message('modelDataV2SP')
  hug_msg.modelDataV2SP.hugSide = hug
  out.append(hug_msg)
  return out
