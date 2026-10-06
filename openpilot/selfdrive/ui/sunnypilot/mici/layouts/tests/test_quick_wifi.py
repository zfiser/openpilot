"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "quick_wifi.py"
spec = importlib.util.spec_from_file_location("quick_wifi_under_test", MODULE_PATH)
quick_wifi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quick_wifi)


def net(ssid: str, strength: int, tethering: bool = False):
  return SimpleNamespace(ssid=ssid, strength=strength, is_tethering=tethering)


class FakeManager:
  def __init__(self, networks=(), saved=(), connected=None, connecting=None):
    self.networks = list(networks)
    self.saved = set(saved)
    self.connected_ssid = connected
    self.connecting_to_ssid = connecting
    self.active_calls = []
    self.activated = []

  def set_active(self, active):
    self.active_calls.append(active)

  def is_connection_saved(self, ssid):
    return ssid in self.saved

  def activate_connection(self, ssid):
    self.activated.append(ssid)


class TestChooseKnownNetwork(unittest.TestCase):
  def test_strongest_saved(self):
    networks = [net("a", 40), net("b", 80), net("c", 95)]
    assert quick_wifi.choose_known_network(networks, lambda s: s in ("a", "b")) == "b"

  def test_none_saved(self):
    assert quick_wifi.choose_known_network([net("a", 40)], lambda s: False) is None

  def test_no_networks(self):
    assert quick_wifi.choose_known_network([], lambda s: True) is None

  def test_skips_own_hotspot(self):
    networks = [net("comma-hotspot", 100, tethering=True), net("home", 30)]
    assert quick_wifi.choose_known_network(networks, lambda s: True) == "home"


class TestQuickWifiConnect(unittest.TestCase):
  def make(self, manager, wifi_connected=None):
    state = {"wifi": False} if wifi_connected is None else wifi_connected
    q = quick_wifi.QuickWifiConnect(lambda: state["wifi"], manager_factory=lambda: manager)
    return q, state

  def test_tap_when_connected_does_nothing(self):
    manager = FakeManager()
    q, _ = self.make(manager, {"wifi": True})
    q.tap()
    assert not q.connecting and manager.active_calls == []

  def test_tap_starts_scan(self):
    manager = FakeManager()
    q, _ = self.make(manager)
    q.tap()
    assert q.connecting and manager.active_calls == [True]

  def test_connects_to_strongest_known_once(self):
    manager = FakeManager(networks=[net("a", 40), net("b", 80), net("open", 99)], saved=("a", "b"))
    q, _ = self.make(manager)
    q.tap()
    q.update()
    q.update()
    assert manager.activated == ["b"]

  def test_waits_for_scan_results(self):
    manager = FakeManager()
    q, _ = self.make(manager)
    q.tap()
    q.update()
    assert manager.activated == [] and q.connecting
    manager.networks = [net("a", 50)]
    manager.saved = {"a"}
    q.update()
    assert manager.activated == ["a"]

  def test_no_known_network_in_range_gives_up(self):
    manager = FakeManager(networks=[net("cafe", 70)], saved=("home",))
    q, _ = self.make(manager)
    q.tap()
    q.update()
    assert manager.activated == [] and not q.connecting and manager.active_calls == [True, False]

  def test_finishes_when_wifi_comes_up(self):
    manager = FakeManager(networks=[net("a", 50)], saved=("a",))
    q, state = self.make(manager)
    q.tap()
    q.update()
    state["wifi"] = True
    q.update()
    assert not q.connecting and manager.active_calls[-1] is False

  def test_already_on_a_network_does_nothing(self):
    manager = FakeManager(networks=[net("a", 50)], saved=("a",), connected="a")
    q, _ = self.make(manager)
    q.tap()
    q.update()
    assert manager.activated == [] and not q.connecting

  def test_gives_up_after_timeout(self):
    manager = FakeManager()
    q, _ = self.make(manager)
    with mock.patch.object(quick_wifi.time, "monotonic", return_value=1000.0):
      q.tap()
    with mock.patch.object(quick_wifi.time, "monotonic", return_value=1000.0 + quick_wifi.CONNECT_TIMEOUT + 1):
      q.update()
    assert not q.connecting and manager.active_calls == [True, False]

  def test_second_tap_while_connecting_is_ignored(self):
    manager = FakeManager()
    q, _ = self.make(manager)
    q.tap()
    q.tap()
    assert manager.active_calls == [True]


if __name__ == "__main__":
  unittest.main()
