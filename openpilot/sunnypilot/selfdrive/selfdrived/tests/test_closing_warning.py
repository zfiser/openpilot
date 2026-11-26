"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import math
from types import SimpleNamespace

from openpilot.sunnypilot.selfdrive.selfdrived.closing_warning import (APPEARED, COLLISION, COOLDOWN, DISTRACTED, ClosingWarning, LeadRate,
                                                                       looking_away, radar_distance, radar_lead)

DT = 0.01
V = 25.0  # m/s, 90 km/h


def run(cw, seconds, d=40.0, closing=12.0, v=V, acc=False, gas=False, brake=False, blinker=False, wheel=0.0, distracted=False,
        present=True, look=None):
  """The gap shrinks by closing m/s from d metres; the radar reports whole metres. Returns the chimes and the last distance."""
  out = []
  for _ in range(round(seconds / DT)):
    reported = float(round(d)) if present else None
    kind = cw.update(v, reported, acc, gas, brake, blinker, wheel, distracted, DT, looking_away=look)
    if kind:
      out.append(kind)
    d = max(d - closing * DT, 1.0)
  return out


class TestLeadRate:
  def test_slope_of_whole_metres(self):
    r = LeadRate()
    rate = None
    for i in range(101):
      rate = r.update(i * DT, float(round(40.0 - 10.0 * i * DT)))
    assert abs(rate + 10.0) < 0.5

  def test_no_rate_at_first_and_after_a_gap(self):
    r = LeadRate()
    assert r.update(0.0, 30.0) is None
    assert r.update(0.3, 29.0) is None
    assert r.update(0.4, None) is None
    assert r.update(0.5, 28.0) is None


