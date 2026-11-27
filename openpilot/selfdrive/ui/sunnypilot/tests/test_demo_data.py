"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.selfdrive.ui.sunnypilot import demo_data as dd


class TestDemoData:
  def test_off_in_the_normal_build(self):
    assert dd.DEMO is False  # the demo branch flips it; main must never ship it on

  def test_every_situation_builds_its_messages(self):
    names = set()
    for i in range(5):
      t = dd.SITUATION_SECONDS * (i + 0.5)
      names.add(dd.demo_situation(t)[0])
      topics = {m.which() for m in dd.demo_messages(t)}
      assert {"deviceState", "pandaStates", "carState", "carStateSP", "modelV2", "radarState", "modelDataV2SP"} <= topics
    assert len(names) == 5

  def test_started_with_ignition(self):
    msgs = {m.which(): m for m in dd.demo_messages(3.0)}
    assert msgs["deviceState"].deviceState.started
    assert msgs["pandaStates"].pandaStates[0].ignitionLine

  def test_values_move_and_stay_plausible(self):
    def items(t):
      return {i[0]: i[2] for i in dd.demo_items(t)}
    a, b = items(10.0), items(40.0)
    assert a["diag_oil_temp"] != b["diag_oil_temp"]
    for t in range(0, 600, 7):
      v = items(float(t))
      assert 40 <= v["diag_oil_temp"] <= 110 and 11.0 <= v["diag_12v_v"] <= 15.5
      assert v["rpm"] >= 0
      assert 200 <= v["diag_tire_p_fl"] <= 300

  def test_closing_reaches_the_decimal_range(self):
    t = dd.SITUATION_SECONDS * 1.95  # end of the "closing in" situation
    name, scenario, _ = dd.demo_situation(t)
    assert name == "closing in" and scenario[10]["radar_distance"] < 10
