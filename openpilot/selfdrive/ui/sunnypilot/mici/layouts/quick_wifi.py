"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import time
from collections.abc import Callable

CONNECT_TIMEOUT = 15.0  # seconds to wait for a scan and the connection before giving up


def choose_known_network(networks, is_saved: Callable[[str], bool]) -> str | None:
  """Strongest saved network that is currently in range, tethering hotspots of the device itself are skipped."""
  candidates = [n for n in networks if is_saved(n.ssid) and not n.is_tethering]
  if not candidates:
    return None
  return max(candidates, key=lambda n: n.strength).ssid


class QuickWifiConnect:
  """Tap to connect to a saved network without opening the network menu."""

  def __init__(self, is_wifi_connected: Callable[[], bool], manager_factory: Callable | None = None):
    self._is_wifi_connected = is_wifi_connected
    self._manager_factory = manager_factory or self._default_factory
    self._manager = None
    self._deadline: float | None = None
    self._activated = False

  @staticmethod
  def _default_factory():
    from openpilot.system.ui.lib.wifi_manager import WifiManager  # only needed (and importable) once the user taps
    return WifiManager()

  @property
  def connecting(self) -> bool:
    return self._deadline is not None

  def tap(self) -> None:
    if self.connecting or self._is_wifi_connected():
      return
    if self._manager is None:
      self._manager = self._manager_factory()
    self._manager.set_active(True)  # refreshes the scan results and the connection state
    self._deadline = time.monotonic() + CONNECT_TIMEOUT
    self._activated = False

  def _finish(self) -> None:
    self._deadline = None
    self._activated = False
    if self._manager is not None:
      self._manager.set_active(False)

  def update(self) -> None:
    if self._deadline is None:
      return

    if time.monotonic() > self._deadline or self._is_wifi_connected():
      self._finish()
      return

    manager = self._manager
    if self._activated or manager.connecting_to_ssid is not None:
      return  # waiting for the connection to come up

    networks = manager.networks
    if not networks:
      return  # scan results not in yet

    if manager.connected_ssid is not None:
      self._finish()  # already on a network, nothing to do
      return

    target = choose_known_network(networks, manager.is_connection_saved)
    if target is None:
      self._finish()  # no saved network in range
      return

    manager.activate_connection(target)
    self._activated = True
