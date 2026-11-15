"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.sunnypilot.selfdrive.selfdrived.closing_warning import COLLISION, COOLDOWN, DISTRACTED, ClosingWarning

DT = 0.01
V = 25.0  # m/s, 90 km/h


def run(cw, seconds, d=20.0, v_rel=-12.0, v=V, acc=False, gas=False, brake=False, blinker=False, wheel=0.0, distracted=False,
        present=True):
  """Closing at -v_rel m/s from d metres; the gap shrinks as it would. Returns the chimes."""
  out = []
  for _ in range(round(seconds / DT)):
    kind = cw.update(v, present, d, v_rel, acc, gas, brake, blinker, wheel, distracted, DT)
    if kind:
      out.append(kind)
    d = max(d + v_rel * DT, 1.0)
  return out


class TestClosingWarning:
  def test_collision_chimes_whatever_the_camera_says(self):
    assert run(ClosingWarning(), 1.0) == [COLLISION]  # 20 m at 12 m/s: 1.7 s
    assert run(ClosingWarning(), 1.0, distracted=True) == [COLLISION]  # the stronger one only

  def test_distracted_only_when_not_looking(self):
    # 30 m at 12 m/s: 2.5 s, between the two limits
    assert run(ClosingWarning(), 0.2, d=30.0) == []
    assert run(ClosingWarning(), 0.4, d=30.0, distracted=True) == [DISTRACTED]

  def test_acc_on_without_gas_is_left_to_the_car(self):
    assert run(ClosingWarning(), 1.0, acc=True) == []
    assert run(ClosingWarning(), 1.0, acc=True, gas=True) == [COLLISION]

  def test_exceptions(self):
    assert run(ClosingWarning(), 1.0, brake=True) == []
    assert run(ClosingWarning(), 1.0, blinker=True) == []  # overtaking
    assert run(ClosingWarning(), 1.0, wheel=45.0) == []  # a turn
    assert run(ClosingWarning(), 1.0, v=6.0) == []  # 22 km/h
    assert run(ClosingWarning(), 1.0, v_rel=-0.5, d=0.8) == []  # hardly closing

  def test_a_glitch_does_not_chime(self):
    cw = ClosingWarning()
    assert run(cw, 0.2) == []  # shorter than PERSIST
    assert run(cw, 0.5, v_rel=2.0) == []  # opening again

  def test_cooldown(self):
    cw = ClosingWarning()
    assert run(cw, 1.0) == [COLLISION]
    assert run(cw, 1.0, d=20.0) == []
    run(cw, COOLDOWN, present=False)
    assert run(cw, 1.0, d=20.0) == [COLLISION]

  def test_cut_in(self):
    cw = ClosingWarning()
    run(cw, 1.0, present=False, distracted=True)
    assert run(cw, 0.05, d=18.0, v_rel=0.0, distracted=True) == [DISTRACTED]  # 0.7 s gap, the car just appeared
    cw = ClosingWarning()
    run(cw, 1.0, present=False)
    assert run(cw, 0.05, d=18.0, v_rel=0.0) == []  # looking: no chime
    cw = ClosingWarning()
    run(cw, 1.0, present=False, distracted=True)
    assert run(cw, 0.05, d=40.0, v_rel=0.0, distracted=True) == []  # far enough