class TestClosingWarning:
  def test_collision_chimes_whatever_the_camera_says(self):
    # from 40 m at 12 m/s: the closing speed is known after 0.6 s, the gap would be gone in under 2 s at ~24 m
    assert run(ClosingWarning(), 2.0) == [COLLISION]
    # not looking: the soft chime at ~3 s, then the strong warning at 2 s (escalation)
    assert run(ClosingWarning(), 2.0, distracted=True) == [DISTRACTED, COLLISION]

  def test_distracted_only_when_not_looking(self):
    # 50 m at 12 m/s for 1.5 s: down to ~32 m, 2.7 s left, between the two limits
    assert run(ClosingWarning(), 1.5, d=50.0) == []
    assert run(ClosingWarning(), 1.7, d=50.0, distracted=True) == [DISTRACTED]

  def test_acc_on_without_gas_is_left_to_the_car(self):
    assert run(ClosingWarning(), 2.0, acc=True) == []
    assert run(ClosingWarning(), 2.0, acc=True, gas=True) == [COLLISION]

  def test_exceptions(self):
    assert run(ClosingWarning(), 2.0, brake=True) == []
    assert run(ClosingWarning(), 2.0, blinker=True) == []  # overtaking
    assert run(ClosingWarning(), 2.0, wheel=45.0) == []  # a turn
    assert run(ClosingWarning(), 2.0, v=6.0) == []  # 22 km/h
    assert run(ClosingWarning(), 3.0, d=10.0, closing=0.5) == []  # following steadily, hardly closing

  def test_far_blip_does_not_chime(self):
    # 19 Nov: a "car" on the radar for 0.3 s at 67 m and 0.6 s at 80 m while looking away
    cw = ClosingWarning()
    run(cw, 1.5, present=False, look=True)
    assert run(cw, 0.6, d=80.0, closing=0.0, look=True) == []
    assert run(cw, 0.5, present=False, look=True) == []
    # a real car there stays: it chimes once it was seen for FAR_HOLD
    cw = ClosingWarning()
    run(cw, 1.5, present=False, look=True)
    assert run(cw, 0.69, d=80.0, closing=8.0, look=True) == []
    assert run(cw, 0.1, d=75.0, closing=8.0, look=True) == [APPEARED]
    # a close one (a cut-in) at once
    cw = ClosingWarning()
    run(cw, 1.5, present=False, look=True)
    assert run(cw, 0.05, d=25.0, closing=0.0, look=True) == [APPEARED]

  def test_far_car_that_flickers_at_first_still_chimes(self):
    # review 26 Nov: a real far car the radar loses for a moment during the hold was dropped for good
    cw = ClosingWarning()
    run(cw, 1.5, present=False, look=True)
    assert run(cw, 0.4, d=90.0, closing=8.0, look=True) == []
    assert run(cw, 0.3, present=False, look=True) == []  # a short dropout
    assert run(cw, 0.29, d=84.0, closing=8.0, look=True) == []  # seen 0.69 s in all
    assert run(cw, 0.1, d=82.0, closing=8.0, look=True) == [APPEARED]
    # gone for a second or more: the old appearance is over, coming back at about the same distance is the same car
    cw = ClosingWarning()
    run(cw, 1.5, present=False, look=True)
    run(cw, 0.4, d=90.0, closing=0.0, look=True)
    run(cw, 1.2, present=False, look=True)
    assert run(cw, 2.0, d=90.0, closing=0.0, look=True) == []
    # a blip, a pause and then braking: nothing
    cw = ClosingWarning()
    run(cw, 1.5, present=False, look=True)
    run(cw, 0.4, d=90.0, closing=0.0, look=True)
    run(cw, 0.3, present=False, look=True, brake=True)
    assert run(cw, 2.0, d=90.0, closing=0.0, look=True) == []

  def test_far_car_glance_before_it_appeared_still_counts(self):
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    run(cw, 0.2, present=False, look=True)  # looked away 0.5 s before the radar found it
    run(cw, 0.3, present=False)
    assert run(cw, 1.0, d=110.0, closing=8.0) == [APPEARED]  # chimes after the 0.7 s hold

  def test_coming_out_of_a_turn(self):
    # 18 Nov (0x9f 2.74 min): unwinding a left turn at 41 km/h, the radar swept a roadside post from 6.5 m at our own speed
    cw = ClosingWarning()
    run(cw, 1.0, v=11.4, wheel=-35.0, present=False)
    run(cw, 0.8, v=11.4, wheel=-14.0, present=False)  # the wheel back under 30 deg
    assert run(cw, 0.5, d=6.5, closing=11.4, v=11.4, wheel=-12.0) == []
    # the same thing 2 s or more after the turn still warns (e.g. stopped traffic behind the bend)
    cw = ClosingWarning()
    run(cw, 1.0, v=11.4, wheel=-35.0, present=False)
    run(cw, 2.1, v=11.4, wheel=-5.0, present=False)
    assert COLLISION in run(cw, 1.0, d=18.0, closing=11.4, v=11.4, wheel=-3.0)  # needs 0.6 s of readings for a closing speed

  def test_steady_whole_metre_jitter_does_not_chime(self):
    cw = ClosingWarning()
    out = []
    for i in range(1000):
      d = 20.0 + (1.0 if (i // 20) % 2 else 0.0)  # flips between 20 and 21 m every 0.2 s
      if (k := cw.update(V, d, False, False, False, False, 0.0, True, DT)):
        out.append(k)
    assert out == []

  def test_cooldown(self):
    cw = ClosingWarning()
    assert run(cw, 2.0) == [COLLISION]
    assert run(cw, 2.0) == []
    run(cw, COOLDOWN, present=False)
    assert run(cw, 2.0) == [COLLISION]

  def test_cut_in(self):
    cw = ClosingWarning()
    run(cw, 1.5, present=False, distracted=True)
    assert run(cw, 0.05, d=18.0, closing=0.0, distracted=True) == [APPEARED]  # 0.7 s gap, the car just appeared
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    assert run(cw, 0.05, d=18.0, closing=0.0) == []  # looking: no chime
    cw = ClosingWarning()
    run(cw, 1.5, present=False, distracted=True)
    assert run(cw, 1.0, d=120.0, closing=0.0, distracted=True) == [APPEARED]  # any distance (a far one after FAR_HOLD)
    cw = ClosingWarning()
    run(cw, 1.5, present=False, acc=True, distracted=True)
    assert run(cw, 0.5, d=40.0, closing=0.0, acc=True, distracted=True) == []  # ACC holds the speed: no chime

  def test_cut_in_glance_just_before_or_after(self):
    # 16 Nov: looked away 0.4 s before the radar found the car, and in another case looked back one frame before it
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    run(cw, 0.2, present=False, distracted=True)
    run(cw, 0.4, present=False)
    assert run(cw, 0.05, d=18.0, closing=0.0) == [APPEARED]
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    run(cw, 0.5, d=18.0, closing=0.0)
    assert run(cw, 0.2, d=18.0, closing=0.0, distracted=True) == [APPEARED]  # glanced away right after it appeared
    # too long before or after: no chime
    cw = ClosingWarning()
    run(cw, 1.5, present=False, distracted=True)
    run(cw, 1.2, present=False)
    assert run(cw, 1.5, d=18.0, closing=0.0) == []
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    run(cw, 1.2, d=18.0, closing=0.0)
    assert run(cw, 0.5, d=18.0, closing=0.0, distracted=True) == []

  def test_cut_in_during_own_lane_change(self):
    # 16 Nov: the blinker was on when the radar found the car (our lane change), then went off: no chime
    cw = ClosingWarning()
    run(cw, 1.5, present=False, blinker=True)
    run(cw, 0.3, d=18.0, closing=0.0, blinker=True, distracted=True)
    assert run(cw, 0.5, d=18.0, closing=0.0, distracted=True) == []

  def test_slower_car_ahead_found_while_looking_in_the_mirror(self):
    # a glance (looking_away) smaller than the camera's "distracted" is enough for a car that appears
    cw = ClosingWarning()
    run(cw, 3.0, present=False)
    run(cw, 0.3, present=False, look=True)
    assert run(cw, 1.0, d=125.0, closing=8.0) == [APPEARED]
    # but not for the closing rules: following closely while closing and only glancing does not chime
    cw = ClosingWarning()
    assert run(cw, 3.0, d=15.0, closing=2.0, look=True) == []

  def test_appear_setting_off(self):
    cw = ClosingWarning()
    cw.appear_on = False
    run(cw, 1.5, present=False)
    assert run(cw, 0.8, d=60.0, closing=0.0, look=True) == []  # no chime for the new car
    cw = ClosingWarning()
    cw.appear_on = False
    assert run(cw, 1.0, d=40.0, closing=12.0, distracted=True) == [DISTRACTED]  # closing in while not looking still warns

  def test_one_chime_per_appearance(self):
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    assert run(cw, 0.8, d=60.0, closing=0.0, look=True) == [APPEARED]
    run(cw, 20.0, d=60.0, closing=0.0, look=True)  # still the same car after the cooldown: nothing new
    assert run(cw, 1.0, d=60.0, closing=0.0, look=True) == []

  def test_same_car_after_a_dropout_at_long_range(self):
    cw = ClosingWarning()
    run(cw, 2.0, d=118.0, closing=0.0)
    run(cw, 3.0, present=False)  # lost at 118 m
    assert run(cw, 1.5, d=112.0, closing=0.0, look=True) == []  # back at about the same distance
    cw = ClosingWarning()
    run(cw, 2.0, d=118.0, closing=0.0)
    run(cw, 3.0, present=False)
    assert run(cw, 0.5, d=40.0, closing=0.0, look=True) == [APPEARED]  # another car
    cw = ClosingWarning()
    run(cw, 2.0, d=118.0, closing=0.0)
    run(cw, 12.0, present=False)  # long gone: a car at that distance is new
    assert run(cw, 1.0, d=115.0, closing=0.0, look=True) == [APPEARED]

  def test_radar_switches_to_a_nearer_car(self):
    cw = ClosingWarning()
    run(cw, 2.0, d=90.0, closing=0.0)
    assert run(cw, 0.3, d=35.0, closing=0.0, look=True) == [APPEARED]
    cw = ClosingWarning()
    run(cw, 2.0, d=35.0, closing=0.0)
    assert run(cw, 0.3, d=90.0, closing=0.0, look=True) == []  # to a farther car: the road ahead got clearer

  def test_looking_away(self):
    def vps(yaw=0.0, pitch=0.0, distracted=False, face=True, kind="pose"):
      calib = SimpleNamespace(offset=math.radians(3.0))
      pose = SimpleNamespace(yaw=math.radians(yaw + 3.0), pitch=math.radians(pitch + 3.0), yawCalib=calib, pitchCalib=calib)
      types = SimpleNamespace(**{k: distracted and k == kind for k in ("pose", "eye", "phone", "sleep")})
      return SimpleNamespace(isDistracted=distracted, faceDetected=face, pose=pose, distractedTypes=types)
    assert not looking_away(vps())
    assert not looking_away(vps(yaw=10.0, pitch=8.0))  # looking up (the rear-view mirror tilt) or a little aside
    assert looking_away(vps(yaw=-20.0))  # the left mirror
    assert looking_away(vps(yaw=20.0))
    assert looking_away(vps(pitch=-15.0))  # the screen
    assert looking_away(vps(distracted=True, face=False))
    assert not looking_away(vps(yaw=40.0, face=False))
    assert not looking_away(vps(yaw=15.5))  # 19 Nov: a small glance at 15 deg while looking ahead
    assert not looking_away(vps(distracted=True, kind="eye"))  # a blink (eyes closed for 3 frames)
    assert looking_away(vps(distracted=True, kind="phone"))

  def test_a_short_radar_dropout_is_no_cut_in(self):
    cw = ClosingWarning()
    run(cw, 2.0, d=18.0, closing=0.0, distracted=True)
    run(cw, 0.4, present=False, distracted=True)
    assert run(cw, 0.05, d=18.0, closing=0.0, distracted=True) == []

  def test_radar_lead_items(self):
    item = lambda k, v, ok: SimpleNamespace(key=k, value=v, valid=ok)  # noqa: E731
    assert radar_lead([item("lead_distance", 40.0, True)]) is None  # the car sends no radar data: use the dashboard
    assert radar_lead([item("radar_distance", 40.25, True), item("radar_rel_speed", -3.5, True)]) == (40.25, -3.5)
    assert radar_lead([item("radar_distance", 0.0, False), item("radar_rel_speed", 0.0, False)]) == (None, None)  # no lead
    assert radar_lead([item("radar_distance", 40.0, True), item("radar_rel_speed", 0.0, False)]) == (40.0, None)

  def test_radar_rel_speed_is_used(self):
    # the distance stays at 40 m (no slope) but the radar says the gap closes at 15 m/s: ttc 2.7 s, distracted chime
    cw = ClosingWarning()
    out = []
    for _ in range(100):
      k = cw.update(V, 40.0, False, False, False, False, 0.0, True, DT, radar_v_rel=-15.0)
      if k:
        out.append(k)
    assert out == [DISTRACTED]
    cw = ClosingWarning()
    assert run(cw, 1.0, d=40.0, closing=0.0, distracted=True) == []  # without it: no closing seen

  def test_radar_distance_item(self):
    items = [SimpleNamespace(key="rpm", value=1.0, valid=True), SimpleNamespace(key="lead_distance", value=23.0, valid=True)]
    assert radar_distance(items) == 23.0
    items[1].valid = False
    assert radar_distance(items) is None
    assert radar_distance(items[:1]) is None
