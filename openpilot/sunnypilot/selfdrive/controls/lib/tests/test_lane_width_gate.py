"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from types import SimpleNamespace

from openpilot.cereal import log
from openpilot.common.test import OpenpilotTestCase
from openpilot.selfdrive.controls.lib.desire_helper import DesireHelper, LaneChangeState
from openpilot.sunnypilot.selfdrive.controls.lib.auto_lane_change import AutoLaneChangeMode

MIN_WIDTH = 2.8


def car(**kw):
  base = dict(vEgo=25.0, leftBlinker=True, rightBlinker=False, leftBlindspot=False, rightBlindspot=False, steeringPressed=False,
              steeringTorque=0.0, brakePressed=False)
  base.update(kw)
  return SimpleNamespace(**base)


def run(dh, carstate, seconds, width_left=3.6, width_right=3.6, min_width=MIN_WIDTH, edge_left=False, edge_right=False):
  for _ in range(round(seconds / 0.05)):
    dh.update(carstate, True, 1.0, edge_left, edge_right, width_left, width_right, min_width)


class TestLaneWidthGate(OpenpilotTestCase):
  def setup_method(self):
    self.dh = DesireHelper()
    self.dh.alc.lane_change_set_timer = AutoLaneChangeMode.NUDGELESS
    self.dh.alc.lane_change_bsm_delay = False
    self.dh.alc.read_params = lambda: None  # keep the values set here, no reading of the settings

  def test_a_wide_lane_starts_at_once(self):
    run(self.dh, car(), 1.0)
    assert self.dh.lane_change_state == LaneChangeState.laneChangeStarting
    assert not self.dh.waiting_for_lane

  def test_a_narrow_lane_waits_without_cancelling(self):
    run(self.dh, car(), 5.0, width_left=1.9)
    assert self.dh.lane_change_state == LaneChangeState.preLaneChange
    assert self.dh.waiting_for_lane

  def test_it_starts_by_itself_when_the_lane_opens_up(self):
    run(self.dh, car(), 3.0, width_left=1.9)
    assert self.dh.lane_change_state == LaneChangeState.preLaneChange
    run(self.dh, car(), 0.5, width_left=3.4)  # the split: the new lane is there
    assert self.dh.lane_change_state == LaneChangeState.laneChangeStarting
    assert not self.dh.waiting_for_lane

  def test_a_nudge_is_not_held_back(self):
    run(self.dh, car(steeringPressed=True, steeringTorque=1.0), 0.5, width_left=1.9)
    assert self.dh.lane_change_state == LaneChangeState.laneChangeStarting

  def test_the_radar_blind_spot_blocks_hard(self):
    run(self.dh, car(leftBlindspot=True), 3.0)
    assert self.dh.lane_change_state == LaneChangeState.preLaneChange

  def test_the_old_edge_flag_is_ignored_when_the_width_is_used(self):
    run(self.dh, car(), 1.0, edge_left=True)  # the flag, but the lane next to the car is wide
    assert self.dh.lane_change_state == LaneChangeState.laneChangeStarting

  def test_the_other_side_does_not_matter(self):
    run(self.dh, car(), 1.0, width_left=3.6, width_right=0.0)
    assert self.dh.lane_change_state == LaneChangeState.laneChangeStarting

  def test_right_blinker_uses_the_right_width(self):
    run(self.dh, car(leftBlinker=False, rightBlinker=True), 3.0, width_left=3.6, width_right=1.9)
    assert self.dh.lane_change_state == LaneChangeState.preLaneChange and self.dh.waiting_for_lane

  def test_setting_off_or_no_width_keeps_the_old_edge_block(self):
    run(self.dh, car(), 3.0, min_width=0.0, edge_left=True)
    assert self.dh.lane_change_state == LaneChangeState.preLaneChange and not self.dh.waiting_for_lane
    dh2 = DesireHelper()
    dh2.alc.lane_change_set_timer = AutoLaneChangeMode.NUDGELESS
    dh2.alc.read_params = lambda: None
    for _ in range(60):
      dh2.update(car(), True, 1.0, True, False)  # old call without widths
    assert dh2.lane_change_state == LaneChangeState.preLaneChange

  def test_the_notice_flag_is_only_for_the_waiting_state(self):
    run(self.dh, car(), 2.0, width_left=1.9)
    assert self.dh.waiting_for_lane
    run(self.dh, car(leftBlinker=False), 0.5, width_left=1.9)  # blinker off: nothing is waiting
    assert not self.dh.waiting_for_lane
    assert self.dh.lane_change_state == LaneChangeState.off
    assert log.LaneChangeDirection.left != log.LaneChangeDirection.right
