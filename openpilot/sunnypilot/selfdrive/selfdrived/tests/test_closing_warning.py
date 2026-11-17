"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import math
from types import SimpleNamespace

from openpilot.sunnypilot.selfdrive.selfdrived.closing_warning import (COLLISION, COOLDOWN, DISTRACTED, ClosingWarning, LeadRate,
                                                                       looking_away, radar_distance)

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
    assert run(cw, 0.05, d=18.0, closing=0.0, distracted=True) == [DISTRACTED]  # 0.7 s gap, the car just appeared
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    assert run(cw, 0.05, d=18.0, closing=0.0) == []  # looking: no chime
    cw = ClosingWarning()
    run(cw, 1.5, present=False, distracted=True)
    assert run(cw, 0.05, d=120.0, closing=0.0, distracted=True) == [DISTRACTED]  # any distance: the road is no longer clear
    cw = ClosingWarning()
    run(cw, 1.5, present=False, acc=True, distracted=True)
    assert run(cw, 0.5, d=40.0, closing=0.0, acc=True, distracted=True) == []  # ACC holds the speed: no chime

  def test_cut_in_glance_just_before_or_after(self):
    # 16 Nov: looked away 0.4 s before the radar found the car, and in another case looked back one frame before it
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    run(cw, 0.2, present=False, distracted=True)
    run(cw, 0.4, present=False)
    assert run(cw, 0.05, d=18.0, closing=0.0) == [DISTRACTED]
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    run(cw, 0.5, d=18.0, closing=0.0)
    assert run(cw, 0.2, d=18.0, closing=0.0, distracted=True) == [DISTRACTED]  # glanced away right after it appeared
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
    assert run(cw, 0.5, d=125.0, closing=8.0) == [DISTRACTED]
    # but not for the closing rules: following closely while closing and only glancing does not chime
    cw = ClosingWarning()
    assert run(cw, 3.0, d=15.0, closing=2.0, look=True) == []

  def test_one_chime_per_appearance(self):
    cw = ClosingWarning()
    run(cw, 1.5, present=False)
    assert run(cw, 0.8, d=60.0, closing=0.0, look=True) == [DISTRACTED]
    run(cw, 20.0, d=60.0, closing=0.0, look=True)  # still the same car after the cooldown: nothing new
    assert run(cw, 1.0, d=60.0, closing=0.0, look=True) == []

  def test_same_car_after_a_dropout_at_long_range(self):
    cw = ClosingWarning()
    run(cw, 2.0, d=118.0, closing=0.0)
    run(cw, 3.0, present=False)  # lost at 118 m
    assert run(cw, 0.5, d=112.0, closing=0.0, look=True) == []  # back at about the same distance
    cw = ClosingWarning()
    run(cw, 2.0, d=118.0, closing=0.0)
    run(cw, 3.0, present=False)
    assert run(cw, 0.5, d=40.0, closing=0.0, look=True) == [DISTRACTED]  # another car
    cw = ClosingWarning()
    run(cw, 2.0, d=118.0, closing=0.0)
    run(cw, 12.0, present=False)  # long gone: a car at that distance is new
    assert run(cw, 0.5, d=115.0, closing=0.0, look=True) == [DISTRACTED]

  def test_radar_switches_to_a_nearer_car(self):
    cw = ClosingWarning()
    run(cw, 2.0, d=90.0, closing=0.0)
    assert run(cw, 0.3, d=35.0, closing=0.0, look=True) == [DISTRACTED]
    cw = ClosingWarning()
    run(cw, 2.0, d=35.0, closing=0.0)
    assert run(cw, 0.3, d=90.0, closing=0.0, look=True) == []  # to a farther car: the road ahead got clearer

  def test_looking_away(self):
    def vps(yaw=0.0, pitch=0.0, distracted=False, face=True):
      calib = SimpleNamespace(offset=math.radians(3.0))
      pose = SimpleNamespace(yaw=math.radians(yaw + 3.0), pitch=math.radians(pitch + 3.0), yawCalib=calib, pitchCalib=calib)
      return SimpleNamespace(isDistracted=distracted, faceDetected=face, pose=pose)
    assert not looking_away(vps())
    assert not looking_away(vps(yaw=10.0, pitch=8.0))  # looking up (the rear-view mirror tilt) or a little aside
    assert looking_away(vps(yaw=-18.0))  # the left mirror
    assert looking_away(vps(yaw=20.0))
    assert looking_away(vps(pitch=-15.0))  # the screen
    assert looking_away(vps(distracted=True, face=False))
    assert not looking_away(vps(yaw=40.0, face=False))

  def test_a_short_radar_dropout_is_no_cut_in(self):
    cw = ClosingWarning()
    run(cw, 2.0, d=18.0, closing=0.0, distracted=True)
    run(cw, 0.4, present=False, distracted=True)
    assert run(cw, 0.05, d=18.0, closing=0.0, distracted=True) == []

  def test_radar_distance_item(self):
    items = [SimpleNamespace(key="rpm", value=1.0, valid=True), SimpleNamespace(key="lead_distance", value=23.0, valid=True)]
    assert radar_distance(items) == 23.0
    items[1].valid = False
    assert radar_distance(items) is None
    assert radar_distance(items[:1]) is None
